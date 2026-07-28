from __future__ import annotations

import pytest
from types import SimpleNamespace

from app.models.ai_index_jobs import AIJobStatus
from app.models.ai_knowledge_sources import AIPublishStatus
from app.tasks.material_index import (
    _acquire_material_write_fence,
    _can_reuse_canonical_chunks,
    _compute_retry_delay_seconds,
    _get_material_job_metadata,
    _get_prompt_log_user_id,
    _optional_str,
    _should_auto_retry,
    _supersede_if_newer_material_job,
    _to_markdown_content,
    _to_publish_status,
    _truncate_text,
)


def test_material_metadata_validation_requires_dict_and_required_fields() -> None:
    # Tests material job metadata validation rejects missing required data.
    with pytest.raises(Exception) as missing_metadata:
        _get_material_job_metadata(None)

    with pytest.raises(Exception) as missing_title:
        _get_material_job_metadata({"title": " "})

    assert "metadata is missing" in str(missing_metadata.value)
    assert "field 'title' is required" in str(missing_title.value)


def test_material_metadata_validation_returns_valid_metadata() -> None:
    # Tests valid material job metadata is returned unchanged.
    metadata = {
        "title": "Lesson",
        "resourceUrl": "/materials/1",
        "storagePath": "local://lesson.txt",
        "sizeBytes": 10,
        "moduleStatus": "published",
        "storageProvider": "local",
        "objectKey": "lesson.txt",
    }

    assert _get_material_job_metadata(metadata) is metadata


def test_material_index_small_helpers(monkeypatch) -> None:
    # Tests small material index helper conversions and retry delay calculation.
    monkeypatch.setattr(
        "app.tasks.material_index.settings",
        SimpleNamespace(ai_index_job_retry_base_seconds=10, ai_index_job_retry_max_seconds=25),
    )

    assert _optional_str(None) is None
    assert _optional_str("  value ") == "value"
    assert _get_prompt_log_user_id({"educatorId": 9}) == 9
    assert _get_prompt_log_user_id({"educatorId": 0}) == 0
    assert _truncate_text("  abc  ", limit=2) == "ab"
    assert _to_publish_status("published") == AIPublishStatus.PUBLISHED
    assert _to_publish_status("archived") == AIPublishStatus.ARCHIVED
    assert _to_publish_status("draft") == AIPublishStatus.DRAFT
    assert _to_markdown_content(content_text="# Title", content_type=None, object_key="lesson.md") == "# Title"
    assert _to_markdown_content(content_text="plain", content_type="text/plain", object_key="lesson.txt") is None
    assert _compute_retry_delay_seconds(1) == 10
    assert _compute_retry_delay_seconds(3) == 25


@pytest.mark.parametrize(
    ("exc", "stage", "expected"),
    [
        (RuntimeError("timeout from provider"), "embedding_chunk_0", True),
        (RuntimeError("metadata field title is required"), "content_extraction", False),
        (RuntimeError("anything"), "metadata_validation", False),
        (RuntimeError("anything"), "embedding_chunk_1", True),
        (RuntimeError("anything"), "embedding_model_configuration", True),
        (RuntimeError("anything"), "index_write", True),
        (RuntimeError("anything"), "multi_vector_index_write", True),
        (RuntimeError("anything"), "other", False),
    ],
)
def test_should_auto_retry_classifies_failures(exc, stage, expected) -> None:
    # Tests material index auto-retry decisions for failure stages and messages.
    assert _should_auto_retry(exc=exc, stage=stage) is expected


def test_supersede_helper_rolls_back_pending_writes_before_terminal_update(
    monkeypatch,
) -> None:
    calls = []
    job = SimpleNamespace(
        job_id=8,
        material_id=9,
        started_at="started",
    )
    session = SimpleNamespace(
        rollback=lambda: calls.append("rollback"),
        commit=lambda: calls.append("commit"),
    )
    jobs = SimpleNamespace(
        has_newer_material_job=lambda **_: True,
        get_by_id=lambda _job_id: job,
        update_status=lambda current_job, **kwargs: (
            calls.append(("status", kwargs["status"]))
            or setattr(current_job, "status", kwargs["status"])
        ),
    )
    monkeypatch.setattr(
        "app.tasks.material_index.now_local",
        lambda: SimpleNamespace(isoformat=lambda **_: "2026-07-28T12:00:00"),
    )

    response = _supersede_if_newer_material_job(
        session=session,
        jobs=jobs,
        job=job,
    )

    assert calls == [
        "rollback",
        ("status", AIJobStatus.SUPERSEDED),
        "commit",
    ]
    assert response["status"] == "superseded"


@pytest.mark.parametrize(
    "newer_status",
    [AIJobStatus.QUEUED, AIJobStatus.BLOCKED],
)
def test_material_write_fence_locks_before_observing_competing_newer_job(
    monkeypatch,
    newer_status,
) -> None:
    events = []
    job = SimpleNamespace(
        job_id=8,
        material_id=9,
        started_at="started",
    )
    competing_job = SimpleNamespace(job_id=10, status=newer_status)
    state = {"competing_committed": False}

    def lock_material_job_scope(**_):
        events.append("lock")
        # Simulate another transaction committing while this transaction waits
        # for the same advisory lock.
        state["competing_committed"] = True

    def has_newer_material_job(**_):
        events.append(("newer", competing_job.status))
        return state["competing_committed"]

    session = SimpleNamespace(
        rollback=lambda: events.append("rollback"),
        commit=lambda: events.append("commit"),
    )
    jobs = SimpleNamespace(
        lock_material_job_scope=lock_material_job_scope,
        is_running_material_job=lambda **_: (
            events.append("current") or True
        ),
        has_newer_material_job=has_newer_material_job,
        get_by_id=lambda _job_id: job,
        update_status=lambda current_job, **kwargs: (
            events.append(("status", kwargs["status"]))
            or setattr(current_job, "status", kwargs["status"])
        ),
    )
    monkeypatch.setattr(
        "app.tasks.material_index.now_local",
        lambda: SimpleNamespace(
            isoformat=lambda **_: "2026-07-28T12:00:00"
        ),
    )

    response = _acquire_material_write_fence(
        session=session,
        jobs=jobs,
        job=job,
    )

    assert events == [
        "lock",
        "current",
        ("newer", newer_status),
        "rollback",
        ("status", AIJobStatus.SUPERSEDED),
        "commit",
    ]
    assert response["status"] == "superseded"


def test_material_write_fence_aborts_when_delete_removed_current_job() -> None:
    events = []
    stale_job = SimpleNamespace(job_id=8, material_id=9)
    session = SimpleNamespace(
        rollback=lambda: events.append("rollback"),
    )
    jobs = SimpleNamespace(
        lock_material_job_scope=lambda **_: events.append("lock"),
        is_running_material_job=lambda **_: (
            events.append("current_missing") or False
        ),
        has_newer_material_job=lambda **_: pytest.fail(
            "a missing current job must abort before the newer-job check"
        ),
    )

    response = _acquire_material_write_fence(
        session=session,
        jobs=jobs,
        job=stale_job,
    )

    assert events == ["lock", "current_missing", "rollback"]
    assert response == {
        "status": "skipped",
        "jobId": 8,
        "materialId": 9,
        "jobStatus": "missing_or_not_running",
    }


def test_canonical_chunk_reuse_rejects_stale_or_inactive_rows() -> None:
    source = SimpleNamespace(
        content_hash="hash",
        source_version="lesson.pdf",
        publish_status=AIPublishStatus.PUBLISHED,
        metadata_json={},
    )
    chunks = [SimpleNamespace(is_active=True)]
    common = {
        "source": source,
        "chunks": chunks,
        "content_hash": "hash",
        "source_version": "lesson.pdf",
        "publish_status": AIPublishStatus.PUBLISHED,
        "existing_chunk_fingerprint": [(0, "chunk")],
        "expected_chunk_fingerprint": [(0, "chunk")],
    }

    assert _can_reuse_canonical_chunks(**common) is True

    source.metadata_json = {"indexStale": True}
    assert _can_reuse_canonical_chunks(**common) is False

    source.metadata_json = {}
    chunks[0].is_active = False
    assert _can_reuse_canonical_chunks(**common) is False

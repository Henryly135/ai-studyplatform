from __future__ import annotations

import pytest
from types import SimpleNamespace

from app.models.ai_knowledge_sources import AIPublishStatus
from app.tasks.material_index import (
    _compute_retry_delay_seconds,
    _get_material_job_metadata,
    _get_prompt_log_user_id,
    _optional_str,
    _should_auto_retry,
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
        (RuntimeError("anything"), "index_write", True),
        (RuntimeError("anything"), "other", False),
    ],
)
def test_should_auto_retry_classifies_failures(exc, stage, expected) -> None:
    # Tests material index auto-retry decisions for failure stages and messages.
    assert _should_auto_retry(exc=exc, stage=stage) is expected

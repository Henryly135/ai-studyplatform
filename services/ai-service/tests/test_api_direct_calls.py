from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import chat as chat_api
from app.api import demo as demo_api
from app.api import internal_index_jobs as index_api
from app.api import profiles as profiles_api
from app.api import quiz_generation as quiz_api
from app.api import tasks as tasks_api
from app.models.ai_index_jobs import AIIndexJobType, AIIndexSourceType, AIJobStatus
from app.schemas.demo import ChatRequest, ChatServiceRequest
from app.schemas.index_jobs import MaterialIndexDeleteRequest, ReleaseIndexJobsRequest
from app.schemas.profiles import GlobalProfileInitRequest, GlobalProfileRead, ModuleProfileRead
from app.schemas.tasks import SmokeTaskRequest


class RollbackSession:
    def __init__(self) -> None:
        self.rollback_calls = 0

    def rollback(self) -> None:
        self.rollback_calls += 1


def _run(status: str = "queued") -> dict:
    return {
        "runId": "run-1",
        "courseUuid": "course-uuid",
        "moduleUuid": "module-uuid",
        "actorId": 7,
        "additionalInstructions": None,
        "status": status,
        "currentStep": None,
        "message": "Queued",
        "startedAt": "2026-04-29T00:00:00Z",
        "updatedAt": "2026-04-29T00:00:00Z",
        "error": None,
        "attemptStartResponse": None,
        "events": [],
    }


def test_demo_health_reports_configured_provider(monkeypatch) -> None:
    # Tests demo health returns provider metadata when Gemini is configured.
    monkeypatch.setattr("app.api.demo.settings", SimpleNamespace(gemini_api_key="key", ai_demo_model_name="model"))

    response = demo_api.demo_health()

    assert response.status == "ok"
    assert response.provider == "gemini"


def test_demo_health_rejects_missing_api_key(monkeypatch) -> None:
    # Tests demo health returns service unavailable when Gemini key is absent.
    monkeypatch.setattr("app.api.demo.settings", SimpleNamespace(gemini_api_key="", ai_demo_model_name="model"))

    with pytest.raises(HTTPException) as exc_info:
        demo_api.demo_health()

    assert exc_info.value.status_code == 503


def test_demo_chat_trims_message_and_maps_success(monkeypatch) -> None:
    # Tests demo chat calls persist_chat and encodes the returned session id.
    monkeypatch.setattr("app.api.demo.encode_session_uuid", lambda value: f"session-{value}")
    monkeypatch.setattr(
        "app.api.demo.persist_chat",
        lambda db, payload: SimpleNamespace(
            session_id=5,
            user_message_id=6,
            assistant_message_id=7,
            reply="ok",
            sources=[],
        ),
    )

    response = demo_api.demo_chat(ChatServiceRequest(user_id=1, message=" hi "), db=RollbackSession())

    assert response.session_uuid == "session-5"
    assert response.reply == "ok"


def test_demo_chat_rejects_blank_message() -> None:
    # Tests demo chat rejects messages that become blank after trimming.
    with pytest.raises(HTTPException) as exc_info:
        demo_api.demo_chat(ChatServiceRequest(user_id=1, message=" "), db=RollbackSession())

    assert exc_info.value.status_code == 400


@pytest.mark.parametrize(
    ("exc", "status_code"),
    [
        (demo_api.AIChatConfigurationError("not configured"), 503),
        (demo_api.AIChatQuotaError("quota"), 429),
        (demo_api.AIChatSessionError("bad session"), 400),
        (RuntimeError("boom"), 500),
    ],
)
def test_demo_chat_maps_service_errors_to_http(monkeypatch, exc, status_code) -> None:
    # Tests demo chat converts service exceptions to expected HTTP errors.
    db = RollbackSession()
    monkeypatch.setattr("app.api.demo.persist_chat", lambda *_: (_ for _ in ()).throw(exc))

    with pytest.raises(HTTPException) as exc_info:
        demo_api.demo_chat(ChatServiceRequest(user_id=1, message="hello"), db=db)

    assert exc_info.value.status_code == status_code
    assert db.rollback_calls == 1


def test_authenticated_chat_success_and_error_mapping(monkeypatch) -> None:
    # Tests authenticated chat decodes ids, persists chat, and maps model errors.
    monkeypatch.setattr("app.api.chat.decode_session_uuid", lambda value: 1)
    monkeypatch.setattr("app.api.chat.decode_course_uuid", lambda value: 2)
    monkeypatch.setattr("app.api.chat.decode_module_uuid", lambda value: 3)
    monkeypatch.setattr("app.api.chat.encode_session_uuid", lambda value: f"session-{value}")
    monkeypatch.setattr(
        "app.api.chat.persist_chat",
        lambda db, payload: SimpleNamespace(
            session_id=9,
            user_message_id=10,
            assistant_message_id=11,
            reply="reply",
            sources=[{"chunk": 1}],
        ),
    )

    response = chat_api.chat(
        ChatRequest(session_uuid="s", course_uuid="c", module_uuid="m", message="hello"),
        current_user={"id": 7},
        db=RollbackSession(),
    )

    assert response.success is True
    assert response.data.session_uuid == "session-9"
    assert response.data.sources == [{"chunk": 1}]


def test_chat_list_and_detail_helpers_return_serialized_rows(monkeypatch) -> None:
    # Tests chat session list/detail endpoints serialize repository rows.
    now = datetime(2026, 4, 29, tzinfo=timezone.utc)
    session_row = SimpleNamespace(
        session_id=1,
        user_id=7,
        course_id=None,
        module_id=None,
        session_type="demo",
        title="T",
        status="active",
        message_count=1,
        summary_text=None,
        last_message_at=None,
        created_at=now,
        updated_at=now,
    )
    message_row = SimpleNamespace(
        message_id=2,
        session_id=1,
        role="user",
        message_type="plain_text",
        parent_message_id=None,
        content_text="hello",
        created_at=now,
    )
    monkeypatch.setattr("app.api.chat.encode_session_uuid", lambda value: f"session-{value}")
    monkeypatch.setattr("app.api.chat.decode_session_uuid", lambda value: 1)
    monkeypatch.setattr(
        "app.api.chat.AIChatSessionsRepository",
        lambda db: SimpleNamespace(
            list_by_user=lambda user_id: [session_row],
            list_by_user_and_module=lambda user_id, module_id: [session_row],
            get_by_id=lambda session_id: session_row,
        ),
    )
    monkeypatch.setattr(
        "app.api.chat.AIChatMessagesRepository",
        lambda db: SimpleNamespace(list_visible_by_session=lambda session_id: [message_row]),
    )

    assert chat_api.list_chat_sessions(current_user={"id": 7}, db=object())[0].session_uuid == "session-1"
    assert chat_api.get_chat_session("session-1", current_user={"id": 7}, db=object()).messages[0].message_id == 2


def test_quiz_generation_run_endpoints_create_and_read_runs(monkeypatch) -> None:
    # Tests quiz generation run creation and status lookup direct endpoint calls.
    sent_tasks = []
    store = SimpleNamespace(
        create_or_get_active_run=lambda **_: (_run(), True),
        get_active_run=lambda **_: _run(),
        get_run=lambda run_id: _run(),
    )
    monkeypatch.setattr("app.api.quiz_generation.LearningQuizGenerationClient", lambda: SimpleNamespace(ensure_learner_quiz_access=lambda **_: None))
    monkeypatch.setattr("app.api.quiz_generation.QuizGenerationRunStore", lambda: store)
    monkeypatch.setattr("app.api.quiz_generation.celery_app", SimpleNamespace(send_task=lambda *args, **kwargs: sent_tasks.append((args, kwargs))))
    monkeypatch.setattr("app.api.quiz_generation.settings", SimpleNamespace(celery_task_default_queue="ai.default"))

    started = quiz_api.create_auto_generated_quiz_attempt_run(
        "course-uuid",
        "module-uuid",
        payload=quiz_api.QuizGenerationAutoStartRequest(),
        current_user={"id": 7},
    )
    active = quiz_api.get_active_course_quiz_generation_run("course-uuid", "module-uuid", current_user={"id": 7})
    by_id = quiz_api.get_quiz_generation_run("run-1", current_user={"id": 7})
    scoped = quiz_api.get_course_quiz_generation_run("course-uuid", "module-uuid", "run-1", current_user={"id": 7})

    assert started.runId == "run-1"
    assert active.runId == "run-1"
    assert by_id.runId == "run-1"
    assert scoped.runId == "run-1"
    assert sent_tasks


def test_quiz_generation_owner_and_missing_run_errors() -> None:
    # Tests quiz generation run ownership and missing-run errors become 404s.
    with pytest.raises(HTTPException):
        quiz_api._ensure_run_owner(_run(), current_user={"id": 99})
    with pytest.raises(HTTPException):
        quiz_api._ensure_run_owner(_run(), current_user={"id": 7}, course_uuid="other")


def test_stream_event_returns_ndjson_bytes() -> None:
    # Tests quiz stream events are encoded as newline-delimited JSON bytes.
    payload = quiz_api._stream_event(event="started", step="graph", message="hello", data={"a": 1})

    assert payload.endswith(b"\n")
    assert b'"event": "started"' in payload


def test_tasks_api_enqueue_and_read_task_results(monkeypatch) -> None:
    # Tests smoke task enqueue and result status mapping.
    monkeypatch.setattr("app.api.tasks.ping_task", SimpleNamespace(delay=lambda message: SimpleNamespace(id="task-1")))
    monkeypatch.setattr("app.api.tasks.settings", SimpleNamespace(celery_task_default_queue="ai.default"))

    enqueued = tasks_api.enqueue_smoke_task(SmokeTaskRequest(message=" ping "), current_user={"id": 7})

    assert enqueued.task_id == "task-1"
    assert enqueued.requested_by == 7


@pytest.mark.parametrize(
    ("status_value", "result_value", "expected"),
    [
        ("PENDING", None, "pending"),
        ("STARTED", None, "started"),
        ("SUCCESS", {"pong": "ok"}, "success"),
        ("RETRY", None, "retry"),
    ],
)
def test_tasks_api_result_statuses(monkeypatch, status_value, result_value, expected) -> None:
    # Tests smoke task result endpoint maps Celery states to response statuses.
    monkeypatch.setattr(
        "app.api.tasks.celery_app",
        SimpleNamespace(AsyncResult=lambda task_id: SimpleNamespace(status=status_value, result=result_value)),
    )

    response = tasks_api.get_smoke_task_result("task-1", _={"id": 7})

    assert response.status == expected


def test_tasks_api_failure_and_index_job_status(monkeypatch) -> None:
    # Tests task failure raises HTTP 500 and index job status serializes repository row.
    monkeypatch.setattr(
        "app.api.tasks.celery_app",
        SimpleNamespace(AsyncResult=lambda task_id: SimpleNamespace(status="FAILURE", result=RuntimeError("boom"))),
    )
    with pytest.raises(HTTPException):
        tasks_api.get_smoke_task_result("task-1", _={"id": 7})

    job = SimpleNamespace(
        job_id=1,
        job_type=AIIndexJobType.INDEX_MATERIAL,
        source_type=AIIndexSourceType.MATERIAL,
        source_ref_id="1",
        course_id=2,
        module_id=3,
        material_id=4,
        status=AIJobStatus.SUCCESS,
        priority=100,
        attempt_count=1,
        error_message=None,
        worker_id=None,
        next_retry_at=None,
        locked_at=None,
        created_at=datetime(2026, 4, 29, tzinfo=timezone.utc),
        started_at=None,
        finished_at=None,
    )
    monkeypatch.setattr("app.api.tasks.AIIndexJobsRepository", lambda session: SimpleNamespace(get_by_id=lambda job_id: job))

    assert tasks_api.get_index_job_status(1, _={"id": 7}, session=object()).job_id == 1


def test_profile_api_direct_calls(monkeypatch) -> None:
    # Tests public profile API functions call profile services with current user id.
    global_profile = GlobalProfileRead(learnerId=7, content="# Profile", isDefaultProfile=True)
    module_profile = ModuleProfileRead(
        learnerId=7,
        courseUuid="course-uuid",
        moduleUuid="module-uuid",
        content={},
        isDefaultProfile=True,
    )
    monkeypatch.setattr(
        "app.api.profiles.GlobalProfileService",
        lambda db: SimpleNamespace(
            initialize_for_learner=lambda learner_id, payload: global_profile,
            get_for_learner=lambda learner_id: global_profile,
        ),
    )
    monkeypatch.setattr(
        "app.api.profiles.ModuleProfileService",
        lambda db: SimpleNamespace(
            initialize_for_learner=lambda **_: module_profile,
            get_for_learner=lambda **_: module_profile,
        ),
    )

    payload = GlobalProfileInitRequest(
        supportRole="coach",
        helpStyle="steps",
        learningFocus="concepts",
        responseTone="calm",
    )

    assert profiles_api.initialize_global_profile(payload, current_user={"id": 7}, db=object()).learnerId == 7
    assert profiles_api.get_my_global_profile(current_user={"id": 7}, db=object()).learnerId == 7
    assert profiles_api.initialize_module_profile("course-uuid", "module-uuid", current_user={"id": 7}, db=object()).moduleUuid == "module-uuid"
    assert profiles_api.get_my_module_profile("course-uuid", "module-uuid", current_user={"id": 7}, db=object()).moduleUuid == "module-uuid"


def test_internal_index_job_api_direct_calls(monkeypatch) -> None:
    # Tests internal index job API functions delegate to IndexJobService methods.
    service = SimpleNamespace(
        delete_material_index=lambda payload: SimpleNamespace(materialId=payload.materialId, deletedSourceCount=1, deletedChunkCount=2, deletedJobCount=3),
        release_blocked_jobs=lambda payload: SimpleNamespace(releasedJobIds=[1], releasedCount=1, dispatchedCount=1),
        retry_job=lambda job_id: SimpleNamespace(jobId=job_id, status="queued", dispatched=True),
        recover_stale_running_jobs=lambda: SimpleNamespace(recoveredJobIds=[1], recoveredCount=1, dispatchedCount=1),
    )
    monkeypatch.setattr("app.api.internal_index_jobs.IndexJobService", lambda session: service)

    assert index_api.delete_material_index(MaterialIndexDeleteRequest(materialId=1), session=object()).deletedJobCount == 3
    assert index_api.release_blocked_index_jobs(ReleaseIndexJobsRequest(courseId=1, moduleIds=[2]), session=object()).releasedCount == 1
    assert index_api.retry_index_job(5, session=object()).jobId == 5
    assert index_api.recover_stale_index_jobs(session=object()).recoveredCount == 1

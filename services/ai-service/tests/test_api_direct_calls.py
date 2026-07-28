from __future__ import annotations

import inspect
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import admin_telemetry as admin_telemetry_api
from app.api import ai_models as ai_models_api
from app.api import chat as chat_api
from app.api import demo as demo_api
from app.api import internal_index_jobs as index_api
from app.api import profiles as profiles_api
from app.api import quiz_generation as quiz_api
from app.api import tasks as tasks_api
from app.models.ai_index_jobs import AIIndexJobType, AIIndexSourceType, AIJobStatus
from app.schemas.admin_telemetry import (
    AdminAIGovernanceAlert,
    AdminAIGovernanceMetric,
    AdminAIGovernanceResponse,
    AdminAIProviderAnomaly,
    AdminAIProviderConfigItem,
    AdminAIProviderConfigResponse,
    AdminAIProviderHealthItem,
    AdminAIProviderHealthResponse,
    AdminAITelemetryAnomalyInsight,
    AdminAITelemetryAnomalyResponse,
    AdminAITelemetryFailureItem,
    AdminAITelemetryFailuresResponse,
    AdminAITelemetrySummary,
    AdminAITelemetryTrendPoint,
    AdminAITelemetryTrendResponse,
    ChatTelemetry,
    EmbeddingTelemetry,
    IndexJobTelemetry,
    PromptCallTelemetry,
    RetrievalTelemetry,
)
from app.schemas.demo import ChatRequest, ChatServiceRequest
from app.schemas.index_jobs import MaterialIndexDeleteRequest, ReleaseIndexJobsRequest
from app.schemas.profiles import GlobalProfileInitRequest, GlobalProfileRead, ModuleProfileRead
from app.schemas.tasks import SmokeTaskRequest
from app.services.admin_telemetry_service import AdminAITelemetryService
from app.services.workflows.quiz_generation.schemas import (
    CreatedQuizQuestionRead,
    QuizGenerationCandidateSetRead,
    QuizGenerationContextRead,
    QuizGenerationPlanQuestionRead,
    QuizGenerationPlanRead,
    QuizGenerationRunResponse,
    RetrievalContextRead,
)


class RollbackSession:
    def __init__(self) -> None:
        self.rollback_calls = 0

    def rollback(self) -> None:
        self.rollback_calls += 1


def test_ai_model_catalog_scope_rechecks_course_access(monkeypatch) -> None:
    access_calls = []
    catalog_calls = []
    monkeypatch.setattr(ai_models_api, "decode_course_uuid", lambda value: 11)
    monkeypatch.setattr(ai_models_api, "decode_module_uuid", lambda value: 22)
    monkeypatch.setattr(
        ai_models_api,
        "LearningContextAccessClient",
        lambda: SimpleNamespace(
            ensure_chat_context_access=lambda **kwargs: access_calls.append(
                kwargs
            )
        ),
    )
    monkeypatch.setattr(
        ai_models_api,
        "AIModelCatalogService",
        lambda _db: SimpleNamespace(
            list_model_status=lambda **kwargs: (
                catalog_calls.append(kwargs)
                or {
                    "defaultChatModelId": None,
                    "defaultEmbeddingModelId": None,
                    "userSelectedChatModelId": None,
                    "items": [],
                }
            )
        ),
    )

    response = ai_models_api.list_ai_models(
        courseUuid="course-uuid",
        moduleUuid="module-uuid",
        current_user={"id": 7, "identity": "Learner"},
        db=object(),
    )

    assert response.items == []
    assert access_calls == [
        {
            "course_uuid": "course-uuid",
            "module_uuid": "module-uuid",
            "current_user": {"id": 7, "identity": "Learner"},
        }
    ]
    assert catalog_calls == [
        {"user_id": 7, "course_id": 11, "module_id": 22}
    ]


def test_ai_model_catalog_rejects_module_scope_without_course() -> None:
    with pytest.raises(HTTPException) as exc_info:
        ai_models_api.list_ai_models(
            courseUuid=None,
            moduleUuid="module-uuid",
            current_user={"id": 7, "identity": "Learner"},
            db=object(),
        )

    assert exc_info.value.status_code == 400


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


def _authoring_generation_response() -> QuizGenerationRunResponse:
    return QuizGenerationRunResponse(
        context=QuizGenerationContextRead(
            courseId=1,
            moduleId=2,
            courseUuid="course-uuid",
            moduleUuid="module-uuid",
            courseTitle="Course",
            moduleTitle="Module",
            quizId=3,
            quizUuid="quiz-uuid",
            quizTitle="Draft Quiz",
            quizDescription=None,
            quizStatus="draft",
            questionCountPerAttempt=1,
            timeLimitSeconds=None,
            shuffleQuestions=True,
            shuffleOptions=False,
            availableQuestionCount=0,
        ),
        retrievalContext=RetrievalContextRead(
            usedRetrieval=False,
            queryText="Generate 1 question",
            topK=5,
            chunkCount=0,
            chunks=[],
            chatModelId="glm:glm-4.7",
            embeddingModelId="glm:embedding-3",
            embeddingVersion="glm:embedding-3@1024",
            indexStatus="ready",
            indexCoverage=1.0,
        ),
        plan=QuizGenerationPlanRead(
            titleSuggestion="Draft Quiz",
            overview="Check the core concept",
            plannedQuestionCount=1,
            questions=[
                QuizGenerationPlanQuestionRead(
                    sortOrder=1,
                    learningObjective="Core concept",
                    difficulty="easy",
                    questionStyle="multiple_choice",
                    rationale="baseline review",
                )
            ],
        ),
        candidateSet=QuizGenerationCandidateSetRead(
            questionCount=1,
            questions=[
                {
                    "questionText": "Which answer is correct?",
                    "explanationText": "Because it matches the module.",
                    "sortOrder": 1,
                    "isActive": True,
                    "options": [
                        {"optionLabel": "A", "optionText": "Correct", "sortOrder": 1, "isCorrect": True},
                        {"optionLabel": "B", "optionText": "Wrong", "sortOrder": 2, "isCorrect": False},
                    ],
                }
            ],
        ),
        createdQuestions=[CreatedQuizQuestionRead(questionId=10, questionUuid="question-uuid", sortOrder=2)],
    )


def test_admin_ai_telemetry_summary_uses_aggregate_service(monkeypatch) -> None:
    # Tests admin telemetry returns aggregate metrics without prompt or message text.
    class FakeTelemetryService:
        def __init__(self, db) -> None:
            self.db = db

        def get_summary(self) -> AdminAITelemetrySummary:
            return AdminAITelemetrySummary(
                generatedAt="2026-07-02T00:00:00+00:00",
                promptCalls=PromptCallTelemetry(
                    total=4,
                    success=3,
                    failed=1,
                    timeout=0,
                    totalTokens=123,
                    averageLatencyMs=42.5,
                    latestAt="2026-07-02T00:00:00+00:00",
                ),
                retrievals=RetrievalTelemetry(total=2, averageLatencyMs=11.0),
                embeddings=EmbeddingTelemetry(total=5, success=5, failed=0, totalTokens=50),
                indexJobs=IndexJobTelemetry(
                    total=3,
                    queued=1,
                    running=0,
                    blocked=0,
                    success=2,
                    failed=0,
                    cancelled=0,
                    superseded=0,
                    byStatus=[],
                ),
                chat=ChatTelemetry(sessions=2, messages=6, activeUsers=2),
            )

        def list_failures(self, *, limit: int = 20, **_filters) -> AdminAITelemetryFailuresResponse:
            return AdminAITelemetryFailuresResponse(
                generatedAt="2026-07-02T00:00:00+00:00",
                items=[
                    AdminAITelemetryFailureItem(
                        kind="prompt",
                        id=1,
                        status="failed",
                        userId=7,
                        sessionId=2,
                        modelName="gemini",
                        callType="chat",
                        errorSummary="provider unavailable",
                    )
                ][:limit],
            )

    monkeypatch.setattr(admin_telemetry_api, "AdminAITelemetryService", FakeTelemetryService)

    response = admin_telemetry_api.get_ai_telemetry_summary(current_user={"id": 1}, db=object())

    assert response.promptCalls.total == 4
    assert response.chat.messages == 6
    assert not hasattr(response.promptCalls, "inputText")


def test_admin_ai_telemetry_failures_returns_sanitized_metadata(monkeypatch) -> None:
    # Tests admin failure drill-down avoids prompt/message payload fields.
    class FakeTelemetryService:
        def __init__(self, db) -> None:
            self.db = db

        def list_failures(self, *, limit: int = 20, **_filters) -> AdminAITelemetryFailuresResponse:
            return AdminAITelemetryFailuresResponse(
                generatedAt="2026-07-02T00:00:00+00:00",
                items=[
                    AdminAITelemetryFailureItem(
                        kind="index_job",
                        id=9,
                        status="failed",
                        courseId=1,
                        moduleId=2,
                        materialId=3,
                        attemptCount=2,
                        errorSummary="token=[redacted] service rejected request",
                    )
                ][:limit],
            )

    monkeypatch.setattr(admin_telemetry_api, "AdminAITelemetryService", FakeTelemetryService)

    response = admin_telemetry_api.list_ai_telemetry_failures(
        limit=5,
        current_user={"id": 1},
        db=object(),
    )

    assert response.items[0].kind == "index_job"
    assert "[redacted]" in (response.items[0].errorSummary or "")
    assert not hasattr(response.items[0], "inputText")
    assert not hasattr(response.items[0], "outputText")


def test_admin_ai_telemetry_failures_passes_filters_and_exports_csv(monkeypatch) -> None:
    # Tests admin failure filtering/export use the same sanitized metadata contract.
    calls = []

    class FakeTelemetryService:
        def __init__(self, db) -> None:
            self.db = db

        def list_failures(self, **kwargs) -> AdminAITelemetryFailuresResponse:
            calls.append(("list", kwargs))
            return AdminAITelemetryFailuresResponse(
                generatedAt="2026-07-02T00:00:00+00:00",
                items=[
                    AdminAITelemetryFailureItem(
                        kind="embedding",
                        id=5,
                        status="timeout",
                        userId=7,
                        courseId=11,
                        moduleId=22,
                        errorSummary="provider timeout",
                    )
                ],
            )

        def export_failures_csv(self, **kwargs) -> str:
            calls.append(("export", kwargs))
            return "kind,id,status,errorSummary\r\nembedding,5,timeout,provider timeout\r\n"

    monkeypatch.setattr(admin_telemetry_api, "AdminAITelemetryService", FakeTelemetryService)

    response = admin_telemetry_api.list_ai_telemetry_failures(
        limit=12,
        kind="embedding",
        status="timeout",
        user_id=7,
        course_id=11,
        module_id=22,
        since=None,
        until=None,
        current_user={"id": 1},
        db=object(),
    )
    export_response = admin_telemetry_api.export_ai_telemetry_failures(
        limit=50,
        kind="embedding",
        status="timeout",
        user_id=7,
        course_id=11,
        module_id=22,
        since=None,
        until=None,
        current_user={"id": 1},
        db=object(),
    )

    assert response.items[0].kind == "embedding"
    assert calls[0] == (
        "list",
        {
            "limit": 12,
            "kind": "embedding",
            "status": "timeout",
            "user_id": 7,
            "course_id": 11,
            "module_id": 22,
            "since": None,
            "until": None,
        },
    )
    assert calls[1][0] == "export"
    assert export_response.media_type == "text/csv"
    assert "provider timeout" in export_response.body.decode()


def test_admin_ai_telemetry_index_job_retry_delegates_to_index_service(monkeypatch) -> None:
    # Tests admin failure audit exposes a recovery path for failed material indexing jobs.
    calls = []

    class FakeIndexJobService:
        def __init__(self, session) -> None:
            self.session = session

        def retry_job(self, *, job_id: int):
            calls.append((self.session, job_id))
            return SimpleNamespace(jobId=job_id, status="queued", dispatched=True)

    monkeypatch.setattr(admin_telemetry_api, "IndexJobService", FakeIndexJobService)

    response = admin_telemetry_api.retry_ai_index_job_from_audit(
        42,
        current_user={"id": 1},
        db="db-session",
    )

    assert calls == [("db-session", 42)]
    assert response.jobId == 42
    assert response.status == "queued"
    assert response.dispatched is True


def test_admin_ai_telemetry_index_job_retry_uses_manage_permission() -> None:
    # Tests the recovery endpoint is not protected by read-only audit permission.
    dependency = inspect.signature(admin_telemetry_api.retry_ai_index_job_from_audit).parameters[
        "current_user"
    ].default

    assert dependency.dependency is admin_telemetry_api.require_ai_governance_manage_permission


def test_admin_ai_telemetry_trends_passes_window_and_returns_aggregates(monkeypatch) -> None:
    # Tests admin trend analysis exposes aggregate daily metrics, not prompt or retrieval text.
    calls = []

    class FakeTelemetryService:
        def __init__(self, db) -> None:
            self.db = db

        def get_trends(self, **kwargs) -> AdminAITelemetryTrendResponse:
            calls.append(kwargs)
            return AdminAITelemetryTrendResponse(
                generatedAt="2026-07-02T00:00:00+00:00",
                days=14,
                items=[
                    AdminAITelemetryTrendPoint(
                        date="2026-07-02",
                        promptCalls=8,
                        promptFailures=1,
                        promptTimeouts=0,
                        promptTotalTokens=500,
                        averagePromptLatencyMs=42.5,
                        retrievals=4,
                        averageRetrievalLatencyMs=9.0,
                        embeddingCalls=3,
                        embeddingFailures=1,
                        embeddingTotalTokens=120,
                        averageEmbeddingLatencyMs=11.0,
                        indexJobs=2,
                        indexFailures=1,
                    )
                ],
            )

    monkeypatch.setattr(admin_telemetry_api, "AdminAITelemetryService", FakeTelemetryService)

    response = admin_telemetry_api.get_ai_telemetry_trends(
        days=14,
        current_user={"id": 1},
        db=object(),
    )

    assert calls == [{"days": 14}]
    assert response.items[0].promptCalls == 8
    assert response.items[0].indexFailures == 1
    assert not hasattr(response.items[0], "inputText")
    assert not hasattr(response.items[0], "retrievedChunks")


def test_admin_ai_telemetry_anomalies_returns_sanitized_insights(monkeypatch) -> None:
    # Tests admin anomaly endpoint exposes trend insights without prompt/provider payloads.
    calls = []

    class FakeTelemetryService:
        def __init__(self, db) -> None:
            self.db = db

        def get_anomaly_insights(self, **kwargs) -> AdminAITelemetryAnomalyResponse:
            calls.append((self.db, kwargs))
            return AdminAITelemetryAnomalyResponse(
                generatedAt="2026-07-02T00:00:00+00:00",
                days=14,
                baselineDays=14,
                windowStart="2026-06-19",
                windowEnd="2026-07-02",
                baselineStart="2026-06-05",
                baselineEnd="2026-06-18",
                overallStatus="warning",
                items=[
                    AdminAITelemetryAnomalyInsight(
                        key="failure_rate_spike",
                        severity="warning",
                        category="failure_rate",
                        title="AI failure rate increased",
                        detail="Recent failure rate increased.",
                        recommendation="Review failure audit filters.",
                        metricLabel="Failure rate",
                        currentValue="20%",
                        baselineValue="4%",
                        deltaPercent=400,
                    )
                ],
            )

    monkeypatch.setattr(admin_telemetry_api, "AdminAITelemetryService", FakeTelemetryService)

    response = admin_telemetry_api.get_ai_telemetry_anomalies(days=14, current_user={"id": 1}, db="db-session")
    serialized = response.model_dump_json().lower()

    assert calls == [("db-session", {"days": 14})]
    assert response.overallStatus == "warning"
    assert response.items[0].key == "failure_rate_spike"
    assert "input_text" not in serialized
    assert "output_text" not in serialized
    assert "request_json" not in serialized
    assert "api_key" not in serialized


def test_admin_ai_telemetry_anomaly_helpers_detect_spikes(monkeypatch) -> None:
    # Tests trend anomaly helper compares recent and baseline windows across AI risk categories.
    monkeypatch.setattr(
        "app.services.admin_telemetry_service.settings",
        SimpleNamespace(
            ai_governance_failure_rate_warning_percent=10,
            ai_governance_failure_rate_blocked_percent=50,
        ),
    )
    service = AdminAITelemetryService(object())
    previous = [
        AdminAITelemetryTrendPoint(
            date="2026-06-18",
            promptCalls=20,
            promptFailures=0,
            promptTimeouts=0,
            promptTotalTokens=80_000,
            averagePromptLatencyMs=1_000,
            retrievals=8,
            averageRetrievalLatencyMs=500,
            embeddingCalls=5,
            embeddingFailures=0,
            embeddingTotalTokens=1_000,
            averageEmbeddingLatencyMs=1_000,
            indexJobs=5,
            indexFailures=0,
        )
    ]
    recent = [
        AdminAITelemetryTrendPoint(
            date="2026-07-02",
            promptCalls=20,
            promptFailures=4,
            promptTimeouts=1,
            promptTotalTokens=240_000,
            averagePromptLatencyMs=12_000,
            retrievals=0,
            averageRetrievalLatencyMs=None,
            embeddingCalls=5,
            embeddingFailures=0,
            embeddingTotalTokens=1_000,
            averageEmbeddingLatencyMs=2_500,
            indexJobs=5,
            indexFailures=3,
        )
    ]

    insights = service._build_trend_anomaly_insights(recent=recent, previous=previous)
    keys = {insight.key for insight in insights}

    assert "failure_rate_spike" in keys
    assert "prompt_latency_spike" in keys
    assert "retrieval_drop_to_zero" in keys
    assert "index_failure_spike" in keys
    assert "token_usage_spike" in keys
    assert service._overall_anomaly_status(insights) == "warning"


def test_admin_ai_provider_config_status_returns_sanitized_summary(monkeypatch) -> None:
    # Tests admin provider config status exposes readiness metadata, not secret values.
    calls = []

    class FakeTelemetryService:
        def __init__(self, db) -> None:
            self.db = db

        def get_provider_config_status(self) -> AdminAIProviderConfigResponse:
            calls.append(self.db)
            return AdminAIProviderConfigResponse(
                generatedAt="2026-07-02T00:00:00+00:00",
                overallStatus="warning",
                provider="gemini",
                model="gemini-3.6-flash",
                embeddingProvider="gemini",
                embeddingModel="gemini-embedding-2",
                storageProvider="local",
                items=[
                    AdminAIProviderConfigItem(
                        key="chat_provider",
                        label="Chat provider",
                        status="ready",
                        detail="gemini / gemini-3.6-flash",
                    )
                ],
            )

    monkeypatch.setattr(admin_telemetry_api, "AdminAITelemetryService", FakeTelemetryService)

    response = admin_telemetry_api.get_ai_provider_config_status(
        current_user={"id": 1},
        db="db-session",
    )

    assert calls == ["db-session"]
    assert response.overallStatus == "warning"
    assert response.items[0].key == "chat_provider"
    assert "api_key" not in response.model_dump_json().lower()
    assert "secret" not in response.model_dump_json().lower()


def test_admin_ai_provider_health_returns_success_rate_and_anomalies(monkeypatch) -> None:
    # Tests admin provider health exposes real-call aggregates without prompt/provider payloads.
    calls = []

    class FakeTelemetryService:
        def __init__(self, db) -> None:
            self.db = db

        def get_provider_health(self, **kwargs) -> AdminAIProviderHealthResponse:
            calls.append((self.db, kwargs))
            return AdminAIProviderHealthResponse(
                generatedAt="2026-07-02T00:00:00+00:00",
                windowStart="2026-06-18T00:00:00+00:00",
                windowEnd="2026-07-02T00:00:00+00:00",
                days=14,
                overallStatus="warning",
                provider="gemini",
                totalCalls=10,
                successRatePercent=80,
                averageLatencyMs=8500,
                items=[
                    AdminAIProviderHealthItem(
                        key="prompt:chat:gemini-3.6-flash",
                        provider="gemini",
                        modelName="gemini-3.6-flash",
                        callType="chat",
                        totalCalls=10,
                        success=8,
                        failed=1,
                        timeout=1,
                        successRatePercent=80,
                        failureRatePercent=20,
                        averageLatencyMs=8500,
                        latestAt="2026-07-02T00:00:00+00:00",
                        status="warning",
                        recommendation="Review provider errors.",
                    )
                ],
                anomalies=[
                    AdminAIProviderAnomaly(
                        key="prompt:chat:gemini-3.6-flash:failure_rate",
                        severity="warning",
                        title="Provider failure rate needs review",
                        detail="20% failures across 10 calls.",
                        recommendation="Use failure filters.",
                    )
                ],
            )

    monkeypatch.setattr(admin_telemetry_api, "AdminAITelemetryService", FakeTelemetryService)

    response = admin_telemetry_api.get_ai_provider_health(days=14, current_user={"id": 1}, db="db-session")
    serialized = response.model_dump_json().lower()

    assert calls == [("db-session", {"days": 14})]
    assert response.successRatePercent == 80
    assert response.items[0].failureRatePercent == 20
    assert response.anomalies[0].severity == "warning"
    assert "input_text" not in serialized
    assert "output_text" not in serialized
    assert "request_json" not in serialized
    assert "api_key" not in serialized


def test_admin_ai_provider_config_service_redacts_secret_values(monkeypatch) -> None:
    # Tests the real provider config builder summarizes configuration without returning secret material.
    monkeypatch.setattr(
        "app.services.admin_telemetry_service.settings",
        SimpleNamespace(
            ai_embedding_dimension=1536,
            ai_retrieval_top_k=5,
            ai_retrieval_min_score=0.45,
            celery_broker_url="redis://:super-secret-password@redis:6379/0",
            celery_result_backend="redis://:super-secret-password@redis:6379/0",
            learning_material_ai_queue="ai.material.index",
            ai_index_job_max_auto_retries=3,
            langgraph_checkpoint_enabled=True,
            langgraph_checkpoint_redis_url="redis://:super-secret-password@redis:6379/1",
            langgraph_checkpoint_key_prefix="ai.langgraph",
            object_storage_provider="minio",
            minio_bucket="learning-materials",
            minio_signed_url_expires_seconds=300,
            internal_api_token="internal-token-secret",
            public_id_secret="public-id-secret",
        ),
    )

    response = AdminAITelemetryService(object()).get_provider_config_status()
    serialized = response.model_dump_json().lower()

    assert response.overallStatus == "blocked"
    assert response.embeddingProvider == "unconfigured"
    assert response.embeddingModel == "unconfigured"
    assert "super-secret" not in serialized
    assert "internal-token-secret" not in serialized
    assert "public-id-secret" not in serialized
    assert any(item.key == "object_storage" for item in response.items)


def test_admin_ai_provider_health_anomalies_flag_failures_latency_and_missing_calls(monkeypatch) -> None:
    # Tests provider health helper turns success rate and latency into operator signals.
    monkeypatch.setattr(
        "app.services.admin_telemetry_service.settings",
        SimpleNamespace(
            ai_governance_failure_rate_warning_percent=10,
            ai_governance_failure_rate_blocked_percent=25,
        ),
    )
    service = AdminAITelemetryService(object())
    item = service._build_provider_health_item(
        key="prompt:chat:gemini-3.6-flash",
        provider="gemini",
        model_name="gemini-3.6-flash",
        call_type="chat",
        total_calls=10,
        success=6,
        failed=3,
        timeout=1,
        average_latency_ms=31_000,
        latest_at=datetime(2026, 7, 2, tzinfo=timezone.utc),
    )
    anomalies = service._build_provider_health_anomalies(items=[item], total_calls=10, days=14)
    missing = service._build_provider_health_anomalies(items=[], total_calls=0, days=14)

    assert item.status == "blocked"
    assert item.successRatePercent == 60
    assert any(anomaly.severity == "critical" and "failure rate" in anomaly.title.lower() for anomaly in anomalies)
    assert any(anomaly.severity == "critical" and "latency" in anomaly.title.lower() for anomaly in anomalies)
    assert missing[0].key == "no_provider_calls"
    assert missing[0].severity == "warning"


def test_admin_ai_governance_summary_returns_guardrail_metadata(monkeypatch) -> None:
    # Tests admin governance endpoint returns cost/quota metadata without prompt payloads.
    calls = []

    class FakeTelemetryService:
        def __init__(self, db) -> None:
            self.db = db

        def get_governance_summary(self) -> AdminAIGovernanceResponse:
            calls.append(self.db)
            return AdminAIGovernanceResponse(
                generatedAt="2026-07-02T00:00:00+00:00",
                periodStart="2026-07-01T00:00:00+00:00",
                periodEnd="2026-07-02T00:00:00+00:00",
                overallStatus="warning",
                estimatedCostUsd=1.25,
                monthlyCostBudgetUsd=10,
                costBudgetUsagePercent=12.5,
                monthlyTokenBudget=1_000_000,
                tokenBudgetUsagePercent=15,
                promptTokens=100_000,
                embeddingTokens=50_000,
                totalTokens=150_000,
                promptCalls=20,
                embeddingCalls=10,
                indexJobs=3,
                failures=2,
                failureRatePercent=6.06,
                alerts=[
                    AdminAIGovernanceAlert(
                        severity="warning",
                        title="Monthly token budget nearing limit",
                        detail="Token usage needs review.",
                        recommendation="Audit planned generation volume.",
                    )
                ],
                metrics=[
                    AdminAIGovernanceMetric(
                        key="estimated_cost",
                        label="Estimated cost",
                        value="$1.25",
                        detail="12.5% of $10.00",
                        status="ready",
                    )
                ],
            )

    monkeypatch.setattr(admin_telemetry_api, "AdminAITelemetryService", FakeTelemetryService)

    response = admin_telemetry_api.get_ai_governance_summary(current_user={"id": 1}, db="db-session")
    serialized = response.model_dump_json().lower()

    assert calls == ["db-session"]
    assert response.estimatedCostUsd == 1.25
    assert response.alerts[0].severity == "warning"
    assert "input_text" not in serialized
    assert "output_text" not in serialized
    assert "request_json" not in serialized


def test_admin_ai_governance_alerts_flag_budget_and_failure_risks(monkeypatch) -> None:
    # Tests governance helper turns cost, quota, failure, and indexing risk into operator alerts.
    monkeypatch.setattr(
        "app.services.admin_telemetry_service.settings",
        SimpleNamespace(
            ai_prompt_input_cost_per_1m_tokens=0.2,
            ai_prompt_output_cost_per_1m_tokens=0.6,
            ai_embedding_cost_per_1m_tokens=0.1,
            ai_governance_budget_warning_percent=80,
            ai_governance_failure_rate_warning_percent=10,
            ai_governance_failure_rate_blocked_percent=25,
            ai_governance_index_backlog_warning=25,
        ),
    )
    service = AdminAITelemetryService(object())

    cost = service._estimate_monthly_cost(
        prompt_input_tokens=1_000_000,
        prompt_output_tokens=500_000,
        embedding_tokens=2_000_000,
    )
    alerts = service._build_governance_alerts(
        cost_budget_usage=105,
        token_budget_usage=85,
        failure_rate=30,
        index_usage={"jobs": 10, "failed": 1, "queued": 0, "running": 0, "blocked": 2, "backlog": 2},
        pricing_configured=True,
        cost_budget_configured=True,
        token_budget_configured=True,
    )

    assert round(cost, 2) == 0.7
    assert service._overall_alert_status(alerts) == "blocked"
    assert any(alert.title == "Monthly AI cost budget exceeded" for alert in alerts)
    assert any(alert.title == "AI failure rate is high" for alert in alerts)
    assert any(alert.title == "Blocked indexing jobs require action" for alert in alerts)


def test_admin_ai_telemetry_error_summary_redacts_secrets() -> None:
    # Tests failure summaries do not expose obvious credentials.
    summary = AdminAITelemetryService(object())._sanitize_error_message(
        "provider failed api_key=abc123 Authorization: Bearer very.secret.token"
    )

    assert "abc123" not in (summary or "")
    assert "very.secret.token" not in (summary or "")
    assert "[redacted]" in (summary or "")


def test_demo_health_reports_configured_provider(monkeypatch) -> None:
    # Tests demo health returns the configured default from the shared model catalog.
    class FakeCatalog:
        def ensure_seeded(self) -> None:
            return None

        def list_model_status(self) -> dict:
            return {
                "defaultChatModelId": "glm:glm-4.7",
                "items": [
                    {
                        "modelId": "glm:glm-4.7",
                        "provider": "glm",
                        "modelName": "glm-4.7",
                        "available": True,
                    }
                ],
            }

    monkeypatch.setattr(demo_api, "AIModelCatalogService", lambda _: FakeCatalog())

    response = demo_api.demo_health(db=object())

    assert response.status == "ok"
    assert response.provider == "glm"
    assert response.model == "glm-4.7"


def test_demo_health_rejects_unavailable_default_model(monkeypatch) -> None:
    # Tests demo health is blocked when the catalog default has no usable credential.
    class FakeCatalog:
        def ensure_seeded(self) -> None:
            return None

        def list_model_status(self) -> dict:
            return {
                "defaultChatModelId": "gemini:gemini-3.5-flash-lite",
                "items": [
                    {
                        "modelId": "gemini:gemini-3.5-flash-lite",
                        "provider": "gemini",
                        "modelName": "gemini-3.5-flash-lite",
                        "available": False,
                    }
                ],
            }

    monkeypatch.setattr(demo_api, "AIModelCatalogService", lambda _: FakeCatalog())

    with pytest.raises(HTTPException) as exc_info:
        demo_api.demo_health(db=object())

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "AI provider is temporarily unavailable."


def test_demo_chat_trims_message_and_maps_success(monkeypatch) -> None:
    # Tests demo chat binds persistence to the authenticated user and encodes the returned session id.
    captured_payloads = []
    monkeypatch.setattr("app.api.demo.encode_session_uuid", lambda value: f"session-{value}")

    def fake_persist_chat(db, payload):
        captured_payloads.append(payload)
        return SimpleNamespace(
            session_id=5,
            user_message_id=6,
            assistant_message_id=7,
            reply="ok",
            sources=[],
        )

    monkeypatch.setattr("app.api.demo.persist_chat", fake_persist_chat)

    response = demo_api.demo_chat(
        ChatServiceRequest(user_id=1, course_id=99, module_id=88, message=" hi "),
        current_user={"id": 7},
        db=RollbackSession(),
    )

    assert response.session_uuid == "session-5"
    assert response.reply == "ok"
    assert captured_payloads[0].user_id == 7
    assert captured_payloads[0].course_id is None
    assert captured_payloads[0].module_id is None


def test_demo_chat_rejects_blank_message() -> None:
    # Tests demo chat rejects messages that become blank after trimming.
    with pytest.raises(HTTPException) as exc_info:
        demo_api.demo_chat(ChatServiceRequest(user_id=1, message=" "), current_user={"id": 7}, db=RollbackSession())

    assert exc_info.value.status_code == 400


@pytest.mark.parametrize(
    ("exc", "status_code", "detail"),
    [
        (demo_api.AIChatConfigurationError("Provider credential is not configured"), 503, "AI provider is temporarily unavailable."),
        (demo_api.AIChatQuotaError("quota api_key=abc123"), 429, "AI provider quota is temporarily unavailable. Please retry later."),
        (demo_api.AIChatSessionError("bad session private detail"), 400, "Chat session is invalid."),
        (RuntimeError("boom"), 500, "AI provider call failed."),
    ],
)
def test_demo_chat_maps_service_errors_to_http(monkeypatch, exc, status_code, detail) -> None:
    # Tests demo chat converts service exceptions to expected HTTP errors.
    db = RollbackSession()
    monkeypatch.setattr("app.api.demo.persist_chat", lambda *_: (_ for _ in ()).throw(exc))

    with pytest.raises(HTTPException) as exc_info:
        demo_api.demo_chat(ChatServiceRequest(user_id=1, message="hello"), current_user={"id": 7}, db=db)

    assert exc_info.value.status_code == status_code
    assert exc_info.value.detail == detail
    assert "api_key" not in exc_info.value.detail
    assert "private detail" not in exc_info.value.detail
    assert db.rollback_calls == 1


def test_authenticated_chat_success_and_error_mapping(monkeypatch) -> None:
    # Tests authenticated chat decodes ids, persists chat, and maps model errors.
    access_calls = []
    monkeypatch.setattr("app.api.chat.decode_session_uuid", lambda value: 1)
    monkeypatch.setattr("app.api.chat.decode_course_uuid", lambda value: 2)
    monkeypatch.setattr("app.api.chat.decode_module_uuid", lambda value: 3)
    monkeypatch.setattr("app.api.chat.encode_session_uuid", lambda value: f"session-{value}")
    monkeypatch.setattr(
        "app.api.chat.LearningContextAccessClient",
        lambda: SimpleNamespace(
            ensure_chat_context_access=lambda **kwargs: access_calls.append(kwargs),
        ),
    )
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
        current_user={"id": 7, "identity": "Learner"},
        db=RollbackSession(),
    )

    assert response.success is True
    assert response.data.session_uuid == "session-9"
    assert response.data.sources == [{"chunk": 1}]
    assert access_calls == [
        {
            "course_uuid": "c",
            "module_uuid": "m",
            "current_user": {"id": 7, "identity": "Learner"},
        }
    ]


@pytest.mark.parametrize(
    ("exc", "status_code", "code", "message"),
    [
        (
            chat_api.AIChatConfigurationError("Provider credential is not configured"),
            503,
            "AI_NOT_CONFIGURED",
            "AI provider is temporarily unavailable.",
        ),
        (
            chat_api.AIChatQuotaError("quota api_key=abc123"),
            429,
            "AI_QUOTA_EXCEEDED",
            "AI provider quota is temporarily unavailable. Please retry later.",
        ),
        (
            chat_api.AIChatSessionError("bad session private detail"),
            400,
            "CHAT_SESSION_INVALID",
            "Chat session is invalid.",
        ),
    ],
)
def test_authenticated_chat_redacts_service_error_details(monkeypatch, exc, status_code, code, message) -> None:
    # Tests authenticated chat keeps stable error codes without exposing provider/config/session internals.
    db = RollbackSession()
    monkeypatch.setattr("app.api.chat.persist_chat", lambda *_: (_ for _ in ()).throw(exc))

    with pytest.raises(HTTPException) as exc_info:
        chat_api.chat(
            ChatRequest(message="hello"),
            current_user={"id": 7, "identity": "Learner"},
            db=db,
        )

    assert exc_info.value.status_code == status_code
    assert exc_info.value.detail == {"code": code, "message": message}
    assert "Provider credential is not configured" not in str(exc_info.value.detail)
    assert "api_key" not in str(exc_info.value.detail)
    assert "private detail" not in str(exc_info.value.detail)
    assert db.rollback_calls == 1


def test_authenticated_chat_stops_before_persist_when_context_forbidden(monkeypatch) -> None:
    # Tests RAG context access is checked before chat persistence/retrieval.
    db = RollbackSession()
    persist_calls = []
    forbidden = HTTPException(
        status_code=403,
        detail={"code": "COURSE_ENROLLMENT_REQUIRED", "message": "Enrollment required"},
    )
    monkeypatch.setattr(
        "app.api.chat.LearningContextAccessClient",
        lambda: SimpleNamespace(
            ensure_chat_context_access=lambda **_kwargs: (_ for _ in ()).throw(forbidden),
        ),
    )
    monkeypatch.setattr("app.api.chat.persist_chat", lambda *_args: persist_calls.append(True))

    with pytest.raises(HTTPException) as exc_info:
        chat_api.chat(
            ChatRequest(course_uuid="c", module_uuid="m", message="hello"),
            current_user={"id": 7, "identity": "Learner"},
            db=db,
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "COURSE_ENROLLMENT_REQUIRED"
    assert persist_calls == []
    assert db.rollback_calls == 1


def test_authenticated_chat_rejects_module_context_without_course() -> None:
    # Tests module-scoped chat cannot bypass course-context authorization.
    db = RollbackSession()

    with pytest.raises(HTTPException) as exc_info:
        chat_api.chat(
            ChatRequest(module_uuid="m", message="hello"),
            current_user={"id": 7, "identity": "Learner"},
            db=db,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "AI_COURSE_CONTEXT_REQUIRED"
    assert db.rollback_calls == 1


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


def test_chat_session_list_filters_inaccessible_course_context(monkeypatch) -> None:
    # Tests stale course-scoped sessions are hidden after the learner loses context access.
    now = datetime(2026, 4, 29, tzinfo=timezone.utc)
    allowed_session = SimpleNamespace(
        session_id=1,
        user_id=7,
        course_id=2,
        module_id=3,
        session_type="demo",
        title="Allowed",
        status="active",
        message_count=1,
        summary_text=None,
        last_message_at=None,
        created_at=now,
        updated_at=now,
    )
    forbidden_session = SimpleNamespace(
        session_id=2,
        user_id=7,
        course_id=4,
        module_id=5,
        session_type="demo",
        title="Forbidden",
        status="active",
        message_count=1,
        summary_text=None,
        last_message_at=None,
        created_at=now,
        updated_at=now,
    )
    monkeypatch.setattr("app.api.chat.encode_session_uuid", lambda value: f"session-{value}")
    monkeypatch.setattr("app.api.chat.encode_course_uuid", lambda value: f"course-{value}")
    monkeypatch.setattr("app.api.chat.encode_module_uuid", lambda value: f"module-{value}")
    monkeypatch.setattr(
        "app.api.chat.AIChatSessionsRepository",
        lambda db: SimpleNamespace(list_by_user=lambda user_id: [allowed_session, forbidden_session]),
    )

    def _ensure_chat_context_access(**kwargs):
        if kwargs["course_uuid"] == "course-4":
            raise HTTPException(
                status_code=403,
                detail={"code": "COURSE_ENROLLMENT_REQUIRED", "message": "Enrollment required"},
            )

    monkeypatch.setattr(
        "app.api.chat.LearningContextAccessClient",
        lambda: SimpleNamespace(ensure_chat_context_access=_ensure_chat_context_access),
    )

    sessions = chat_api.list_chat_sessions(current_user={"id": 7, "identity": "Learner"}, db=object())

    assert [session.session_uuid for session in sessions] == ["session-1"]


def test_chat_session_detail_rechecks_course_context_before_returning_messages(monkeypatch) -> None:
    # Tests a stale course-scoped chat detail does not expose prior course AI content.
    now = datetime(2026, 4, 29, tzinfo=timezone.utc)
    session_row = SimpleNamespace(
        session_id=2,
        user_id=7,
        course_id=4,
        module_id=5,
        session_type="demo",
        title="Forbidden",
        status="active",
        message_count=1,
        summary_text=None,
        last_message_at=None,
        created_at=now,
        updated_at=now,
    )
    message_reads = []
    monkeypatch.setattr("app.api.chat.decode_session_uuid", lambda value: 2)
    monkeypatch.setattr("app.api.chat.encode_course_uuid", lambda value: f"course-{value}")
    monkeypatch.setattr("app.api.chat.encode_module_uuid", lambda value: f"module-{value}")
    monkeypatch.setattr(
        "app.api.chat.AIChatSessionsRepository",
        lambda db: SimpleNamespace(get_by_id=lambda session_id: session_row),
    )
    monkeypatch.setattr(
        "app.api.chat.AIChatMessagesRepository",
        lambda db: SimpleNamespace(list_visible_by_session=lambda session_id: message_reads.append(session_id)),
    )
    monkeypatch.setattr(
        "app.api.chat.LearningContextAccessClient",
        lambda: SimpleNamespace(
            ensure_chat_context_access=lambda **_kwargs: (_ for _ in ()).throw(
                HTTPException(
                    status_code=423,
                    detail={"code": "MODULE_LOCKED", "message": "Module locked"},
                )
            )
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        chat_api.get_chat_session("session-2", current_user={"id": 7, "identity": "Learner"}, db=object())

    assert exc_info.value.status_code == 423
    assert exc_info.value.detail["code"] == "MODULE_LOCKED"
    assert message_reads == []


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


def test_authoring_quiz_generation_checks_access_and_runs_graph(monkeypatch) -> None:
    # Tests educator/admin AI quiz generation is an authoring draft flow guarded by learning-service ownership checks.
    access_calls = []
    graph_calls = []

    class FakeGraphRunner:
        def __init__(self, session, checkpointer=None) -> None:
            self.session = session
            self.checkpointer = checkpointer

        def run(self, *, payload, config=None):
            graph_calls.append({"payload": payload, "config": config})
            return _authoring_generation_response()

    monkeypatch.setattr(
        "app.api.quiz_generation.LearningQuizGenerationClient",
        lambda: SimpleNamespace(
            ensure_authoring_quiz_access=lambda **kwargs: access_calls.append(kwargs),
        ),
    )
    monkeypatch.setattr("app.api.quiz_generation.QuizGenerationGraphRunner", FakeGraphRunner)
    monkeypatch.setattr("app.api.quiz_generation.get_langgraph_checkpointer", lambda: None)

    response = quiz_api.generate_authoring_quiz_questions(
        "course-uuid",
        "module-uuid",
        payload=quiz_api.QuizGenerationAuthoringRequest(additionalInstructions="Focus on week 1."),
        current_user={"id": 7, "identity": "Educator"},
        session=object(),
    )

    assert access_calls == [
        {
            "course_uuid": "course-uuid",
            "module_uuid": "module-uuid",
            "actor_id": 7,
            "actor_identity": "Educator",
        }
    ]
    assert graph_calls[0]["payload"].educatorId == 7
    assert graph_calls[0]["payload"].learnerId is None
    assert graph_calls[0]["payload"].additionalInstructions == "Focus on week 1."
    assert response.createdQuestions[0].questionUuid == "question-uuid"


def test_authoring_quiz_generation_rejects_invalid_identity(monkeypatch) -> None:
    # Tests the public authoring generation endpoint fails closed when identity data is malformed.
    monkeypatch.setattr(
        "app.api.quiz_generation.LearningQuizGenerationClient",
        lambda: SimpleNamespace(ensure_authoring_quiz_access=lambda **_kwargs: None),
    )

    with pytest.raises(HTTPException) as error:
        quiz_api.generate_authoring_quiz_questions(
            "course-uuid",
            "module-uuid",
            payload=quiz_api.QuizGenerationAuthoringRequest(),
            current_user={"id": "7", "identity": "Educator"},
            session=object(),
        )

    assert error.value.status_code == 401


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

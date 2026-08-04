from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import require_identity_permission
from app.db.session import get_db_session
from app.schemas.admin_telemetry import (
    AdminAIGovernanceResponse,
    AdminAIProviderHealthResponse,
    AdminAITelemetryAnomalyResponse,
    AdminAITelemetryFailuresResponse,
    AdminAITelemetrySummary,
    AdminAITelemetryTrendResponse,
    AdminAIProviderConfigResponse,
)
from app.schemas.index_jobs import ReindexAllMaterialsResponse, RetryIndexJobResponse
from app.services.admin_telemetry_service import AdminAITelemetryService
from app.services.indexing.index_job_service import IndexJobService
from platform_common.permissions.codes import AI_GOVERNANCE_MANAGE, AUDIT_LOG_READ


router = APIRouter(prefix="/admin/telemetry", tags=["admin-telemetry"])
require_ai_audit_read_permission = require_identity_permission(AUDIT_LOG_READ)
require_ai_governance_manage_permission = require_identity_permission(AI_GOVERNANCE_MANAGE)


@router.get(
    "/summary",
    response_model=AdminAITelemetrySummary,
    summary="Get AI telemetry summary [Admin]",
    description="Returns aggregate AI usage and indexing telemetry without exposing prompt or message text.",
)
def get_ai_telemetry_summary(
    current_user: dict = Depends(require_ai_audit_read_permission),
    db: Session = Depends(get_db_session),
) -> AdminAITelemetrySummary:
    _ = current_user
    return AdminAITelemetryService(db).get_summary()


@router.get(
    "/trends",
    response_model=AdminAITelemetryTrendResponse,
    summary="Get AI telemetry daily trends [Admin]",
    description="Returns daily aggregate AI usage, latency, token, and failure counts without prompt or retrieval payloads.",
)
def get_ai_telemetry_trends(
    days: int = Query(default=14, ge=1, le=60),
    current_user: dict = Depends(require_ai_audit_read_permission),
    db: Session = Depends(get_db_session),
) -> AdminAITelemetryTrendResponse:
    _ = current_user
    return AdminAITelemetryService(db).get_trends(days=days)


@router.get(
    "/anomalies",
    response_model=AdminAITelemetryAnomalyResponse,
    summary="Get AI telemetry anomaly insights [Admin]",
    description="Returns baseline-vs-current AI usage, latency, retrieval, and indexing anomaly insights without prompt or provider payloads.",
)
def get_ai_telemetry_anomalies(
    days: int = Query(default=14, ge=1, le=30),
    current_user: dict = Depends(require_ai_audit_read_permission),
    db: Session = Depends(get_db_session),
) -> AdminAITelemetryAnomalyResponse:
    _ = current_user
    return AdminAITelemetryService(db).get_anomaly_insights(days=days)


@router.get(
    "/provider-config",
    response_model=AdminAIProviderConfigResponse,
    summary="Get AI provider configuration status [Admin]",
    description="Returns sanitized AI provider, embedding, retrieval, workflow, storage, and service-boundary configuration status without secret values.",
)
def get_ai_provider_config_status(
    current_user: dict = Depends(require_ai_audit_read_permission),
    db: Session = Depends(get_db_session),
) -> AdminAIProviderConfigResponse:
    _ = current_user
    return AdminAITelemetryService(db).get_provider_config_status()


@router.get(
    "/provider-health",
    response_model=AdminAIProviderHealthResponse,
    summary="Get AI provider health [Admin]",
    description="Returns provider/model success rate, latency, and anomaly metadata without prompt or provider payloads.",
)
def get_ai_provider_health(
    days: int = Query(default=14, ge=1, le=60),
    current_user: dict = Depends(require_ai_audit_read_permission),
    db: Session = Depends(get_db_session),
) -> AdminAIProviderHealthResponse:
    _ = current_user
    return AdminAITelemetryService(db).get_provider_health(days=days)


@router.get(
    "/governance",
    response_model=AdminAIGovernanceResponse,
    summary="Get AI cost and quota governance summary [Admin]",
    description="Returns monthly AI token, cost, failure, and indexing guardrail alerts without prompt or provider payloads.",
)
def get_ai_governance_summary(
    current_user: dict = Depends(require_ai_audit_read_permission),
    db: Session = Depends(get_db_session),
) -> AdminAIGovernanceResponse:
    _ = current_user
    return AdminAITelemetryService(db).get_governance_summary()


@router.get(
    "/failures",
    response_model=AdminAITelemetryFailuresResponse,
    summary="List AI telemetry failures [Admin]",
    description="Returns recent failed AI prompt, embedding, and index job metadata without prompt, message, or retrieved text.",
)
def list_ai_telemetry_failures(
    limit: int = Query(default=20, ge=1, le=100),
    kind: str | None = Query(default=None, pattern="^(prompt|embedding|index_job)$"),
    status: str | None = Query(default=None, pattern="^(failed|timeout)$"),
    user_id: int | None = Query(default=None, alias="userId", ge=1),
    course_id: int | None = Query(default=None, alias="courseId", ge=1),
    module_id: int | None = Query(default=None, alias="moduleId", ge=1),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    current_user: dict = Depends(require_ai_audit_read_permission),
    db: Session = Depends(get_db_session),
) -> AdminAITelemetryFailuresResponse:
    _ = current_user
    return AdminAITelemetryService(db).list_failures(
        limit=limit,
        kind=kind,
        status=status,
        user_id=user_id,
        course_id=course_id,
        module_id=module_id,
        since=since,
        until=until,
    )


@router.get(
    "/failures/export",
    summary="Export AI telemetry failures as CSV [Admin]",
    description="Exports filtered AI failure metadata without prompt, message, retrieved chunk, request, or response bodies.",
)
def export_ai_telemetry_failures(
    limit: int = Query(default=100, ge=1, le=100),
    kind: str | None = Query(default=None, pattern="^(prompt|embedding|index_job)$"),
    status: str | None = Query(default=None, pattern="^(failed|timeout)$"),
    user_id: int | None = Query(default=None, alias="userId", ge=1),
    course_id: int | None = Query(default=None, alias="courseId", ge=1),
    module_id: int | None = Query(default=None, alias="moduleId", ge=1),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    current_user: dict = Depends(require_ai_audit_read_permission),
    db: Session = Depends(get_db_session),
) -> Response:
    _ = current_user
    csv_body = AdminAITelemetryService(db).export_failures_csv(
        limit=limit,
        kind=kind,
        status=status,
        user_id=user_id,
        course_id=course_id,
        module_id=module_id,
        since=since,
        until=until,
    )
    return Response(
        content=csv_body,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="ai-failure-audit.csv"'},
    )


@router.post(
    "/index-jobs/{job_id}/retry",
    response_model=RetryIndexJobResponse,
    summary="Retry Failed AI Index Job [Admin]",
    description="Requeues a failed or cancelled material indexing job from the admin failure audit without exposing source content.",
)
def retry_ai_index_job_from_audit(
    job_id: int,
    current_user: dict = Depends(require_ai_governance_manage_permission),
    db: Session = Depends(get_db_session),
) -> RetryIndexJobResponse:
    _ = current_user
    return IndexJobService(db).retry_job(job_id=job_id)


@router.post(
    "/index-jobs/reindex-all",
    response_model=ReindexAllMaterialsResponse,
    summary="Backfill all material vectors [Admin]",
    description="Queues every canonical material source for all configured paired embedding models.",
)
def reindex_all_ai_materials(
    current_user: dict = Depends(require_ai_governance_manage_permission),
    db: Session = Depends(get_db_session),
) -> ReindexAllMaterialsResponse:
    _ = current_user
    return IndexJobService(db).reindex_all_materials()

from __future__ import annotations

import csv
from datetime import date, datetime, time, timedelta, timezone
from io import StringIO
import re

from sqlalchemy import case, desc, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ai_chat_messages import AIChatMessage
from app.models.ai_chat_sessions import AIChatSession
from app.models.ai_embedding_logs import AIEmbeddingLog
from app.models.ai_index_jobs import AIIndexJob, AIJobStatus
from app.models.ai_prompt_logs import AIPromptLog, AIPromptStatus
from app.models.ai_retrieval_logs import AIRetrievalLog
from app.repositories.ai_model_catalog_repository import AIModelCatalogRepository
from app.schemas.admin_telemetry import (
    AdminAIGovernanceAlert,
    AdminAIGovernanceMetric,
    AdminAIGovernanceResponse,
    AdminAIProviderAnomaly,
    AdminAITelemetryAnomalyInsight,
    AdminAITelemetryAnomalyResponse,
    AdminAITelemetryFailureItem,
    AdminAITelemetryFailuresResponse,
    AdminAITelemetrySummary,
    AdminAITelemetryTrendPoint,
    AdminAITelemetryTrendResponse,
    AdminAIProviderConfigItem,
    AdminAIProviderConfigResponse,
    AdminAIProviderHealthItem,
    AdminAIProviderHealthResponse,
    ChatTelemetry,
    EmbeddingTelemetry,
    IndexJobTelemetry,
    PromptCallTelemetry,
    RetrievalTelemetry,
    TelemetryCountByStatus,
)
from app.services.providers.model_service import AIModelCatalogService

_SECRET_PATTERNS = [
    re.compile(r"(?i)(bearer\s+)[a-z0-9._~+/=-]+"),
    re.compile(r"(?i)(api[_-]?key|token|authorization|password|secret)(\s*[:=]\s*)([^\s,;]+)"),
]


class AdminAITelemetryService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_summary(self) -> AdminAITelemetrySummary:
        return AdminAITelemetrySummary(
            generatedAt=self._format_datetime(datetime.now(timezone.utc)) or "",
            promptCalls=self._get_prompt_call_telemetry(),
            retrievals=self._get_retrieval_telemetry(),
            embeddings=self._get_embedding_telemetry(),
            indexJobs=self._get_index_job_telemetry(),
            chat=self._get_chat_telemetry(),
        )

    def get_provider_config_status(self) -> AdminAIProviderConfigResponse:
        default_chat_model = None
        default_embedding_model = None
        if hasattr(self.session, "get"):
            AIModelCatalogService(self.session).ensure_seeded()
            repo = AIModelCatalogRepository(self.session)
            defaults = repo.get_defaults()
            default_chat_model = (
                repo.get_model(defaults.default_chat_model_id)
                if defaults and defaults.default_chat_model_id
                else None
            )
            default_embedding_model = (
                repo.get_model(default_chat_model.paired_embedding_model_id)
                if default_chat_model
                and default_chat_model.paired_embedding_model_id
                else None
            )
        items = [
            self._build_chat_provider_config_item(),
            self._build_embedding_provider_config_item(),
            self._build_retrieval_config_item(),
            self._build_indexing_config_item(),
            self._build_checkpoint_config_item(),
            self._build_storage_config_item(),
            self._build_security_config_item(),
        ]
        return AdminAIProviderConfigResponse(
            generatedAt=self._format_datetime(datetime.now(timezone.utc)) or "",
            overallStatus=self._overall_config_status(items),
            provider=(
                default_chat_model.provider_key
                if default_chat_model
                else "unconfigured"
            ),
            model=default_chat_model.model_name if default_chat_model else "unconfigured",
            embeddingProvider=(
                default_embedding_model.provider_key
                if default_embedding_model
                else "unconfigured"
            ),
            embeddingModel=(
                default_embedding_model.model_name
                if default_embedding_model
                else "unconfigured"
            ),
            storageProvider=settings.object_storage_provider,
            items=items,
        )

    def get_provider_health(self, *, days: int = 14) -> AdminAIProviderHealthResponse:
        AIModelCatalogService(self.session).ensure_seeded()
        normalized_days = min(max(days, 1), 60)
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=normalized_days)
        window_start_naive = self._to_naive_utc(window_start)
        items = [
            *self._get_prompt_provider_health_items(window_start_naive),
            *self._get_embedding_provider_health_items(window_start_naive),
        ]
        items.sort(key=lambda item: (self._status_rank(item.status), -item.totalCalls, item.provider, item.modelName, item.callType))

        total_calls = sum(item.totalCalls for item in items)
        total_success = sum(item.success for item in items)
        latency_items = [item for item in items if item.averageLatencyMs is not None]
        weighted_latency = (
            sum((item.averageLatencyMs or 0) * item.totalCalls for item in latency_items)
            / sum(item.totalCalls for item in latency_items)
            if latency_items
            else None
        )
        anomalies = self._build_provider_health_anomalies(items=items, total_calls=total_calls, days=normalized_days)
        return AdminAIProviderHealthResponse(
            generatedAt=self._format_datetime(now) or "",
            windowStart=self._format_datetime(window_start) or "",
            windowEnd=self._format_datetime(now) or "",
            days=normalized_days,
            overallStatus=self._overall_provider_health_status(items=items, anomalies=anomalies),
            provider="multi_provider",
            totalCalls=total_calls,
            successRatePercent=self._format_float(self._percentage(total_success, total_calls)) or 0.0,
            averageLatencyMs=self._format_float(weighted_latency),
            items=items,
            anomalies=anomalies,
        )

    def get_governance_summary(self) -> AdminAIGovernanceResponse:
        now = datetime.now(timezone.utc)
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        period_start_naive = self._to_naive_utc(period_start)

        prompt_usage = self._get_monthly_prompt_usage(period_start_naive)
        embedding_usage = self._get_monthly_embedding_usage(period_start_naive)
        index_usage = self._get_monthly_index_usage(period_start_naive)
        cost_usd = self._estimate_monthly_cost(
            prompt_input_tokens=prompt_usage["billable_input_tokens"],
            prompt_output_tokens=prompt_usage["billable_output_tokens"],
            embedding_tokens=embedding_usage["tokens"],
        )
        total_tokens = prompt_usage["tokens"] + embedding_usage["tokens"]
        total_events = prompt_usage["calls"] + embedding_usage["calls"] + index_usage["jobs"]
        failures = prompt_usage["failed"] + prompt_usage["timeout"] + embedding_usage["failed"] + index_usage["failed"]
        failure_rate = self._percentage(failures, total_events)
        cost_budget = self._optional_positive_float(settings.ai_governance_monthly_cost_budget_usd)
        token_budget = self._optional_positive_int(settings.ai_governance_monthly_token_budget)
        cost_budget_usage = self._percentage(cost_usd, cost_budget) if cost_budget else None
        token_budget_usage = self._percentage(total_tokens, token_budget) if token_budget else None
        alerts = self._build_governance_alerts(
            cost_budget_usage=cost_budget_usage,
            token_budget_usage=token_budget_usage,
            failure_rate=failure_rate,
            index_usage=index_usage,
            pricing_configured=self._is_pricing_configured(),
            cost_budget_configured=cost_budget is not None,
            token_budget_configured=token_budget is not None,
        )

        return AdminAIGovernanceResponse(
            generatedAt=self._format_datetime(now) or "",
            periodStart=self._format_datetime(period_start) or "",
            periodEnd=self._format_datetime(now) or "",
            overallStatus=self._overall_alert_status(alerts),
            estimatedCostUsd=round(cost_usd, 4),
            monthlyCostBudgetUsd=cost_budget,
            costBudgetUsagePercent=self._format_float(cost_budget_usage),
            monthlyTokenBudget=token_budget,
            tokenBudgetUsagePercent=self._format_float(token_budget_usage),
            promptTokens=prompt_usage["tokens"],
            embeddingTokens=embedding_usage["tokens"],
            totalTokens=total_tokens,
            promptCalls=prompt_usage["calls"],
            embeddingCalls=embedding_usage["calls"],
            indexJobs=index_usage["jobs"],
            failures=failures,
            failureRatePercent=self._format_float(failure_rate) or 0.0,
            alerts=alerts,
            metrics=self._build_governance_metrics(
                cost_usd=cost_usd,
                cost_budget=cost_budget,
                cost_budget_usage=cost_budget_usage,
                total_tokens=total_tokens,
                token_budget=token_budget,
                token_budget_usage=token_budget_usage,
                failure_rate=failure_rate,
                failures=failures,
                total_events=total_events,
                index_usage=index_usage,
            ),
        )

    def get_trends(self, *, days: int = 14) -> AdminAITelemetryTrendResponse:
        normalized_days = min(max(days, 1), 60)
        today = datetime.now(timezone.utc).date()
        start_day = today - timedelta(days=normalized_days - 1)
        start_at = datetime.combine(start_day, time.min)
        points = self._build_empty_trend_points(start_day, normalized_days)

        self._merge_prompt_trends(points, start_at=start_at)
        self._merge_retrieval_trends(points, start_at=start_at)
        self._merge_embedding_trends(points, start_at=start_at)
        self._merge_index_job_trends(points, start_at=start_at)

        return AdminAITelemetryTrendResponse(
            generatedAt=self._format_datetime(datetime.now(timezone.utc)) or "",
            days=normalized_days,
            items=[
                AdminAITelemetryTrendPoint(**points[day_key])
                for day_key in sorted(points)
            ],
        )

    def get_anomaly_insights(self, *, days: int = 14) -> AdminAITelemetryAnomalyResponse:
        normalized_days = min(max(days, 1), 30)
        trend_days = min(max(normalized_days * 2, 2), 60)
        trends = self.get_trends(days=trend_days).items
        recent = trends[-normalized_days:]
        previous = trends[
            max(0, len(trends) - (normalized_days * 2)): max(0, len(trends) - normalized_days)
        ]
        items = self._build_trend_anomaly_insights(recent=recent, previous=previous)
        return AdminAITelemetryAnomalyResponse(
            generatedAt=self._format_datetime(datetime.now(timezone.utc)) or "",
            days=normalized_days,
            baselineDays=len(previous),
            windowStart=recent[0].date if recent else None,
            windowEnd=recent[-1].date if recent else None,
            baselineStart=previous[0].date if previous else None,
            baselineEnd=previous[-1].date if previous else None,
            overallStatus=self._overall_anomaly_status(items),
            items=items,
        )

    def list_failures(
        self,
        *,
        limit: int = 20,
        kind: str | None = None,
        status: str | None = None,
        user_id: int | None = None,
        course_id: int | None = None,
        module_id: int | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> AdminAITelemetryFailuresResponse:
        normalized_limit = min(max(limit, 1), 100)
        normalized_kind = self._normalize_kind(kind)
        normalized_status = self._normalize_status_filter(status)
        prompt_failures = (
            self._list_prompt_failures(limit=normalized_limit, status=normalized_status, user_id=user_id, since=since, until=until)
            if normalized_kind in (None, "prompt") and course_id is None and module_id is None
            else []
        )
        embedding_failures = (
            self._list_embedding_failures(
                limit=normalized_limit,
                status=normalized_status,
                user_id=user_id,
                course_id=course_id,
                module_id=module_id,
                since=since,
                until=until,
            )
            if normalized_kind in (None, "embedding")
            else []
        )
        index_failures = (
            self._list_index_failures(
                limit=normalized_limit,
                status=normalized_status,
                course_id=course_id,
                module_id=module_id,
                since=since,
                until=until,
            )
            if normalized_kind in (None, "index_job") and user_id is None
            else []
        )
        items = sorted(
            [*prompt_failures, *embedding_failures, *index_failures],
            key=lambda item: item.occurredAt or "",
            reverse=True,
        )[:normalized_limit]
        return AdminAITelemetryFailuresResponse(
            generatedAt=self._format_datetime(datetime.now(timezone.utc)) or "",
            items=items,
        )

    def export_failures_csv(
        self,
        *,
        limit: int = 100,
        kind: str | None = None,
        status: str | None = None,
        user_id: int | None = None,
        course_id: int | None = None,
        module_id: int | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> str:
        response = self.list_failures(
            limit=limit,
            kind=kind,
            status=status,
            user_id=user_id,
            course_id=course_id,
            module_id=module_id,
            since=since,
            until=until,
        )
        output = StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "kind",
                "id",
                "status",
                "occurredAt",
                "userId",
                "sessionId",
                "messageId",
                "courseId",
                "moduleId",
                "materialId",
                "modelName",
                "callType",
                "latencyMs",
                "totalTokens",
                "attemptCount",
                "errorSummary",
            ],
        )
        writer.writeheader()
        for item in response.items:
            writer.writerow(item.model_dump(mode="json"))
        return output.getvalue()

    def _build_trend_anomaly_insights(
        self,
        *,
        recent: list[AdminAITelemetryTrendPoint],
        previous: list[AdminAITelemetryTrendPoint],
    ) -> list[AdminAITelemetryAnomalyInsight]:
        insights: list[AdminAITelemetryAnomalyInsight] = []
        recent_failures = self._trend_failures(recent)
        previous_failures = self._trend_failures(previous)
        recent_events = self._trend_events(recent)
        previous_events = self._trend_events(previous)
        recent_failure_rate = self._percentage(recent_failures, recent_events)
        previous_failure_rate = self._percentage(previous_failures, previous_events)
        failure_delta = self._relative_delta_percent(recent_failure_rate, previous_failure_rate)

        if recent_failures > 0 and recent_failure_rate >= max(settings.ai_governance_failure_rate_blocked_percent, 0):
            insights.append(
                self._trend_anomaly(
                    key="failure_rate_high",
                    severity="critical",
                    category="failure_rate",
                    title="AI failure rate is above the blocked threshold",
                    detail=(
                        f"Recent AI failure rate is {self._format_percent_value(recent_failure_rate)} "
                        f"with {recent_failures:,} failures across {recent_events:,} tracked events."
                    ),
                    recommendation="Pause broad AI rollout and review provider health, failure audit filters, and indexing worker status.",
                    metric_label="Failure rate",
                    current_value=self._format_percent_value(recent_failure_rate),
                    baseline_value=self._format_percent_value(previous_failure_rate),
                    delta_percent=failure_delta,
                )
            )
        elif recent_failures > 0 and (
            recent_failure_rate >= max(settings.ai_governance_failure_rate_warning_percent, 0)
            or (
                recent_failures >= 3
                and previous_events > 0
                and recent_failure_rate >= max(previous_failure_rate * 2, previous_failure_rate + 5)
            )
        ):
            insights.append(
                self._trend_anomaly(
                    key="failure_rate_spike",
                    severity="warning",
                    category="failure_rate",
                    title="AI failure rate increased",
                    detail=(
                        f"Recent AI failure rate is {self._format_percent_value(recent_failure_rate)} "
                        f"versus {self._format_percent_value(previous_failure_rate)} in the previous window."
                    ),
                    recommendation="Filter the failure audit by kind/status and compare affected users, courses, and modules before expanding usage.",
                    metric_label="Failure rate",
                    current_value=self._format_percent_value(recent_failure_rate),
                    baseline_value=self._format_percent_value(previous_failure_rate),
                    delta_percent=failure_delta,
                )
            )

        prompt_latency = self._weighted_trend_average(recent, count_attr="promptCalls", value_attr="averagePromptLatencyMs")
        previous_prompt_latency = self._weighted_trend_average(previous, count_attr="promptCalls", value_attr="averagePromptLatencyMs")
        prompt_severity = self._trend_latency_severity(prompt_latency, previous_prompt_latency)
        if prompt_severity:
            insights.append(
                self._trend_anomaly(
                    key="prompt_latency_spike",
                    severity=prompt_severity,
                    category="latency",
                    title="Prompt latency needs review",
                    detail=(
                        f"Recent average prompt latency is {self._format_latency_value(prompt_latency)} "
                        f"versus {self._format_latency_value(previous_prompt_latency)} in the previous window."
                    ),
                    recommendation="Review slow prompt traces, prompt size, retrieval scope, provider quota, and timeout settings.",
                    metric_label="Prompt latency",
                    current_value=self._format_latency_value(prompt_latency),
                    baseline_value=self._format_latency_value(previous_prompt_latency),
                    delta_percent=self._relative_delta_percent(prompt_latency, previous_prompt_latency),
                )
            )

        embedding_latency = self._weighted_trend_average(recent, count_attr="embeddingCalls", value_attr="averageEmbeddingLatencyMs")
        previous_embedding_latency = self._weighted_trend_average(previous, count_attr="embeddingCalls", value_attr="averageEmbeddingLatencyMs")
        embedding_severity = self._trend_latency_severity(embedding_latency, previous_embedding_latency)
        if embedding_severity:
            insights.append(
                self._trend_anomaly(
                    key="embedding_latency_spike",
                    severity=embedding_severity,
                    category="latency",
                    title="Embedding latency needs review",
                    detail=(
                        f"Recent average embedding latency is {self._format_latency_value(embedding_latency)} "
                        f"versus {self._format_latency_value(previous_embedding_latency)} in the previous window."
                    ),
                    recommendation="Check embedding provider quota, indexing batch size, worker concurrency, and retry pressure.",
                    metric_label="Embedding latency",
                    current_value=self._format_latency_value(embedding_latency),
                    baseline_value=self._format_latency_value(previous_embedding_latency),
                    delta_percent=self._relative_delta_percent(embedding_latency, previous_embedding_latency),
                )
            )

        retrieval_latency = self._weighted_trend_average(recent, count_attr="retrievals", value_attr="averageRetrievalLatencyMs")
        previous_retrieval_latency = self._weighted_trend_average(previous, count_attr="retrievals", value_attr="averageRetrievalLatencyMs")
        retrieval_severity = self._retrieval_latency_severity(retrieval_latency, previous_retrieval_latency)
        if retrieval_severity:
            insights.append(
                self._trend_anomaly(
                    key="retrieval_latency_spike",
                    severity=retrieval_severity,
                    category="retrieval",
                    title="RAG retrieval latency increased",
                    detail=(
                        f"Recent retrieval latency is {self._format_latency_value(retrieval_latency)} "
                        f"versus {self._format_latency_value(previous_retrieval_latency)} in the previous window."
                    ),
                    recommendation="Review vector index health, top-k settings, database load, and query filters.",
                    metric_label="Retrieval latency",
                    current_value=self._format_latency_value(retrieval_latency),
                    baseline_value=self._format_latency_value(previous_retrieval_latency),
                    delta_percent=self._relative_delta_percent(retrieval_latency, previous_retrieval_latency),
                )
            )

        recent_prompt_calls = self._sum_trend(recent, "promptCalls")
        recent_retrievals = self._sum_trend(recent, "retrievals")
        previous_retrievals = self._sum_trend(previous, "retrievals")
        if recent_prompt_calls >= 10 and recent_retrievals == 0 and previous_retrievals > 0:
            insights.append(
                self._trend_anomaly(
                    key="retrieval_drop_to_zero",
                    severity="warning",
                    category="retrieval",
                    title="RAG retrievals dropped to zero",
                    detail=(
                        f"Recent prompt calls reached {recent_prompt_calls:,}, but retrieval logs dropped from "
                        f"{previous_retrievals:,} to 0."
                    ),
                    recommendation="Verify course-context authorization, indexing availability, and retrieval logging before relying on course-grounded chat.",
                    metric_label="Retrievals",
                    current_value="0",
                    baseline_value=f"{previous_retrievals:,}",
                    delta_percent=-100.0,
                )
            )

        recent_index_failures = self._sum_trend(recent, "indexFailures")
        previous_index_failures = self._sum_trend(previous, "indexFailures")
        if recent_index_failures >= 3 and (previous_index_failures == 0 or recent_index_failures >= previous_index_failures * 2):
            insights.append(
                self._trend_anomaly(
                    key="index_failure_spike",
                    severity="warning",
                    category="indexing",
                    title="Indexing failures spiked",
                    detail=(
                        f"Recent indexing failures increased to {recent_index_failures:,} "
                        f"from {previous_index_failures:,} in the previous window."
                    ),
                    recommendation="Review failed index jobs, material scanner results, worker health, and provider embedding availability.",
                    metric_label="Index failures",
                    current_value=f"{recent_index_failures:,}",
                    baseline_value=f"{previous_index_failures:,}",
                    delta_percent=self._relative_delta_percent(recent_index_failures, previous_index_failures),
                )
            )

        recent_tokens = self._sum_trend(recent, "promptTotalTokens")
        previous_tokens = self._sum_trend(previous, "promptTotalTokens")
        if recent_tokens >= 100_000 and previous_tokens > 0 and recent_tokens >= previous_tokens * 2:
            insights.append(
                self._trend_anomaly(
                    key="token_usage_spike",
                    severity="warning",
                    category="usage",
                    title="Prompt token usage spiked",
                    detail=(
                        f"Recent prompt tokens increased to {recent_tokens:,} "
                        f"from {previous_tokens:,} in the previous window."
                    ),
                    recommendation="Review high-volume generation workflows and cost guardrails before approving wider usage.",
                    metric_label="Prompt tokens",
                    current_value=f"{recent_tokens:,}",
                    baseline_value=f"{previous_tokens:,}",
                    delta_percent=self._relative_delta_percent(recent_tokens, previous_tokens),
                )
            )

        insights.sort(key=lambda item: (self._severity_rank(item.severity), item.category, item.key))
        return insights[:8]

    def _trend_anomaly(
        self,
        *,
        key: str,
        severity: str,
        category: str,
        title: str,
        detail: str,
        recommendation: str,
        metric_label: str,
        current_value: str,
        baseline_value: str | None,
        delta_percent: float | None,
    ) -> AdminAITelemetryAnomalyInsight:
        return AdminAITelemetryAnomalyInsight(
            key=key,
            severity=severity,
            category=category,
            title=title,
            detail=detail,
            recommendation=recommendation,
            metricLabel=metric_label,
            currentValue=current_value,
            baselineValue=baseline_value,
            deltaPercent=self._format_float(delta_percent),
        )

    def _get_prompt_provider_health_items(self, window_start: datetime) -> list[AdminAIProviderHealthItem]:
        stmt = (
            select(
                AIPromptLog.model_name,
                AIPromptLog.call_type,
                func.count(AIPromptLog.prompt_log_id),
                func.coalesce(func.sum(case((AIPromptLog.status == AIPromptStatus.SUCCESS, 1), else_=0)), 0),
                func.coalesce(func.sum(case((AIPromptLog.status == AIPromptStatus.FAILED, 1), else_=0)), 0),
                func.coalesce(func.sum(case((AIPromptLog.status == AIPromptStatus.TIMEOUT, 1), else_=0)), 0),
                func.avg(AIPromptLog.latency_ms),
                func.max(AIPromptLog.created_at),
            )
            .where(AIPromptLog.created_at >= window_start)
            .group_by(AIPromptLog.model_name, AIPromptLog.call_type)
        )
        return [
            self._build_provider_health_item(
                key=f"prompt:{self._status_value(call_type)}:{model_name}",
                provider=self._provider_for_model_name(model_name),
                model_name=model_name,
                call_type=self._status_value(call_type),
                total_calls=int(total or 0),
                success=int(success or 0),
                failed=int(failed or 0),
                timeout=int(timeout or 0),
                average_latency_ms=self._format_float(avg_latency),
                latest_at=latest_at,
            )
            for model_name, call_type, total, success, failed, timeout, avg_latency, latest_at in self.session.execute(stmt).all()
        ]

    def _provider_for_model_name(self, model_name: str) -> str:
        repo = AIModelCatalogRepository(self.session)
        for model in repo.list_models():
            if model.model_name == model_name or model.model_id == model_name:
                return model.provider_key
        return "unknown"

    def _get_embedding_provider_health_items(self, window_start: datetime) -> list[AdminAIProviderHealthItem]:
        stmt = (
            select(
                AIEmbeddingLog.model_name,
                AIEmbeddingLog.task_type,
                func.count(AIEmbeddingLog.embedding_log_id),
                func.coalesce(func.sum(case((AIEmbeddingLog.status == AIPromptStatus.SUCCESS, 1), else_=0)), 0),
                func.coalesce(func.sum(case((AIEmbeddingLog.status == AIPromptStatus.FAILED, 1), else_=0)), 0),
                func.coalesce(func.sum(case((AIEmbeddingLog.status == AIPromptStatus.TIMEOUT, 1), else_=0)), 0),
                func.avg(AIEmbeddingLog.latency_ms),
                func.max(AIEmbeddingLog.created_at),
            )
            .where(AIEmbeddingLog.created_at >= window_start)
            .group_by(AIEmbeddingLog.model_name, AIEmbeddingLog.task_type)
        )
        return [
            self._build_provider_health_item(
                key=f"embedding:{task_type or 'default'}:{model_name}",
                provider=self._provider_for_model_name(model_name),
                model_name=model_name,
                call_type=f"embedding/{task_type}" if task_type else "embedding",
                total_calls=int(total or 0),
                success=int(success or 0),
                failed=int(failed or 0),
                timeout=int(timeout or 0),
                average_latency_ms=self._format_float(avg_latency),
                latest_at=latest_at,
            )
            for model_name, task_type, total, success, failed, timeout, avg_latency, latest_at in self.session.execute(stmt).all()
        ]

    def _build_provider_health_item(
        self,
        *,
        key: str,
        provider: str,
        model_name: str,
        call_type: str,
        total_calls: int,
        success: int,
        failed: int,
        timeout: int,
        average_latency_ms: float | None,
        latest_at: datetime | None,
    ) -> AdminAIProviderHealthItem:
        failure_rate = self._percentage(failed + timeout, total_calls)
        success_rate = self._percentage(success, total_calls)
        status = self._provider_health_status(failure_rate=failure_rate, average_latency_ms=average_latency_ms)
        return AdminAIProviderHealthItem(
            key=key,
            provider=provider,
            modelName=model_name,
            callType=call_type,
            totalCalls=total_calls,
            success=success,
            failed=failed,
            timeout=timeout,
            successRatePercent=self._format_float(success_rate) or 0.0,
            failureRatePercent=self._format_float(failure_rate) or 0.0,
            averageLatencyMs=average_latency_ms,
            latestAt=self._format_datetime(latest_at),
            status=status,
            recommendation=self._provider_health_recommendation(
                status=status,
                failure_rate=failure_rate,
                average_latency_ms=average_latency_ms,
            ),
        )

    def _build_provider_health_anomalies(
        self,
        *,
        items: list[AdminAIProviderHealthItem],
        total_calls: int,
        days: int,
    ) -> list[AdminAIProviderAnomaly]:
        if total_calls == 0:
            return [
                AdminAIProviderAnomaly(
                    key="no_provider_calls",
                    severity="warning",
                    title="No provider calls recorded",
                    detail=f"No prompt or embedding provider calls were logged in the last {days} days.",
                    recommendation="Run a real chat, quiz generation, or material indexing smoke test before signing off provider health.",
                )
            ]

        anomalies: list[AdminAIProviderAnomaly] = []
        for item in items:
            if item.failureRatePercent >= max(settings.ai_governance_failure_rate_blocked_percent, 0):
                anomalies.append(
                    AdminAIProviderAnomaly(
                        key=f"{item.key}:failure_rate",
                        severity="critical",
                        title="Provider failure rate is high",
                        detail=(
                            f"{item.provider} {item.modelName} {item.callType} has "
                            f"{self._format_percent_value(item.failureRatePercent)} failures across {item.totalCalls} calls."
                        ),
                        recommendation="Pause broad rollout for this workflow and review provider status, credentials, quota, and recent failure audit entries.",
                    )
                )
            elif item.failureRatePercent >= max(settings.ai_governance_failure_rate_warning_percent, 0):
                anomalies.append(
                    AdminAIProviderAnomaly(
                        key=f"{item.key}:failure_rate",
                        severity="warning",
                        title="Provider failure rate needs review",
                        detail=(
                            f"{item.provider} {item.modelName} {item.callType} has "
                            f"{self._format_percent_value(item.failureRatePercent)} failures across {item.totalCalls} calls."
                        ),
                        recommendation="Use the failure audit filters to identify affected users, courses, or modules.",
                    )
                )

            if item.averageLatencyMs is not None and item.averageLatencyMs >= 30_000:
                anomalies.append(
                    AdminAIProviderAnomaly(
                        key=f"{item.key}:latency",
                        severity="critical",
                        title="Provider latency is severe",
                        detail=(
                            f"{item.provider} {item.modelName} {item.callType} average latency is "
                            f"{round(item.averageLatencyMs)} ms."
                        ),
                        recommendation="Check provider quota, network path, and timeout settings before learners depend on this workflow.",
                    )
                )
            elif item.averageLatencyMs is not None and item.averageLatencyMs >= 10_000:
                anomalies.append(
                    AdminAIProviderAnomaly(
                        key=f"{item.key}:latency",
                        severity="warning",
                        title="Provider latency needs review",
                        detail=(
                            f"{item.provider} {item.modelName} {item.callType} average latency is "
                            f"{round(item.averageLatencyMs)} ms."
                        ),
                        recommendation="Review slow traces and consider reducing prompt size, retrieval scope, or generation concurrency.",
                    )
                )

        return anomalies[:8]

    def _get_prompt_call_telemetry(self) -> PromptCallTelemetry:
        stmt = select(
            func.count(AIPromptLog.prompt_log_id),
            func.coalesce(func.sum(case((AIPromptLog.status == AIPromptStatus.SUCCESS, 1), else_=0)), 0),
            func.coalesce(func.sum(case((AIPromptLog.status == AIPromptStatus.FAILED, 1), else_=0)), 0),
            func.coalesce(func.sum(case((AIPromptLog.status == AIPromptStatus.TIMEOUT, 1), else_=0)), 0),
            func.coalesce(func.sum(AIPromptLog.total_tokens), 0),
            func.avg(AIPromptLog.latency_ms),
            func.max(AIPromptLog.created_at),
        )
        total, success, failed, timeout, total_tokens, avg_latency, latest_at = self.session.execute(stmt).one()
        return PromptCallTelemetry(
            total=int(total or 0),
            success=int(success or 0),
            failed=int(failed or 0),
            timeout=int(timeout or 0),
            totalTokens=int(total_tokens or 0),
            averageLatencyMs=self._format_float(avg_latency),
            latestAt=self._format_datetime(latest_at),
        )

    def _get_retrieval_telemetry(self) -> RetrievalTelemetry:
        stmt = select(
            func.count(AIRetrievalLog.retrieval_id),
            func.avg(AIRetrievalLog.latency_ms),
            func.max(AIRetrievalLog.created_at),
        )
        total, avg_latency, latest_at = self.session.execute(stmt).one()
        return RetrievalTelemetry(
            total=int(total or 0),
            averageLatencyMs=self._format_float(avg_latency),
            latestAt=self._format_datetime(latest_at),
        )

    def _get_embedding_telemetry(self) -> EmbeddingTelemetry:
        stmt = select(
            func.count(AIEmbeddingLog.embedding_log_id),
            func.coalesce(func.sum(case((AIEmbeddingLog.status == AIPromptStatus.SUCCESS, 1), else_=0)), 0),
            func.coalesce(func.sum(case((AIEmbeddingLog.status == AIPromptStatus.FAILED, 1), else_=0)), 0),
            func.coalesce(func.sum(AIEmbeddingLog.provider_total_tokens), 0),
            func.avg(AIEmbeddingLog.latency_ms),
            func.max(AIEmbeddingLog.created_at),
        )
        total, success, failed, total_tokens, avg_latency, latest_at = self.session.execute(stmt).one()
        return EmbeddingTelemetry(
            total=int(total or 0),
            success=int(success or 0),
            failed=int(failed or 0),
            totalTokens=int(total_tokens or 0),
            averageLatencyMs=self._format_float(avg_latency),
            latestAt=self._format_datetime(latest_at),
        )

    def _get_index_job_telemetry(self) -> IndexJobTelemetry:
        counts_stmt = select(AIIndexJob.status, func.count(AIIndexJob.job_id)).group_by(AIIndexJob.status)
        status_counts: dict[str, int] = {
            self._status_value(status): int(count or 0)
            for status, count in self.session.execute(counts_stmt).all()
        }
        total = sum(status_counts.values())

        latest_failure_stmt = select(func.max(AIIndexJob.finished_at)).where(AIIndexJob.status == AIJobStatus.FAILED)
        latest_failure_at = self.session.execute(latest_failure_stmt).scalar_one_or_none()

        return IndexJobTelemetry(
            total=total,
            queued=status_counts.get(AIJobStatus.QUEUED.value, 0),
            running=status_counts.get(AIJobStatus.RUNNING.value, 0),
            blocked=status_counts.get(AIJobStatus.BLOCKED.value, 0),
            success=status_counts.get(AIJobStatus.SUCCESS.value, 0),
            failed=status_counts.get(AIJobStatus.FAILED.value, 0),
            cancelled=status_counts.get(AIJobStatus.CANCELLED.value, 0),
            superseded=status_counts.get(AIJobStatus.SUPERSEDED.value, 0),
            byStatus=[
                TelemetryCountByStatus(status=status, count=count)
                for status, count in sorted(status_counts.items(), key=lambda item: item[0])
            ],
            latestFailureAt=self._format_datetime(latest_failure_at),
        )

    def _get_chat_telemetry(self) -> ChatTelemetry:
        session_stmt = select(
            func.count(AIChatSession.session_id),
            func.count(func.distinct(AIChatSession.user_id)),
            func.max(AIChatSession.updated_at),
        )
        sessions, active_users, latest_at = self.session.execute(session_stmt).one()

        message_stmt = select(func.count(AIChatMessage.message_id))
        messages = self.session.execute(message_stmt).scalar_one()

        return ChatTelemetry(
            sessions=int(sessions or 0),
            messages=int(messages or 0),
            activeUsers=int(active_users or 0),
            latestActivityAt=self._format_datetime(latest_at),
        )

    def _get_monthly_prompt_usage(self, period_start: datetime) -> dict[str, int]:
        stmt = select(
            func.count(AIPromptLog.prompt_log_id),
            func.coalesce(func.sum(case((AIPromptLog.status == AIPromptStatus.FAILED, 1), else_=0)), 0),
            func.coalesce(func.sum(case((AIPromptLog.status == AIPromptStatus.TIMEOUT, 1), else_=0)), 0),
            func.coalesce(func.sum(AIPromptLog.prompt_tokens), 0),
            func.coalesce(func.sum(AIPromptLog.completion_tokens), 0),
            func.coalesce(func.sum(AIPromptLog.total_tokens), 0),
        ).where(AIPromptLog.created_at >= period_start)
        calls, failed, timeout, input_tokens, output_tokens, total_tokens = self.session.execute(stmt).one()
        known_input = int(input_tokens or 0)
        known_output = int(output_tokens or 0)
        logged_total = int(total_tokens or 0)
        split_total = known_input + known_output
        metered_total = max(logged_total, split_total)
        missing_split = max(0, metered_total - split_total)
        return {
            "calls": int(calls or 0),
            "failed": int(failed or 0),
            "timeout": int(timeout or 0),
            "tokens": metered_total,
            "billable_input_tokens": known_input + missing_split,
            "billable_output_tokens": known_output,
        }

    def _get_monthly_embedding_usage(self, period_start: datetime) -> dict[str, int]:
        stmt = select(
            func.count(AIEmbeddingLog.embedding_log_id),
            func.coalesce(
                func.sum(
                    case((AIEmbeddingLog.status.in_([AIPromptStatus.FAILED, AIPromptStatus.TIMEOUT]), 1), else_=0)
                ),
                0,
            ),
            func.coalesce(func.sum(AIEmbeddingLog.provider_total_tokens), 0),
        ).where(AIEmbeddingLog.created_at >= period_start)
        calls, failed, total_tokens = self.session.execute(stmt).one()
        return {
            "calls": int(calls or 0),
            "failed": int(failed or 0),
            "tokens": int(total_tokens or 0),
        }

    def _get_monthly_index_usage(self, period_start: datetime) -> dict[str, int]:
        stmt = select(
            func.count(AIIndexJob.job_id),
            func.coalesce(func.sum(case((AIIndexJob.status == AIJobStatus.FAILED, 1), else_=0)), 0),
            func.coalesce(func.sum(case((AIIndexJob.status == AIJobStatus.QUEUED, 1), else_=0)), 0),
            func.coalesce(func.sum(case((AIIndexJob.status == AIJobStatus.RUNNING, 1), else_=0)), 0),
            func.coalesce(func.sum(case((AIIndexJob.status == AIJobStatus.BLOCKED, 1), else_=0)), 0),
        ).where(AIIndexJob.created_at >= period_start)
        jobs, failed, queued, running, blocked = self.session.execute(stmt).one()
        return {
            "jobs": int(jobs or 0),
            "failed": int(failed or 0),
            "queued": int(queued or 0),
            "running": int(running or 0),
            "blocked": int(blocked or 0),
            "backlog": int((queued or 0) + (running or 0) + (blocked or 0)),
        }

    def _estimate_monthly_cost(
        self,
        *,
        prompt_input_tokens: int,
        prompt_output_tokens: int,
        embedding_tokens: int,
    ) -> float:
        return (
            (prompt_input_tokens / 1_000_000) * max(settings.ai_prompt_input_cost_per_1m_tokens, 0)
            + (prompt_output_tokens / 1_000_000) * max(settings.ai_prompt_output_cost_per_1m_tokens, 0)
            + (embedding_tokens / 1_000_000) * max(settings.ai_embedding_cost_per_1m_tokens, 0)
        )

    def _build_governance_alerts(
        self,
        *,
        cost_budget_usage: float | None,
        token_budget_usage: float | None,
        failure_rate: float,
        index_usage: dict[str, int],
        pricing_configured: bool,
        cost_budget_configured: bool,
        token_budget_configured: bool,
    ) -> list[AdminAIGovernanceAlert]:
        alerts: list[AdminAIGovernanceAlert] = []
        warning_threshold = max(settings.ai_governance_budget_warning_percent, 0)
        if not pricing_configured:
            alerts.append(
                AdminAIGovernanceAlert(
                    severity="warning",
                    title="AI pricing is not configured",
                    detail="Estimated cost is shown as zero because token price settings are disabled.",
                    recommendation="Set AI_PROMPT_* and AI_EMBEDDING_COST_PER_1M_TOKENS for provider-specific estimates.",
                )
            )
        if not cost_budget_configured:
            alerts.append(
                AdminAIGovernanceAlert(
                    severity="warning",
                    title="Monthly cost budget is not configured",
                    detail="Cost usage cannot be compared with an approved platform budget.",
                    recommendation="Set AI_GOVERNANCE_MONTHLY_COST_BUDGET_USD after finance approves the monthly AI budget.",
                )
            )
        elif cost_budget_usage is not None and cost_budget_usage >= 100:
            alerts.append(
                AdminAIGovernanceAlert(
                    severity="critical",
                    title="Monthly AI cost budget exceeded",
                    detail=f"Estimated usage is {self._format_percent_value(cost_budget_usage)} of the monthly cost budget.",
                    recommendation="Throttle non-critical generation workflows or raise the approved budget before expanding usage.",
                )
            )
        elif cost_budget_usage is not None and cost_budget_usage >= warning_threshold:
            alerts.append(
                AdminAIGovernanceAlert(
                    severity="warning",
                    title="Monthly AI cost budget nearing limit",
                    detail=f"Estimated usage is {self._format_percent_value(cost_budget_usage)} of the monthly cost budget.",
                    recommendation="Review high-volume courses and planned generation jobs before the next rollout.",
                )
            )

        if not token_budget_configured:
            alerts.append(
                AdminAIGovernanceAlert(
                    severity="warning",
                    title="Monthly token budget is not configured",
                    detail="Token volume has no configured guardrail.",
                    recommendation="Set AI_GOVERNANCE_MONTHLY_TOKEN_BUDGET to catch runaway prompt or embedding volume.",
                )
            )
        elif token_budget_usage is not None and token_budget_usage >= 100:
            alerts.append(
                AdminAIGovernanceAlert(
                    severity="critical",
                    title="Monthly AI token budget exceeded",
                    detail=f"Token usage is {self._format_percent_value(token_budget_usage)} of the monthly token budget.",
                    recommendation="Pause bulk indexing/generation and review usage drivers.",
                )
            )
        elif token_budget_usage is not None and token_budget_usage >= warning_threshold:
            alerts.append(
                AdminAIGovernanceAlert(
                    severity="warning",
                    title="Monthly AI token budget nearing limit",
                    detail=f"Token usage is {self._format_percent_value(token_budget_usage)} of the monthly token budget.",
                    recommendation="Audit recent prompt and embedding activity before approving more generation.",
                )
            )

        if failure_rate >= max(settings.ai_governance_failure_rate_blocked_percent, 0):
            alerts.append(
                AdminAIGovernanceAlert(
                    severity="critical",
                    title="AI failure rate is high",
                    detail=f"Current month failure rate is {self._format_percent_value(failure_rate)}.",
                    recommendation="Review provider status, failed prompt logs, and indexing worker health before broad rollout.",
                )
            )
        elif failure_rate >= max(settings.ai_governance_failure_rate_warning_percent, 0):
            alerts.append(
                AdminAIGovernanceAlert(
                    severity="warning",
                    title="AI failure rate needs review",
                    detail=f"Current month failure rate is {self._format_percent_value(failure_rate)}.",
                    recommendation="Use the failure audit filters to identify affected courses, users, or job types.",
                )
            )

        if index_usage["blocked"] > 0:
            alerts.append(
                AdminAIGovernanceAlert(
                    severity="critical",
                    title="Blocked indexing jobs require action",
                    detail=f"{index_usage['blocked']} indexing jobs are blocked this month.",
                    recommendation="Release jobs after publishing modules or fix failed prerequisites before learners rely on RAG.",
                )
            )
        elif index_usage["backlog"] >= max(settings.ai_governance_index_backlog_warning, 0):
            alerts.append(
                AdminAIGovernanceAlert(
                    severity="warning",
                    title="Indexing backlog is growing",
                    detail=f"{index_usage['backlog']} indexing jobs are queued or running.",
                    recommendation="Check worker concurrency and queue latency before publishing more materials.",
                )
            )

        return alerts

    def _build_governance_metrics(
        self,
        *,
        cost_usd: float,
        cost_budget: float | None,
        cost_budget_usage: float | None,
        total_tokens: int,
        token_budget: int | None,
        token_budget_usage: float | None,
        failure_rate: float,
        failures: int,
        total_events: int,
        index_usage: dict[str, int],
    ) -> list[AdminAIGovernanceMetric]:
        return [
            AdminAIGovernanceMetric(
                key="estimated_cost",
                label="Estimated cost",
                value=self._format_money(cost_usd),
                detail=(
                    f"{self._format_percent_value(cost_budget_usage)} of {self._format_money(cost_budget)}"
                    if cost_budget and cost_budget_usage is not None
                    else "Pricing or budget not fully configured"
                ),
                status=self._budget_status(cost_budget_usage, configured=cost_budget is not None and self._is_pricing_configured()),
            ),
            AdminAIGovernanceMetric(
                key="token_budget",
                label="Token budget",
                value=f"{total_tokens:,}",
                detail=(
                    f"{self._format_percent_value(token_budget_usage)} of {token_budget:,} tokens"
                    if token_budget and token_budget_usage is not None
                    else "Monthly token guardrail not configured"
                ),
                status=self._budget_status(token_budget_usage, configured=token_budget is not None),
            ),
            AdminAIGovernanceMetric(
                key="failure_rate",
                label="Failure rate",
                value=self._format_percent_value(failure_rate),
                detail=f"{failures:,} failures across {total_events:,} AI events",
                status=self._failure_rate_status(failure_rate),
            ),
            AdminAIGovernanceMetric(
                key="index_backlog",
                label="Index backlog",
                value=f"{index_usage['backlog']:,}",
                detail=(
                    f"{index_usage['queued']:,} queued, {index_usage['running']:,} running, "
                    f"{index_usage['blocked']:,} blocked"
                ),
                status=self._index_backlog_status(index_usage),
            ),
        ]

    def _overall_alert_status(self, alerts: list[AdminAIGovernanceAlert]) -> str:
        severities = {alert.severity for alert in alerts}
        if "critical" in severities:
            return "blocked"
        if "warning" in severities:
            return "warning"
        return "ready"

    def _overall_anomaly_status(self, items: list[AdminAITelemetryAnomalyInsight]) -> str:
        severities = {item.severity for item in items}
        if "critical" in severities:
            return "blocked"
        if "warning" in severities:
            return "warning"
        return "ready"

    def _trend_failures(self, points: list[AdminAITelemetryTrendPoint]) -> int:
        return sum(
            point.promptFailures + point.promptTimeouts + point.embeddingFailures + point.indexFailures
            for point in points
        )

    def _trend_events(self, points: list[AdminAITelemetryTrendPoint]) -> int:
        return sum(point.promptCalls + point.embeddingCalls + point.indexJobs for point in points)

    def _sum_trend(self, points: list[AdminAITelemetryTrendPoint], attr: str) -> int:
        return sum(int(getattr(point, attr) or 0) for point in points)

    def _weighted_trend_average(
        self,
        points: list[AdminAITelemetryTrendPoint],
        *,
        count_attr: str,
        value_attr: str,
    ) -> float | None:
        weighted_total = 0.0
        count_total = 0
        for point in points:
            count = int(getattr(point, count_attr) or 0)
            value = getattr(point, value_attr)
            if count <= 0 or value is None:
                continue
            weighted_total += count * float(value)
            count_total += count
        if count_total <= 0:
            return None
        return weighted_total / count_total

    def _trend_latency_severity(self, current: float | None, baseline: float | None) -> str | None:
        if current is None:
            return None
        if current >= 30_000:
            return "critical"
        if current >= 10_000:
            return "warning"
        if baseline and baseline > 0 and current >= max(baseline * 2, baseline + 2_000):
            return "warning"
        return None

    def _retrieval_latency_severity(self, current: float | None, baseline: float | None) -> str | None:
        if current is None:
            return None
        if current >= 15_000:
            return "critical"
        if current >= 5_000:
            return "warning"
        if baseline and baseline > 0 and current >= max(baseline * 2, baseline + 1_000):
            return "warning"
        return None

    def _relative_delta_percent(self, current: float | int | None, baseline: float | int | None) -> float | None:
        if current is None or baseline is None or baseline == 0:
            return None
        return ((float(current) - float(baseline)) / float(baseline)) * 100

    def _format_latency_value(self, value: float | None) -> str:
        if value is None:
            return "not available"
        if value >= 1000:
            return f"{round(value / 1000, 1)}s"
        return f"{round(value)}ms"

    def _provider_health_status(self, *, failure_rate: float, average_latency_ms: float | None) -> str:
        failure_status = self._failure_rate_status(failure_rate)
        latency_status = self._latency_status(average_latency_ms)
        if "blocked" in {failure_status, latency_status}:
            return "blocked"
        if "warning" in {failure_status, latency_status}:
            return "warning"
        return "ready"

    def _latency_status(self, average_latency_ms: float | None) -> str:
        if average_latency_ms is None:
            return "ready"
        if average_latency_ms >= 30_000:
            return "blocked"
        if average_latency_ms >= 10_000:
            return "warning"
        return "ready"

    def _provider_health_recommendation(
        self,
        *,
        status: str,
        failure_rate: float,
        average_latency_ms: float | None,
    ) -> str | None:
        if status == "ready":
            return None
        if failure_rate >= max(settings.ai_governance_failure_rate_warning_percent, 0):
            return "Review provider errors, quota, credentials, and failure audit filters for this workflow."
        if average_latency_ms is not None and average_latency_ms >= 10_000:
            return "Review slow traces, prompt size, retrieval scope, and provider timeout settings."
        return "Review provider health before expanding AI usage."

    def _overall_provider_health_status(
        self,
        *,
        items: list[AdminAIProviderHealthItem],
        anomalies: list[AdminAIProviderAnomaly],
    ) -> str:
        statuses = {item.status for item in items}
        severities = {anomaly.severity for anomaly in anomalies}
        if "blocked" in statuses or "critical" in severities:
            return "blocked"
        if "warning" in statuses or "warning" in severities:
            return "warning"
        return "ready"

    def _status_rank(self, value: str) -> int:
        return {"blocked": 0, "warning": 1, "ready": 2}.get(value, 3)

    def _severity_rank(self, value: str) -> int:
        return {"critical": 0, "warning": 1, "info": 2}.get(value, 3)

    def _budget_status(self, usage_percent: float | None, *, configured: bool) -> str:
        if not configured:
            return "warning"
        if usage_percent is not None and usage_percent >= 100:
            return "blocked"
        if usage_percent is not None and usage_percent >= max(settings.ai_governance_budget_warning_percent, 0):
            return "warning"
        return "ready"

    def _failure_rate_status(self, failure_rate: float) -> str:
        if failure_rate >= max(settings.ai_governance_failure_rate_blocked_percent, 0):
            return "blocked"
        if failure_rate >= max(settings.ai_governance_failure_rate_warning_percent, 0):
            return "warning"
        return "ready"

    def _index_backlog_status(self, index_usage: dict[str, int]) -> str:
        if index_usage["blocked"] > 0:
            return "blocked"
        if index_usage["backlog"] >= max(settings.ai_governance_index_backlog_warning, 0):
            return "warning"
        return "ready"

    def _is_pricing_configured(self) -> bool:
        return any(
            value > 0
            for value in (
                settings.ai_prompt_input_cost_per_1m_tokens,
                settings.ai_prompt_output_cost_per_1m_tokens,
                settings.ai_embedding_cost_per_1m_tokens,
            )
        )

    def _build_empty_trend_points(self, start_day: date, days: int) -> dict[str, dict[str, object]]:
        return {
            (start_day + timedelta(days=index)).isoformat(): {
                "date": (start_day + timedelta(days=index)).isoformat(),
                "promptCalls": 0,
                "promptFailures": 0,
                "promptTimeouts": 0,
                "promptTotalTokens": 0,
                "averagePromptLatencyMs": None,
                "retrievals": 0,
                "averageRetrievalLatencyMs": None,
                "embeddingCalls": 0,
                "embeddingFailures": 0,
                "embeddingTotalTokens": 0,
                "averageEmbeddingLatencyMs": None,
                "indexJobs": 0,
                "indexFailures": 0,
            }
            for index in range(days)
        }

    def _build_chat_provider_config_item(self) -> AdminAIProviderConfigItem:
        if not hasattr(self.session, "get"):
            return AdminAIProviderConfigItem(
                key="chat_provider",
                label="Chat provider",
                status="blocked",
                detail="Database-backed model catalog unavailable",
                recommendation="Configure an AI provider credential in the administrator model settings.",
            )
        catalog = AIModelCatalogService(self.session)
        catalog.ensure_seeded()
        repo = AIModelCatalogRepository(self.session)
        defaults = repo.get_defaults()
        model = repo.get_model(defaults.default_chat_model_id) if defaults and defaults.default_chat_model_id else None
        if model is None:
            return AdminAIProviderConfigItem(
                key="chat_provider",
                label="Chat provider",
                status="blocked",
                detail="No default chat model",
                recommendation="Set a default chat model in AI provider settings.",
            )
        availability = catalog.availability_for_model(model)
        provider = repo.get_provider(model.provider_key)
        if not availability.available:
            return AdminAIProviderConfigItem(
                key="chat_provider",
                label="Chat provider",
                status="blocked",
                detail=f"{model.provider_key} / {model.model_name}",
                recommendation=availability.reason or "Configure a supported AI provider credential.",
            )
        return AdminAIProviderConfigItem(
            key="chat_provider",
            label="Chat provider",
            status="ready",
            detail=f"{provider.display_name if provider else model.provider_key} / {model.model_name}",
        )

    def _build_embedding_provider_config_item(self) -> AdminAIProviderConfigItem:
        if hasattr(self.session, "get"):
            catalog = AIModelCatalogService(self.session)
            catalog.ensure_seeded()
            repo = AIModelCatalogRepository(self.session)
            defaults = repo.get_defaults()
            chat_model = (
                repo.get_model(defaults.default_chat_model_id)
                if defaults and defaults.default_chat_model_id
                else None
            )
            embedding_model = (
                repo.get_model(chat_model.paired_embedding_model_id)
                if chat_model and chat_model.paired_embedding_model_id
                else None
            )
            if embedding_model is None:
                return AdminAIProviderConfigItem(
                    key="embedding_provider",
                    label="Embedding provider",
                    status="blocked",
                    detail="No embedding model paired with the default chat model",
                    recommendation=(
                        "Choose a default chat model with a supported embedding pair."
                    ),
                )
            availability = catalog.availability_for_model(embedding_model)
            provider = repo.get_provider(embedding_model.provider_key)
            return AdminAIProviderConfigItem(
                key="embedding_provider",
                label="Embedding provider",
                status="ready" if availability.available else "blocked",
                detail=(
                    f"{provider.display_name if provider else embedding_model.provider_key}"
                    f" / {embedding_model.model_name}"
                    f" / {embedding_model.embedding_dimension}d"
                ),
                recommendation=(
                    None
                    if availability.available
                    else availability.reason
                    or "Configure the paired embedding provider credential."
                ),
            )

        return AdminAIProviderConfigItem(
            key="embedding_provider",
            label="Embedding provider",
            status="blocked",
            detail="Model catalog unavailable",
            recommendation="Read embedding configuration from a database-backed model catalog session.",
        )

    def _build_retrieval_config_item(self) -> AdminAIProviderConfigItem:
        if settings.ai_retrieval_top_k <= 0:
            return AdminAIProviderConfigItem(
                key="retrieval_policy",
                label="Retrieval policy",
                status="blocked",
                detail=f"topK={settings.ai_retrieval_top_k}, minScore={settings.ai_retrieval_min_score}",
                recommendation="Set AI_RETRIEVAL_TOP_K to at least 1.",
            )
        if not 0 <= settings.ai_retrieval_min_score <= 1:
            return AdminAIProviderConfigItem(
                key="retrieval_policy",
                label="Retrieval policy",
                status="warning",
                detail=f"topK={settings.ai_retrieval_top_k}, minScore={settings.ai_retrieval_min_score}",
                recommendation="Use a retrieval min score between 0 and 1 for predictable filtering.",
            )
        return AdminAIProviderConfigItem(
            key="retrieval_policy",
            label="Retrieval policy",
            status="ready",
            detail=f"topK={settings.ai_retrieval_top_k}, minScore={settings.ai_retrieval_min_score}",
        )

    def _build_indexing_config_item(self) -> AdminAIProviderConfigItem:
        if not settings.celery_broker_url or not settings.celery_result_backend:
            return AdminAIProviderConfigItem(
                key="indexing_worker",
                label="Indexing worker",
                status="blocked",
                detail=f"queue={settings.learning_material_ai_queue}",
                recommendation="Configure Celery broker and result backend before material indexing.",
            )
        if settings.ai_index_job_max_auto_retries < 0:
            return AdminAIProviderConfigItem(
                key="indexing_worker",
                label="Indexing worker",
                status="warning",
                detail=f"queue={settings.learning_material_ai_queue}, retries={settings.ai_index_job_max_auto_retries}",
                recommendation="Use a non-negative retry count for indexing jobs.",
            )
        return AdminAIProviderConfigItem(
            key="indexing_worker",
            label="Indexing worker",
            status="ready",
            detail=f"queue={settings.learning_material_ai_queue}, retries={settings.ai_index_job_max_auto_retries}",
        )

    def _build_checkpoint_config_item(self) -> AdminAIProviderConfigItem:
        if not settings.langgraph_checkpoint_enabled:
            return AdminAIProviderConfigItem(
                key="workflow_checkpointing",
                label="Workflow checkpointing",
                status="warning",
                detail="disabled",
                recommendation="Enable LangGraph checkpointing for resumable AI workflows.",
            )
        if not settings.langgraph_checkpoint_redis_url:
            return AdminAIProviderConfigItem(
                key="workflow_checkpointing",
                label="Workflow checkpointing",
                status="blocked",
                detail="enabled without Redis URL",
                recommendation="Configure LANGGRAPH_CHECKPOINT_REDIS_URL.",
            )
        return AdminAIProviderConfigItem(
            key="workflow_checkpointing",
            label="Workflow checkpointing",
            status="ready",
            detail=f"enabled / prefix={settings.langgraph_checkpoint_key_prefix}",
        )

    def _build_storage_config_item(self) -> AdminAIProviderConfigItem:
        provider = settings.object_storage_provider.strip().lower()
        if provider == "minio":
            if not settings.minio_bucket or settings.minio_signed_url_expires_seconds <= 0:
                return AdminAIProviderConfigItem(
                    key="object_storage",
                    label="Object storage",
                    status="blocked",
                    detail=f"minio / bucket={settings.minio_bucket or 'missing'}",
                    recommendation="Configure MinIO bucket and positive signed URL expiry.",
                )
            return AdminAIProviderConfigItem(
                key="object_storage",
                label="Object storage",
                status="ready",
                detail=f"minio / bucket={settings.minio_bucket} / signedUrl={settings.minio_signed_url_expires_seconds}s",
            )
        return AdminAIProviderConfigItem(
            key="object_storage",
            label="Object storage",
            status="warning",
            detail=f"{settings.object_storage_provider} / local profile assets",
            recommendation="Use MinIO or managed object storage for shared production deployments.",
        )

    def _build_security_config_item(self) -> AdminAIProviderConfigItem:
        missing = []
        if not settings.internal_api_token:
            missing.append("internal API token")
        if not settings.public_id_secret:
            missing.append("public ID secret")
        if missing:
            return AdminAIProviderConfigItem(
                key="service_security",
                label="Service security",
                status="blocked",
                detail=", ".join(missing),
                recommendation="Configure all service boundary secrets before production deployment.",
            )
        return AdminAIProviderConfigItem(
            key="service_security",
            label="Service security",
            status="ready",
            detail="service boundary secrets configured",
        )

    def _overall_config_status(self, items: list[AdminAIProviderConfigItem]) -> str:
        statuses = {item.status for item in items}
        if "blocked" in statuses:
            return "blocked"
        if "warning" in statuses:
            return "warning"
        return "ready"

    def _merge_prompt_trends(self, points: dict[str, dict[str, object]], *, start_at: datetime) -> None:
        day_column = func.date(AIPromptLog.created_at)
        stmt = (
            select(
                day_column,
                func.count(AIPromptLog.prompt_log_id),
                func.coalesce(func.sum(case((AIPromptLog.status == AIPromptStatus.FAILED, 1), else_=0)), 0),
                func.coalesce(func.sum(case((AIPromptLog.status == AIPromptStatus.TIMEOUT, 1), else_=0)), 0),
                func.coalesce(func.sum(AIPromptLog.total_tokens), 0),
                func.avg(AIPromptLog.latency_ms),
            )
            .where(AIPromptLog.created_at >= start_at)
            .group_by(day_column)
        )
        for day, total, failed, timeout, total_tokens, avg_latency in self.session.execute(stmt).all():
            point = points.get(self._format_date_key(day))
            if point is None:
                continue
            point["promptCalls"] = int(total or 0)
            point["promptFailures"] = int(failed or 0)
            point["promptTimeouts"] = int(timeout or 0)
            point["promptTotalTokens"] = int(total_tokens or 0)
            point["averagePromptLatencyMs"] = self._format_float(avg_latency)

    def _merge_retrieval_trends(self, points: dict[str, dict[str, object]], *, start_at: datetime) -> None:
        day_column = func.date(AIRetrievalLog.created_at)
        stmt = (
            select(
                day_column,
                func.count(AIRetrievalLog.retrieval_id),
                func.avg(AIRetrievalLog.latency_ms),
            )
            .where(AIRetrievalLog.created_at >= start_at)
            .group_by(day_column)
        )
        for day, total, avg_latency in self.session.execute(stmt).all():
            point = points.get(self._format_date_key(day))
            if point is None:
                continue
            point["retrievals"] = int(total or 0)
            point["averageRetrievalLatencyMs"] = self._format_float(avg_latency)

    def _merge_embedding_trends(self, points: dict[str, dict[str, object]], *, start_at: datetime) -> None:
        day_column = func.date(AIEmbeddingLog.created_at)
        stmt = (
            select(
                day_column,
                func.count(AIEmbeddingLog.embedding_log_id),
                func.coalesce(func.sum(case((AIEmbeddingLog.status == AIPromptStatus.FAILED, 1), else_=0)), 0),
                func.coalesce(func.sum(AIEmbeddingLog.provider_total_tokens), 0),
                func.avg(AIEmbeddingLog.latency_ms),
            )
            .where(AIEmbeddingLog.created_at >= start_at)
            .group_by(day_column)
        )
        for day, total, failed, total_tokens, avg_latency in self.session.execute(stmt).all():
            point = points.get(self._format_date_key(day))
            if point is None:
                continue
            point["embeddingCalls"] = int(total or 0)
            point["embeddingFailures"] = int(failed or 0)
            point["embeddingTotalTokens"] = int(total_tokens or 0)
            point["averageEmbeddingLatencyMs"] = self._format_float(avg_latency)

    def _merge_index_job_trends(self, points: dict[str, dict[str, object]], *, start_at: datetime) -> None:
        day_column = func.date(AIIndexJob.created_at)
        stmt = (
            select(
                day_column,
                func.count(AIIndexJob.job_id),
                func.coalesce(func.sum(case((AIIndexJob.status == AIJobStatus.FAILED, 1), else_=0)), 0),
            )
            .where(AIIndexJob.created_at >= start_at)
            .group_by(day_column)
        )
        for day, total, failed in self.session.execute(stmt).all():
            point = points.get(self._format_date_key(day))
            if point is None:
                continue
            point["indexJobs"] = int(total or 0)
            point["indexFailures"] = int(failed or 0)

    def _list_prompt_failures(
        self,
        *,
        limit: int,
        status: str | None,
        user_id: int | None,
        since: datetime | None,
        until: datetime | None,
    ) -> list[AdminAITelemetryFailureItem]:
        stmt = (
            select(AIPromptLog)
            .where(AIPromptLog.status.in_([AIPromptStatus.FAILED, AIPromptStatus.TIMEOUT]))
            .order_by(AIPromptLog.created_at.desc(), AIPromptLog.prompt_log_id.desc())
            .limit(limit)
        )
        if status:
            prompt_status = self._to_prompt_status(status)
            if prompt_status is None:
                return []
            stmt = stmt.where(AIPromptLog.status == prompt_status)
        if user_id is not None:
            stmt = stmt.where(AIPromptLog.user_id == user_id)
        stmt = self._apply_datetime_range(stmt, AIPromptLog.created_at, since=since, until=until)
        return [
            AdminAITelemetryFailureItem(
                kind="prompt",
                id=log.prompt_log_id,
                status=self._status_value(log.status),
                occurredAt=self._format_datetime(log.created_at),
                userId=log.user_id,
                sessionId=log.session_id,
                messageId=log.message_id,
                modelName=log.model_name,
                callType=self._status_value(log.call_type),
                latencyMs=log.latency_ms,
                totalTokens=log.total_tokens,
                errorSummary=self._sanitize_error_message(log.error_message),
            )
            for log in self.session.scalars(stmt)
        ]

    def _list_embedding_failures(
        self,
        *,
        limit: int,
        status: str | None,
        user_id: int | None,
        course_id: int | None,
        module_id: int | None,
        since: datetime | None,
        until: datetime | None,
    ) -> list[AdminAITelemetryFailureItem]:
        stmt = (
            select(AIEmbeddingLog)
            .where(AIEmbeddingLog.status.in_([AIPromptStatus.FAILED, AIPromptStatus.TIMEOUT]))
            .order_by(AIEmbeddingLog.created_at.desc(), AIEmbeddingLog.embedding_log_id.desc())
            .limit(limit)
        )
        if status:
            prompt_status = self._to_prompt_status(status)
            if prompt_status is None:
                return []
            stmt = stmt.where(AIEmbeddingLog.status == prompt_status)
        if user_id is not None:
            stmt = stmt.where(AIEmbeddingLog.user_id == user_id)
        if course_id is not None:
            stmt = stmt.where(AIEmbeddingLog.course_id == course_id)
        if module_id is not None:
            stmt = stmt.where(AIEmbeddingLog.module_id == module_id)
        stmt = self._apply_datetime_range(stmt, AIEmbeddingLog.created_at, since=since, until=until)
        return [
            AdminAITelemetryFailureItem(
                kind="embedding",
                id=log.embedding_log_id,
                status=self._status_value(log.status),
                occurredAt=self._format_datetime(log.created_at),
                userId=log.user_id,
                courseId=log.course_id,
                moduleId=log.module_id,
                materialId=log.material_id,
                modelName=log.model_name,
                callType=log.task_type,
                latencyMs=log.latency_ms,
                totalTokens=log.provider_total_tokens,
                errorSummary=self._sanitize_error_message(log.error_message),
            )
            for log in self.session.scalars(stmt)
        ]

    def _list_index_failures(
        self,
        *,
        limit: int,
        status: str | None,
        course_id: int | None,
        module_id: int | None,
        since: datetime | None,
        until: datetime | None,
    ) -> list[AdminAITelemetryFailureItem]:
        occurred_at = func.coalesce(AIIndexJob.finished_at, AIIndexJob.started_at, AIIndexJob.created_at)
        stmt = (
            select(AIIndexJob)
            .where(AIIndexJob.status == AIJobStatus.FAILED)
            .order_by(desc(AIIndexJob.finished_at).nulls_last(), AIIndexJob.created_at.desc(), AIIndexJob.job_id.desc())
            .limit(limit)
        )
        if status:
            job_status = self._to_job_status(status)
            if job_status is None:
                return []
            stmt = stmt.where(AIIndexJob.status == job_status)
        if course_id is not None:
            stmt = stmt.where(AIIndexJob.course_id == course_id)
        if module_id is not None:
            stmt = stmt.where(AIIndexJob.module_id == module_id)
        stmt = self._apply_datetime_range(stmt, occurred_at, since=since, until=until)
        return [
            AdminAITelemetryFailureItem(
                kind="index_job",
                id=job.job_id,
                status=self._status_value(job.status),
                occurredAt=self._format_datetime(job.finished_at or job.started_at or job.created_at),
                courseId=job.course_id,
                moduleId=job.module_id,
                materialId=job.material_id,
                callType=self._status_value(job.job_type),
                attemptCount=job.attempt_count,
                errorSummary=self._sanitize_error_message(job.error_message),
            )
            for job in self.session.scalars(stmt)
        ]

    def _normalize_kind(self, value: str | None) -> str | None:
        normalized = value.strip().lower() if value else None
        return normalized if normalized in {"prompt", "embedding", "index_job"} else None

    def _normalize_status_filter(self, value: str | None) -> str | None:
        normalized = value.strip().lower() if value else None
        return normalized if normalized in {"failed", "timeout"} else None

    def _to_prompt_status(self, value: str) -> AIPromptStatus | None:
        if value == AIPromptStatus.FAILED.value:
            return AIPromptStatus.FAILED
        if value == AIPromptStatus.TIMEOUT.value:
            return AIPromptStatus.TIMEOUT
        return None

    def _to_job_status(self, value: str) -> AIJobStatus | None:
        if value == AIJobStatus.FAILED.value:
            return AIJobStatus.FAILED
        return None

    def _apply_datetime_range(self, stmt, column, *, since: datetime | None, until: datetime | None):
        if since is not None:
            stmt = stmt.where(column >= self._to_naive_utc(since))
        if until is not None:
            stmt = stmt.where(column <= self._to_naive_utc(until))
        return stmt

    def _to_naive_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def _format_datetime(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()

    def _format_date_key(self, value: object) -> str:
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return str(value)[:10]

    def _format_float(self, value: object) -> float | None:
        if value is None:
            return None
        return round(float(value), 2)

    def _percentage(self, numerator: float | int, denominator: float | int | None) -> float:
        if not denominator:
            return 0.0
        return (float(numerator) / float(denominator)) * 100

    def _optional_positive_float(self, value: float) -> float | None:
        return float(value) if value > 0 else None

    def _optional_positive_int(self, value: int) -> int | None:
        return int(value) if value > 0 else None

    def _format_percent_value(self, value: float | None) -> str:
        if value is None:
            return "not configured"
        return f"{round(value, 1)}%"

    def _format_money(self, value: float | None) -> str:
        if value is None:
            return "not configured"
        return f"${value:.2f}"

    def _status_value(self, status: object) -> str:
        value = getattr(status, "value", status)
        return str(value)

    def _sanitize_error_message(self, value: str | None) -> str | None:
        if value is None:
            return None
        sanitized = " ".join(value.split())
        for pattern in _SECRET_PATTERNS:
            sanitized = pattern.sub(lambda match: f"{match.group(1)}{match.group(2) if match.lastindex and match.lastindex >= 2 else ''}[redacted]", sanitized)
        if len(sanitized) > 300:
            return f"{sanitized[:297]}..."
        return sanitized

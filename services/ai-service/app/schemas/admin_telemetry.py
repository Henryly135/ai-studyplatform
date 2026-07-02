from pydantic import BaseModel


class TelemetryCountByStatus(BaseModel):
    status: str
    count: int


class PromptCallTelemetry(BaseModel):
    total: int
    success: int
    failed: int
    timeout: int
    totalTokens: int
    averageLatencyMs: float | None = None
    latestAt: str | None = None


class RetrievalTelemetry(BaseModel):
    total: int
    averageLatencyMs: float | None = None
    latestAt: str | None = None


class EmbeddingTelemetry(BaseModel):
    total: int
    success: int
    failed: int
    totalTokens: int
    averageLatencyMs: float | None = None
    latestAt: str | None = None


class IndexJobTelemetry(BaseModel):
    total: int
    queued: int
    running: int
    blocked: int
    success: int
    failed: int
    cancelled: int
    superseded: int
    byStatus: list[TelemetryCountByStatus]
    latestFailureAt: str | None = None


class ChatTelemetry(BaseModel):
    sessions: int
    messages: int
    activeUsers: int
    latestActivityAt: str | None = None


class AdminAITelemetrySummary(BaseModel):
    generatedAt: str
    promptCalls: PromptCallTelemetry
    retrievals: RetrievalTelemetry
    embeddings: EmbeddingTelemetry
    indexJobs: IndexJobTelemetry
    chat: ChatTelemetry


class AdminAITelemetryTrendPoint(BaseModel):
    date: str
    promptCalls: int
    promptFailures: int
    promptTimeouts: int
    promptTotalTokens: int
    averagePromptLatencyMs: float | None = None
    retrievals: int
    averageRetrievalLatencyMs: float | None = None
    embeddingCalls: int
    embeddingFailures: int
    embeddingTotalTokens: int
    averageEmbeddingLatencyMs: float | None = None
    indexJobs: int
    indexFailures: int


class AdminAITelemetryTrendResponse(BaseModel):
    generatedAt: str
    days: int
    items: list[AdminAITelemetryTrendPoint]


class AdminAITelemetryAnomalyInsight(BaseModel):
    key: str
    severity: str
    category: str
    title: str
    detail: str
    recommendation: str
    metricLabel: str
    currentValue: str
    baselineValue: str | None = None
    deltaPercent: float | None = None


class AdminAITelemetryAnomalyResponse(BaseModel):
    generatedAt: str
    days: int
    baselineDays: int
    windowStart: str | None = None
    windowEnd: str | None = None
    baselineStart: str | None = None
    baselineEnd: str | None = None
    overallStatus: str
    items: list[AdminAITelemetryAnomalyInsight]


class AdminAIProviderConfigItem(BaseModel):
    key: str
    label: str
    status: str
    detail: str
    recommendation: str | None = None


class AdminAIProviderConfigResponse(BaseModel):
    generatedAt: str
    overallStatus: str
    provider: str
    model: str
    embeddingProvider: str
    embeddingModel: str
    storageProvider: str
    items: list[AdminAIProviderConfigItem]


class AdminAIProviderHealthItem(BaseModel):
    key: str
    provider: str
    modelName: str
    callType: str
    totalCalls: int
    success: int
    failed: int
    timeout: int
    successRatePercent: float
    failureRatePercent: float
    averageLatencyMs: float | None = None
    latestAt: str | None = None
    status: str
    recommendation: str | None = None


class AdminAIProviderAnomaly(BaseModel):
    key: str
    severity: str
    title: str
    detail: str
    recommendation: str


class AdminAIProviderHealthResponse(BaseModel):
    generatedAt: str
    windowStart: str
    windowEnd: str
    days: int
    overallStatus: str
    provider: str
    totalCalls: int
    successRatePercent: float
    averageLatencyMs: float | None = None
    items: list[AdminAIProviderHealthItem]
    anomalies: list[AdminAIProviderAnomaly]


class AdminAIGovernanceMetric(BaseModel):
    key: str
    label: str
    value: str
    detail: str
    status: str


class AdminAIGovernanceAlert(BaseModel):
    severity: str
    title: str
    detail: str
    recommendation: str


class AdminAIGovernanceResponse(BaseModel):
    generatedAt: str
    periodStart: str
    periodEnd: str
    overallStatus: str
    estimatedCostUsd: float
    monthlyCostBudgetUsd: float | None = None
    costBudgetUsagePercent: float | None = None
    monthlyTokenBudget: int | None = None
    tokenBudgetUsagePercent: float | None = None
    promptTokens: int
    embeddingTokens: int
    totalTokens: int
    promptCalls: int
    embeddingCalls: int
    indexJobs: int
    failures: int
    failureRatePercent: float
    alerts: list[AdminAIGovernanceAlert]
    metrics: list[AdminAIGovernanceMetric]


class AdminAITelemetryFailureItem(BaseModel):
    kind: str
    id: int
    status: str
    occurredAt: str | None = None
    userId: int | None = None
    sessionId: int | None = None
    messageId: int | None = None
    courseId: int | None = None
    moduleId: int | None = None
    materialId: int | None = None
    modelName: str | None = None
    callType: str | None = None
    latencyMs: int | None = None
    totalTokens: int | None = None
    attemptCount: int | None = None
    errorSummary: str | None = None


class AdminAITelemetryFailuresResponse(BaseModel):
    generatedAt: str
    items: list[AdminAITelemetryFailureItem]

import type {
  APIErrorResponse,
  AdminAiIndexJobRetryResponse,
  AdminAiGovernance,
  AdminAiProviderConfig,
  AdminAiProviderHealth,
  AdminAiTelemetryAnomalies,
  AdminAiTelemetryFailureFilters,
  AdminAiTelemetryFailuresResponse,
  AdminAiTelemetrySummary,
  AdminAiTelemetryTrendResponse,
  AiModelCatalog,
  AiRuntimeHealth,
  ChatSessionDetail,
  ChatSessionSummary,
  ChatSendPayload,
  StableChatSendPayload,
  ChatSuccessResponse,
} from "../types/chat";
import {
  buildAuthHeaders,
  getStoredAccessToken,
  handleAuthenticationFailureFromResponse,
  parseJsonText,
} from "./api";

const CHAT_API_URL = "/api/ai/chat";
const CHAT_SESSIONS_API_URL = "/api/ai/chat/sessions";
const AI_MODELS_API_URL = "/api/ai/models";
const AI_RUNTIME_HEALTH_URL = "/api/ai/demo/health";
const ADMIN_AI_TELEMETRY_SUMMARY_URL = "/api/ai/admin/telemetry/summary";
const ADMIN_AI_TELEMETRY_TRENDS_URL = "/api/ai/admin/telemetry/trends";
const ADMIN_AI_TELEMETRY_ANOMALIES_URL = "/api/ai/admin/telemetry/anomalies";
const ADMIN_AI_PROVIDER_CONFIG_URL = "/api/ai/admin/telemetry/provider-config";
const ADMIN_AI_PROVIDER_HEALTH_URL = "/api/ai/admin/telemetry/provider-health";
const ADMIN_AI_GOVERNANCE_URL = "/api/ai/admin/telemetry/governance";
const ADMIN_AI_TELEMETRY_FAILURES_URL = "/api/ai/admin/telemetry/failures";
const ADMIN_AI_INDEX_JOB_RETRY_URL = "/api/ai/admin/telemetry/index-jobs";
const SUPPORTED_AI_PROVIDERS = new Set(["gemini", "glm", "openrouter"]);

function getAccessToken() {
  return getStoredAccessToken();
}

export function createChatRequestId() {
  if (typeof globalThis.crypto?.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }
  return `chat-${Date.now()}-${Math.random().toString(36).slice(2, 14)}`;
}

async function parseResponse<T>(response: Response): Promise<T> {
  const responseText = await response.text();
  const data: unknown = parseJsonText(responseText);
  handleAuthenticationFailureFromResponse(response.status, data);

  if (data === null) {
    if (!response.ok) {
      if (response.status >= 500) {
        throw new Error("智能服务暂时不可用，请稍后重试。");
      }
      throw new Error("请求失败。");
    }

    throw new Error("The server returned an unexpected response.");
  }

  if (!response.ok) {
    const errorPayload = data as APIErrorResponse;
    const detailPayload =
      errorPayload.detail && typeof errorPayload.detail === "object"
        ? (errorPayload.detail as { code?: string; message?: string })
        : null;
    throw new Error(
      errorPayload.error?.message
        ? errorPayload.error.message
        : detailPayload?.message
          ? detailPayload.message
          : typeof errorPayload.detail === "string"
          ? errorPayload.detail
          : "请求失败。"
    );
  }

  return data as T;
}

function asRecord(payload: unknown): Record<string, unknown> {
  return payload && typeof payload === "object" ? (payload as Record<string, unknown>) : {};
}

function toFiniteNumber(value: unknown, fallback: number, minimum?: number, maximum?: number) {
  const parsed =
    typeof value === "number"
      ? value
      : typeof value === "string" && value.trim()
        ? Number(value)
        : fallback;

  if (!Number.isFinite(parsed)) {
    return fallback;
  }

  const withMinimum = minimum === undefined ? parsed : Math.max(minimum, parsed);
  return maximum === undefined ? withMinimum : Math.min(maximum, withMinimum);
}

function toNonNegativeNumber(value: unknown, fallback = 0) {
  return toFiniteNumber(value, fallback, 0);
}

function toPercentNumber(value: unknown, fallback = 0) {
  return toFiniteNumber(value, fallback, 0, 100);
}

function toNullableNonNegativeNumber(value: unknown) {
  if (value === null || value === undefined) {
    return null;
  }

  const parsed =
    typeof value === "number"
      ? value
      : typeof value === "string" && value.trim()
        ? Number(value)
        : Number.NaN;
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
}

function toNullableFiniteNumber(value: unknown) {
  if (value === null || value === undefined) {
    return null;
  }

  const parsed =
    typeof value === "number"
      ? value
      : typeof value === "string" && value.trim()
        ? Number(value)
        : Number.NaN;
  return Number.isFinite(parsed) ? parsed : null;
}

function toNullableString(value: unknown) {
  return value === null || value === undefined ? null : String(value);
}

function toStringList(value: unknown) {
  if (Array.isArray(value)) {
    return value.map((item) => String(item));
  }
  if (value && typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .filter(([, enabled]) => toBoolean(enabled))
      .map(([key]) => key);
  }
  return [];
}

function toBoolean(value: unknown, fallback = false) {
  if (typeof value === "boolean") {
    return value;
  }

  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (["true", "1", "yes"].includes(normalized)) {
      return true;
    }
    if (["false", "0", "no"].includes(normalized)) {
      return false;
    }
  }

  return fallback;
}

function toNullableBoolean(value: unknown) {
  if (value === null || value === undefined) {
    return null;
  }

  if (typeof value === "boolean") {
    return value;
  }

  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (["true", "1", "yes"].includes(normalized)) {
      return true;
    }
    if (["false", "0", "no"].includes(normalized)) {
      return false;
    }
  }

  return null;
}

function normalizeIndexCoverage(value: unknown) {
  const parsed = toNullableFiniteNumber(value);
  if (parsed === null) {
    return null;
  }

  const ratio = parsed > 1 ? parsed / 100 : parsed;
  return Math.min(1, Math.max(0, ratio));
}

function isSupportedAiProvider(provider: string) {
  return SUPPORTED_AI_PROVIDERS.has(provider.trim().toLowerCase());
}

function getField(data: Record<string, unknown>, camelKey: string, snakeKey?: string) {
  return data[camelKey] ?? (snakeKey ? data[snakeKey] : undefined);
}

function normalizeAiModelCatalogModel(
  payload: unknown,
  fallbackProvider = ""
): AiModelCatalog["providers"][number]["models"][number] {
  const data = asRecord(payload);
  const provider = String(data.provider ?? fallbackProvider);
  const modelId = String(getField(data, "modelId", "model_id") ?? data.id ?? data.name ?? "");
  const unavailableReason = toNullableString(
    getField(data, "unavailableReason", "unavailable_reason") ?? data.reason
  );
  const pairedEmbeddingModel = asRecord(
    getField(data, "pairedEmbeddingModel", "paired_embedding_model")
  );
  const pairedEmbeddingModelId = toNullableString(
    getField(data, "pairedEmbeddingModelId", "paired_embedding_model_id") ??
      getField(data, "embeddingModelId", "embedding_model_id") ??
      getField(pairedEmbeddingModel, "modelId", "model_id") ??
      pairedEmbeddingModel.id
  );
  const pairedEmbeddingModelName = toNullableString(
    getField(data, "pairedEmbeddingModelName", "paired_embedding_model_name") ??
      getField(pairedEmbeddingModel, "displayName", "display_name") ??
      pairedEmbeddingModel.name
  );
  const embeddingDimension = toNullableNonNegativeNumber(
    getField(data, "embeddingDimension", "embedding_dimension") ??
      getField(pairedEmbeddingModel, "outputDimension", "output_dimension") ??
      pairedEmbeddingModel.dimension
  );

  return {
    modelId,
    provider,
    name: String(data.name ?? getField(data, "displayName", "display_name") ?? data.modelName ?? modelId),
    description: toNullableString(data.description),
    available: data.available === undefined ? !unavailableReason : toBoolean(data.available),
    unavailableReason,
    backendSupported: toBoolean(getField(data, "backendSupported", "backend_supported"), true),
    displayOnly: toBoolean(getField(data, "displayOnly", "display_only")),
    isDefault: toBoolean(getField(data, "isDefaultChat", "is_default_chat") ?? getField(data, "isDefault", "is_default")),
    capabilities: toStringList(data.capabilities),
    pairedEmbeddingModelId,
    pairedEmbeddingModelName,
    embeddingDimension,
    ragReady: toNullableBoolean(
      getField(data, "ragReady", "rag_ready") ??
        getField(pairedEmbeddingModel, "ragReady", "rag_ready")
    ),
    indexCoverage: normalizeIndexCoverage(
      getField(data, "indexCoverage", "index_coverage") ??
        getField(pairedEmbeddingModel, "indexCoverage", "index_coverage")
    ),
    indexStatus: toNullableString(
      getField(data, "indexStatus", "index_status") ??
        getField(pairedEmbeddingModel, "indexStatus", "index_status")
    ),
  };
}

function normalizeAiModelProvider(payload: unknown): AiModelCatalog["providers"][number] {
  const data = asRecord(payload);
  const provider = String(data.provider ?? data.id ?? "");

  return {
    provider,
    label: String(data.label ?? data.name ?? provider),
    backendSupported: toBoolean(getField(data, "backendSupported", "backend_supported"), true),
    configured: toBoolean(data.configured ?? getField(data, "hasCredential", "has_credential")),
    models: Array.isArray(data.models)
      ? data.models.map((model) => normalizeAiModelCatalogModel(model, provider))
      : [],
  };
}

function normalizeAiModelCatalog(payload: unknown): AiModelCatalog {
  const data = asRecord(payload);
  const providers = Array.isArray(data.providers)
    ? data.providers
        .map(normalizeAiModelProvider)
        .filter((provider) => isSupportedAiProvider(provider.provider))
    : [];
  const rawModels = Array.isArray(data.items) ? data.items : Array.isArray(data.models) ? data.models : [];

  if (providers.length === 0 && rawModels.length > 0) {
    const groupedProviders = new Map<string, AiModelCatalog["providers"][number]>();
    rawModels
      .map((payload) => {
        const data = asRecord(payload);
        const model = normalizeAiModelCatalogModel(payload);
        const configuredValue =
          data.configured ?? getField(data, "hasCredential", "has_credential");

        return {
          model,
          providerLabel: String(
            getField(data, "providerLabel", "provider_label") ??
              data.providerName ??
              model.provider
          ),
          configured:
            configuredValue === undefined
              ? model.available
              : toBoolean(configuredValue),
        };
      })
      .filter(({ model }) => isSupportedAiProvider(model.provider))
      .forEach(({ model, providerLabel, configured }) => {
        const providerKey = model.provider || "default";
        const currentProvider = groupedProviders.get(providerKey);
        if (currentProvider) {
          currentProvider.models.push(model);
          currentProvider.configured = currentProvider.configured || configured;
          currentProvider.backendSupported = currentProvider.backendSupported || model.backendSupported;
          if (currentProvider.label === providerKey && providerLabel !== providerKey) {
            currentProvider.label = providerLabel;
          }
        } else {
          groupedProviders.set(providerKey, {
            provider: providerKey,
            label: providerLabel,
            backendSupported: model.backendSupported,
            configured,
            models: [model],
          });
        }
      });
    providers.push(...groupedProviders.values());
  }

  const knownModelIds = new Set(
    providers.flatMap((provider) => provider.models.map((model) => model.modelId))
  );
  const defaultModelId = toNullableString(
    getField(data, "defaultChatModelId", "default_chat_model_id") ??
      getField(data, "defaultModelId", "default_model_id")
  );
  const userSelectedModelId = toNullableString(
    getField(data, "userSelectedChatModelId", "user_selected_chat_model_id") ??
      getField(data, "userSelectedModelId", "user_selected_model_id")
  );

  return {
    generatedAt: String(getField(data, "generatedAt", "generated_at") ?? ""),
    defaultModelId: defaultModelId && knownModelIds.has(defaultModelId) ? defaultModelId : null,
    userSelectedModelId:
      userSelectedModelId && knownModelIds.has(userSelectedModelId) ? userSelectedModelId : null,
    providers,
  };
}

function normalizeCountByStatus(payload: unknown): AdminAiTelemetrySummary["indexJobs"]["byStatus"][number] {
  const data = asRecord(payload);

  return {
    status: String(data.status ?? "unknown"),
    count: toNonNegativeNumber(data.count),
  };
}

function normalizePromptCallTelemetry(payload: unknown): AdminAiTelemetrySummary["promptCalls"] {
  const data = asRecord(payload);

  return {
    total: toNonNegativeNumber(data.total),
    success: toNonNegativeNumber(data.success),
    failed: toNonNegativeNumber(data.failed),
    timeout: toNonNegativeNumber(data.timeout),
    totalTokens: toNonNegativeNumber(getField(data, "totalTokens", "total_tokens")),
    averageLatencyMs: toNullableNonNegativeNumber(getField(data, "averageLatencyMs", "average_latency_ms")),
    latestAt: toNullableString(getField(data, "latestAt", "latest_at")),
  };
}

function normalizeRetrievalTelemetry(payload: unknown): AdminAiTelemetrySummary["retrievals"] {
  const data = asRecord(payload);

  return {
    total: toNonNegativeNumber(data.total),
    averageLatencyMs: toNullableNonNegativeNumber(getField(data, "averageLatencyMs", "average_latency_ms")),
    latestAt: toNullableString(getField(data, "latestAt", "latest_at")),
  };
}

function normalizeEmbeddingTelemetry(payload: unknown): AdminAiTelemetrySummary["embeddings"] {
  const data = asRecord(payload);

  return {
    total: toNonNegativeNumber(data.total),
    success: toNonNegativeNumber(data.success),
    failed: toNonNegativeNumber(data.failed),
    totalTokens: toNonNegativeNumber(getField(data, "totalTokens", "total_tokens")),
    averageLatencyMs: toNullableNonNegativeNumber(getField(data, "averageLatencyMs", "average_latency_ms")),
    latestAt: toNullableString(getField(data, "latestAt", "latest_at")),
  };
}

function normalizeIndexJobTelemetry(payload: unknown): AdminAiTelemetrySummary["indexJobs"] {
  const data = asRecord(payload);

  return {
    total: toNonNegativeNumber(data.total),
    queued: toNonNegativeNumber(data.queued),
    running: toNonNegativeNumber(data.running),
    blocked: toNonNegativeNumber(data.blocked),
    success: toNonNegativeNumber(data.success),
    failed: toNonNegativeNumber(data.failed),
    cancelled: toNonNegativeNumber(data.cancelled),
    superseded: toNonNegativeNumber(data.superseded),
    byStatus: Array.isArray(getField(data, "byStatus", "by_status"))
      ? (getField(data, "byStatus", "by_status") as unknown[]).map(normalizeCountByStatus)
      : [],
    latestFailureAt: toNullableString(getField(data, "latestFailureAt", "latest_failure_at")),
  };
}

function normalizeChatTelemetry(payload: unknown): AdminAiTelemetrySummary["chat"] {
  const data = asRecord(payload);

  return {
    sessions: toNonNegativeNumber(data.sessions),
    messages: toNonNegativeNumber(data.messages),
    activeUsers: toNonNegativeNumber(getField(data, "activeUsers", "active_users")),
    latestActivityAt: toNullableString(getField(data, "latestActivityAt", "latest_activity_at")),
  };
}

function normalizeAdminAiTelemetrySummary(payload: unknown): AdminAiTelemetrySummary {
  const data = asRecord(payload);

  return {
    generatedAt: String(getField(data, "generatedAt", "generated_at") ?? ""),
    promptCalls: normalizePromptCallTelemetry(getField(data, "promptCalls", "prompt_calls")),
    retrievals: normalizeRetrievalTelemetry(data.retrievals),
    embeddings: normalizeEmbeddingTelemetry(data.embeddings),
    indexJobs: normalizeIndexJobTelemetry(getField(data, "indexJobs", "index_jobs")),
    chat: normalizeChatTelemetry(data.chat),
  };
}

function normalizeTelemetryTrendPoint(payload: unknown): AdminAiTelemetryTrendResponse["items"][number] {
  const data = asRecord(payload);

  return {
    date: String(data.date ?? ""),
    promptCalls: toNonNegativeNumber(getField(data, "promptCalls", "prompt_calls")),
    promptFailures: toNonNegativeNumber(getField(data, "promptFailures", "prompt_failures")),
    promptTimeouts: toNonNegativeNumber(getField(data, "promptTimeouts", "prompt_timeouts")),
    promptTotalTokens: toNonNegativeNumber(getField(data, "promptTotalTokens", "prompt_total_tokens")),
    averagePromptLatencyMs: toNullableNonNegativeNumber(
      getField(data, "averagePromptLatencyMs", "average_prompt_latency_ms")
    ),
    retrievals: toNonNegativeNumber(data.retrievals),
    averageRetrievalLatencyMs: toNullableNonNegativeNumber(
      getField(data, "averageRetrievalLatencyMs", "average_retrieval_latency_ms")
    ),
    embeddingCalls: toNonNegativeNumber(getField(data, "embeddingCalls", "embedding_calls")),
    embeddingFailures: toNonNegativeNumber(getField(data, "embeddingFailures", "embedding_failures")),
    embeddingTotalTokens: toNonNegativeNumber(getField(data, "embeddingTotalTokens", "embedding_total_tokens")),
    averageEmbeddingLatencyMs: toNullableNonNegativeNumber(
      getField(data, "averageEmbeddingLatencyMs", "average_embedding_latency_ms")
    ),
    indexJobs: toNonNegativeNumber(getField(data, "indexJobs", "index_jobs")),
    indexFailures: toNonNegativeNumber(getField(data, "indexFailures", "index_failures")),
  };
}

function normalizeAdminAiTelemetryTrends(payload: unknown): AdminAiTelemetryTrendResponse {
  const data = asRecord(payload);

  return {
    generatedAt: String(getField(data, "generatedAt", "generated_at") ?? ""),
    days: toNonNegativeNumber(data.days),
    items: Array.isArray(data.items) ? data.items.map(normalizeTelemetryTrendPoint) : [],
  };
}

function normalizeTelemetryAnomaly(payload: unknown): AdminAiTelemetryAnomalies["items"][number] {
  const data = asRecord(payload);

  return {
    key: String(data.key ?? ""),
    severity: String(data.severity ?? "warning"),
    category: String(data.category ?? ""),
    title: String(data.title ?? "Telemetry anomaly"),
    detail: String(data.detail ?? ""),
    recommendation: String(data.recommendation ?? ""),
    metricLabel: String(getField(data, "metricLabel", "metric_label") ?? ""),
    currentValue: String(getField(data, "currentValue", "current_value") ?? ""),
    baselineValue: toNullableString(getField(data, "baselineValue", "baseline_value")),
    deltaPercent: toNullableFiniteNumber(getField(data, "deltaPercent", "delta_percent")),
  };
}

function normalizeAdminAiTelemetryAnomalies(payload: unknown): AdminAiTelemetryAnomalies {
  const data = asRecord(payload);

  return {
    generatedAt: String(getField(data, "generatedAt", "generated_at") ?? ""),
    days: toNonNegativeNumber(data.days),
    baselineDays: toNonNegativeNumber(getField(data, "baselineDays", "baseline_days")),
    windowStart: toNullableString(getField(data, "windowStart", "window_start")),
    windowEnd: toNullableString(getField(data, "windowEnd", "window_end")),
    baselineStart: toNullableString(getField(data, "baselineStart", "baseline_start")),
    baselineEnd: toNullableString(getField(data, "baselineEnd", "baseline_end")),
    overallStatus: String(getField(data, "overallStatus", "overall_status") ?? "unknown"),
    items: Array.isArray(data.items) ? data.items.map(normalizeTelemetryAnomaly) : [],
  };
}

function normalizeProviderConfigItem(payload: unknown): AdminAiProviderConfig["items"][number] {
  const data = asRecord(payload);

  return {
    key: String(data.key ?? ""),
    label: String(data.label ?? ""),
    status: String(data.status ?? "unknown"),
    detail: String(data.detail ?? ""),
    recommendation: toNullableString(data.recommendation),
  };
}

function normalizeAdminAiProviderConfig(payload: unknown): AdminAiProviderConfig {
  const data = asRecord(payload);

  return {
    generatedAt: String(getField(data, "generatedAt", "generated_at") ?? ""),
    overallStatus: String(getField(data, "overallStatus", "overall_status") ?? "unknown"),
    provider: String(data.provider ?? ""),
    model: String(data.model ?? ""),
    embeddingProvider: String(getField(data, "embeddingProvider", "embedding_provider") ?? ""),
    embeddingModel: String(getField(data, "embeddingModel", "embedding_model") ?? ""),
    storageProvider: String(getField(data, "storageProvider", "storage_provider") ?? ""),
    items: Array.isArray(data.items) ? data.items.map(normalizeProviderConfigItem) : [],
  };
}

function normalizeProviderHealthItem(payload: unknown): AdminAiProviderHealth["items"][number] {
  const data = asRecord(payload);

  return {
    key: String(data.key ?? ""),
    provider: String(data.provider ?? ""),
    modelName: String(data.modelName ?? data.model_name ?? ""),
    callType: String(data.callType ?? data.call_type ?? ""),
    totalCalls: toNonNegativeNumber(data.totalCalls ?? data.total_calls),
    success: toNonNegativeNumber(data.success),
    failed: toNonNegativeNumber(data.failed),
    timeout: toNonNegativeNumber(data.timeout),
    successRatePercent: toPercentNumber(data.successRatePercent ?? data.success_rate_percent),
    failureRatePercent: toPercentNumber(data.failureRatePercent ?? data.failure_rate_percent),
    averageLatencyMs: toNullableNonNegativeNumber(data.averageLatencyMs ?? data.average_latency_ms),
    latestAt: toNullableString(data.latestAt ?? data.latest_at),
    status: String(data.status ?? "unknown"),
    recommendation: toNullableString(data.recommendation),
  };
}

function normalizeProviderAnomaly(payload: unknown): AdminAiProviderHealth["anomalies"][number] {
  const data = asRecord(payload);

  return {
    key: String(data.key ?? ""),
    severity: String(data.severity ?? "warning"),
    title: String(data.title ?? "Provider anomaly"),
    detail: String(data.detail ?? ""),
    recommendation: String(data.recommendation ?? ""),
  };
}

function normalizeAdminAiProviderHealth(payload: unknown): AdminAiProviderHealth {
  const data = asRecord(payload);
  const items = Array.isArray(data.items) ? data.items.map(normalizeProviderHealthItem) : [];
  const anomalies = Array.isArray(data.anomalies)
    ? data.anomalies.map(normalizeProviderAnomaly)
    : [];

  return {
    generatedAt: String(data.generatedAt ?? data.generated_at ?? ""),
    windowStart: String(data.windowStart ?? data.window_start ?? ""),
    windowEnd: String(data.windowEnd ?? data.window_end ?? ""),
    days: toNonNegativeNumber(data.days),
    overallStatus: String(data.overallStatus ?? data.overall_status ?? "unknown"),
    provider: String(data.provider ?? ""),
    totalCalls: toNonNegativeNumber(data.totalCalls ?? data.total_calls),
    successRatePercent: toPercentNumber(data.successRatePercent ?? data.success_rate_percent),
    averageLatencyMs: toNullableNonNegativeNumber(data.averageLatencyMs ?? data.average_latency_ms),
    items,
    anomalies,
  };
}

function normalizeGovernanceMetric(payload: unknown): AdminAiGovernance["metrics"][number] {
  const data = asRecord(payload);

  return {
    key: String(data.key ?? ""),
    label: String(data.label ?? ""),
    value: String(data.value ?? ""),
    detail: String(data.detail ?? ""),
    status: String(data.status ?? "unknown"),
  };
}

function normalizeGovernanceAlert(payload: unknown): AdminAiGovernance["alerts"][number] {
  const data = asRecord(payload);

  return {
    severity: String(data.severity ?? "warning"),
    title: String(data.title ?? "智能治理告警"),
    detail: String(data.detail ?? ""),
    recommendation: String(data.recommendation ?? ""),
  };
}

function normalizeAdminAiGovernance(payload: unknown): AdminAiGovernance {
  const data = asRecord(payload);

  return {
    generatedAt: String(getField(data, "generatedAt", "generated_at") ?? ""),
    periodStart: String(getField(data, "periodStart", "period_start") ?? ""),
    periodEnd: String(getField(data, "periodEnd", "period_end") ?? ""),
    overallStatus: String(getField(data, "overallStatus", "overall_status") ?? "unknown"),
    estimatedCostUsd: toNonNegativeNumber(getField(data, "estimatedCostUsd", "estimated_cost_usd")),
    monthlyCostBudgetUsd: toNullableNonNegativeNumber(
      getField(data, "monthlyCostBudgetUsd", "monthly_cost_budget_usd")
    ),
    costBudgetUsagePercent: toNullableNonNegativeNumber(
      getField(data, "costBudgetUsagePercent", "cost_budget_usage_percent")
    ),
    monthlyTokenBudget: toNullableNonNegativeNumber(getField(data, "monthlyTokenBudget", "monthly_token_budget")),
    tokenBudgetUsagePercent: toNullableNonNegativeNumber(
      getField(data, "tokenBudgetUsagePercent", "token_budget_usage_percent")
    ),
    promptTokens: toNonNegativeNumber(getField(data, "promptTokens", "prompt_tokens")),
    embeddingTokens: toNonNegativeNumber(getField(data, "embeddingTokens", "embedding_tokens")),
    totalTokens: toNonNegativeNumber(getField(data, "totalTokens", "total_tokens")),
    promptCalls: toNonNegativeNumber(getField(data, "promptCalls", "prompt_calls")),
    embeddingCalls: toNonNegativeNumber(getField(data, "embeddingCalls", "embedding_calls")),
    indexJobs: toNonNegativeNumber(getField(data, "indexJobs", "index_jobs")),
    failures: toNonNegativeNumber(data.failures),
    failureRatePercent: toPercentNumber(getField(data, "failureRatePercent", "failure_rate_percent")),
    alerts: Array.isArray(data.alerts) ? data.alerts.map(normalizeGovernanceAlert) : [],
    metrics: Array.isArray(data.metrics) ? data.metrics.map(normalizeGovernanceMetric) : [],
  };
}

function normalizeTelemetryFailure(payload: unknown): AdminAiTelemetryFailuresResponse["items"][number] {
  const data = asRecord(payload);

  return {
    kind: String(data.kind ?? ""),
    id: toNonNegativeNumber(data.id),
    status: String(data.status ?? ""),
    occurredAt: toNullableString(getField(data, "occurredAt", "occurred_at")),
    userId: toNullableNonNegativeNumber(getField(data, "userId", "user_id")),
    sessionId: toNullableNonNegativeNumber(getField(data, "sessionId", "session_id")),
    messageId: toNullableNonNegativeNumber(getField(data, "messageId", "message_id")),
    courseId: toNullableNonNegativeNumber(getField(data, "courseId", "course_id")),
    moduleId: toNullableNonNegativeNumber(getField(data, "moduleId", "module_id")),
    materialId: toNullableNonNegativeNumber(getField(data, "materialId", "material_id")),
    modelName: toNullableString(getField(data, "modelName", "model_name")),
    callType: toNullableString(getField(data, "callType", "call_type")),
    latencyMs: toNullableNonNegativeNumber(getField(data, "latencyMs", "latency_ms")),
    totalTokens: toNullableNonNegativeNumber(getField(data, "totalTokens", "total_tokens")),
    attemptCount: toNullableNonNegativeNumber(getField(data, "attemptCount", "attempt_count")),
    errorSummary: toNullableString(getField(data, "errorSummary", "error_summary")),
  };
}

function normalizeAdminAiTelemetryFailures(payload: unknown): AdminAiTelemetryFailuresResponse {
  const data = asRecord(payload);

  return {
    generatedAt: String(getField(data, "generatedAt", "generated_at") ?? ""),
    items: Array.isArray(data.items) ? data.items.map(normalizeTelemetryFailure) : [],
  };
}

export async function listModuleChatSessions(moduleUuid: string): Promise<ChatSessionSummary[]> {
  const response = await fetch(`/api/ai/chat/modules/${moduleUuid}/sessions`, {
    headers: buildAuthHeaders(),
  });

  return parseResponse<ChatSessionSummary[]>(response);
}

export async function listChatSessions(): Promise<ChatSessionSummary[]> {
  const response = await fetch(CHAT_SESSIONS_API_URL, {
    headers: buildAuthHeaders(),
  });

  return parseResponse<ChatSessionSummary[]>(response);
}

export async function getChatSessionDetail(sessionUuid: string): Promise<ChatSessionDetail> {
  const response = await fetch(`${CHAT_SESSIONS_API_URL}/${sessionUuid}`, {
    headers: buildAuthHeaders(),
  });

  return parseResponse<ChatSessionDetail>(response);
}

export async function getAiModelCatalog(context?: {
  courseUuid?: string | null;
  moduleUuid?: string | null;
}): Promise<AiModelCatalog> {
  const params = new URLSearchParams();
  if (context?.courseUuid) {
    params.set("courseUuid", context.courseUuid);
  }
  if (context?.moduleUuid) {
    params.set("moduleUuid", context.moduleUuid);
  }
  const url = params.size > 0 ? `${AI_MODELS_API_URL}?${params.toString()}` : AI_MODELS_API_URL;
  const response = await fetch(url, {
    headers: buildAuthHeaders(),
  });

  return normalizeAiModelCatalog(await parseResponse<unknown>(response));
}

export async function getAiRuntimeHealth(): Promise<AiRuntimeHealth> {
  const response = await fetch(AI_RUNTIME_HEALTH_URL, {
    headers: buildAuthHeaders(),
  });

  return parseResponse<AiRuntimeHealth>(response);
}

export async function getAdminAiTelemetrySummary(): Promise<AdminAiTelemetrySummary> {
  const response = await fetch(ADMIN_AI_TELEMETRY_SUMMARY_URL, {
    headers: buildAuthHeaders(),
  });

  return normalizeAdminAiTelemetrySummary(await parseResponse<unknown>(response));
}

export async function getAdminAiTelemetryTrends(days = 14): Promise<AdminAiTelemetryTrendResponse> {
  const params = new URLSearchParams({ days: String(days) });
  const response = await fetch(`${ADMIN_AI_TELEMETRY_TRENDS_URL}?${params.toString()}`, {
    headers: buildAuthHeaders(),
  });

  return normalizeAdminAiTelemetryTrends(await parseResponse<unknown>(response));
}

export async function getAdminAiTelemetryAnomalies(days = 14): Promise<AdminAiTelemetryAnomalies> {
  const params = new URLSearchParams({ days: String(days) });
  const response = await fetch(`${ADMIN_AI_TELEMETRY_ANOMALIES_URL}?${params.toString()}`, {
    headers: buildAuthHeaders(),
  });

  return normalizeAdminAiTelemetryAnomalies(await parseResponse<unknown>(response));
}

export async function getAdminAiProviderConfig(): Promise<AdminAiProviderConfig> {
  const response = await fetch(ADMIN_AI_PROVIDER_CONFIG_URL, {
    headers: buildAuthHeaders(),
  });

  return normalizeAdminAiProviderConfig(await parseResponse<unknown>(response));
}

export async function getAdminAiProviderHealth(days = 14): Promise<AdminAiProviderHealth> {
  const params = new URLSearchParams({ days: String(days) });
  const response = await fetch(`${ADMIN_AI_PROVIDER_HEALTH_URL}?${params.toString()}`, {
    headers: buildAuthHeaders(),
  });

  return normalizeAdminAiProviderHealth(await parseResponse<unknown>(response));
}

export async function getAdminAiGovernance(): Promise<AdminAiGovernance> {
  const response = await fetch(ADMIN_AI_GOVERNANCE_URL, {
    headers: buildAuthHeaders(),
  });

  return normalizeAdminAiGovernance(await parseResponse<unknown>(response));
}

export async function getAdminAiTelemetryFailures(limit = 5): Promise<AdminAiTelemetryFailuresResponse> {
  const params = buildAdminAiTelemetryFailureParams({ limit });
  const response = await fetch(`${ADMIN_AI_TELEMETRY_FAILURES_URL}?${params.toString()}`, {
    headers: buildAuthHeaders(),
  });

  return normalizeAdminAiTelemetryFailures(await parseResponse<unknown>(response));
}

function buildAdminAiTelemetryFailureParams(filters: AdminAiTelemetryFailureFilters) {
  const params = new URLSearchParams();
  params.set("limit", String(filters.limit ?? 20));
  if (filters.kind) params.set("kind", filters.kind);
  if (filters.status) params.set("status", filters.status);
  if (filters.userId?.trim()) params.set("userId", filters.userId.trim());
  if (filters.courseId?.trim()) params.set("courseId", filters.courseId.trim());
  if (filters.moduleId?.trim()) params.set("moduleId", filters.moduleId.trim());
  if (filters.since?.trim()) params.set("since", filters.since.trim());
  if (filters.until?.trim()) params.set("until", filters.until.trim());
  return params;
}

export async function searchAdminAiTelemetryFailures(
  filters: AdminAiTelemetryFailureFilters = {}
): Promise<AdminAiTelemetryFailuresResponse> {
  const params = buildAdminAiTelemetryFailureParams(filters);
  const response = await fetch(`${ADMIN_AI_TELEMETRY_FAILURES_URL}?${params.toString()}`, {
    headers: buildAuthHeaders(),
  });

  return normalizeAdminAiTelemetryFailures(await parseResponse<unknown>(response));
}

export async function exportAdminAiTelemetryFailures(
  filters: AdminAiTelemetryFailureFilters = {}
): Promise<Blob> {
  const params = buildAdminAiTelemetryFailureParams({ ...filters, limit: filters.limit ?? 100 });
  const response = await fetch(`${ADMIN_AI_TELEMETRY_FAILURES_URL}/export?${params.toString()}`, {
    headers: buildAuthHeaders(),
  });
  const responseText = await response.text();
  const contentType = response.headers.get("Content-Type") || "text/csv";
  handleAuthenticationFailureFromResponse(response.status, parseJsonText(responseText));

  if (!response.ok) {
    const errorPayload = parseJsonText(responseText) as APIErrorResponse | null;
    throw new Error(
      errorPayload?.error?.message ||
      (typeof errorPayload?.detail === "string" ? errorPayload.detail : "导出智能服务失败审计失败。")
    );
  }

  return new Blob([responseText], { type: contentType });
}

export async function retryAdminAiIndexJob(jobId: number): Promise<AdminAiIndexJobRetryResponse> {
  const response = await fetch(`${ADMIN_AI_INDEX_JOB_RETRY_URL}/${jobId}/retry`, {
    method: "POST",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
  });

  return parseResponse<AdminAiIndexJobRetryResponse>(response);
}

export function resolveChatSendPayload(
  payload: ChatSendPayload,
  previousUncertainRequest: StableChatSendPayload | null = null,
  requestIdFactory: () => string = createChatRequestId
): StableChatSendPayload {
  const canReuse = previousUncertainRequest !== null
    && previousUncertainRequest.courseUuid === payload.courseUuid
    && previousUncertainRequest.moduleUuid === payload.moduleUuid
    && previousUncertainRequest.message === payload.message
    && (previousUncertainRequest.sessionUuid ?? null) === (payload.sessionUuid ?? null)
    && previousUncertainRequest.modelId === payload.modelId;
  return {
    ...payload,
    requestId: canReuse ? previousUncertainRequest.requestId : payload.requestId ?? requestIdFactory(),
  };
}

export async function sendChatMessage(payload: ChatSendPayload) {
  getAccessToken();
  const requestBody: Record<string, unknown> = {
    session_uuid: payload.sessionUuid ?? null,
    course_uuid: payload.courseUuid,
    module_uuid: payload.moduleUuid,
    message: payload.message,
    model_id: payload.modelId,
    request_id: payload.requestId ?? createChatRequestId(),
  };

  const response = await fetch(CHAT_API_URL, {
    method: "POST",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify(requestBody),
  });

  const data = await parseResponse<ChatSuccessResponse>(response);
  return data.data;
}

export async function retryChatMessage(messageId: number) {
  const response = await fetch(`${CHAT_API_URL}/messages/${messageId}/retry`, {
    method: "POST",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
  });

  const data = await parseResponse<ChatSuccessResponse>(response);
  return data.data;
}

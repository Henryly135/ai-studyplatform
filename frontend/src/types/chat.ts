export type ChatSessionSummary = {
  session_uuid: string;
  user_id: number;
  course_uuid: string | null;
  module_uuid: string | null;
  session_type: string;
  title: string | null;
  status: string;
  message_count: number;
  summary_text: string | null;
  last_message_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ChatSessionMessage = {
  message_id: number;
  session_uuid: string;
  role: "user" | "assistant" | "system" | "tool";
  message_type: string;
  parent_message_id: number | null;
  content_text: string;
  created_at: string;
};

export type ChatSessionDetail = {
  session: ChatSessionSummary;
  messages: ChatSessionMessage[];
};

export type ChatResponse = {
  session_uuid: string;
  user_message_id: number;
  assistant_message_id: number;
  reply: string;
};

export type AiModelCatalogModel = {
  modelId: string;
  provider: string;
  name: string;
  description: string | null;
  available: boolean;
  unavailableReason: string | null;
  backendSupported: boolean;
  displayOnly: boolean;
  isDefault: boolean;
  capabilities: string[];
  pairedEmbeddingModelId: string | null;
  pairedEmbeddingModelName: string | null;
  embeddingDimension: number | null;
  ragReady: boolean | null;
  indexCoverage: number | null;
  indexStatus: string | null;
};

export type AiModelCatalogProvider = {
  provider: string;
  label: string;
  backendSupported: boolean;
  configured: boolean;
  models: AiModelCatalogModel[];
};

export type AiModelCatalog = {
  generatedAt: string;
  defaultModelId: string | null;
  userSelectedModelId: string | null;
  providers: AiModelCatalogProvider[];
};

export type ChatSuccessResponse = {
  success: true;
  data: ChatResponse;
};

export type AiRuntimeHealth = {
  status: string;
  module: string;
  provider: string;
  model: string;
  configured: boolean;
};

export type AdminAiTelemetrySummary = {
  generatedAt: string;
  promptCalls: {
    total: number;
    success: number;
    failed: number;
    timeout: number;
    totalTokens: number;
    averageLatencyMs: number | null;
    latestAt: string | null;
  };
  retrievals: {
    total: number;
    averageLatencyMs: number | null;
    latestAt: string | null;
  };
  embeddings: {
    total: number;
    success: number;
    failed: number;
    totalTokens: number;
    averageLatencyMs: number | null;
    latestAt: string | null;
  };
  indexJobs: {
    total: number;
    queued: number;
    running: number;
    blocked: number;
    success: number;
    failed: number;
    cancelled: number;
    superseded: number;
    byStatus: Array<{ status: string; count: number }>;
    latestFailureAt: string | null;
  };
  chat: {
    sessions: number;
    messages: number;
    activeUsers: number;
    latestActivityAt: string | null;
  };
};

export type AdminAiTelemetryTrendPoint = {
  date: string;
  promptCalls: number;
  promptFailures: number;
  promptTimeouts: number;
  promptTotalTokens: number;
  averagePromptLatencyMs: number | null;
  retrievals: number;
  averageRetrievalLatencyMs: number | null;
  embeddingCalls: number;
  embeddingFailures: number;
  embeddingTotalTokens: number;
  averageEmbeddingLatencyMs: number | null;
  indexJobs: number;
  indexFailures: number;
};

export type AdminAiTelemetryTrendResponse = {
  generatedAt: string;
  days: number;
  items: AdminAiTelemetryTrendPoint[];
};

export type AdminAiTelemetryAnomalyInsight = {
  key: string;
  severity: "warning" | "critical" | string;
  category: string;
  title: string;
  detail: string;
  recommendation: string;
  metricLabel: string;
  currentValue: string;
  baselineValue: string | null;
  deltaPercent: number | null;
};

export type AdminAiTelemetryAnomalies = {
  generatedAt: string;
  days: number;
  baselineDays: number;
  windowStart: string | null;
  windowEnd: string | null;
  baselineStart: string | null;
  baselineEnd: string | null;
  overallStatus: "ready" | "warning" | "blocked" | string;
  items: AdminAiTelemetryAnomalyInsight[];
};

export type AdminAiProviderConfigItem = {
  key: string;
  label: string;
  status: "ready" | "warning" | "blocked" | string;
  detail: string;
  recommendation: string | null;
};

export type AdminAiProviderConfig = {
  generatedAt: string;
  overallStatus: "ready" | "warning" | "blocked" | string;
  provider: string;
  model: string;
  embeddingProvider: string;
  embeddingModel: string;
  storageProvider: string;
  items: AdminAiProviderConfigItem[];
};

export type AdminAiProviderHealthItem = {
  key: string;
  provider: string;
  modelName: string;
  callType: string;
  totalCalls: number;
  success: number;
  failed: number;
  timeout: number;
  successRatePercent: number;
  failureRatePercent: number;
  averageLatencyMs: number | null;
  latestAt: string | null;
  status: "ready" | "warning" | "blocked" | string;
  recommendation: string | null;
};

export type AdminAiProviderAnomaly = {
  key: string;
  severity: "warning" | "critical" | string;
  title: string;
  detail: string;
  recommendation: string;
};

export type AdminAiProviderHealth = {
  generatedAt: string;
  windowStart: string;
  windowEnd: string;
  days: number;
  overallStatus: "ready" | "warning" | "blocked" | string;
  provider: string;
  totalCalls: number;
  successRatePercent: number;
  averageLatencyMs: number | null;
  items: AdminAiProviderHealthItem[];
  anomalies: AdminAiProviderAnomaly[];
};

export type AdminAiGovernanceMetric = {
  key: string;
  label: string;
  value: string;
  detail: string;
  status: "ready" | "warning" | "blocked" | string;
};

export type AdminAiGovernanceAlert = {
  severity: "warning" | "critical" | string;
  title: string;
  detail: string;
  recommendation: string;
};

export type AdminAiGovernance = {
  generatedAt: string;
  periodStart: string;
  periodEnd: string;
  overallStatus: "ready" | "warning" | "blocked" | string;
  estimatedCostUsd: number;
  monthlyCostBudgetUsd: number | null;
  costBudgetUsagePercent: number | null;
  monthlyTokenBudget: number | null;
  tokenBudgetUsagePercent: number | null;
  promptTokens: number;
  embeddingTokens: number;
  totalTokens: number;
  promptCalls: number;
  embeddingCalls: number;
  indexJobs: number;
  failures: number;
  failureRatePercent: number;
  alerts: AdminAiGovernanceAlert[];
  metrics: AdminAiGovernanceMetric[];
};

export type AdminAiTelemetryFailureItem = {
  kind: string;
  id: number;
  status: string;
  occurredAt: string | null;
  userId: number | null;
  sessionId: number | null;
  messageId: number | null;
  courseId: number | null;
  moduleId: number | null;
  materialId: number | null;
  modelName: string | null;
  callType: string | null;
  latencyMs: number | null;
  totalTokens: number | null;
  attemptCount: number | null;
  errorSummary: string | null;
};

export type AdminAiTelemetryFailuresResponse = {
  generatedAt: string;
  items: AdminAiTelemetryFailureItem[];
};

export type AdminAiIndexJobRetryResponse = {
  jobId: number;
  status: string;
  dispatched: boolean;
};

export type AdminAiTelemetryFailureFilters = {
  limit?: number;
  kind?: "" | "prompt" | "embedding" | "index_job";
  status?: "" | "failed" | "timeout";
  userId?: string;
  courseId?: string;
  moduleId?: string;
  since?: string;
  until?: string;
};

export type APIErrorResponse = {
  success?: false;
  error?: {
    code: string;
    message: string;
  };
  detail?: string;
};

export type CourseChatMessage = {
  id: number;
  role: "user" | "assistant";
  text: string;
};

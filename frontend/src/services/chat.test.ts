import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  getAiModelCatalog,
  getAdminAiGovernance,
  getAdminAiProviderConfig,
  getAdminAiProviderHealth,
  getAdminAiTelemetryAnomalies,
  getAdminAiTelemetrySummary,
  getAdminAiTelemetryTrends,
  searchAdminAiTelemetryFailures,
  sendChatMessage,
} from "./chat";

const NOW_MS = 1_800_000_000_000;

function base64UrlEncode(value: unknown) {
  return btoa(JSON.stringify(value)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/u, "");
}

function makeToken(exp: number) {
  return `${base64UrlEncode({ alg: "HS256", typ: "JWT" })}.${base64UrlEncode({ exp })}.signature`;
}

function createMemoryStorage(): Storage {
  const values = new Map<string, string>();

  return {
    get length() {
      return values.size;
    },
    clear() {
      values.clear();
    },
    getItem(key: string) {
      return values.get(key) ?? null;
    },
    key(index: number) {
      return Array.from(values.keys())[index] ?? null;
    },
    removeItem(key: string) {
      values.delete(key);
    },
    setItem(key: string, value: string) {
      values.set(key, String(value));
    },
  };
}

function mockJsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("admin AI provider health normalization", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(NOW_MS));
    vi.stubGlobal("localStorage", createMemoryStorage());
    vi.stubGlobal("window", {
      location: {
        pathname: "/home/ai",
        assign: vi.fn(),
      },
    });
    localStorage.setItem("accessToken", makeToken(NOW_MS / 1000 + 60));
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("normalizes malformed provider health metrics to display-safe values", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockJsonResponse({
          generated_at: "2026-07-02T00:00:00Z",
          window_start: "2026-06-18T00:00:00Z",
          window_end: "2026-07-02T00:00:00Z",
          days: "not-days",
          overall_status: "warning",
          provider: "gemini",
          total_calls: "not-calls",
          success_rate_percent: 140,
          average_latency_ms: -50,
          items: [
            {
              key: "gemini-chat",
              provider: "gemini",
              model_name: "gemini-1.5",
              call_type: "chat",
              total_calls: "7",
              success: "bad-success",
              failed: -2,
              timeout: "1",
              success_rate_percent: "not-rate",
              failure_rate_percent: 125,
              average_latency_ms: "250",
              latest_at: null,
              status: "warning",
              recommendation: 123,
            },
          ],
          anomalies: [
            {
              key: "latency-spike",
              severity: "critical",
              title: "Latency spike",
              detail: "P95 latency increased.",
              recommendation: "Inspect provider status.",
            },
          ],
        })
      )
    );

    const result = await getAdminAiProviderHealth(14);

    expect(result.days).toBe(0);
    expect(result.totalCalls).toBe(0);
    expect(result.successRatePercent).toBe(100);
    expect(result.averageLatencyMs).toBeNull();
    expect(result.items[0].modelName).toBe("gemini-1.5");
    expect(result.items[0].callType).toBe("chat");
    expect(result.items[0].totalCalls).toBe(7);
    expect(result.items[0].success).toBe(0);
    expect(result.items[0].failed).toBe(0);
    expect(result.items[0].timeout).toBe(1);
    expect(result.items[0].successRatePercent).toBe(0);
    expect(result.items[0].failureRatePercent).toBe(100);
    expect(result.items[0].averageLatencyMs).toBe(250);
    expect(result.items[0].latestAt).toBeNull();
    expect(result.items[0].recommendation).toBe("123");
    expect(result.anomalies[0].severity).toBe("critical");
  });

  it("normalizes malformed telemetry summary and trend metrics", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        mockJsonResponse({
          generated_at: "2026-07-02T00:00:00Z",
          prompt_calls: {
            total: "4",
            success: -1,
            failed: "bad",
            timeout: "2",
            total_tokens: "9",
            average_latency_ms: -20,
            latest_at: null,
          },
          retrievals: {
            total: "not-total",
            average_latency_ms: "150",
            latest_at: "2026-07-02T00:01:00Z",
          },
          embeddings: {
            total: "3",
            success: "2",
            failed: -5,
            total_tokens: "bad",
            average_latency_ms: "bad",
          },
          index_jobs: {
            total: "6",
            queued: -1,
            running: "2",
            blocked: "bad",
            success: "1",
            failed: "3",
            cancelled: -1,
            superseded: "1",
            by_status: [{ status: "failed", count: "3" }, { status: "running", count: -2 }],
            latest_failure_at: null,
          },
          chat: {
            sessions: "5",
            messages: -10,
            active_users: "3",
            latest_activity_at: "2026-07-02T00:02:00Z",
          },
        })
      )
      .mockResolvedValueOnce(
        mockJsonResponse({
          generated_at: "2026-07-02T00:00:00Z",
          days: "not-days",
          items: [
            {
              date: "2026-07-02",
              prompt_calls: -1,
              prompt_failures: "2",
              prompt_timeouts: "bad",
              prompt_total_tokens: "11",
              average_prompt_latency_ms: -5,
              retrievals: "3",
              average_retrieval_latency_ms: "bad",
              embedding_calls: "4",
              embedding_failures: -7,
              embedding_total_tokens: "13",
              average_embedding_latency_ms: "100",
              index_jobs: "5",
              index_failures: "bad",
            },
          ],
        })
      );
    vi.stubGlobal("fetch", fetchMock);

    const summary = await getAdminAiTelemetrySummary();
    const trends = await getAdminAiTelemetryTrends(14);

    expect(summary.promptCalls.total).toBe(4);
    expect(summary.promptCalls.success).toBe(0);
    expect(summary.promptCalls.failed).toBe(0);
    expect(summary.promptCalls.timeout).toBe(2);
    expect(summary.promptCalls.totalTokens).toBe(9);
    expect(summary.promptCalls.averageLatencyMs).toBeNull();
    expect(summary.retrievals.total).toBe(0);
    expect(summary.retrievals.averageLatencyMs).toBe(150);
    expect(summary.embeddings.failed).toBe(0);
    expect(summary.embeddings.averageLatencyMs).toBeNull();
    expect(summary.indexJobs.queued).toBe(0);
    expect(summary.indexJobs.byStatus[0].count).toBe(3);
    expect(summary.indexJobs.byStatus[1].count).toBe(0);
    expect(summary.chat.messages).toBe(0);
    expect(summary.chat.activeUsers).toBe(3);
    expect(trends.days).toBe(0);
    expect(trends.items[0].promptCalls).toBe(0);
    expect(trends.items[0].promptFailures).toBe(2);
    expect(trends.items[0].averagePromptLatencyMs).toBeNull();
    expect(trends.items[0].retrievals).toBe(3);
    expect(trends.items[0].averageRetrievalLatencyMs).toBeNull();
    expect(trends.items[0].embeddingCalls).toBe(4);
    expect(trends.items[0].embeddingFailures).toBe(0);
    expect(trends.items[0].averageEmbeddingLatencyMs).toBe(100);
    expect(trends.items[0].indexFailures).toBe(0);
  });

  it("normalizes malformed anomaly, provider config, and governance responses", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        mockJsonResponse({
          generated_at: "2026-07-02T00:00:00Z",
          days: "-3",
          baseline_days: "bad",
          window_start: null,
          window_end: "2026-07-02",
          overall_status: "warning",
          items: [
            {
              key: "failure-rate",
              severity: "critical",
              category: "failure_rate",
              title: "Failure rate increased",
              detail: "Bad spike.",
              recommendation: "Inspect failures.",
              metric_label: "Failure rate",
              current_value: "20%",
              baseline_value: null,
              delta_percent: "bad",
            },
          ],
        })
      )
      .mockResolvedValueOnce(
        mockJsonResponse({
          generated_at: "2026-07-02T00:00:00Z",
          overall_status: "blocked",
          provider: "gemini",
          model: "gemini-1.5",
          embedding_provider: "gemini",
          embedding_model: "embedding-001",
          storage_provider: "minio",
          items: [{ key: "api-key", label: "API key", status: "blocked", detail: "Missing", recommendation: 123 }],
        })
      )
      .mockResolvedValueOnce(
        mockJsonResponse({
          generated_at: "2026-07-02T00:00:00Z",
          period_start: "2026-07-01T00:00:00Z",
          period_end: "2026-07-02T00:00:00Z",
          overall_status: "warning",
          estimated_cost_usd: "-9",
          monthly_cost_budget_usd: "100",
          cost_budget_usage_percent: "125",
          monthly_token_budget: "-500",
          token_budget_usage_percent: "bad",
          prompt_tokens: "200",
          embedding_tokens: -3,
          total_tokens: "not-total",
          prompt_calls: "7",
          embedding_calls: "2",
          index_jobs: -1,
          failures: "3",
          failure_rate_percent: 140,
          alerts: [{ severity: "critical", detail: "Budget exceeded.", recommendation: "Pause rollout." }],
          metrics: [{ key: "cost", label: "Cost", value: "$0", detail: "Estimate", status: "ready" }],
        })
      );
    vi.stubGlobal("fetch", fetchMock);

    const anomalies = await getAdminAiTelemetryAnomalies(14);
    const config = await getAdminAiProviderConfig();
    const governance = await getAdminAiGovernance();

    expect(anomalies.days).toBe(0);
    expect(anomalies.baselineDays).toBe(0);
    expect(anomalies.windowStart).toBeNull();
    expect(anomalies.items[0].metricLabel).toBe("Failure rate");
    expect(anomalies.items[0].deltaPercent).toBeNull();
    expect(config.overallStatus).toBe("blocked");
    expect(config.embeddingProvider).toBe("gemini");
    expect(config.items[0].recommendation).toBe("123");
    expect(governance.estimatedCostUsd).toBe(0);
    expect(governance.monthlyCostBudgetUsd).toBe(100);
    expect(governance.costBudgetUsagePercent).toBe(125);
    expect(governance.monthlyTokenBudget).toBeNull();
    expect(governance.tokenBudgetUsagePercent).toBeNull();
    expect(governance.embeddingTokens).toBe(0);
    expect(governance.totalTokens).toBe(0);
    expect(governance.indexJobs).toBe(0);
    expect(governance.failureRatePercent).toBe(100);
    expect(governance.alerts[0].title).toBe("智能治理告警");
  });

  it("normalizes malformed failure audit items", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockJsonResponse({
          generated_at: "2026-07-02T00:00:00Z",
          items: [
            {
              kind: "index_job",
              id: "9",
              status: "failed",
              occurred_at: null,
              user_id: -1,
              session_id: "12",
              message_id: "bad",
              course_id: "3",
              module_id: "4",
              material_id: -2,
              model_name: 123,
              call_type: null,
              latency_ms: -20,
              total_tokens: "99",
              attempt_count: "bad",
              error_summary: 456,
            },
          ],
        })
      )
    );

    const result = await searchAdminAiTelemetryFailures({ limit: 20 });

    expect(result.items[0].id).toBe(9);
    expect(result.items[0].occurredAt).toBeNull();
    expect(result.items[0].userId).toBeNull();
    expect(result.items[0].sessionId).toBe(12);
    expect(result.items[0].messageId).toBeNull();
    expect(result.items[0].courseId).toBe(3);
    expect(result.items[0].moduleId).toBe(4);
    expect(result.items[0].materialId).toBeNull();
    expect(result.items[0].modelName).toBe("123");
    expect(result.items[0].callType).toBeNull();
    expect(result.items[0].latencyMs).toBeNull();
    expect(result.items[0].totalTokens).toBe(99);
    expect(result.items[0].attemptCount).toBeNull();
    expect(result.items[0].errorSummary).toBe("456");
  });

  it("normalizes model catalog providers and flat model responses", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        mockJsonResponse({
          generated_at: "2026-07-02T00:00:00Z",
          default_model_id: "deepseek:deepseek-v4-flash",
          user_selected_chat_model_id: "glm:glm-4.5-air",
          providers: [
            {
              provider: "deepseek",
              label: "DeepSeek",
              backend_supported: true,
              has_credential: "true",
              models: [
                {
                  model_id: "deepseek:deepseek-v4-flash",
                  display_name: "DeepSeek V4 Flash",
                  available: true,
                  is_default: true,
                  backend_supported: true,
                  capabilities: ["chat", 123],
                },
                {
                  model_id: "deepseek:embedding",
                  display_name: "DeepSeek Embedding",
                  unavailable_reason: "Missing key",
                  capabilities: { embedding: true, chat: false },
                },
              ],
            },
          ],
        })
      )
      .mockResolvedValueOnce(
        mockJsonResponse({
          models: [
            {
              id: "gemini:flash",
              provider: "gemini",
              name: "Gemini Flash",
              available: true,
            },
          ],
        })
      );
    vi.stubGlobal("fetch", fetchMock);

    const catalog = await getAiModelCatalog();
    const flatCatalog = await getAiModelCatalog();

    expect(catalog.defaultModelId).toBe("deepseek:deepseek-v4-flash");
    expect(catalog.userSelectedModelId).toBe("glm:glm-4.5-air");
    expect(catalog.providers[0].backendSupported).toBe(true);
    expect(catalog.providers[0].configured).toBe(true);
    expect(catalog.providers[0].models[0].name).toBe("DeepSeek V4 Flash");
    expect(catalog.providers[0].models[0].capabilities).toEqual(["chat", "123"]);
    expect(catalog.providers[0].models[1].available).toBe(false);
    expect(catalog.providers[0].models[1].unavailableReason).toBe("Missing key");
    expect(catalog.providers[0].models[1].capabilities).toEqual(["embedding"]);
    expect(flatCatalog.providers[0].provider).toBe("gemini");
    expect(flatCatalog.providers[0].models[0].modelId).toBe("gemini:flash");
  });

  it("sends optional model_id with chat messages", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      mockJsonResponse({
        success: true,
        data: {
          session_uuid: "session-1",
          user_message_id: 1,
          assistant_message_id: 2,
          reply: "Hello",
        },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await sendChatMessage({
      courseUuid: "course-1",
      moduleUuid: "module-1",
      message: "Hi",
      modelId: "deepseek:deepseek-v4-flash",
    });

    expect(result.reply).toBe("Hello");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/ai/chat",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          session_uuid: null,
          course_uuid: "course-1",
          module_uuid: "module-1",
          message: "Hi",
          model_id: "deepseek:deepseek-v4-flash",
        }),
      })
    );
  });
});

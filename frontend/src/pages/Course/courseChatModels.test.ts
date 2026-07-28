import { describe, expect, it } from "vitest";

import type { AiModelCatalog, AiModelCatalogModel } from "../../types/chat";
import {
  formatRagOptionSuffix,
  formatRagStatusText,
  isChatModelSelectable,
  resolveChatModelSelection,
} from "./courseChatModels";

function model(overrides: Partial<AiModelCatalogModel>): AiModelCatalogModel {
  return {
    modelId: "glm:glm-4.7",
    provider: "glm",
    name: "GLM 4.7",
    description: null,
    available: true,
    unavailableReason: null,
    backendSupported: true,
    displayOnly: false,
    isDefault: false,
    capabilities: ["chat"],
    pairedEmbeddingModelId: "glm:embedding-3",
    pairedEmbeddingModelName: "GLM Embedding-3",
    embeddingDimension: 1024,
    ragReady: false,
    indexCoverage: 0.42,
    indexStatus: "indexing",
    ...overrides,
  };
}

function catalog(models: AiModelCatalogModel[]): AiModelCatalog {
  return {
    generatedAt: "",
    defaultModelId: "glm:glm-4.7",
    userSelectedModelId: null,
    providers: [
      {
        provider: "glm",
        label: "GLM",
        backendSupported: true,
        configured: true,
        models,
      },
    ],
  };
}

describe("resolveChatModelSelection", () => {
  it("keeps a building model visible for status while preventing selection", () => {
    expect(resolveChatModelSelection(catalog([model({})]), "")).toBe(
      "glm:glm-4.7"
    );
    expect(isChatModelSelectable(model({}))).toBe(false);
  });

  it("allows ordinary chat when the selected scope has no materials", () => {
    const empty = model({
      ragReady: false,
      indexCoverage: 0,
      indexStatus: "empty",
    });

    expect(resolveChatModelSelection(catalog([empty]), "")).toBe(empty.modelId);
    expect(isChatModelSelectable(empty)).toBe(true);
  });

  it("keeps a ready current selection and falls back to another ready model", () => {
    const current = model({
      modelId: "gemini:gemini-3.5-flash-lite",
      provider: "gemini",
      name: "Gemini 3.5 Flash-Lite",
      pairedEmbeddingModelId: "gemini:gemini-embedding-2",
      pairedEmbeddingModelName: "Gemini Embedding 2",
      ragReady: true,
      indexCoverage: 1,
      indexStatus: "ready",
    });
    const fallback = model({
      ragReady: true,
      indexCoverage: 1,
      indexStatus: "ready",
    });
    const value = catalog([current, fallback]);

    expect(resolveChatModelSelection(value, current.modelId)).toBe(current.modelId);
    expect(
      resolveChatModelSelection(
        catalog([{ ...current, available: false }, fallback]),
        current.modelId
      )
    ).toBe(fallback.modelId);
  });

  it("skips an available but unready preferred model", () => {
    const unreadyDefault = model({});
    const readyFallback = model({
      modelId: "openrouter:openrouter/auto",
      provider: "openrouter",
      name: "OpenRouter Auto",
      pairedEmbeddingModelId: "openrouter:openai/text-embedding-3-small",
      pairedEmbeddingModelName: "OpenAI Text Embedding 3 Small via OpenRouter",
      ragReady: true,
      indexCoverage: 1,
      indexStatus: "ready",
    });

    expect(resolveChatModelSelection(catalog([unreadyDefault, readyFallback]), "")).toBe(
      readyFallback.modelId
    );
  });

  it("falls back to the preferred unavailable model when no model is usable", () => {
    const unavailableDefault = model({
      available: false,
      unavailableReason: "供应商健康检查失败，当前暂不可用。",
      ragReady: false,
      indexCoverage: 1,
      indexStatus: "ready",
    });

    expect(
      resolveChatModelSelection(catalog([unavailableDefault]), "")
    ).toBe(unavailableDefault.modelId);
    expect(isChatModelSelectable(unavailableDefault)).toBe(false);
  });
});

describe("RAG readiness copy", () => {
  it("distinguishes a partial index from an index that is still building", () => {
    const partial = model({
      ragReady: false,
      indexCoverage: 0.42,
      indexStatus: "partial",
    });

    expect(formatRagStatusText(partial)).toBe(
      "课程资料索引仅部分完成（42%），完成前暂不可选择。"
    );
    expect(formatRagOptionSuffix(partial)).toBe(" · 索引部分完成 42%");
  });

  it("gives a recovery-oriented message for a failed index", () => {
    const failed = model({
      ragReady: false,
      indexCoverage: 0,
      indexStatus: "failed",
    });

    expect(formatRagStatusText(failed)).toBe(
      "课程资料索引失败，请联系课程管理员重试。"
    );
    expect(formatRagOptionSuffix(failed)).toBe(" · 索引失败");
  });
});

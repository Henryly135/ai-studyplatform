import { describe, expect, it } from "vitest";

import type { AiModelCatalog, AiModelCatalogModel } from "../../types/chat";
import {
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
  it("does not resolve a model while its course index is building", () => {
    expect(resolveChatModelSelection(catalog([model({})]), "")).toBe("");
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
      modelId: "glm:glm-4.5-air",
      name: "GLM 4.5 Air",
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
      modelId: "glm:glm-4.5-air",
      name: "GLM 4.5 Air",
      ragReady: true,
      indexCoverage: 1,
      indexStatus: "ready",
    });

    expect(resolveChatModelSelection(catalog([unreadyDefault, readyFallback]), "")).toBe(
      readyFallback.modelId
    );
  });
});

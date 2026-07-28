import type { AiModelCatalog, AiModelCatalogModel } from "../../types/chat";

function normalizeIndexStatus(value: string | null) {
  return value?.trim().toLowerCase().replaceAll("-", "_") ?? "";
}

export function isNoMaterialIndexStatus(value: string | null) {
  return ["empty", "no_material", "no_materials", "not_applicable"].includes(
    normalizeIndexStatus(value)
  );
}

export function isChatModelSelectable(model: AiModelCatalogModel) {
  return (
    model.available &&
    model.capabilities.includes("chat") &&
    (model.ragReady === true || isNoMaterialIndexStatus(model.indexStatus))
  );
}

export function resolveChatModelSelection(catalog: AiModelCatalog, currentModelId: string) {
  const availableModels = catalog.providers.flatMap((provider) =>
    provider.models.filter(isChatModelSelectable)
  );

  if (availableModels.some((model) => model.modelId === currentModelId)) {
    return currentModelId;
  }

  return (
    availableModels.find((model) => model.modelId === catalog.userSelectedModelId)?.modelId ??
    availableModels.find(
      (model) => model.modelId === catalog.defaultModelId || model.isDefault
    )?.modelId ??
    availableModels[0]?.modelId ??
    ""
  );
}

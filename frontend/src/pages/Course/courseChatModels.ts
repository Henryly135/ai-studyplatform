import type { AiModelCatalog, AiModelCatalogModel } from "../../types/chat";

function normalizeIndexStatus(value: string | null) {
  return value?.trim().toLowerCase().replaceAll("-", "_") ?? "";
}

function formatIndexCoverage(value: number | null) {
  return value === null ? null : `${Math.round(value * 100)}%`;
}

function isIndexBuildingStatus(value: string | null) {
  return ["building", "indexing", "pending", "queued", "running"].includes(
    normalizeIndexStatus(value)
  );
}

export function isNoMaterialIndexStatus(value: string | null) {
  return ["empty", "no_material", "no_materials", "not_applicable"].includes(
    normalizeIndexStatus(value)
  );
}

export function formatRagStatusText(model: AiModelCatalogModel) {
  const coverage = formatIndexCoverage(model.indexCoverage);
  const indexStatus = normalizeIndexStatus(model.indexStatus);

  if (isNoMaterialIndexStatus(model.indexStatus)) {
    return "当前模块暂无可检索资料，可继续普通聊天。";
  }
  if (model.ragReady === true) {
    return `课程资料检索已就绪${coverage ? `，索引覆盖 ${coverage}` : ""}。`;
  }
  if (model.ragReady === false && isIndexBuildingStatus(model.indexStatus)) {
    return `课程资料索引构建中${coverage ? `（${coverage}）` : ""}，完成前暂不可选择。`;
  }
  if (model.ragReady === false && indexStatus === "partial") {
    return `课程资料索引仅部分完成${coverage ? `（${coverage}）` : ""}，完成前暂不可选择。`;
  }
  if (model.ragReady === false && indexStatus === "failed") {
    return `课程资料索引失败${coverage && coverage !== "0%" ? `（${coverage}）` : ""}，请联系课程管理员重试。`;
  }
  if (model.ragReady === false) {
    return "课程资料检索暂未就绪，当前模型暂不可选择。";
  }
  return "课程资料检索状态待确认，当前模型暂不可选择。";
}

export function formatRagOptionSuffix(model: AiModelCatalogModel) {
  const coverage = formatIndexCoverage(model.indexCoverage);
  const indexStatus = normalizeIndexStatus(model.indexStatus);

  if (isNoMaterialIndexStatus(model.indexStatus)) {
    return " · 暂无资料";
  }
  if (model.ragReady === true) {
    return " · 资料检索就绪";
  }
  if (model.ragReady === false && isIndexBuildingStatus(model.indexStatus)) {
    return ` · 索引构建中${coverage ? ` ${coverage}` : ""}`;
  }
  if (model.ragReady === false && indexStatus === "partial") {
    return ` · 索引部分完成${coverage ? ` ${coverage}` : ""}`;
  }
  if (model.ragReady === false && indexStatus === "failed") {
    return ` · 索引失败${coverage && coverage !== "0%" ? ` ${coverage}` : ""}`;
  }
  if (model.ragReady === false) {
    return " · 资料检索未就绪";
  }
  return "";
}

export function isChatModelSelectable(model: AiModelCatalogModel) {
  return (
    model.available &&
    model.capabilities.includes("chat") &&
    (model.ragReady === true || isNoMaterialIndexStatus(model.indexStatus))
  );
}

export function resolveChatModelSelection(catalog: AiModelCatalog, currentModelId: string) {
  const chatModels = catalog.providers.flatMap((provider) =>
    provider.models.filter((model) => model.capabilities.includes("chat"))
  );
  const selectableModels = chatModels.filter(isChatModelSelectable);

  if (selectableModels.some((model) => model.modelId === currentModelId)) {
    return currentModelId;
  }

  return (
    selectableModels.find((model) => model.modelId === catalog.userSelectedModelId)?.modelId ??
    selectableModels.find(
      (model) => model.modelId === catalog.defaultModelId || model.isDefault
    )?.modelId ??
    selectableModels[0]?.modelId ??
    chatModels.find((model) => model.modelId === currentModelId)?.modelId ??
    chatModels.find((model) => model.modelId === catalog.userSelectedModelId)?.modelId ??
    chatModels.find(
      (model) => model.modelId === catalog.defaultModelId || model.isDefault
    )?.modelId ??
    chatModels[0]?.modelId ??
    ""
  );
}

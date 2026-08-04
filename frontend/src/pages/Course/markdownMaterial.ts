import type { CourseMaterial } from "../../types/course";

export type MarkdownFetcher = (
  input: RequestInfo | URL,
  init?: RequestInit
) => Promise<Response>;

function getMetadataString(material: CourseMaterial, key: string) {
  const value = material.metadataJson?.[key];
  return typeof value === "string" ? value.trim().toLowerCase() : "";
}

function getMaterialExtension(material: CourseMaterial) {
  const rawValue =
    getMetadataString(material, "originalFilename") ||
    material.resourceUrl.trim().toLowerCase() ||
    material.title.trim().toLowerCase();
  const cleanValue = rawValue.split("?")[0]?.split("#")[0] ?? "";
  const lastDotIndex = cleanValue.lastIndexOf(".");
  return lastDotIndex >= 0 ? cleanValue.slice(lastDotIndex + 1) : "";
}

export function isMarkdownMaterial(material: CourseMaterial) {
  const contentType = getMetadataString(material, "contentType");
  const materialType = material.materialType.trim().toLowerCase();

  return (
    contentType === "text/markdown" ||
    contentType === "text/x-markdown" ||
    materialType === "markdown" ||
    ["md", "markdown", "mdown", "mkd"].includes(getMaterialExtension(material))
  );
}

export async function loadMarkdownText(
  resourceUrl: string,
  signal?: AbortSignal,
  request: MarkdownFetcher = fetch
) {
  const response = await request(resourceUrl, {
    method: "GET",
    credentials: "same-origin",
    signal,
    headers: {
      Accept: "text/markdown, text/plain;q=0.9, */*;q=0.1",
    },
  });

  if (!response.ok) {
    throw new Error(`Markdown 资料加载失败（${response.status}）。`);
  }

  return response.text();
}

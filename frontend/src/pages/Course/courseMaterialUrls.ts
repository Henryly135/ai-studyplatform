export function getMaterialDownloadUrl(resourceUrl: string) {
  const hashIndex = resourceUrl.indexOf("#");
  const baseUrl = hashIndex >= 0 ? resourceUrl.slice(0, hashIndex) : resourceUrl;
  const fragment = hashIndex >= 0 ? resourceUrl.slice(hashIndex) : "";
  const isLocalMaterialAccessUrl = /^(?:https?:\/\/[^/]+)?\/(?:api\/learning\/)?materials\//.test(baseUrl);
  if (!isLocalMaterialAccessUrl) {
    return resourceUrl;
  }
  const separator = baseUrl.includes("?") ? "&" : "?";

  return `${baseUrl}${separator}download=1${fragment}`;
}

import { describe, expect, it } from "vitest";

import { getMaterialDownloadUrl } from "./courseMaterialUrls";

describe("getMaterialDownloadUrl", () => {
  it("adds the explicit download mode to a signed material URL", () => {
    expect(getMaterialDownloadUrl("/api/learning/materials/notes.md?expires=10&signature=abc")).toBe(
      "/api/learning/materials/notes.md?expires=10&signature=abc&download=1"
    );
  });

  it("preserves a URL fragment after the download query parameter", () => {
    expect(getMaterialDownloadUrl("/materials/notes.pdf#view=FitH")).toBe(
      "/materials/notes.pdf?download=1#view=FitH"
    );
  });

  it("does not invalidate a MinIO presigned URL with an unsigned query parameter", () => {
    const url = "/learning-materials/notes.pdf?X-Amz-Signature=abc";

    expect(getMaterialDownloadUrl(url)).toBe(url);
  });
});

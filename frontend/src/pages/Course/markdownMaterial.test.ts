import { describe, expect, it, vi } from "vitest";

import type { CourseMaterial } from "../../types/course";
import {
  isMarkdownMaterial,
  loadMarkdownText,
  type MarkdownFetcher,
} from "./markdownMaterial";

function createMaterial(overrides: Partial<CourseMaterial> = {}): CourseMaterial {
  return {
    materialUuid: "material-1",
    title: "Course notes",
    materialType: "text",
    resourceUrl: "/materials/course-notes",
    sortOrder: 1,
    metadataJson: null,
    ...overrides,
  };
}

describe("Markdown material helpers", () => {
  it("recognizes Markdown from content type and filename metadata", () => {
    expect(
      isMarkdownMaterial(
        createMaterial({ metadataJson: { contentType: "text/markdown" } })
      )
    ).toBe(true);
    expect(
      isMarkdownMaterial(
        createMaterial({ metadataJson: { originalFilename: "lesson-notes.MD" } })
      )
    ).toBe(true);
    expect(
      isMarkdownMaterial(
        createMaterial({ resourceUrl: "/materials/lesson.txt", metadataJson: { contentType: "text/plain" } })
      )
    ).toBe(false);
  });

  it("loads Markdown text through the signed resource URL", async () => {
    const text = vi.fn().mockResolvedValue("# Lesson");
    const request = vi.fn().mockResolvedValue({ ok: true, status: 200, text }) as MarkdownFetcher;

    await expect(loadMarkdownText("/api/learning/materials/lesson.md", undefined, request)).resolves.toBe(
      "# Lesson"
    );
    expect(request).toHaveBeenCalledWith(
      "/api/learning/materials/lesson.md",
      expect.objectContaining({ method: "GET", credentials: "same-origin" })
    );
  });

  it("reports an HTTP failure instead of rendering an error response as Markdown", async () => {
    const request = vi.fn().mockResolvedValue({ ok: false, status: 403 }) as MarkdownFetcher;

    await expect(loadMarkdownText("/expired.md", undefined, request)).rejects.toThrow(
      "Markdown 资料加载失败（403）。"
    );
  });
});

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import {
  MarkdownMaterialDocument,
  MarkdownMaterialViewer,
} from "./MarkdownMaterialViewer";

describe("MarkdownMaterialViewer", () => {
  it("defaults to a preview control and exposes both view choices", () => {
    const markup = renderToStaticMarkup(
      <MarkdownMaterialViewer resourceUrl="/materials/lesson.md" title="Lesson" />
    );

    expect(markup).toContain("Preview");
    expect(markup).toContain("Source");
    expect(markup).toContain('aria-pressed="true"');
    expect(markup).toContain("正在加载 Markdown 预览");
  });

  it("renders formatted Markdown in preview mode and literal text in source mode", () => {
    const content = "# Lesson\n\n- First item";
    const previewMarkup = renderToStaticMarkup(
      <MarkdownMaterialDocument content={content} viewMode="preview" />
    );
    const sourceMarkup = renderToStaticMarkup(
      <MarkdownMaterialDocument content={content} viewMode="source" />
    );

    expect(previewMarkup).toContain("<h1>Lesson</h1>");
    expect(previewMarkup).toContain("<li>First item</li>");
    expect(sourceMarkup).toContain("# Lesson");
    expect(sourceMarkup).not.toContain("<h1>");
  });
});

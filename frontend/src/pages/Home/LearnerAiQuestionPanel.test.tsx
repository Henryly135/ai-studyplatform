import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { LearnerAiQuestionPanel } from "./LearnerAiQuestionPanel";

describe("LearnerAiQuestionPanel", () => {
  it("renders a module-scoped question input and send button", () => {
    const markup = renderToStaticMarkup(
      <LearnerAiQuestionPanel
        courses={[{ value: "course-1", label: "Course one" }]}
        modules={[{ value: "module-1", label: "Module one" }]}
        models={[{ value: "gemini:flash", label: "Gemini Flash", disabled: false }]}
        selectedCourseUuid="course-1"
        selectedModuleUuid="module-1"
        selectedModelId="gemini:flash"
        question=""
        status="可以开始提问。"
        isSending={false}
        onCourseChange={vi.fn()}
        onModuleChange={vi.fn()}
        onModelChange={vi.fn()}
        onQuestionChange={vi.fn()}
        onSubmit={vi.fn()}
      />
    );

    expect(markup).toContain("询问课程内容");
    expect(markup).toContain("发送问题");
    expect(markup).toContain("Module one");
  });
});

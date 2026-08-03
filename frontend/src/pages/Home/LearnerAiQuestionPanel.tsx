import type { FormEvent } from "react";

export type LearnerAiQuestionOption = {
  value: string;
  label: string;
  disabled?: boolean;
};

type LearnerAiQuestionPanelProps = {
  courses: LearnerAiQuestionOption[];
  modules: LearnerAiQuestionOption[];
  models: LearnerAiQuestionOption[];
  selectedCourseUuid: string;
  selectedModuleUuid: string;
  selectedModelId: string;
  question: string;
  status: string;
  isSending: boolean;
  onCourseChange: (value: string) => void;
  onModuleChange: (value: string) => void;
  onModelChange: (value: string) => void;
  onQuestionChange: (value: string) => void;
  onSubmit: () => void;
};

export function LearnerAiQuestionPanel({
  courses,
  modules,
  models,
  selectedCourseUuid,
  selectedModuleUuid,
  selectedModelId,
  question,
  status,
  isSending,
  onCourseChange,
  onModuleChange,
  onModelChange,
  onQuestionChange,
  onSubmit,
}: LearnerAiQuestionPanelProps) {
  const hasUsableSelectedModel = models.some(
    (model) => model.value === selectedModelId && !model.disabled
  );
  const canSubmit = Boolean(
    selectedCourseUuid && selectedModuleUuid && hasUsableSelectedModel && question.trim() && !isSending
  );

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (canSubmit) {
      onSubmit();
    }
  }

  return (
    <form className="home-ai-provider-card" onSubmit={handleSubmit}>
      <div className="home-ai-panel-heading">
        <h2>课程提问</h2>
        <span>基于模块资料</span>
      </div>

      <div className="home-ai-default-model-row">
        <label>
          <span>课程</span>
          <select
            aria-label="提问课程"
            value={selectedCourseUuid}
            onChange={(event) => onCourseChange(event.target.value)}
            disabled={courses.length === 0 || isSending}
          >
            {courses.length === 0 ? <option value="">暂无已加入课程</option> : null}
            {courses.map((course) => (
              <option key={course.value} value={course.value}>
                {course.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="home-ai-default-model-row">
        <label>
          <span>模块</span>
          <select
            aria-label="提问模块"
            value={selectedModuleUuid}
            onChange={(event) => onModuleChange(event.target.value)}
            disabled={modules.length === 0 || isSending}
          >
            {modules.length === 0 ? <option value="">暂无可用模块</option> : null}
            {modules.map((module) => (
              <option key={module.value} value={module.value}>
                {module.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="home-ai-default-model-row">
        <label>
          <span>模型</span>
          <select
            aria-label="提问模型"
            value={selectedModelId}
            onChange={(event) => onModelChange(event.target.value)}
            disabled={models.length === 0 || isSending}
          >
            {models.length === 0 ? <option value="">正在加载可用模型</option> : null}
            {models.map((model) => (
              <option key={model.value} value={model.value} disabled={model.disabled}>
                {model.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="home-ai-provider-actions">
        <input
          aria-label="询问课程内容"
          placeholder="询问课程内容..."
          value={question}
          onChange={(event) => onQuestionChange(event.target.value)}
          disabled={!selectedModuleUuid || isSending}
        />
        <button type="submit" disabled={!canSubmit}>
          {isSending ? "正在发送..." : "发送问题"}
        </button>
      </div>
      <small>{status}</small>
    </form>
  );
}

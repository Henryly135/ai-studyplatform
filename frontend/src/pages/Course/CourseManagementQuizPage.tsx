import { useCallback, useEffect, useState } from "react";
import { Link, Navigate, useOutletContext, useParams } from "react-router-dom";

import ManagementPanel from "../../components/course-management/ManagementPanel";
import type { QuizOptionDraft, QuizQuestionDraft, QuizRecord } from "../../types/course";
import { getQuizAuthoring, listQuizAuthoringQuestions, publishQuiz, upsertQuiz } from "../../services/course";
import { emitAppRefresh } from "../../utils/refreshEvents";
import type { CourseManagementOutletContext } from "./CourseManagementLayout";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const QUESTIONS_PAGE_SIZE = 20;

function optionLabel(index: number): string {
  return String.fromCharCode(65 + index); // 0→A, 1→B, 2→C …
}

function makeEmptyOption(sortOrder: number, index: number): QuizOptionDraft {
  return { optionUuid: null, optionLabel: optionLabel(index), optionText: "", sortOrder, isCorrect: false };
}

function makeEmptyQuestion(sortOrder: number): QuizQuestionDraft {
  return {
    questionUuid: null,
    questionText: "",
    explanationText: "",
    sortOrder,
    isActive: true,
    options: [0, 1, 2, 3].map((i) => makeEmptyOption(i + 1, i)),
  };
}

function getStatusPillClass(status: QuizRecord["status"]) {
  if (status === "published") return "course-management-status-pill-published";
  if (status === "archived") return "course-management-status-pill-archived";
  return "course-management-status-pill-draft";
}

function formatStatus(status: QuizRecord["status"]) {
  if (status === "published") return "Published";
  if (status === "archived") return "Archived";
  return "Draft";
}

// ---------------------------------------------------------------------------
// Question editor (inline expanded form)
// ---------------------------------------------------------------------------

type QuestionEditorProps = {
  question: QuizQuestionDraft;
  index: number;
  onChange: (q: QuizQuestionDraft) => void;
  onDelete: () => void;
  isOnly: boolean;
  defaultExpanded?: boolean;
};

function QuestionEditor({ question, index, onChange, onDelete, isOnly, defaultExpanded = false }: QuestionEditorProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  const setOptionField = (
    optIndex: number,
    field: keyof QuizOptionDraft,
    value: string | boolean | number
  ) => {
    const updatedOptions = question.options.map((o, i) =>
      i === optIndex ? { ...o, [field]: value } : o
    );
    onChange({ ...question, options: updatedOptions });
  };

  const setCorrectOption = (optIndex: number) => {
    const updatedOptions = question.options.map((o, i) => ({
      ...o,
      isCorrect: i === optIndex,
    }));
    onChange({ ...question, options: updatedOptions });
  };

  const addOption = () => {
    if (question.options.length >= 6) return;
    const nextSort = Math.max(0, ...question.options.map((o) => o.sortOrder)) + 1;
    const nextIndex = question.options.length; // A=0, B=1 … next letter
    onChange({ ...question, options: [...question.options, makeEmptyOption(nextSort, nextIndex)] });
  };

  const removeOption = (optIndex: number) => {
    if (question.options.length <= 2) return;
    const remaining = question.options
      .filter((_, i) => i !== optIndex)
      .map((o, i) => ({ ...o, sortOrder: i + 1, optionLabel: optionLabel(i) }));
    const hasCorrect = remaining.some((o) => o.isCorrect);
    onChange({ ...question, options: hasCorrect ? remaining : remaining.map((o, i) => ({ ...o, isCorrect: i === 0 })) });
  };

  const correctCount = question.options.filter((o) => o.isCorrect).length;
  const hasText = question.questionText.trim().length > 0;
  const preview = hasText
    ? question.questionText.slice(0, 60) + (question.questionText.length > 60 ? "…" : "")
    : `Question ${index + 1}`;

  return (
    <div className={`quiz-question-card${question.isActive ? "" : " quiz-question-card-inactive"}`}>
      <div className="quiz-question-header" onClick={() => setExpanded((v) => !v)}>
        <div className="quiz-question-header-left">
          <span className="quiz-question-number">Q{index + 1}</span>
          <span className="quiz-question-preview">{preview}</span>
          {!question.isActive && (
            <span className="quiz-question-badge quiz-question-badge-inactive">Inactive</span>
          )}
          {correctCount !== 1 && hasText && (
            <span className="quiz-question-badge quiz-question-badge-warn">No correct answer</span>
          )}
        </div>
        <div className="quiz-question-header-right">
          <button
            type="button"
            className="quiz-question-toggle"
            aria-label={expanded ? "Collapse question" : "Expand question"}
          >
            {expanded ? "▲" : "▼"}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="quiz-question-body">
          <label className="course-management-field course-management-field-full">
            <span>Question text</span>
            <textarea
              value={question.questionText}
              onChange={(e) => onChange({ ...question, questionText: e.target.value })}
              rows={3}
              placeholder="Enter the question…"
              required
            />
          </label>

          <label className="course-management-field course-management-field-full">
            <span>
              Explanation <small style={{ fontWeight: 400, color: "#64748b" }}>(shown after attempt)</small>
            </span>
            <textarea
              value={question.explanationText}
              onChange={(e) => onChange({ ...question, explanationText: e.target.value })}
              rows={2}
              placeholder="Optional: explain the correct answer…"
            />
          </label>

          <div className="quiz-options-section">
            <div className="quiz-options-header">
              <span>Answer options</span>
              <small style={{ color: "#64748b" }}>Select the correct option</small>
            </div>

            {question.options.map((opt, optIndex) => (
              <div key={optIndex} className={`quiz-option-row${opt.isCorrect ? " quiz-option-row-correct" : ""}`}>
                <label className="quiz-option-radio" title="Mark as correct answer">
                  <input
                    type="radio"
                    name={`correct-${question.sortOrder}`}
                    checked={opt.isCorrect}
                    onChange={() => setCorrectOption(optIndex)}
                  />
                </label>
                <input
                  className="quiz-option-label-input"
                  value={opt.optionLabel}
                  onChange={(e) => setOptionField(optIndex, "optionLabel", e.target.value)}
                  placeholder="A"
                  maxLength={10}
                  title="Option label (e.g. A, B, C)"
                />
                <input
                  className="quiz-option-text-input"
                  value={opt.optionText}
                  onChange={(e) => setOptionField(optIndex, "optionText", e.target.value)}
                  placeholder={`Option ${optIndex + 1}`}
                />
                <button
                  type="button"
                  className="quiz-option-remove"
                  onClick={() => removeOption(optIndex)}
                  disabled={question.options.length <= 2}
                  title="Remove option"
                >
                  ✕
                </button>
              </div>
            ))}

            {question.options.length < 6 && (
              <button type="button" className="quiz-add-option-btn" onClick={addOption}>
                + Add option
              </button>
            )}
          </div>

          <div className="quiz-question-actions">
            <label className="course-management-checkbox">
              <input
                type="checkbox"
                checked={question.isActive}
                onChange={(e) => onChange({ ...question, isActive: e.target.checked })}
              />
              <span>Active (included in question pool)</span>
            </label>
            <button
              type="button"
              className="course-management-action-button"
              onClick={onDelete}
              disabled={isOnly}
              title={isOnly ? "Quiz must have at least one question" : "Delete this question"}
              style={{ marginLeft: "auto", color: "#dc2626", borderColor: "#fca5a5" }}
            >
              Delete question
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

function CourseManagementQuizPage() {
  const { moduleUuid } = useParams();
  const { course, managementSearchSuffix } = useOutletContext<CourseManagementOutletContext>();

  const module = course.modules.find((m) => m.moduleUuid === moduleUuid) ?? null;

  // Quiz state
  const [quiz, setQuiz] = useState<QuizRecord | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Settings form state
  const [title, setTitle] = useState("");
  const [timeLimitMinutes, setTimeLimitMinutes] = useState("");
  const [timeLimitSecs, setTimeLimitSecs] = useState("");
  const [questionCountPerAttempt, setQuestionCountPerAttempt] = useState("1");
  const [shuffleQuestions, setShuffleQuestions] = useState(true);
  const [shuffleOptions, setShuffleOptions] = useState(false);

  // Questions state
  const [questions, setQuestions] = useState<QuizQuestionDraft[]>([]);
  const [questionPage, setQuestionPage] = useState(1);
  const [questionTotal, setQuestionTotal] = useState(0);
  const [questionTotalPages, setQuestionTotalPages] = useState(1);
  const [questionSearch, setQuestionSearch] = useState("");
  const [appliedQuestionSearch, setAppliedQuestionSearch] = useState("");
  const [isLoadingQuestions, setIsLoadingQuestions] = useState(false);
  const [questionLoadError, setQuestionLoadError] = useState<string | null>(null);
  // UUIDs of previously-saved questions pending deletion (sent as isActive=false on next save)
  const [pendingDeletions, setPendingDeletions] = useState<QuizQuestionDraft[]>([]);

  // Save state
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);

  // Publish state
  const [isPublishing, setIsPublishing] = useState(false);
  const [publishError, setPublishError] = useState<string | null>(null);

  const loadQuestionPage = useCallback(
    async (page: number, query: string) => {
      if (!module) return;

      setIsLoadingQuestions(true);
      setQuestionLoadError(null);
      try {
        const loadedPage = await listQuizAuthoringQuestions(course.courseUuid, module.moduleUuid, {
          page,
          pageSize: QUESTIONS_PAGE_SIZE,
          query,
        });
        setQuestions(loadedPage.items);
        setQuestionPage(loadedPage.page);
        setQuestionTotal(loadedPage.total);
        setQuestionTotalPages(loadedPage.totalPages);
      } catch (err) {
        setQuestionLoadError(err instanceof Error ? err.message : "Failed to load quiz questions.");
      } finally {
        setIsLoadingQuestions(false);
      }
    },
    [course.courseUuid, module]
  );

  useEffect(() => {
    if (!module) return;

    setIsLoading(true);
    setLoadError(null);
    setQuestions([]);
    setQuestionPage(1);
    setQuestionTotal(0);
    setQuestionTotalPages(1);
    setQuestionSearch("");
    setAppliedQuestionSearch("");
    setQuestionLoadError(null);

    getQuizAuthoring(course.courseUuid, module.moduleUuid, { includeQuestions: false })
      .then((loaded) => {
        if (loaded) {
          setQuiz(loaded);
          setTitle(loaded.title);
          if (loaded.timeLimitSeconds) {
            setTimeLimitMinutes(String(Math.floor(loaded.timeLimitSeconds / 60)));
            setTimeLimitSecs(String(loaded.timeLimitSeconds % 60));
          } else {
            setTimeLimitMinutes("");
            setTimeLimitSecs("");
          }
          setQuestionCountPerAttempt(String(loaded.questionCountPerAttempt));
          setShuffleQuestions(loaded.shuffleQuestions);
          setShuffleOptions(loaded.shuffleOptions);
          setQuestionTotal(loaded.availableQuestionCount);
          setPendingDeletions([]);
          void loadQuestionPage(1, "");
        } else {
          // No quiz yet — defaults are fine
          setQuiz(null);
        }
      })
      .catch((err) => {
        setLoadError(err instanceof Error ? err.message : "Failed to load quiz.");
      })
      .finally(() => setIsLoading(false));
  }, [course.courseUuid, loadQuestionPage, module]);

  if (!module) {
    return <Navigate to={`/course/${course.courseUuid}/management/modules${managementSearchSuffix}`} replace />;
  }

  // -------------------------------------------------------------------------
  // Handlers
  // -------------------------------------------------------------------------

  const addQuestion = () => {
    const localMaxSort = questions.length > 0 ? Math.max(...questions.map((q) => q.sortOrder)) : 0;
    const nextSort = Math.max(localMaxSort, questionTotal) + 1;
    setQuestions([...questions, makeEmptyQuestion(nextSort)]);
    setQuestionTotal((total) => total + 1);
  };

  const updateQuestion = (index: number, q: QuizQuestionDraft) => {
    setQuestions(questions.map((existing, i) => (i === index ? q : existing)));
  };

  const deleteQuestion = (index: number) => {
    const q = questions[index];
    if (q.questionUuid) {
      // Already saved — queue for archiving on next save; keep original sortOrder to avoid conflicts
      setPendingDeletions((prev) => [...prev, { ...q, isActive: false }]);
    }
    setQuestions(questions.filter((_, i) => i !== index));
    setQuestionTotal((total) => Math.max(0, total - 1));
  };

  const handleQuestionSearch = () => {
    const normalizedQuery = questionSearch.trim();
    setAppliedQuestionSearch(normalizedQuery);
    void loadQuestionPage(1, normalizedQuery);
  };

  const clearQuestionSearch = () => {
    setQuestionSearch("");
    setAppliedQuestionSearch("");
    void loadQuestionPage(1, "");
  };

  const goToQuestionPage = (page: number) => {
    const safePage = Math.min(Math.max(1, page), questionTotalPages);
    void loadQuestionPage(safePage, appliedQuestionSearch);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaveError(null);
    setSaveSuccess(null);
    setPublishError(null);

    // Frontend validation
    for (let i = 0; i < questions.length; i++) {
      const q = questions[i];
      if (!q.questionText.trim()) {
        setSaveError(`Question ${i + 1} is missing question text.`);
        return;
      }
      const correctCount = q.options.filter((o) => o.isCorrect).length;
      if (correctCount !== 1) {
        setSaveError(`Question ${i + 1} must have exactly one correct answer selected.`);
        return;
      }
      for (let j = 0; j < q.options.length; j++) {
        if (!q.options[j].optionText.trim()) {
          setSaveError(`Question ${i + 1}, option ${j + 1} is missing option text.`);
          return;
        }
      }
    }

    setIsSaving(true);

    const mins = Number(timeLimitMinutes) || 0;
    const secs = Number(timeLimitSecs) || 0;
    const totalSeconds = mins * 60 + secs || null;

    try {
      const saved = await upsertQuiz(course.courseUuid, module.moduleUuid, {
        title: title.trim() || "Quiz",
        description: null,
        timeLimitSeconds: totalSeconds,
        questionCountPerAttempt: Number(questionCountPerAttempt) || 1,
        shuffleQuestions,
        shuffleOptions,
        questions: [...pendingDeletions, ...questions],
      }, { includeQuestions: false });
      setQuiz(saved);
      setPendingDeletions([]);
      await loadQuestionPage(questionPage, appliedQuestionSearch);
      emitAppRefresh({ scope: "course:quiz", courseUuid: course.courseUuid, moduleUuid: module.moduleUuid });
      setSaveSuccess("Quiz saved successfully.");
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save quiz.");
    } finally {
      setIsSaving(false);
    }
  };

  const handlePublish = async (targetStatus: "published" | "draft") => {
    if (!quiz) {
      setPublishError("Save the quiz first before publishing.");
      return;
    }
    setIsPublishing(true);
    setPublishError(null);
    setSaveSuccess(null);

    try {
      const updated = await publishQuiz(course.courseUuid, module.moduleUuid, targetStatus, { includeQuestions: false });
      setQuiz(updated);
      emitAppRefresh({ scope: "course:quiz", courseUuid: course.courseUuid, moduleUuid: module.moduleUuid });
      emitAppRefresh({ scope: "course:detail", courseUuid: course.courseUuid, moduleUuid: module.moduleUuid });
    } catch (err) {
      setPublishError(err instanceof Error ? err.message : "Failed to update quiz status.");
    } finally {
      setIsPublishing(false);
    }
  };

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  const isPublished = quiz?.status === "published";
  const activeCount = quiz?.availableQuestionCount ?? questions.filter((q) => q.isActive).length;
  const qcpa = Number(questionCountPerAttempt) || 1;
  const isCoursePublished = course.status?.toLowerCase() === "published";
  const isModulePublished = module?.status === "available";
  const canPublish = quiz !== null && activeCount >= qcpa && isCoursePublished && isModulePublished;

  return (
    <section className="course-management-page">
      <Link
        to={`/course/${course.courseUuid}/management/modules/${module.moduleUuid}${managementSearchSuffix}`}
        className="course-management-back-link"
      >
        Back to module
      </Link>

      <div className="course-management-section-heading">
        <div>
          <span className="course-surface-badge">Quiz Editor</span>
          <div className="course-management-title-row">
            <h1>{module.title}</h1>
            {quiz && (
              <span className={`course-management-status-pill ${getStatusPillClass(quiz.status)}`}>
                {formatStatus(quiz.status)}
              </span>
            )}
          </div>
          <p>Create and manage multiple-choice questions for this module's quiz.</p>
        </div>
      </div>

      {isLoading && <p style={{ padding: "1rem", color: "#64748b" }}>Loading quiz…</p>}

      {loadError && (
        <div className="course-management-inline-alert">
          <strong>Failed to load quiz.</strong>
          <span>{loadError}</span>
        </div>
      )}

      {!isLoading && (
        <form onSubmit={handleSave}>
          {/* Settings panel — full width single row */}
          <ManagementPanel title="Quiz settings" style={{ marginBottom: "1.25rem" }}>
            <div className="course-management-form">
              <label className="course-management-field course-management-field-full">
                <span>Quiz title</span>
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g. Module 1 Knowledge Check"
                  required
                />
              </label>

              <div className="course-management-field">
                <span>
                  Time limit{" "}
                  <small style={{ fontWeight: 400, color: "#64748b" }}>(leave blank for no limit)</small>
                </span>
                <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                  <input
                    type="number"
                    min="0"
                    value={timeLimitMinutes}
                    onChange={(e) => setTimeLimitMinutes(e.target.value)}
                    placeholder="0"
                    style={{ width: "5rem" }}
                  />
                  <span style={{ color: "#64748b", fontSize: "0.875rem" }}>min</span>
                  <input
                    type="number"
                    min="0"
                    max="59"
                    value={timeLimitSecs}
                    onChange={(e) => setTimeLimitSecs(e.target.value)}
                    placeholder="0"
                    style={{ width: "5rem" }}
                  />
                  <span style={{ color: "#64748b", fontSize: "0.875rem" }}>sec</span>
                </div>
              </div>

              <label className="course-management-field">
                <span>Number of questions randomly selected for quiz per attempt</span>
                <input
                  type="number"
                  min="1"
                  value={questionCountPerAttempt}
                  onChange={(e) => setQuestionCountPerAttempt(e.target.value)}
                  required
                />
              </label>

              <label className="course-management-checkbox">
                <input
                  type="checkbox"
                  checked={shuffleQuestions}
                  onChange={(e) => setShuffleQuestions(e.target.checked)}
                />
                <span>Shuffle question order each attempt</span>
              </label>
            </div>
          </ManagementPanel>

          {/* Questions */}
          <ManagementPanel title={`Questions (${questionTotal})`} style={{ marginBottom: "1.25rem" }}>
            <div
              style={{
                display: "flex",
                gap: "0.75rem",
                alignItems: "center",
                justifyContent: "space-between",
                flexWrap: "wrap",
                marginBottom: "1rem",
              }}
            >
              <label className="course-management-field" style={{ flex: "1 1 18rem", margin: 0 }}>
                <span>Search question pool</span>
                <input
                  value={questionSearch}
                  onChange={(e) => setQuestionSearch(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      handleQuestionSearch();
                    }
                  }}
                  placeholder="Search question text or explanation"
                />
              </label>
              <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", marginTop: "1.55rem" }}>
                <button type="button" className="course-management-action-button" disabled={isLoadingQuestions} onClick={handleQuestionSearch}>
                  Search
                </button>
                {appliedQuestionSearch && (
                  <button
                    type="button"
                    className="course-management-action-button"
                    onClick={clearQuestionSearch}
                    disabled={isLoadingQuestions}
                  >
                    Clear
                  </button>
                )}
              </div>
            </div>

            {questionLoadError && (
              <div className="course-management-inline-alert" style={{ marginBottom: "1rem" }}>
                <strong>Failed to load questions.</strong>
                <span>{questionLoadError}</span>
              </div>
            )}

            {isLoadingQuestions && (
              <p style={{ padding: "0.5rem 0", color: "#64748b" }}>Loading questions...</p>
            )}

            <div className="quiz-questions-list">
              {!isLoadingQuestions && questions.length === 0 && (
                <p style={{ color: "#64748b", margin: 0 }}>
                  {appliedQuestionSearch ? "No questions match this search." : "No questions in this pool yet."}
                </p>
              )}

              {questions.map((q, index) => (
                <QuestionEditor
                  key={q.questionUuid ?? index}
                  question={q}
                  index={index}
                  onChange={(updated) => updateQuestion(index, updated)}
                  onDelete={() => deleteQuestion(index)}
                  isOnly={false}
                  defaultExpanded={!q.questionUuid}
                />
              ))}

              <button type="button" className="quiz-add-question-btn" onClick={addQuestion}>
                + Add question
              </button>
            </div>

            <div className="course-pagination" style={{ marginTop: "1rem" }}>
              <span className="course-pagination-summary">
                Page {questionPage} of {questionTotalPages} · {questionTotal} question{questionTotal === 1 ? "" : "s"}
              </span>
              <div className="course-pagination-nav">
                <button
                  type="button"
                  className="course-pagination-button"
                  onClick={() => goToQuestionPage(questionPage - 1)}
                  disabled={isLoadingQuestions || questionPage <= 1}
                >
                  Previous
                </button>
                <button
                  type="button"
                  className="course-pagination-button"
                  onClick={() => goToQuestionPage(questionPage + 1)}
                  disabled={isLoadingQuestions || questionPage >= questionTotalPages}
                >
                  Next
                </button>
              </div>
            </div>

            <div className="course-management-form-actions" style={{ marginTop: "1.25rem" }}>
              {saveError && (
                <div className="course-management-inline-alert" style={{ flex: 1 }}>
                  <strong>Unable to save quiz.</strong>
                  <span>{saveError}</span>
                </div>
              )}
              {saveSuccess && (
                <p className="course-management-inline-success" style={{ flex: 1 }}>
                  {saveSuccess}
                </p>
              )}
              <button
                type="submit"
                className="course-management-action-button course-management-action-button-primary"
                disabled={isSaving}
              >
                {isSaving ? "Saving…" : quiz ? "Save changes" : "Create quiz"}
              </button>
            </div>
          </ManagementPanel>

          {/* Publish panel — at the bottom */}
          <ManagementPanel title="Publishing">
            <div className="course-management-form course-management-form-single">
              <div className="course-management-inline-note course-management-field-full">
                <strong>Active questions: {activeCount} / {questions.length}</strong>
                <span>
                  To publish, you need at least {qcpa} active question{qcpa !== 1 ? "s" : ""} (matching
                  &quot;questions per attempt&quot;), each with ≥2 options and exactly 1 correct answer.
                </span>
              </div>

              {!isCoursePublished && !isPublished && (
                <div className="course-management-inline-alert course-management-field-full">
                  <strong>Course not published.</strong>
                  <span>The course must be published before this quiz can be published.</span>
                </div>
              )}
              {isCoursePublished && !isModulePublished && !isPublished && (
                <div className="course-management-inline-alert course-management-field-full">
                  <strong>Module not published.</strong>
                  <span>The module must be published before this quiz can be published.</span>
                </div>
              )}

              {publishError && (
                <div className="course-management-inline-alert course-management-field-full">
                  <strong>Unable to update status.</strong>
                  <span>{publishError}</span>
                </div>
              )}

              <div className="course-management-form-actions course-management-field-full">
                {!isPublished ? (
                  <button
                    type="button"
                    className="course-management-action-button course-management-action-button-primary"
                    onClick={() => handlePublish("published")}
                    disabled={isPublishing || !canPublish}
                    title={canPublish ? undefined : "Save quiz and ensure enough active questions first"}
                  >
                    {isPublishing ? "Publishing…" : "Publish quiz"}
                  </button>
                ) : (
                  <button
                    type="button"
                    className="course-management-action-button"
                    onClick={() => handlePublish("draft")}
                    disabled={isPublishing}
                  >
                    {isPublishing ? "Unpublishing…" : "Unpublish quiz"}
                  </button>
                )}
              </div>
            </div>
          </ManagementPanel>
        </form>
      )}
    </section>
  );
}

export default CourseManagementQuizPage;

import { useCallback, useEffect, useState } from "react";
import { Link, Navigate, useOutletContext, useParams } from "react-router-dom";

import ManagementPanel from "../../components/course-management/ManagementPanel";
import {
  getManagedShortAnswerAssessment,
  listManagedShortAnswerSubmissions,
  reviewShortAnswerSubmission,
  upsertManagedShortAnswerAssessment,
} from "../../services/course";
import type { ShortAnswerAssessmentRecord, ShortAnswerSubmissionRecord } from "../../types/course";
import type { CourseManagementOutletContext } from "./CourseManagementLayout";

type ReviewFormState = {
  finalScore: string;
  finalFeedbackText: string;
  reviewNotes: string;
};

function reviewFormFromSubmission(submission: ShortAnswerSubmissionRecord): ReviewFormState {
  return {
    finalScore: String(submission.finalScore ?? submission.aiSuggestion.scoreSuggestion ?? ""),
    finalFeedbackText: submission.finalFeedbackText ?? submission.aiSuggestion.feedbackText ?? "",
    reviewNotes: submission.reviewNotes ?? "",
  };
}

function CourseManagementShortAnswerPage() {
  const { moduleUuid } = useParams();
  const { course, managementSearchSuffix } = useOutletContext<CourseManagementOutletContext>();
  const module = course.modules.find((item) => item.moduleUuid === moduleUuid) ?? null;
  const [assessment, setAssessment] = useState<ShortAnswerAssessmentRecord | null>(null);
  const [title, setTitle] = useState("");
  const [promptText, setPromptText] = useState("");
  const [rubricText, setRubricText] = useState("");
  const [maxScore, setMaxScore] = useState("10");
  const [statusValue, setStatusValue] = useState<ShortAnswerAssessmentRecord["status"]>("draft");
  const [submissions, setSubmissions] = useState<ShortAnswerSubmissionRecord[]>([]);
  const [reviewForms, setReviewForms] = useState<Record<string, ReviewFormState>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [savingReviewUuid, setSavingReviewUuid] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const loadSubmissions = useCallback(async () => {
    if (!module) return;
    const loaded = await listManagedShortAnswerSubmissions(course.courseUuid, module.moduleUuid);
    setSubmissions(loaded);
    setReviewForms(Object.fromEntries(loaded.map((submission) => [submission.submissionUuid, reviewFormFromSubmission(submission)])));
  }, [course.courseUuid, module]);

  useEffect(() => {
    if (!module) return;
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    getManagedShortAnswerAssessment(course.courseUuid, module.moduleUuid)
      .then(async (loaded) => {
        if (cancelled) return;
        setAssessment(loaded);
        setTitle(loaded?.title ?? `${module.title} Short Answer`);
        setPromptText(loaded?.promptText ?? "");
        setRubricText(loaded?.rubricText ?? "");
        setMaxScore(String(loaded?.maxScore ?? 10));
        setStatusValue(loaded?.status ?? "draft");
        if (loaded) {
          await loadSubmissions();
        } else {
          setSubmissions([]);
          setReviewForms({});
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load short-answer assessment.");
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [course.courseUuid, loadSubmissions, module]);

  if (!module) {
    return <Navigate to={`/course/${course.courseUuid}/management/modules${managementSearchSuffix}`} replace />;
  }

  const handleSave = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setSuccess(null);
    if (!title.trim() || !promptText.trim() || !rubricText.trim()) {
      setError("Title, prompt, and rubric are required.");
      return;
    }
    const parsedMaxScore = Number(maxScore);
    if (!Number.isFinite(parsedMaxScore) || parsedMaxScore < 1 || parsedMaxScore > 100) {
      setError("Max score must be between 1 and 100.");
      return;
    }
    setIsSaving(true);
    try {
      const saved = await upsertManagedShortAnswerAssessment(course.courseUuid, module.moduleUuid, {
        title,
        promptText,
        rubricText,
        maxScore: parsedMaxScore,
        status: statusValue,
      });
      setAssessment(saved);
      setSuccess("Short-answer assessment saved.");
      await loadSubmissions();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save short-answer assessment.");
    } finally {
      setIsSaving(false);
    }
  };

  const updateReviewForm = (submissionUuid: string, field: keyof ReviewFormState, value: string) => {
    setReviewForms((current) => ({
      ...current,
      [submissionUuid]: {
        ...(current[submissionUuid] ?? { finalScore: "", finalFeedbackText: "", reviewNotes: "" }),
        [field]: value,
      },
    }));
  };

  const handleReview = async (submission: ShortAnswerSubmissionRecord) => {
    const form = reviewForms[submission.submissionUuid] ?? reviewFormFromSubmission(submission);
    const score = Number(form.finalScore);
    if (!assessment || !Number.isFinite(score) || score < 0 || score > assessment.maxScore) {
      setError("Final score must be within this assessment's max score.");
      return;
    }
    if (!form.finalFeedbackText.trim()) {
      setError("Final feedback is required.");
      return;
    }
    setSavingReviewUuid(submission.submissionUuid);
    setError(null);
    setSuccess(null);
    try {
      await reviewShortAnswerSubmission(course.courseUuid, module.moduleUuid, submission.submissionUuid, {
        finalScore: score,
        finalFeedbackText: form.finalFeedbackText,
        reviewNotes: form.reviewNotes,
      });
      setSuccess("Submission review saved.");
      await loadSubmissions();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to review submission.");
    } finally {
      setSavingReviewUuid(null);
    }
  };

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
          <span className="course-surface-badge">Short Answer</span>
          <h1>{module.title}</h1>
          <p>Create a rubric-based short-answer task and review learner submissions.</p>
        </div>
      </div>

      {isLoading ? <p style={{ color: "#64748b" }}>Loading short-answer assessment...</p> : null}

      <form onSubmit={handleSave}>
        <ManagementPanel title="Assessment setup" style={{ marginBottom: "1.25rem" }}>
          <div className="course-management-form">
            <label className="course-management-field course-management-field-full">
              <span>Title</span>
              <input value={title} onChange={(event) => setTitle(event.target.value)} required />
            </label>
            <label className="course-management-field course-management-field-full">
              <span>Prompt</span>
              <textarea value={promptText} onChange={(event) => setPromptText(event.target.value)} rows={4} required />
            </label>
            <label className="course-management-field course-management-field-full">
              <span>Rubric</span>
              <textarea value={rubricText} onChange={(event) => setRubricText(event.target.value)} rows={5} required />
            </label>
            <label className="course-management-field">
              <span>Max score</span>
              <input type="number" min="1" max="100" step="0.5" value={maxScore} onChange={(event) => setMaxScore(event.target.value)} />
            </label>
            <label className="course-management-field">
              <span>Status</span>
              <select value={statusValue} onChange={(event) => setStatusValue(event.target.value as ShortAnswerAssessmentRecord["status"])}>
                <option value="draft">Draft</option>
                <option value="published">Published</option>
                <option value="archived">Archived</option>
              </select>
            </label>
            {error ? (
              <div className="course-management-inline-alert course-management-field-full">
                <strong>Short-answer error.</strong>
                <span>{error}</span>
              </div>
            ) : null}
            {success ? <p className="course-management-inline-success course-management-field-full">{success}</p> : null}
            <div className="course-management-form-actions course-management-field-full">
              <button type="submit" className="course-management-action-button course-management-action-button-primary" disabled={isSaving}>
                {isSaving ? "Saving..." : assessment ? "Save changes" : "Create assessment"}
              </button>
            </div>
          </div>
        </ManagementPanel>
      </form>

      <ManagementPanel title={`Submissions (${submissions.length})`}>
        <div className="quiz-questions-list">
          {submissions.length === 0 ? <p style={{ color: "#64748b", margin: 0 }}>No learner submissions yet.</p> : null}
          {submissions.map((submission) => {
            const form = reviewForms[submission.submissionUuid] ?? reviewFormFromSubmission(submission);
            return (
              <article key={submission.submissionUuid} className="quiz-question-card">
                <div className="quiz-question-header">
                  <div className="quiz-question-header-left">
                    <span className="quiz-question-number">{submission.status}</span>
                    <span className="quiz-question-preview">Learner {submission.learnerId}</span>
                  </div>
                </div>
                <div className="quiz-question-body">
                  <div className="course-management-inline-note">
                    <strong>Answer</strong>
                    <span>{submission.answerText}</span>
                  </div>
                  <div className="course-management-inline-note">
                    <strong>AI suggestion: {submission.aiSuggestion.scoreSuggestion ?? "Pending"} / {assessment?.maxScore ?? Number(maxScore)}</strong>
                    <span>{submission.aiSuggestion.feedbackText ?? "No AI feedback returned."}</span>
                  </div>
                  <div className="course-management-form">
                    <label className="course-management-field">
                      <span>Final score</span>
                      <input
                        type="number"
                        min="0"
                        max={assessment?.maxScore ?? Number(maxScore)}
                        step="0.5"
                        value={form.finalScore}
                        onChange={(event) => updateReviewForm(submission.submissionUuid, "finalScore", event.target.value)}
                      />
                    </label>
                    <label className="course-management-field course-management-field-full">
                      <span>Final feedback</span>
                      <textarea
                        rows={3}
                        value={form.finalFeedbackText}
                        onChange={(event) => updateReviewForm(submission.submissionUuid, "finalFeedbackText", event.target.value)}
                      />
                    </label>
                    <label className="course-management-field course-management-field-full">
                      <span>Private review notes</span>
                      <textarea
                        rows={2}
                        value={form.reviewNotes}
                        onChange={(event) => updateReviewForm(submission.submissionUuid, "reviewNotes", event.target.value)}
                      />
                    </label>
                    <div className="course-management-form-actions course-management-field-full">
                      <button
                        type="button"
                        className="course-management-action-button course-management-action-button-primary"
                        onClick={() => void handleReview(submission)}
                        disabled={savingReviewUuid === submission.submissionUuid}
                      >
                        {savingReviewUuid === submission.submissionUuid ? "Saving review..." : "Save review"}
                      </button>
                    </div>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      </ManagementPanel>
    </section>
  );
}

export default CourseManagementShortAnswerPage;

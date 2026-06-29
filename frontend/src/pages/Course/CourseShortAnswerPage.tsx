import { useEffect, useState } from "react";
import { Link, Navigate, useOutletContext, useParams } from "react-router-dom";

import { getLearnerShortAnswerAssessment, submitShortAnswer } from "../../services/course";
import type { ShortAnswerLearnerAssessment, ShortAnswerSubmissionRecord } from "../../types/course";
import type { CourseOutletContext } from "./CourseLayout";

function formatScore(score: number | null, maxScore: number) {
  return score === null ? "Pending" : `${score.toFixed(2)} / ${maxScore.toFixed(2)}`;
}

function CourseShortAnswerPage() {
  const { moduleUuid } = useParams();
  const { course } = useOutletContext<CourseOutletContext>();
  const module = course.modules.find((item) => item.moduleUuid === moduleUuid);
  const [state, setState] = useState<ShortAnswerLearnerAssessment | null>(null);
  const [submission, setSubmission] = useState<ShortAnswerSubmissionRecord | null>(null);
  const [answerText, setAnswerText] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!moduleUuid) return;
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    getLearnerShortAnswerAssessment(course.courseUuid, moduleUuid)
      .then((loaded) => {
        if (cancelled) return;
        setState(loaded);
        setSubmission(loaded?.latestSubmission ?? null);
        setAnswerText(loaded?.latestSubmission?.answerText ?? "");
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
  }, [course.courseUuid, moduleUuid]);

  if (!module) {
    return <Navigate to={`/course/${course.courseUuid}`} replace />;
  }

  const assessment = state?.assessment ?? null;

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!moduleUuid || !answerText.trim()) {
      setError("Write an answer before submitting.");
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      const saved = await submitShortAnswer(course.courseUuid, moduleUuid, answerText);
      setSubmission(saved);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit short-answer response.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section className="course-detail-page">
      <Link to={`/course/${course.courseUuid}/modules/${module.moduleUuid}`} className="course-management-back-link">
        Back to module
      </Link>

      <div className="course-module-hero">
        <span className="course-surface-badge">Short answer</span>
        <h1>{assessment?.title ?? module.title}</h1>
        <p>{assessment?.promptText ?? "No short-answer assessment is available for this module yet."}</p>
      </div>

      {isLoading ? <p style={{ color: "#64748b" }}>Loading assessment...</p> : null}

      {!isLoading && !assessment ? (
        <article className="course-panel">
          <div className="course-panel-heading">
            <h3>No short-answer assessment</h3>
          </div>
          <p>This module does not currently have a published short-answer task.</p>
        </article>
      ) : null}

      {assessment ? (
        <div className="course-detail-grid">
          <article className="course-panel">
            <div className="course-panel-heading">
              <h3>Rubric</h3>
            </div>
            <p>{assessment.rubricText}</p>
            <p>Maximum score: {assessment.maxScore.toFixed(2)}</p>
          </article>

          <article className="course-panel">
            <div className="course-panel-heading">
              <h3>Your response</h3>
            </div>
            <form onSubmit={handleSubmit} className="course-management-form course-management-form-single">
              <label className="course-management-field course-management-field-full">
                <span>Answer</span>
                <textarea
                  value={answerText}
                  onChange={(event) => setAnswerText(event.target.value)}
                  rows={8}
                  placeholder="Write your response..."
                  required
                />
              </label>
              {error ? (
                <div className="course-management-inline-alert course-management-field-full">
                  <strong>Short-answer error.</strong>
                  <span>{error}</span>
                </div>
              ) : null}
              <div className="course-management-form-actions course-management-field-full">
                <button
                  type="submit"
                  className="course-management-action-button course-management-action-button-primary"
                  disabled={isSubmitting}
                >
                  {isSubmitting ? "Submitting..." : submission ? "Submit new response" : "Submit response"}
                </button>
              </div>
            </form>
          </article>
        </div>
      ) : null}

      {assessment && submission ? (
        <article className="course-panel" style={{ marginTop: "1.25rem" }}>
          <div className="course-panel-heading">
            <h3>Feedback</h3>
          </div>
          <p>Status: {submission.status}</p>
          <p>AI suggested score: {formatScore(submission.aiSuggestion.scoreSuggestion, assessment.maxScore)}</p>
          {submission.aiSuggestion.feedbackText ? <p>{submission.aiSuggestion.feedbackText}</p> : null}
          {submission.aiSuggestion.strengths.length > 0 ? (
            <p>Strengths: {submission.aiSuggestion.strengths.join(" ")}</p>
          ) : null}
          {submission.aiSuggestion.improvements.length > 0 ? (
            <p>Improvements: {submission.aiSuggestion.improvements.join(" ")}</p>
          ) : null}
          {submission.status === "reviewed" ? (
            <div className="course-management-inline-success">
              <strong>Educator final score: {formatScore(submission.finalScore, assessment.maxScore)}</strong>
              <span>{submission.finalFeedbackText}</span>
            </div>
          ) : (
            <p style={{ color: "#64748b" }}>Your educator has not released final feedback yet.</p>
          )}
        </article>
      ) : null}
    </section>
  );
}

export default CourseShortAnswerPage;

import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  getEducatorAnalytics,
  getEducatorQuizAnalytics,
  getEducatorTeachingInsights,
} from "../../services/course";
import type {
  AssessmentSignalInsightItem,
  AtRiskLearnerInsightItem,
  CompletionTrendInsightItem,
  EducatorAnalytics,
  EducatorCourseAnalyticsItem,
  EducatorQuizAnalytics,
  EducatorTeachingInsights,
  ModuleBottleneckInsightItem,
  QuizModuleStatsItem,
} from "../../types/course";
import "../Course/CoursePages.css";

function formatStatus(status: string) {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function formatProgress(value: number | null) {
  if (value === null || !Number.isFinite(value)) return "—";
  return `${Math.round(value)}%`;
}

function formatPassRate(value: number | null) {
  if (value === null || !Number.isFinite(value)) return "—";
  return `${Math.round(value * 100)}%`;
}

function formatDuration(seconds: number | null) {
  if (seconds === null || !Number.isFinite(seconds)) return "—";
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
}

function formatDate(value: string | null) {
  if (!value) return "—";
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function formatSignalLabel(value: string) {
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatScore(value: number | null, maxScore: number | null) {
  if (value === null || !Number.isFinite(value)) return "—";
  if (maxScore !== null && Number.isFinite(maxScore)) return `${value.toFixed(1)} / ${maxScore.toFixed(0)}`;
  return value.toFixed(1);
}

function getStatusClassName(status: string) {
  if (status === "published") return "course-management-enrolment-status";
  return undefined;
}

function CourseAnalyticsRow({ item }: { item: EducatorCourseAnalyticsItem }) {
  const completionRate =
    item.totalEnrollments > 0
      ? Math.round((item.completedEnrollments / item.totalEnrollments) * 100)
      : null;

  return (
    <article className="course-management-panel course-management-enrolment-card">
      <div className="course-management-enrolment-summary course-management-enrolment-summary-single-row">
        <strong>
          <Link
            to={`/course/${item.courseUuid}/management`}
            style={{ color: "inherit", textDecoration: "none" }}
          >
            {item.courseTitle}
          </Link>
        </strong>
        <span>{item.totalEnrollments} enrolled</span>
        <span>{item.activeEnrollments} active · {item.completedEnrollments} completed</span>
        <div className="course-management-enrolment-actions">
          <span className={getStatusClassName(item.status)}>
            {formatStatus(item.status)}
          </span>
        </div>
      </div>
      <div className="course-management-enrolment-grid">
        <div className="course-management-key-value">
          <span>Total enrolled</span>
          <strong>{item.totalEnrollments}</strong>
        </div>
        <div className="course-management-key-value">
          <span>Active learners</span>
          <strong>{item.activeEnrollments}</strong>
        </div>
        <div className="course-management-key-value">
          <span>Completed</span>
          <strong>{item.completedEnrollments}</strong>
        </div>
        <div className="course-management-key-value">
          <span>Completion rate</span>
          <strong>{completionRate !== null ? `${completionRate}%` : "—"}</strong>
        </div>
        <div className="course-management-key-value">
          <span>Avg progress</span>
          <strong>{formatProgress(item.avgProgressPercent)}</strong>
        </div>
        <div className="course-management-key-value">
          <span>Status</span>
          <strong>{formatStatus(item.status)}</strong>
        </div>
      </div>
    </article>
  );
}

function QuizStatsRow({ item }: { item: QuizModuleStatsItem }) {
  return (
    <article className="course-management-panel course-management-enrolment-card">
      <div className="course-management-enrolment-summary course-management-enrolment-summary-single-row">
        <strong>{item.courseTitle}</strong>
        <span>{item.moduleTitle}</span>
        <span>{item.quizTitle}</span>
        <div className="course-management-enrolment-actions">
          <span style={{ fontSize: "0.8rem", color: "#475569" }}>
            {item.totalAttempts} attempt{item.totalAttempts !== 1 ? "s" : ""}
          </span>
        </div>
      </div>
      <div className="course-management-enrolment-grid">
        <div className="course-management-key-value">
          <span>Total attempts</span>
          <strong>{item.totalAttempts}</strong>
        </div>
        <div className="course-management-key-value">
          <span>Unique learners</span>
          <strong>{item.uniqueLearners}</strong>
        </div>
        <div className="course-management-key-value">
          <span>Avg score</span>
          <strong>{item.totalAttempts === 0 ? "No attempt" : formatProgress(item.avgScorePercent)}</strong>
        </div>
        <div className="course-management-key-value">
          <span>Pass rate</span>
          <strong>{item.totalAttempts === 0 ? "No attempt" : formatPassRate(item.passRate)}</strong>
        </div>
        <div className="course-management-key-value">
          <span>Avg duration</span>
          <strong>{item.totalAttempts === 0 ? "No attempt" : formatDuration(item.avgDurationSeconds)}</strong>
        </div>
      </div>
    </article>
  );
}

function QuizSection({
  quizAnalytics,
  courses,
}: {
  quizAnalytics: EducatorQuizAnalytics;
  courses: EducatorCourseAnalyticsItem[];
}) {
  const [selectedCourseUuid, setSelectedCourseUuid] = useState<string>("all");

  const filteredItems = useMemo(() => {
    if (selectedCourseUuid === "all") return quizAnalytics.items;
    return quizAnalytics.items.filter((item) => item.courseUuid === selectedCourseUuid);
  }, [quizAnalytics.items, selectedCourseUuid]);

  return (
    <>
      <div className="course-management-toolbar" style={{ marginTop: "1.5rem" }}>
        <strong>Quiz performance</strong>
        <select
          value={selectedCourseUuid}
          onChange={(e) => setSelectedCourseUuid(e.target.value)}
          style={{
            fontSize: "0.84rem",
            padding: "0.25rem 0.5rem",
            border: "1px solid #dbe4ef",
            borderRadius: "6px",
            background: "#fff",
            color: "#0f172a",
          }}
        >
          <option value="all">All courses</option>
          {courses.map((course) => (
            <option key={course.courseUuid} value={course.courseUuid}>
              {course.courseTitle}
            </option>
          ))}
        </select>
      </div>
      {filteredItems.length === 0 ? (
        <div className="course-empty-state">
          <strong>No quiz data</strong>
          <p>No quiz attempts recorded for this course yet.</p>
        </div>
      ) : (
        <div className="course-management-list">
          {filteredItems.map((item) => (
            <QuizStatsRow key={`${item.courseUuid}-${item.moduleUuid}`} item={item} />
          ))}
        </div>
      )}
    </>
  );
}

function SignalTags({ signals }: { signals: string[] }) {
  if (signals.length === 0) {
    return (
      <div className="course-management-inline-tags">
        <span style={{ background: "#ecfdf5", color: "#166534", borderColor: "rgba(22, 101, 52, 0.14)" }}>
          Stable
        </span>
      </div>
    );
  }

  return (
    <div className="course-management-inline-tags">
      {signals.map((signal) => (
        <span key={signal} style={{ background: "#fef3c7", color: "#92400e", borderColor: "rgba(146, 64, 14, 0.16)" }}>
          {formatSignalLabel(signal)}
        </span>
      ))}
    </div>
  );
}

function BottleneckRow({ item }: { item: ModuleBottleneckInsightItem }) {
  return (
    <div className="course-management-key-value-list">
      <div className="course-management-key-value">
        <span>{item.courseTitle}</span>
        <strong>{item.moduleTitle}</strong>
      </div>
      <div className="course-management-key-value">
        <span>Started / enrolled</span>
        <strong>{item.startedLearnerCount} / {item.enrolledLearnerCount}</strong>
      </div>
      <div className="course-management-key-value">
        <span>Completion</span>
        <strong>{formatPassRate(item.completionRate)}</strong>
      </div>
      <div className="course-management-key-value">
        <span>Avg progress</span>
        <strong>{formatProgress(item.avgProgressPercent)}</strong>
      </div>
      <SignalTags signals={item.signals} />
    </div>
  );
}

function AtRiskLearnerRow({ item }: { item: AtRiskLearnerInsightItem }) {
  return (
    <div className="course-management-key-value-list">
      <div className="course-management-key-value">
        <span>{item.courseTitle}</span>
        <strong>Learner {item.learnerId}</strong>
      </div>
      <div className="course-management-key-value">
        <span>Progress</span>
        <strong>{formatProgress(item.progressPercent)}</strong>
      </div>
      <div className="course-management-key-value">
        <span>Incomplete modules</span>
        <strong>{item.incompleteModuleCount} / {item.totalModuleCount}</strong>
      </div>
      <div className="course-management-key-value">
        <span>Last access</span>
        <strong>{formatDate(item.lastAccessedAt?.slice(0, 10) ?? null)}</strong>
      </div>
      <SignalTags signals={item.riskReasons} />
    </div>
  );
}

function AssessmentSignalRow({ item }: { item: AssessmentSignalInsightItem }) {
  return (
    <div className="course-management-key-value-list">
      <div className="course-management-key-value">
        <span>{item.courseTitle}</span>
        <strong>{item.moduleTitle}</strong>
      </div>
      <div className="course-management-key-value">
        <span>Quiz</span>
        <strong>{item.quizTitle ? `${formatProgress(item.quizAvgScorePercent)} avg` : "—"}</strong>
      </div>
      <div className="course-management-key-value">
        <span>Pass rate</span>
        <strong>{item.quizAttemptCount === 0 ? "No attempt" : formatPassRate(item.quizPassRate)}</strong>
      </div>
      <div className="course-management-key-value">
        <span>Short answer</span>
        <strong>
          {item.shortAnswerTitle
            ? `${formatScore(item.shortAnswerAvgFinalScore ?? item.shortAnswerAvgAiScore, item.shortAnswerMaxScore)} avg`
            : "—"}
        </strong>
      </div>
      <div className="course-management-key-value">
        <span>Pending review</span>
        <strong>{item.shortAnswerPendingReviewCount}</strong>
      </div>
      <SignalTags signals={item.signals} />
    </div>
  );
}

function TrendRow({ item }: { item: CompletionTrendInsightItem }) {
  return (
    <div className="course-management-key-value">
      <span>{item.courseTitle} · {formatDate(item.bucketDate)}</span>
      <strong>{item.completedCount}</strong>
    </div>
  );
}

function TeachingInsightsSection({ insights }: { insights: EducatorTeachingInsights }) {
  const activeBottlenecks = insights.moduleBottlenecks.filter((item) => item.signals.length > 0).slice(0, 5);
  const activeAssessmentSignals = insights.assessmentSignals.filter((item) => item.signals.length > 0).slice(0, 5);
  const visibleAtRiskLearners = insights.atRiskLearners.slice(0, 5);
  const visibleTrends = insights.completionTrends.slice(-6).reverse();
  const pendingReviewCount = insights.assessmentSignals.reduce(
    (total, item) => total + item.shortAnswerPendingReviewCount,
    0
  );
  const trendCompletionCount = insights.completionTrends.reduce((total, item) => total + item.completedCount, 0);

  return (
    <>
      <div className="course-management-toolbar" style={{ marginTop: "1.5rem" }}>
        <strong>Teaching insights</strong>
        <span>Risk, module progress, assessment, and completion signals.</span>
      </div>

      <div className="course-management-stat-grid">
        <div className="course-management-stat-card">
          <span>At-risk learners</span>
          <strong>{insights.atRiskLearners.length}</strong>
        </div>
        <div className="course-management-stat-card">
          <span>Module bottlenecks</span>
          <strong>{insights.moduleBottlenecks.filter((item) => item.signals.length > 0).length}</strong>
        </div>
        <div className="course-management-stat-card">
          <span>Pending reviews</span>
          <strong>{pendingReviewCount}</strong>
        </div>
        <div className="course-management-stat-card">
          <span>Recorded completions</span>
          <strong>{trendCompletionCount}</strong>
        </div>
      </div>

      <div className="course-management-grid" style={{ marginTop: "1rem" }}>
        <article className="course-management-panel">
          <div className="course-management-list-top">
            <h3>Risk learners</h3>
            <strong>{visibleAtRiskLearners.length}</strong>
          </div>
          {visibleAtRiskLearners.length === 0 ? (
            <p>No risk signals in current enrollments.</p>
          ) : (
            <div className="course-management-panel-body">
              {visibleAtRiskLearners.map((item) => (
                <AtRiskLearnerRow key={`${item.courseUuid}-${item.learnerUuid}`} item={item} />
              ))}
            </div>
          )}
        </article>

        <article className="course-management-panel">
          <div className="course-management-list-top">
            <h3>Module bottlenecks</h3>
            <strong>{activeBottlenecks.length}</strong>
          </div>
          {activeBottlenecks.length === 0 ? (
            <p>No module bottlenecks detected.</p>
          ) : (
            <div className="course-management-panel-body">
              {activeBottlenecks.map((item) => (
                <BottleneckRow key={`${item.courseUuid}-${item.moduleUuid}`} item={item} />
              ))}
            </div>
          )}
        </article>

        <article className="course-management-panel">
          <div className="course-management-list-top">
            <h3>Assessment signals</h3>
            <strong>{activeAssessmentSignals.length}</strong>
          </div>
          {activeAssessmentSignals.length === 0 ? (
            <p>No assessment signals detected.</p>
          ) : (
            <div className="course-management-panel-body">
              {activeAssessmentSignals.map((item) => (
                <AssessmentSignalRow key={`${item.courseUuid}-${item.moduleUuid}`} item={item} />
              ))}
            </div>
          )}
        </article>

        <article className="course-management-panel">
          <div className="course-management-list-top">
            <h3>Completion trend</h3>
            <strong>{visibleTrends.length}</strong>
          </div>
          {visibleTrends.length === 0 ? (
            <p>No module completions recorded yet.</p>
          ) : (
            <div className="course-management-key-value-list">
              {visibleTrends.map((item) => (
                <TrendRow key={`${item.courseUuid}-${item.bucketDate}`} item={item} />
              ))}
            </div>
          )}
        </article>
      </div>
    </>
  );
}

function AnalyticsPage() {
  const [analytics, setAnalytics] = useState<EducatorAnalytics | null>(null);
  const [quizAnalytics, setQuizAnalytics] = useState<EducatorQuizAnalytics | null>(null);
  const [teachingInsights, setTeachingInsights] = useState<EducatorTeachingInsights | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      try {
        const [enrollmentData, quizData, teachingInsightsData] = await Promise.all([
          getEducatorAnalytics(),
          getEducatorQuizAnalytics(),
          getEducatorTeachingInsights(),
        ]);
        if (!cancelled) {
          setAnalytics(enrollmentData);
          setQuizAnalytics(quizData);
          setTeachingInsights(teachingInsightsData);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load analytics.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void load();
    return () => { cancelled = true; };
  }, []);

  const overallCompletionRate = useMemo(() => {
    if (!analytics || analytics.totalEnrollments === 0) return null;
    return Math.round((analytics.totalCompletedEnrollments / analytics.totalEnrollments) * 100);
  }, [analytics]);

  if (loading) {
    return (
      <section className="home-content-card">
        <div className="home-loading">Loading analytics...</div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="home-content-card">
        <div className="course-management-inline-alert">
          <strong>Unable to load analytics.</strong>
          <span>{error}</span>
        </div>
      </section>
    );
  }

  if (!analytics) return null;

  return (
    <section className="course-management-page" style={{ padding: "1.5rem" }}>
      <div className="course-management-section-heading">
        <div>
          <span className="course-surface-badge">Educator</span>
          <h1>Analytics</h1>
          <p>Enrollment, quiz performance, and teaching signals across all your courses.</p>
        </div>
      </div>

      {/* 1. Summary stats */}
      <div className="course-management-stat-grid course-management-stat-grid-hero">
        <div className="course-management-stat-card">
          <span>Total courses</span>
          <strong>{analytics.totalCourses}</strong>
        </div>
        <div className="course-management-stat-card">
          <span>Total enrolled</span>
          <strong>{analytics.totalEnrollments}</strong>
        </div>
        <div className="course-management-stat-card">
          <span>Active learners</span>
          <strong>{analytics.totalActiveEnrollments}</strong>
        </div>
        <div className="course-management-stat-card">
          <span>Completed</span>
          <strong>{analytics.totalCompletedEnrollments}</strong>
        </div>
        <div className="course-management-stat-card">
          <span>Overall completion rate</span>
          <strong>{overallCompletionRate !== null ? `${overallCompletionRate}%` : "—"}</strong>
        </div>
      </div>

      {analytics.courses.length === 0 ? (
        <div className="course-empty-state">
          <strong>No courses yet</strong>
          <p>Analytics will appear once you create and publish your courses.</p>
        </div>
      ) : (
        <>
          {/* 2. Per-course enrollment breakdown */}
          <div className="course-management-toolbar">
            <strong>{analytics.totalCourses} course{analytics.totalCourses !== 1 ? "s" : ""}</strong>
            <span>Click a course title to open its management page.</span>
          </div>
          <div className="course-management-list">
            {analytics.courses.map((item) => (
              <CourseAnalyticsRow key={item.courseUuid} item={item} />
            ))}
          </div>

          {teachingInsights && <TeachingInsightsSection insights={teachingInsights} />}

          {/* 3. Quiz stats */}
          {quizAnalytics && quizAnalytics.items.length > 0 && (
            <QuizSection quizAnalytics={quizAnalytics} courses={analytics.courses} />
          )}
        </>
      )}
    </section>
  );
}

export default AnalyticsPage;

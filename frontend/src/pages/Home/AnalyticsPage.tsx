import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { getEducatorAnalytics, getEducatorQuizAnalytics } from "../../services/course";
import type {
  EducatorAnalytics,
  EducatorCourseAnalyticsItem,
  EducatorQuizAnalytics,
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

function AnalyticsPage() {
  const [analytics, setAnalytics] = useState<EducatorAnalytics | null>(null);
  const [quizAnalytics, setQuizAnalytics] = useState<EducatorQuizAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      try {
        const [enrollmentData, quizData] = await Promise.all([
          getEducatorAnalytics(),
          getEducatorQuizAnalytics(),
        ]);
        if (!cancelled) {
          setAnalytics(enrollmentData);
          setQuizAnalytics(quizData);
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
          <p>Enrollment and quiz performance overview across all your courses.</p>
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

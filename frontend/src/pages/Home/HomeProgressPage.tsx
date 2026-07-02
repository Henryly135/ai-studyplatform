import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { getMyProgressOverview } from "../../services/course";
import type { LearnerProgressActivityItem, LearnerProgressOverview } from "../../types/course";
import "./HomePage.css";

function formatPercent(value: number) {
  if (!Number.isFinite(value)) return "0%";
  return `${Math.round(value)}%`;
}

function formatScore(value: number | null) {
  if (value === null || !Number.isFinite(value)) return "No attempts";
  return `${Math.round(value)}%`;
}

function formatTimestamp(value: string | null | undefined) {
  if (!value) return "No activity yet";
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) return "Recent";
  return new Intl.DateTimeFormat("en-AU", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(timestamp);
}

function activityPath(activity: LearnerProgressActivityItem) {
  if (activity.moduleUuid) {
    return `/course/${activity.courseUuid}/modules/${activity.moduleUuid}?from=progress`;
  }
  return `/course/${activity.courseUuid}?from=progress`;
}

function HomeProgressPage() {
  const [overview, setOverview] = useState<LearnerProgressOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadProgress() {
      setLoading(true);

      try {
        const progressOverview = await getMyProgressOverview();

        if (!cancelled) {
          setOverview(progressOverview);
          setErrorMessage(null);
        }
      } catch (error) {
        if (!cancelled) {
          setOverview(null);
          setErrorMessage(error instanceof Error ? error.message : "Failed to load progress.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadProgress();

    return () => {
      cancelled = true;
    };
  }, []);

  const summary = useMemo(() => {
    return {
      totalCourses: overview?.totalCourses ?? 0,
      totalModules: overview?.totalModules ?? 0,
      completedModules: overview?.completedModules ?? 0,
      averageProgress: overview?.averageProgressPercent ?? 0,
      quizAverage: overview?.quiz.averageBestScorePercent ?? null,
      quizAttempts: overview?.quiz.totalAttempts ?? 0,
    };
  }, [overview]);

  const courses = overview?.courses ?? [];
  const recentActivity = overview?.recentActivity ?? [];

  return (
    <section className="home-progress-page">
      <div className="home-progress-hero">
        <span className="home-content-badge">学生</span>
        <h1>进度</h1>
        <p>查看已加入课程、已完成模块、测验结果和近期学习活动。</p>
      </div>

      {errorMessage ? <p className="home-progress-alert">{errorMessage}</p> : null}

      <div className="home-progress-metrics">
        <article>
          <span>课程</span>
          <strong>{loading ? "..." : summary.totalCourses}</strong>
        </article>
        <article>
          <span>模块</span>
          <strong>{loading ? "..." : `${summary.completedModules}/${summary.totalModules}`}</strong>
        </article>
        <article>
          <span>平均进度</span>
          <strong>{loading ? "..." : formatPercent(summary.averageProgress)}</strong>
        </article>
        <article>
          <span>测验最佳均分</span>
          <strong>{loading ? "..." : formatScore(summary.quizAverage)}</strong>
          <small>{loading ? "" : `${summary.quizAttempts} attempts`}</small>
        </article>
      </div>

      <div className="home-progress-list">
        {loading ? <p className="home-ai-muted">正在加载进度...</p> : null}
        {!loading && courses.length === 0 && !errorMessage ? (
          <p className="home-ai-muted">暂无已加入课程。</p>
        ) : null}

        {courses.map((course) => {
          const targetPath = course.nextModule
            ? `/course/${course.courseUuid}/modules/${course.nextModule.moduleUuid}?from=progress`
            : `/course/${course.courseUuid}?from=progress`;

          return (
            <article key={course.courseUuid} className="home-progress-course">
              <div>
                <span>{course.courseCode || course.category || "课程"}</span>
                <h2>{course.title}</h2>
                <p>
                  {course.completedModuleCount}/{course.totalModuleCount}个模块已完成
                </p>
                <p>
                  {course.quiz.attemptedQuizzes}/{course.quiz.totalQuizzes}次测验尝试 · 最佳均分{" "}
                  {formatScore(course.quiz.averageBestScorePercent)}
                </p>
              </div>

              <div className="home-progress-course-side">
                <strong>{formatPercent(course.progressPercent)}</strong>
                <small>{formatTimestamp(course.lastAccessedAt)}</small>
                <Link to={targetPath}>{course.nextModule ? "Continue" : "Review"}</Link>
              </div>
            </article>
          );
        })}
      </div>

      <div className="home-progress-activity">
        <div className="home-progress-section-heading">
          <h2>最近活动</h2>
          <span>{loading ? "加载中" : `${recentActivity.length} shown`}</span>
        </div>

        {!loading && recentActivity.length === 0 ? (
          <p className="home-ai-muted">暂无近期学习活动。</p>
        ) : null}

        {recentActivity.map((activity) => (
          <Link
            key={`${activity.activityType}-${activity.occurredAt}-${activity.moduleUuid ?? activity.courseUuid}`}
            to={activityPath(activity)}
            className="home-progress-activity-row"
          >
            <span>
              <strong>{activity.title}</strong>
              <small>
                {activity.detail || activity.moduleTitle || activity.courseTitle} · {formatTimestamp(activity.occurredAt)}
              </small>
            </span>
            <em>
              {activity.scorePercent === null
                ? activity.courseTitle
                : `${formatScore(activity.scorePercent)} ${activity.isPassed ? "passed" : "review"}`}
            </em>
          </Link>
        ))}
      </div>
    </section>
  );
}

export default HomeProgressPage;

import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { LuCheck, LuChevronLeft, LuChevronRight, LuPlus } from "react-icons/lu";

import type { CurrentUserResponse } from "../../types/auth";
import {
  dropMyEnrollment,
  enrollInCourse,
  getCourses,
  getMyEnrolledCourseUuids,
} from "../../services/course";
import type { CourseRecord } from "../../types/course";
import { emitAppRefresh, subscribeAppRefresh } from "../../utils/refreshEvents";
import { useGridColumnCount } from "./useGridColumnCount";
import "./CoursePages.css";

const FALLBACK_COVER_THEMES = ["teal", "prism", "ocean", "neon"];
const COURSE_ROWS_PER_PAGE = 4;

function getCoverTheme(index: number) {
  return FALLBACK_COVER_THEMES[index % FALLBACK_COVER_THEMES.length];
}

function formatHourLabel(minutes: number | null) {
  if (!minutes || minutes <= 0) {
    return "";
  }

  if (minutes < 60) {
    return `${minutes} min`;
  }

  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`;
}

function CourseCard({
  course,
  index,
  canEnroll,
  isEnrolled,
  isEnrolling,
  onToggleEnrollment,
}: {
  course: CourseRecord;
  index: number;
  canEnroll: boolean;
  isEnrolled: boolean;
  isEnrolling: boolean;
  onToggleEnrollment: (course: CourseRecord, isEnrolled: boolean) => void;
}) {
  const navigate = useNavigate();
  const coverTheme = getCoverTheme(index);

  return (
    <article
      className="course-card course-center-card course-card-clickable"
      role="link"
      tabIndex={0}
      onClick={() => navigate(`/course/${course.courseUuid}?from=course-center`)}
      onKeyDown={(event) => {
        if (event.target !== event.currentTarget) {
          return;
        }
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          navigate(`/course/${course.courseUuid}?from=course-center`);
        }
      }}
    >
      <div className={`course-card-cover course-card-cover-${coverTheme}`}>
        {course.coverImageUrl ? (
          <img src={course.coverImageUrl} alt={course.title} className="course-card-cover-image" />
        ) : (
          course.courseCode ? <div className="course-card-cover-badge">{course.courseCode}</div> : null
        )}
      </div>

      <div className="course-card-body">
        <div className="course-card-body-top">
          <div className="course-card-meta">
            {course.courseCode ? <span>{course.courseCode}</span> : null}
            {course.difficultyLevel ? <span>{course.difficultyLevel}</span> : null}
            {canEnroll ? (
              <button
                type="button"
                className={`course-enroll-icon-button course-center-card-enroll-icon${
                  isEnrolled ? " course-enroll-icon-button-complete" : ""
                }`}
                onClick={(event) => {
                  event.stopPropagation();
                  onToggleEnrollment(course, isEnrolled);
                }}
                disabled={isEnrolling}
                aria-label={
                  isEnrolled
                    ? "取消报名该课程"
                    : isEnrolling
                      ? "正在报名该课程"
                      : "报名该课程"
                }
                title={
                  isEnrolled
                    ? "取消报名"
                    : isEnrolling
                      ? "正在更新报名状态..."
                      : "Enroll"
                }
              >
                {isEnrolled ? <LuCheck size={18} aria-hidden="true" /> : <LuPlus size={18} aria-hidden="true" />}
              </button>
            ) : null}
          </div>
          <h3>{course.title}</h3>
        </div>

        <div className="course-card-footer">
          {course.category ? <span>{course.category}</span> : null}
          {formatHourLabel(course.estimatedMinutes) ? (
            <strong>{formatHourLabel(course.estimatedMinutes)}</strong>
          ) : null}
        </div>
      </div>
    </article>
  );
}

function buildPagination(currentPage: number, totalPages: number) {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }

  if (currentPage <= 4) {
    return [1, 2, 3, 4, 5, "ellipsis", totalPages] as const;
  }

  if (currentPage >= totalPages - 3) {
    return [1, "ellipsis", totalPages - 4, totalPages - 3, totalPages - 2, totalPages - 1, totalPages] as const;
  }

  return [1, "ellipsis", currentPage - 1, currentPage, currentPage + 1, "ellipsis", totalPages] as const;
}

function getCourseCenterHeroCopy(identity?: CurrentUserResponse["identity"]) {
  if (identity === "Learner") {
    return {
      badge: "课程目录",
      title: "查找可加入课程",
      description:
        "浏览已发布课程，按标题或代码搜索，并加入适合你的课程。",
    };
  }

  if (identity === "Educator") {
    return {
      badge: "目录预览",
      title: "查看学生侧课程目录",
      description:
        "查看已发布课程在学生侧的展示方式、发现信息和共享课程空间。",
    };
  }

  if (identity === "Admin") {
    return {
      badge: "课程目录治理",
      title: "监控已发布课程目录",
      description:
        "从平台视角查看公开课程记录、搜索目录，并进入课程空间进行监管。",
    };
  }

  return {
    badge: "课程大厅",
    title: "在一个位置浏览所有课程",
    description:
      "浏览完整课程目录，按标题或代码搜索，并进入共享课程空间。",
  };
}

type CourseCenterPageProps = {
  currentUser?: CurrentUserResponse;
};

type PendingEnrollmentAction = {
  courseUuid: string;
  courseTitle: string;
  action: "enroll" | "cancel";
};

function CourseCenterPage({ currentUser }: CourseCenterPageProps) {
  const gridRef = useRef<HTMLDivElement | null>(null);
  const enrollmentActionTriggerRef = useRef<HTMLElement | null>(null);
  const columnCount = useGridColumnCount(gridRef);
  const coursesPerPage = columnCount > 0 ? columnCount * COURSE_ROWS_PER_PAGE : 0;
  const isLearner = currentUser?.identity === "Learner";
  const [courses, setCourses] = useState<CourseRecord[]>([]);
  const [enrolledCourseUuids, setEnrolledCourseUuids] = useState<Set<string>>(new Set());
  const [enrollingCourseUuid, setEnrollingCourseUuid] = useState<string | null>(null);
  const [pendingEnrollmentAction, setPendingEnrollmentAction] = useState<PendingEnrollmentAction | null>(null);
  const [query, setQuery] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [totalCourses, setTotalCourses] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [enrollmentActionError, setEnrollmentActionError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [enrollmentRefreshKey, setEnrollmentRefreshKey] = useState(0);

  const restoreEnrollmentActionFocus = useCallback(() => {
    const trigger = enrollmentActionTriggerRef.current;
    enrollmentActionTriggerRef.current = null;
    if (!trigger?.isConnected) {
      return;
    }

    window.setTimeout(() => trigger.focus(), 0);
  }, []);

  const closePendingEnrollmentAction = useCallback(() => {
    if (enrollingCourseUuid) {
      return;
    }

    setPendingEnrollmentAction(null);
    setEnrollmentActionError("");
    restoreEnrollmentActionFocus();
  }, [enrollingCourseUuid, restoreEnrollmentActionFocus]);

  useEffect(() => {
    if (!isLearner) {
      setEnrolledCourseUuids(new Set());
      return undefined;
    }

    let cancelled = false;

    const loadEnrolledCourses = async () => {
      try {
        const courseUuids = await getMyEnrolledCourseUuids();
        if (!cancelled) {
          setEnrolledCourseUuids(courseUuids);
        }
      } catch {
        if (!cancelled) {
          setEnrolledCourseUuids(new Set());
        }
      }
    };

    void loadEnrolledCourses();

    return () => {
      cancelled = true;
    };
  }, [enrollmentRefreshKey, isLearner]);

  useEffect(() => {
    return subscribeAppRefresh(["course:catalog", "course:enrollment"], () => {
      setRefreshKey((current) => current + 1);
      setEnrollmentRefreshKey((current) => current + 1);
    });
  }, []);

  const handleToggleEnrollment = (course: CourseRecord, currentlyEnrolled: boolean) => {
    if (!isLearner || enrollingCourseUuid) {
      return;
    }

    enrollmentActionTriggerRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setEnrollmentActionError("");
    setPendingEnrollmentAction({
      courseUuid: course.courseUuid,
      courseTitle: course.title,
      action: currentlyEnrolled ? "cancel" : "enroll",
    });
  };

  const confirmEnrollmentAction = async () => {
    if (!isLearner || !pendingEnrollmentAction || enrollingCourseUuid) {
      return;
    }

    const { courseUuid, action } = pendingEnrollmentAction;
    setEnrollingCourseUuid(courseUuid);
    try {
      if (action === "cancel") {
        await dropMyEnrollment(courseUuid);
        setEnrolledCourseUuids((current) => {
          const next = new Set(current);
          next.delete(courseUuid);
          return next;
        });
      } else {
        await enrollInCourse(courseUuid);
        setEnrolledCourseUuids((current) => new Set(current).add(courseUuid));
      }
      setRefreshKey((current) => current + 1);
      setEnrollmentRefreshKey((current) => current + 1);
      emitAppRefresh({ scope: "course:enrollment", courseUuid });
      setPendingEnrollmentAction(null);
      restoreEnrollmentActionFocus();
      setEnrollmentActionError("");
      setError(null);
    } catch (enrollError) {
      setEnrollmentActionError(
        enrollError instanceof Error
          ? enrollError.message
          : action === "cancel"
            ? "Failed to cancel enrollment."
            : "Failed to enroll in course."
      );
    } finally {
      setEnrollingCourseUuid(null);
    }
  };

  useEffect(() => {
    if (coursesPerPage === 0) {
      return undefined;
    }

    let cancelled = false;

    const loadCourses = async () => {
      setLoading(true);

      try {
        const data = await getCourses({
          search: query,
          page: currentPage,
          pageSize: coursesPerPage,
        });
        if (!cancelled) {
          setCourses(data.items);
          setTotalCourses(data.total);
          setTotalPages(data.totalPages);
          setError(null);
        }
      } catch (loadError) {
        if (!cancelled) {
          setCourses([]);
          setTotalCourses(0);
          setTotalPages(1);
          setError(loadError instanceof Error ? loadError.message : "Failed to load courses.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    const timer = window.setTimeout(() => {
      void loadCourses();
    }, 250);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [coursesPerPage, currentPage, query, refreshKey]);

  useEffect(() => {
    if (coursesPerPage === 0) {
      return;
    }

    setCurrentPage(1);
  }, [coursesPerPage, query]);

  const safeCurrentPage = Math.min(currentPage, totalPages);
  const startIndex = totalCourses === 0 || coursesPerPage === 0 ? 0 : (safeCurrentPage - 1) * coursesPerPage;
  const endIndex = startIndex + courses.length;
  const paginationItems = buildPagination(safeCurrentPage, totalPages);
  const heroCopy = getCourseCenterHeroCopy(currentUser?.identity);

  useEffect(() => {
    if (currentPage !== safeCurrentPage) {
      setCurrentPage(safeCurrentPage);
    }
  }, [currentPage, safeCurrentPage]);

  useEffect(() => {
    if (!pendingEnrollmentAction || enrollingCourseUuid) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closePendingEnrollmentAction();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [closePendingEnrollmentAction, enrollingCourseUuid, pendingEnrollmentAction]);

  return (
    <section className="course-center-page">
      <div className="course-center-hero">
        <div>
          <span className="course-surface-badge">{heroCopy.badge}</span>
          <h1>{heroCopy.title}</h1>
          <p>{heroCopy.description}</p>
        </div>

        <label className="course-search-card">
          <span>搜索课程</span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="按标题、代码、分类或学院搜索..."
          />
        </label>
      </div>

      <div className="course-center-toolbar">
        <strong>{loading ? "正在加载课程..." : `${totalCourses} courses found`}</strong>
      </div>

      <div ref={gridRef} className="course-grid course-center-grid">
        {courses.map((course, index) => (
          <CourseCard
            key={`${course.courseUuid}-${course.title}`}
            course={course}
            index={startIndex + index}
            canEnroll={isLearner}
            isEnrolled={enrolledCourseUuids.has(course.courseUuid)}
            isEnrolling={enrollingCourseUuid === course.courseUuid}
            onToggleEnrollment={handleToggleEnrollment}
          />
        ))}
      </div>

      {pendingEnrollmentAction ? (
        <div
          className="course-confirm-modal-overlay"
          role="presentation"
          onClick={closePendingEnrollmentAction}
        >
          <div
            className="course-confirm-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="course-center-enrollment-confirm-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="course-confirm-modal-header">
              <h3 id="course-center-enrollment-confirm-title">
                {pendingEnrollmentAction.action === "cancel" ? "确认取消报名？" : "确认报名该课程？"}
              </h3>
              <p>{pendingEnrollmentAction.courseTitle}</p>
            </div>

            <p className="course-confirm-modal-copy">
              {pendingEnrollmentAction.action === "cancel"
                ? "该课程会从你的学习空间移除，重新报名前不可见；已有学习进度会保留。"
                : "该课程会加入你的学习空间和课程列表。"}
            </p>
            {enrollmentActionError ? (
              <p className="course-confirm-modal-error" role="alert">
                {enrollmentActionError}
              </p>
            ) : null}

            <div className="course-confirm-modal-actions">
              <button
                type="button"
                className="course-secondary-link"
                onClick={closePendingEnrollmentAction}
                disabled={Boolean(enrollingCourseUuid)}
                autoFocus
              >返回
              </button>
              <button
                type="button"
                className={`course-enroll-button${
                  pendingEnrollmentAction.action === "cancel" ? "" : " course-enroll-button-primary"
                }`}
                onClick={() => void confirmEnrollmentAction()}
                disabled={Boolean(enrollingCourseUuid)}
              >
                {enrollingCourseUuid
                  ? pendingEnrollmentAction.action === "cancel"
                    ? "正在取消..."
                    : "报名中..."
                  : pendingEnrollmentAction.action === "cancel"
                    ? "取消报名"
                    : "Enroll"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {!loading && totalCourses > 0 ? (
        <div className="course-pagination">
          <span className="course-pagination-summary">显示 {startIndex + 1}-{Math.min(endIndex, totalCourses)}共 {totalCourses}门课程。
          </span>
          {coursesPerPage > 0 && totalCourses > coursesPerPage ? (
            <nav className="course-pagination-nav" aria-label="课程中心分页">
          <button
            type="button"
            className="course-pagination-button"
            onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
            disabled={safeCurrentPage === 1}
            aria-label="上一页课程中心"
          >
            <LuChevronLeft size={18} aria-hidden="true" />
          </button>

          <div className="course-pagination-pages">
            {paginationItems.map((item, index) =>
              item === "ellipsis" ? (
                <span key={`ellipsis-${index}`} className="course-pagination-ellipsis" aria-hidden="true">
                  ...
                </span>
              ) : (
                <button
                  key={item}
                  type="button"
                  className={`course-pagination-button${item === safeCurrentPage ? " course-pagination-button-active" : ""}`}
                  onClick={() => setCurrentPage(item)}
                  aria-current={item === safeCurrentPage ? "page" : undefined}
                >
                  {item}
                </button>
              )
            )}
          </div>

          <button
            type="button"
            className="course-pagination-button"
            onClick={() => setCurrentPage((page) => Math.min(totalPages, page + 1))}
            disabled={safeCurrentPage === totalPages}
            aria-label="下一页课程中心"
            >
              <LuChevronRight size={18} aria-hidden="true" />
            </button>
            </nav>
          ) : null}
        </div>
      ) : null}

      {!loading && totalCourses === 0 ? (
        <div className="course-empty-state">
          <strong>{error ? "无法加载课程" : query ? "没有匹配课程" : "暂无课程"}</strong>
          <p>
            {error
              ? error
              : query
                ? "请尝试其他课程代码、分类或关键词。"
                : "当前数据库中没有课程记录。"}
          </p>
        </div>
      ) : null}
    </section>
  );
}

export default CourseCenterPage;

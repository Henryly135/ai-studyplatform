import { useEffect, useRef, useState } from "react";
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
                    ? "Cancel enrollment for this course"
                    : isEnrolling
                      ? "Enrolling in this course"
                      : "Enroll in this course"
                }
                title={
                  isEnrolled
                    ? "Cancel enrollment"
                    : isEnrolling
                      ? "Updating enrollment..."
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
  const [refreshKey, setRefreshKey] = useState(0);
  const [enrollmentRefreshKey, setEnrollmentRefreshKey] = useState(0);

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
      setError(null);
    } catch (enrollError) {
      setError(
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

  useEffect(() => {
    if (currentPage !== safeCurrentPage) {
      setCurrentPage(safeCurrentPage);
    }
  }, [currentPage, safeCurrentPage]);

  return (
    <section className="course-center-page">
      <div className="course-center-hero">
        <div>
          <span className="course-surface-badge">Course Lobby</span>
          <h1>Explore all courses in one place</h1>
          <p>
            Browse the full catalog, search by title or code, and jump directly into a shared
            course workspace layout.
          </p>
        </div>

        <label className="course-search-card">
          <span>Search courses</span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search by title, code, category, school..."
          />
        </label>
      </div>

      <div className="course-center-toolbar">
        <strong>{loading ? "Loading courses..." : `${totalCourses} courses found`}</strong>
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
          onClick={() => setPendingEnrollmentAction(null)}
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
                {pendingEnrollmentAction.action === "cancel" ? "Cancel enrollment?" : "Enroll in this course?"}
              </h3>
              <p>{pendingEnrollmentAction.courseTitle}</p>
            </div>

            <p className="course-confirm-modal-copy">
              {pendingEnrollmentAction.action === "cancel"
                ? "This course will be removed from your learner workspace until you enroll again. Your existing learning progress will be kept."
                : "This course will be added to your learner workspace and course list."}
            </p>

            <div className="course-confirm-modal-actions">
              <button
                type="button"
                className="course-secondary-link"
                onClick={() => setPendingEnrollmentAction(null)}
                disabled={Boolean(enrollingCourseUuid)}
              >
                Back
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
                    ? "Cancelling..."
                    : "Enrolling..."
                  : pendingEnrollmentAction.action === "cancel"
                    ? "Cancel enrollment"
                    : "Enroll"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {!loading && totalCourses > 0 ? (
        <div className="course-pagination">
          <span className="course-pagination-summary">
            Showing {startIndex + 1}-{Math.min(endIndex, totalCourses)} of {totalCourses} courses.
          </span>
          {coursesPerPage > 0 && totalCourses > coursesPerPage ? (
            <nav className="course-pagination-nav" aria-label="Course center pagination">
          <button
            type="button"
            className="course-pagination-button"
            onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
            disabled={safeCurrentPage === 1}
            aria-label="Go to previous course center page"
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
            aria-label="Go to next course center page"
            >
              <LuChevronRight size={18} aria-hidden="true" />
            </button>
            </nav>
          ) : null}
        </div>
      ) : null}

      {!loading && totalCourses === 0 ? (
        <div className="course-empty-state">
          <strong>{error ? "Unable to load courses" : query ? "No matching courses" : "No courses yet"}</strong>
          <p>
            {error
              ? error
              : query
                ? "Try a different course code, category, or keyword."
                : "No course records are available in the database right now."}
          </p>
        </div>
      ) : null}
    </section>
  );
}

export default CourseCenterPage;

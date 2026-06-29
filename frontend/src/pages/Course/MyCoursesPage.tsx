import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { LuChevronLeft, LuChevronRight } from "react-icons/lu";

import { getMyEnrolledCourses } from "../../services/course";
import type { CourseRecord } from "../../types/course";
import { subscribeAppRefresh } from "../../utils/refreshEvents";
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

function MyCourseCard({
  course,
  index,
}: {
  course: CourseRecord;
  index: number;
}) {
  const coverTheme = getCoverTheme(index);

  return (
    <Link to={`/course/${course.courseUuid}?from=my-courses`} className="my-course-card-link">
      <article className="course-card my-course-card">
        <div className={`course-card-cover course-card-cover-${coverTheme}`}>
          {course.coverImageUrl ? (
            <img src={course.coverImageUrl} alt={course.title} className="course-card-cover-image" />
          ) : (
            course.courseCode ? <div className="course-card-cover-badge">{course.courseCode}</div> : null
          )}
        </div>

        <div className="course-card-body">
          <div className="course-card-meta">
            {course.courseCode ? <span>{course.courseCode}</span> : null}
            {course.difficultyLevel ? <span>{course.difficultyLevel}</span> : null}
          </div>

          <h3>{course.title}</h3>

          {course.subtitle ? <p>{course.subtitle}</p> : null}

          <div className="course-card-footer">
            {course.category ? <span>{course.category}</span> : null}
            {formatHourLabel(course.estimatedMinutes) ? (
              <strong>{formatHourLabel(course.estimatedMinutes)}</strong>
            ) : null}
          </div>
        </div>
      </article>
    </Link>
  );
}

function MyCoursesPage() {
  const gridRef = useRef<HTMLDivElement | null>(null);
  const columnCount = useGridColumnCount(gridRef);
  const coursesPerPage = columnCount > 0 ? columnCount * COURSE_ROWS_PER_PAGE : 0;
  const [courses, setCourses] = useState<CourseRecord[]>([]);
  const [query, setQuery] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    return subscribeAppRefresh(["course:enrollment", "course:progress", "course:catalog"], () => {
      setRefreshKey((current) => current + 1);
    });
  }, []);

  useEffect(() => {
    let cancelled = false;

    const loadCourses = async () => {
      setLoading(true);

      try {
        const data = await getMyEnrolledCourses(query);
        if (!cancelled) {
          setCourses(data);
          setError(null);
        }
      } catch (loadError) {
        if (!cancelled) {
          setCourses([]);
          setError(loadError instanceof Error ? loadError.message : "Failed to load enrolled courses.");
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
  }, [query, refreshKey]);

  useEffect(() => {
    if (coursesPerPage === 0) {
      return;
    }

    setCurrentPage(1);
  }, [coursesPerPage, query]);

  const totalCourses = courses.length;
  const totalPages =
    coursesPerPage > 0 ? Math.max(1, Math.ceil(totalCourses / coursesPerPage)) : 1;
  const safeCurrentPage = Math.min(currentPage, totalPages);
  const startIndex =
    totalCourses === 0 || coursesPerPage === 0 ? 0 : (safeCurrentPage - 1) * coursesPerPage;
  const visibleCourses =
    coursesPerPage > 0 ? courses.slice(startIndex, startIndex + coursesPerPage) : courses;
  const paginationItems = buildPagination(safeCurrentPage, totalPages);

  useEffect(() => {
    if (currentPage !== safeCurrentPage) {
      setCurrentPage(safeCurrentPage);
    }
  }, [currentPage, safeCurrentPage]);

  const toolbarCopy = useMemo(() => {
    if (loading) {
      return "Loading your enrolled courses...";
    }
    if (totalCourses === 0) {
      return query ? "No enrolled courses match this search." : "You have not enrolled in any courses yet.";
    }
    return `Showing ${startIndex + 1}-${Math.min(startIndex + visibleCourses.length, totalCourses)} of ${totalCourses} enrolled courses.`;
  }, [loading, query, startIndex, totalCourses, visibleCourses.length]);

  return (
    <section className="course-center-page">
      <div className="course-center-hero">
        <div>
          <span className="course-surface-badge">Learner Workspace</span>
          <h1>Keep track of your enrolled courses</h1>
          <p>Open the courses you already joined, review your study lineup, or cancel enrollment when needed.</p>
        </div>

        <label className="course-search-card">
          <span>Search my courses</span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search by title, code, category, school..."
          />
        </label>
      </div>

      <div className="course-center-toolbar">
        <strong>{loading ? "Loading courses..." : `${totalCourses} enrolled courses`}</strong>
      </div>

      {error ? (
        <div className="course-management-inline-alert">
          <strong>Unable to load your courses.</strong>
          <span>{error}</span>
        </div>
      ) : null}

      <div ref={gridRef} className="course-grid course-center-grid">
        {visibleCourses.map((course, index) => (
          <MyCourseCard
            key={`${course.courseUuid}-${course.title}`}
            course={course}
            index={startIndex + index}
          />
        ))}
      </div>

      {!loading && totalCourses > 0 ? (
        <div className="course-pagination">
          <span className="course-pagination-summary">{toolbarCopy}</span>
          {coursesPerPage > 0 && totalCourses > coursesPerPage ? (
            <nav className="course-pagination-nav" aria-label="My courses pagination">
          <button
            type="button"
            className="course-pagination-button"
            onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
            disabled={safeCurrentPage === 1}
            aria-label="Go to previous my courses page"
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
            aria-label="Go to next my courses page"
            >
              <LuChevronRight size={18} aria-hidden="true" />
            </button>
            </nav>
          ) : null}
        </div>
      ) : null}

      {!loading && totalCourses === 0 ? (
        <div className="course-empty-state">
          <strong>{query ? "No matching enrolled courses" : "No enrolled courses yet"}</strong>
          <p>
            {query
              ? "Try a different course title, code, or keyword."
              : "Browse Course Center and enroll in a course to start building your learner workspace."}
          </p>
        </div>
      ) : null}
    </section>
  );
}

export default MyCoursesPage;

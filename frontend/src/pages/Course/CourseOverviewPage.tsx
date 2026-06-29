import { Link, useLocation, useOutletContext } from "react-router-dom";

import type { CourseOutletContext } from "./CourseLayout";

function CourseOverviewPage() {
  const { course } = useOutletContext<CourseOutletContext>();
  const location = useLocation();
  const firstModule = course.modules[0];

  return (
    <section className="course-detail-page">
      <div className="course-detail-hero">
        <div>
          <span className="course-surface-badge">{course.category}</span>
          <h1>{course.title}</h1>
          <p>{course.description}</p>
        </div>

        <div className="course-stat-grid">
          <article className="course-stat-card">
            <span>Duration</span>
            <strong>{course.estimatedMinutes ? `${course.estimatedMinutes} min` : "-"}</strong>
          </article>
          <article className="course-stat-card">
            <span>Language</span>
            <strong>{course.languageCode ? course.languageCode.toUpperCase() : "-"}</strong>
          </article>
          <article className="course-stat-card">
            <span>Modules</span>
            <strong>{course.modules.length}</strong>
          </article>
          <article className="course-stat-card">
            <span>Difficulty</span>
            <strong>{course.difficultyLevel}</strong>
          </article>
        </div>
      </div>

      <div className="course-detail-grid">
        <article className="course-panel">
          <div className="course-panel-heading">
            <h3>About this course</h3>
          </div>
          {course.subtitle ? <p>{course.subtitle}</p> : null}
          {course.description ? <p>{course.description}</p> : null}
        </article>

        <article className="course-panel">
          <div className="course-panel-heading">
            <h3>Start learning</h3>
          </div>
          <p>Use the module navigation on the left, or jump into the first module directly.</p>
          {firstModule ? (
            <Link
              to={`/course/${course.courseUuid}/modules/${firstModule.moduleUuid}${location.search}`}
              className="course-primary-link"
            >
              Open first module
            </Link>
          ) : null}
        </article>
      </div>
    </section>
  );
}

export default CourseOverviewPage;

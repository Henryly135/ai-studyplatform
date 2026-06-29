import { useOutletContext } from "react-router-dom";

import type { CourseManagementOutletContext } from "./CourseManagementLayout";

function CourseManagementPublishingPage() {
  const { course } = useOutletContext<CourseManagementOutletContext>();
  const publishedModules = course.modules.filter((module) => module.status === "available").length;
  const draftModules = course.modules.filter((module) => module.status === "draft").length;
  const isPublished = course.status?.toLowerCase() === "published";

  return (
    <section className="course-management-page">
      <div className="course-management-section-heading">
        <div>
          <span className="course-surface-badge">Publishing</span>
          <h1>Publishing control</h1>
          <p>Use this area to judge release readiness before wiring the real publish action.</p>
        </div>
      </div>

      <div className="course-management-grid">
        <article className="course-management-panel">
          <div className="course-panel-heading">
            <h3>Course release status</h3>
          </div>
          <div className="course-management-key-value">
            <span>Course status</span>
            <strong className={isPublished ? "course-text-published" : undefined}>{course.status || "draft"}</strong>
          </div>
          <div className="course-management-key-value">
            <span>Published modules</span>
            <strong className={publishedModules > 0 ? "course-text-published" : undefined}>{publishedModules}</strong>
          </div>
          <div className="course-management-key-value">
            <span>Draft modules</span>
            <strong>{draftModules}</strong>
          </div>
        </article>

        <article className="course-management-panel">
          <div className="course-panel-heading">
            <h3>Readiness checklist</h3>
          </div>
          <div className="course-management-checklist">
            <span>{course.title ? "Complete" : "Missing"} course title</span>
            <span>{course.description ? "Complete" : "Missing"} course description</span>
            <span>{course.modules.length > 0 ? "Complete" : "Missing"} module structure</span>
          </div>
        </article>
      </div>
    </section>
  );
}

export default CourseManagementPublishingPage;

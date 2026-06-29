import { useOutletContext } from "react-router-dom";

import ManagementKeyValueList from "../../components/course-management/ManagementKeyValueList";
import ManagementPanel from "../../components/course-management/ManagementPanel";
import ManagementStatCard from "../../components/course-management/ManagementStatCard";
import type { CourseManagementOutletContext } from "./CourseManagementLayout";

function formatPublishedAt(value?: string | null) {
  if (!value) {
    return "Not published";
  }

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Published" : date.toLocaleString();
}

function getPublishedTextClassName(value: string) {
  return value.toLowerCase().includes("published") ? "course-text-published" : undefined;
}

function CourseManagementOverviewPage() {
  const { course } = useOutletContext<CourseManagementOutletContext>();
  const publishedLabel = formatPublishedAt(course.publishedAt);
  const metadataItems = [
    { label: "Course code", value: course.courseCode || "Not set" },
    { label: "Category", value: course.category || "Not set" },
    { label: "Difficulty", value: course.difficultyLevel || "Not set" },
    { label: "Language", value: course.languageCode || "Not set" },
    { label: "Estimated time", value: course.estimatedMinutes ? `${course.estimatedMinutes} min` : "Not set" },
    { label: "School", value: course.schoolName || "Not set" },
  ];

  return (
    <section className="course-management-page">
      <div className="course-management-hero">
        <div className="course-management-hero-copy">
          <span className="course-surface-badge">Course Info</span>
          <h1>{course.title}</h1>
          <p>{course.description || "Add a course description to help learners understand the learning goals."}</p>
        </div>

        <div className="course-management-stat-grid course-management-stat-grid-hero">
          <ManagementStatCard
            label="Status"
            value={course.status ? course.status.charAt(0).toUpperCase() + course.status.slice(1) : "Draft"}
            valueClassName={course.status?.toLowerCase() === "published" ? "course-text-published" : undefined}
          />
          <ManagementStatCard
            label="Published"
            value={publishedLabel}
            valueClassName={getPublishedTextClassName(publishedLabel)}
          />
          <ManagementStatCard label="Modules" value={String(course.moduleCount ?? course.modules.length)} />
        </div>
      </div>

      <div className="course-management-grid">
        <ManagementPanel title="Course metadata" bodyClassName="course-management-panel-body-scroll">
          <ManagementKeyValueList items={metadataItems} />
        </ManagementPanel>

        <ManagementPanel title="Learning path" bodyClassName="course-management-panel-body-scroll">
          <p>{course.learningPathTitle || "Default learning path"}</p>
          <p>
            {course.learningPathDescription ||
              "This area can later hold editable learning-path copy, onboarding notes, and sequencing context."}
          </p>
        </ManagementPanel>

        <ManagementPanel title="Teaching summary" bodyClassName="course-management-panel-body-scroll">
          <p>{course.subtitle || "Add a short subtitle to make the course easier to scan in management views."}</p>
          <p>{course.description || "No detailed course description has been added yet."}</p>
        </ManagementPanel>

        <ManagementPanel title="Next management actions" bodyClassName="course-management-panel-body-scroll">
          <p>Review module completeness, attach missing materials, and then publish when the structure is ready.</p>
          <div className="course-management-inline-tags">
            <span>Metadata</span>
            <span>Modules</span>
            <span>Publishing</span>
          </div>
        </ManagementPanel>
      </div>
    </section>
  );
}

export default CourseManagementOverviewPage;

import { useOutletContext } from "react-router-dom";

import type { CourseManagementOutletContext } from "./CourseManagementLayout";

function CourseManagementPublishingPage() {
  const { course } = useOutletContext<CourseManagementOutletContext>();
  const publishedModules = course.modules.filter((module) => module.status === "available").length;
  const draftModules = course.modules.filter((module) => module.status === "draft").length;
  const isPublished = course.status?.toLowerCase() === "published";
  const courseStatusLabel = isPublished ? "已发布" : course.status?.toLowerCase() === "archived" ? "已归档" : "草稿";

  return (
    <section className="course-management-page">
      <div className="course-management-section-heading">
        <div>
          <span className="course-surface-badge">发布</span>
          <h1>发布控制</h1>
          <p>在接入真实发布操作前，可用此区域判断发布准备度。</p>
        </div>
      </div>

      <div className="course-management-grid">
        <article className="course-management-panel">
          <div className="course-panel-heading">
            <h3>课程发布状态</h3>
          </div>
          <div className="course-management-key-value">
            <span>课程状态</span>
            <strong className={isPublished ? "course-text-published" : undefined}>{courseStatusLabel}</strong>
          </div>
          <div className="course-management-key-value">
            <span>已发布模块</span>
            <strong className={publishedModules > 0 ? "course-text-published" : undefined}>{publishedModules}</strong>
          </div>
          <div className="course-management-key-value">
            <span>草稿模块</span>
            <strong>{draftModules}</strong>
          </div>
        </article>

        <article className="course-management-panel">
          <div className="course-panel-heading">
            <h3>准备清单</h3>
          </div>
          <div className="course-management-checklist">
            <span>{course.title ? "完成" : "缺失"}课程标题</span>
            <span>{course.description ? "完成" : "缺失"}课程描述</span>
            <span>{course.modules.length > 0 ? "完成" : "缺失"}模块结构</span>
          </div>
        </article>
      </div>
    </section>
  );
}

export default CourseManagementPublishingPage;

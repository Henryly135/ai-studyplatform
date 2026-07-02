import { useOutletContext } from "react-router-dom";

import ManagementKeyValueList from "../../components/course-management/ManagementKeyValueList";
import ManagementPanel from "../../components/course-management/ManagementPanel";
import ManagementStatCard from "../../components/course-management/ManagementStatCard";
import type { CourseManagementOutletContext } from "./CourseManagementLayout";

function formatPublishedAt(value?: string | null) {
  if (!value) {
    return "未发布";
  }

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "已发布" : date.toLocaleString();
}

function getPublishedTextClassName(value: string) {
  return value.includes("已发布") ? "course-text-published" : undefined;
}

function formatCourseStatus(status?: string | null) {
  switch (status?.toLowerCase()) {
    case "published":
      return "已发布";
    case "archived":
      return "已归档";
    case "draft":
    default:
      return "草稿";
  }
}

function CourseManagementOverviewPage() {
  const { course } = useOutletContext<CourseManagementOutletContext>();
  const publishedLabel = formatPublishedAt(course.publishedAt);
  const metadataItems = [
    { label: "课程代码", value: course.courseCode || "未设置" },
    { label: "分类", value: course.category || "未设置" },
    { label: "难度", value: course.difficultyLevel || "未设置" },
    { label: "语言", value: course.languageCode || "未设置" },
    { label: "预计时间", value: course.estimatedMinutes ? `${course.estimatedMinutes} 分钟` : "未设置" },
    { label: "学校", value: course.schoolName || "未设置" },
  ];

  return (
    <section className="course-management-page">
      <div className="course-management-hero">
        <div className="course-management-hero-copy">
          <span className="course-surface-badge">课程信息</span>
          <h1>{course.title}</h1>
          <p>{course.description || "添加课程描述，帮助学生理解学习目标。"}</p>
        </div>

        <div className="course-management-stat-grid course-management-stat-grid-hero">
          <ManagementStatCard
            label="状态"
            value={formatCourseStatus(course.status)}
            valueClassName={course.status?.toLowerCase() === "published" ? "course-text-published" : undefined}
          />
          <ManagementStatCard
            label="已发布"
            value={publishedLabel}
            valueClassName={getPublishedTextClassName(publishedLabel)}
          />
          <ManagementStatCard label="模块" value={String(course.moduleCount ?? course.modules.length)} />
        </div>
      </div>

      <div className="course-management-grid">
        <ManagementPanel title="课程元数据" bodyClassName="course-management-panel-body-scroll">
          <ManagementKeyValueList items={metadataItems} />
        </ManagementPanel>

        <ManagementPanel title="学习路径" bodyClassName="course-management-panel-body-scroll">
          <p>{course.learningPathTitle || "默认学习路径"}</p>
          <p>
            {course.learningPathDescription ||
              "这里后续可以放置可编辑的学习路径说明、入门提示和顺序安排上下文。"}
          </p>
        </ManagementPanel>

        <ManagementPanel title="教学摘要" bodyClassName="course-management-panel-body-scroll">
          <p>{course.subtitle || "添加简短副标题，让管理视图中的课程更容易浏览。"}</p>
          <p>{course.description || "尚未添加详细课程描述。"}</p>
        </ManagementPanel>

        <ManagementPanel title="下一步管理操作" bodyClassName="course-management-panel-body-scroll">
          <p>检查模块完整性、补齐缺失资料，并在结构准备好后发布。</p>
          <div className="course-management-inline-tags">
            <span>元数据</span>
            <span>模块</span>
            <span>发布</span>
          </div>
        </ManagementPanel>
      </div>
    </section>
  );
}

export default CourseManagementOverviewPage;

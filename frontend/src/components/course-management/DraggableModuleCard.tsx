import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import type { CourseModule } from "../../types/course";

type DraggableModuleCardProps = {
  courseUuid: string;
  managementSearchSuffix: string;
  module: CourseModule;
  index: number;
  isDragging: boolean;
  isDropTarget: boolean;
  onDragStart: (moduleUuid: string) => void;
  onDragOver: (moduleUuid: string) => void;
  onDrop: () => void;
  onDragEnd: () => void;
  actions?: ReactNode;
};

function formatModuleStatus(status: CourseModule["status"]) {
  if (status === "available") {
    return "已发布";
  }

  if (status === "locked") {
    return "已锁定";
  }

  return "草稿";
}

function getModuleStatusTextClassName(status: CourseModule["status"]) {
  if (status === "available") {
    return "course-text-published";
  }

  if (status === "locked") {
    return "course-text-archived";
  }

  return "course-text-draft";
}

function getModuleStatusPillClassName(status: CourseModule["status"]) {
  if (status === "available") {
    return "course-management-status-pill-published";
  }

  if (status === "locked") {
    return "course-management-status-pill-archived";
  }

  return "course-management-status-pill-draft";
}

function DraggableModuleCard({
  courseUuid,
  managementSearchSuffix,
  module,
  index,
  isDragging,
  isDropTarget,
  onDragStart,
  onDragOver,
  onDrop,
  onDragEnd,
  actions,
}: DraggableModuleCardProps) {
  return (
    <article
      className={`course-management-list-card course-management-module-card${
        isDragging ? " course-management-module-card-dragging" : ""
      }${isDropTarget ? " course-management-module-card-drop-target" : ""}`}
      draggable
      onDragStart={() => onDragStart(module.moduleUuid)}
      onDragOver={(event) => {
        event.preventDefault();
        onDragOver(module.moduleUuid);
      }}
      onDrop={(event) => {
        event.preventDefault();
        onDrop();
      }}
      onDragEnd={onDragEnd}
    >
      <div className="course-management-module-handle" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>

      <Link to={`/course/${courseUuid}/management/modules/${module.moduleUuid}${managementSearchSuffix}`} className="course-management-module-body">
        <div className="course-management-list-top">
          <div>
            <span>模块 {module.sortOrder ?? index + 1}</span>
            <h3>{module.title}</h3>
          </div>
        </div>
        <p>{module.summary}</p>
        <div className="course-management-inline-tags">
          <span className="course-management-tag-duration">{module.durationLabel || "未设置时长"}</span>
          <span className="course-management-tag-materials">{module.materials.length}份资料</span>
        </div>
      </Link>

      <div className="course-management-module-card-actions" onClick={(event) => event.stopPropagation()}>
        <span
          className={`course-management-status-pill course-management-module-status-pill ${getModuleStatusPillClassName(module.status)} ${getModuleStatusTextClassName(module.status)}`}
        >
          {formatModuleStatus(module.status)}
        </span>
        {actions}
      </div>
    </article>
  );
}

export default DraggableModuleCard;

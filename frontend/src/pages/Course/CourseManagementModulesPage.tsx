import { useEffect, useMemo, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import { LuX } from "react-icons/lu";

import DraggableModuleCard from "../../components/course-management/DraggableModuleCard";
import { deleteManagedModule, reorderCourseModules } from "../../services/course";
import type { CourseModule } from "../../types/course";
import type { CourseManagementOutletContext } from "./CourseManagementLayout";

function moveModule<T>(items: T[], fromIndex: number, toIndex: number) {
  const nextItems = [...items];
  const [movedItem] = nextItems.splice(fromIndex, 1);
  nextItems.splice(toIndex, 0, movedItem);
  return nextItems;
}

function CourseManagementModulesPage() {
  const { course, refreshCourse, managementSearchSuffix } = useOutletContext<CourseManagementOutletContext>();
  const [modules, setModules] = useState(() =>
    [...course.modules].sort((left, right) => (left.sortOrder ?? 0) - (right.sortOrder ?? 0))
  );
  const [draggingModuleUuid, setDraggingModuleUuid] = useState<string | null>(null);
  const [dropTargetModuleUuid, setDropTargetModuleUuid] = useState<string | null>(null);
  const [isSavingOrder, setIsSavingOrder] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
  const [deletingModuleUuid, setDeletingModuleUuid] = useState<string | null>(null);
  const [pendingModuleDelete, setPendingModuleDelete] = useState<CourseModule | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const sortedModules = useMemo(
    () => modules.map((module, index) => ({ ...module, sortOrder: index + 1 })),
    [modules]
  );

  useEffect(() => {
    setModules([...course.modules].sort((left, right) => (left.sortOrder ?? 0) - (right.sortOrder ?? 0)));
  }, [course.modules]);

  const resetDragState = () => {
    setDraggingModuleUuid(null);
    setDropTargetModuleUuid(null);
  };

  useEffect(() => {
    if (!saveSuccess) {
      return;
    }

    const timer = window.setTimeout(() => {
      setSaveSuccess(null);
    }, 2400);

    return () => {
      window.clearTimeout(timer);
    };
  }, [saveSuccess]);

  useEffect(() => {
    if (!pendingModuleDelete) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !deletingModuleUuid) {
        setPendingModuleDelete(null);
        setDeleteError(null);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [deletingModuleUuid, pendingModuleDelete]);

  const persistModuleOrder = async (nextModules = sortedModules) => {
    setIsSavingOrder(true);
    setSaveError(null);
    setSaveSuccess(null);

    try {
      await reorderCourseModules(
        course.courseUuid,
        nextModules.map((module, index) => ({
          moduleUuid: module.moduleUuid,
          sortOrder: index + 1,
        }))
      );
      setSaveSuccess("Module order updated successfully.");
    } catch (error) {
      setModules([...course.modules].sort((left, right) => (left.sortOrder ?? 0) - (right.sortOrder ?? 0)));
      setSaveError(error instanceof Error ? error.message : "Failed to save module order.");
    } finally {
      setIsSavingOrder(false);
    }
  };

  const handleDragStart = (moduleUuid: string) => {
    setDraggingModuleUuid(moduleUuid);
    setDropTargetModuleUuid(moduleUuid);
    setSaveError(null);
    setDeleteError(null);
  };

  const handleDragOver = (moduleUuid: string) => {
    if (!draggingModuleUuid || draggingModuleUuid === moduleUuid) {
      return;
    }

    setModules((current) => {
      const fromIndex = current.findIndex((module) => module.moduleUuid === draggingModuleUuid);
      const toIndex = current.findIndex((module) => module.moduleUuid === moduleUuid);

      if (fromIndex < 0 || toIndex < 0 || fromIndex === toIndex) {
        return current;
      }

      return moveModule(current, fromIndex, toIndex);
    });

    setDropTargetModuleUuid(moduleUuid);
  };

  const handleDrop = () => {
    const nextModules = modules.map((module, index) => ({
      ...module,
      sortOrder: index + 1,
    }));

    setModules(nextModules);
    resetDragState();
    void persistModuleOrder(nextModules);
  };

  const handleDragEnd = () => {
    resetDragState();
  };

  const openModuleDelete = (module: CourseModule) => {
    if (deletingModuleUuid || isSavingOrder) {
      return;
    }

    setDeleteError(null);
    setPendingModuleDelete(module);
  };

  const closeModuleDelete = () => {
    if (deletingModuleUuid) {
      return;
    }

    setPendingModuleDelete(null);
    setDeleteError(null);
  };

  const handleModuleDelete = async () => {
    if (!pendingModuleDelete || deletingModuleUuid || isSavingOrder) {
      return;
    }

    setDeletingModuleUuid(pendingModuleDelete.moduleUuid);
    setDeleteError(null);
    setSaveError(null);

    try {
      await deleteManagedModule(course.courseUuid, pendingModuleDelete.moduleUuid);
      await refreshCourse();
      setPendingModuleDelete(null);
    } catch (error) {
      setDeleteError(error instanceof Error ? error.message : "Failed to delete module.");
    } finally {
      setDeletingModuleUuid(null);
    }
  };

  return (
    <section className="course-management-page">
      {saveSuccess ? (
        <div className="course-management-toast course-management-toast-success" role="status" aria-live="polite">
          <strong>成功</strong>
          <span>{saveSuccess}</span>
        </div>
      ) : null}

      <div className="course-management-section-heading">
        <div>
          <span className="course-surface-badge">模块</span>
          <h1>学习路径与模块</h1>
          <p>拖放模块以调整学习顺序，然后将新顺序保存到课程。</p>
        </div>
      </div>

      <div className="course-management-toolbar">
        <strong>{sortedModules.length} 个模块</strong>
        <span>{isSavingOrder ? "正在保存新顺序..." : "拖动卡片把手即可调整模块顺序。"}</span>
      </div>

      {saveError ? (
        <div className="course-management-inline-alert">
          <strong>无法保存模块顺序。</strong>
          <span>{saveError}</span>
        </div>
      ) : null}

      <div className="course-management-list">
        {sortedModules.length > 0 ? (
          sortedModules.map((module, index) => (
            <DraggableModuleCard
              key={module.moduleUuid}
              courseUuid={course.courseUuid}
              managementSearchSuffix={managementSearchSuffix}
              module={module}
              index={index}
              isDragging={draggingModuleUuid === module.moduleUuid}
              isDropTarget={dropTargetModuleUuid === module.moduleUuid}
              onDragStart={handleDragStart}
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              onDragEnd={handleDragEnd}
              actions={
                <button
                  type="button"
                  className="course-management-action-button course-management-action-button-danger"
                  onClick={() => openModuleDelete(module)}
                  disabled={isSavingOrder || deletingModuleUuid !== null}
                >
                  {deletingModuleUuid === module.moduleUuid ? "Deleting..." : "Delete module"}
                </button>
              }
            />
          ))
        ) : (
          <div className="course-empty-state">
            <strong>暂无模块</strong>
            <p>这门课程还没有模块记录。</p>
          </div>
        )}

        <Link to={`/course/${course.courseUuid}/management/modules/new${managementSearchSuffix}`} className="course-management-create-module-card">
          <span className="course-management-create-module-plus" aria-hidden="true" />
          <strong>创建新模块</strong>
          <p>向学习路径添加新模块，并立即打开编写表单。</p>
        </Link>
      </div>

      {pendingModuleDelete ? (
        <div className="course-management-modal-overlay" role="presentation">
          <div
            className="course-management-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-module-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="course-management-modal-header">
              <div>
                <span className="course-surface-badge">删除模块</span>
                <h3 id="delete-module-title">删除这个模块？</h3>
                <p className="course-management-modal-status">这将永久删除该模块及其资料。
                </p>
              </div>
              <button
                type="button"
                className="course-management-modal-close"
                onClick={closeModuleDelete}
                aria-label="关闭删除模块窗口"
                disabled={deletingModuleUuid !== null}
              >
                <LuX size={18} aria-hidden="true" />
              </button>
            </div>

            <div className="course-management-form course-management-form-single">
              <div className="course-management-inline-alert course-management-field-full">
                <strong>{pendingModuleDelete.title}</strong>
                <span>删除该模块后无法撤销。</span>
              </div>

              {deleteError ? (
                <div className="course-management-inline-alert course-management-field-full">
                  <strong>无法删除模块。</strong>
                  <span>{deleteError}</span>
                </div>
              ) : null}

              <div className="course-management-form-actions course-management-field-full">
                <button
                  type="button"
                  className="course-management-action-button"
                  onClick={closeModuleDelete}
                  disabled={deletingModuleUuid !== null}
                >保留模块
                </button>
                <button
                  type="button"
                  className="course-management-action-button course-management-action-button-danger"
                  onClick={() => void handleModuleDelete()}
                  disabled={deletingModuleUuid !== null}
                >
                  {deletingModuleUuid ? "Deleting..." : "永久删除"}
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}

export default CourseManagementModulesPage;

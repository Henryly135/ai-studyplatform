import { useEffect, useMemo, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";

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

  const handleModuleDelete = async (module: CourseModule) => {
    const confirmed = window.confirm(
      `Delete "${module.title}"? This will permanently remove the module and its materials.`
    );
    if (!confirmed || deletingModuleUuid || isSavingOrder) {
      return;
    }

    setDeletingModuleUuid(module.moduleUuid);
    setDeleteError(null);
    setSaveError(null);

    try {
      await deleteManagedModule(course.courseUuid, module.moduleUuid);
      await refreshCourse();
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
          <strong>Success</strong>
          <span>{saveSuccess}</span>
        </div>
      ) : null}

      <div className="course-management-section-heading">
        <div>
          <span className="course-surface-badge">Modules</span>
          <h1>Learning Paths & Modules</h1>
          <p>Drag and drop modules to change the learning sequence, then save the new order back to the course.</p>
        </div>
      </div>

      <div className="course-management-toolbar">
        <strong>{sortedModules.length} modules</strong>
        <span>{isSavingOrder ? "Saving new order..." : "Drag cards by the handle to reorder modules."}</span>
      </div>

      {saveError ? (
        <div className="course-management-inline-alert">
          <strong>Unable to save module order.</strong>
          <span>{saveError}</span>
        </div>
      ) : null}

      {deleteError ? (
        <div className="course-management-inline-alert">
          <strong>Unable to delete module.</strong>
          <span>{deleteError}</span>
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
                  onClick={() => void handleModuleDelete(module)}
                  disabled={isSavingOrder || deletingModuleUuid !== null}
                >
                  {deletingModuleUuid === module.moduleUuid ? "Deleting..." : "Delete module"}
                </button>
              }
            />
          ))
        ) : (
          <div className="course-empty-state">
            <strong>No modules yet</strong>
            <p>This course does not have module records yet.</p>
          </div>
        )}

        <Link to={`/course/${course.courseUuid}/management/modules/new${managementSearchSuffix}`} className="course-management-create-module-card">
          <span className="course-management-create-module-plus" aria-hidden="true" />
          <strong>Create new module</strong>
          <p>Add a new module to the learning path and open the authoring form right away.</p>
        </Link>
      </div>
    </section>
  );
}

export default CourseManagementModulesPage;

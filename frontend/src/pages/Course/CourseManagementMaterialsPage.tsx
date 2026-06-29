import { useState } from "react";
import { useOutletContext } from "react-router-dom";
import { LuTrash2 } from "react-icons/lu";

import ManagementPanel from "../../components/course-management/ManagementPanel";
import MaterialResourceCard from "../../components/course-management/MaterialResourceCard";
import { deleteManagedModuleMaterial } from "../../services/course";
import { emitAppRefresh } from "../../utils/refreshEvents";
import type { CourseManagementOutletContext } from "./CourseManagementLayout";

function CourseManagementMaterialsPage() {
  const { course, refreshCourse } = useOutletContext<CourseManagementOutletContext>();
  const [deletingMaterialKey, setDeletingMaterialKey] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const modulesWithMaterials = course.modules.filter((module) => module.materials.length > 0);

  const handleMaterialDelete = async (
    moduleUuid: string,
    moduleTitle: string,
    materialUuid: string,
    materialTitle: string
  ) => {
    const confirmed = window.confirm(
      `Delete "${materialTitle}" from "${moduleTitle}"? This will remove the material file and record.`
    );
    const materialKey = `${moduleUuid}:${materialUuid}`;
    if (!confirmed || deletingMaterialKey) {
      return;
    }

    setDeletingMaterialKey(materialKey);
    setDeleteError(null);

    try {
      await deleteManagedModuleMaterial(course.courseUuid, moduleUuid, materialUuid);
      await refreshCourse();
      emitAppRefresh({ scope: "course:materials", courseUuid: course.courseUuid, moduleUuid });
      emitAppRefresh({ scope: "course:detail", courseUuid: course.courseUuid, moduleUuid });
    } catch (error) {
      setDeleteError(error instanceof Error ? error.message : "Failed to delete material.");
    } finally {
      setDeletingMaterialKey(null);
    }
  };

  return (
    <section className="course-management-page">
      <div className="course-management-section-heading">
        <div>
          <span className="course-surface-badge">Materials</span>
          <h1>Material inventory</h1>
          <p>Review which assets are already attached to modules and where gaps still exist.</p>
        </div>
      </div>

      {deleteError ? (
        <div className="course-management-inline-alert">
          <strong>Unable to delete material.</strong>
          <span>{deleteError}</span>
        </div>
      ) : null}

      <div className="course-management-list">
        {modulesWithMaterials.length > 0 ? (
          modulesWithMaterials.map((module) => (
            <ManagementPanel key={module.moduleUuid} title={module.title}>
              <div className="course-management-material-grid">
                {module.materials.map((material) => (
                  <div key={material.materialUuid} className="course-management-material-card-with-actions">
                    <MaterialResourceCard
                      material={material}
                      moduleStatus={module.status}
                      trailingAction={
                        <button
                          type="button"
                          className="course-management-material-delete-inline"
                          onClick={() =>
                            void handleMaterialDelete(
                              module.moduleUuid,
                              module.title,
                              material.materialUuid,
                              material.title
                            )
                          }
                          disabled={deletingMaterialKey !== null}
                          aria-label={
                            deletingMaterialKey === `${module.moduleUuid}:${material.materialUuid}`
                              ? "Deleting material"
                              : `Delete ${material.title}`
                          }
                          title={
                            deletingMaterialKey === `${module.moduleUuid}:${material.materialUuid}`
                              ? "Deleting..."
                              : "Delete material"
                          }
                        >
                          <LuTrash2 size={16} aria-hidden="true" />
                        </button>
                      }
                    />
                  </div>
                ))}
              </div>
            </ManagementPanel>
          ))
        ) : (
          <div className="course-empty-state">
            <strong>No materials attached yet</strong>
            <p>Once modules have resources, they will appear here in an educator-friendly inventory view.</p>
          </div>
        )}
      </div>
    </section>
  );
}

export default CourseManagementMaterialsPage;

import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { LuTrash2, LuX } from "react-icons/lu";

import ManagementPanel from "../../components/course-management/ManagementPanel";
import MaterialResourceCard from "../../components/course-management/MaterialResourceCard";
import { deleteManagedModuleMaterial } from "../../services/course";
import { emitAppRefresh } from "../../utils/refreshEvents";
import type { CourseManagementOutletContext } from "./CourseManagementLayout";

type PendingMaterialDelete = {
  moduleUuid: string;
  moduleTitle: string;
  materialUuid: string;
  materialTitle: string;
};

function CourseManagementMaterialsPage() {
  const { course, refreshCourse } = useOutletContext<CourseManagementOutletContext>();
  const [deletingMaterialKey, setDeletingMaterialKey] = useState<string | null>(null);
  const [pendingMaterialDelete, setPendingMaterialDelete] = useState<PendingMaterialDelete | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const modulesWithMaterials = course.modules.filter((module) => module.materials.length > 0);

  useEffect(() => {
    if (!pendingMaterialDelete) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !deletingMaterialKey) {
        setPendingMaterialDelete(null);
        setDeleteError(null);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [deletingMaterialKey, pendingMaterialDelete]);

  const openMaterialDelete = (
    moduleUuid: string,
    moduleTitle: string,
    materialUuid: string,
    materialTitle: string
  ) => {
    if (deletingMaterialKey) {
      return;
    }

    setDeleteError(null);
    setPendingMaterialDelete({ moduleUuid, moduleTitle, materialUuid, materialTitle });
  };

  const closeMaterialDelete = () => {
    if (deletingMaterialKey) {
      return;
    }

    setPendingMaterialDelete(null);
    setDeleteError(null);
  };

  const handleMaterialDelete = async () => {
    if (!pendingMaterialDelete || deletingMaterialKey) {
      return;
    }

    const { moduleUuid, materialUuid } = pendingMaterialDelete;
    const materialKey = `${moduleUuid}:${materialUuid}`;
    setDeletingMaterialKey(materialKey);
    setDeleteError(null);

    try {
      await deleteManagedModuleMaterial(course.courseUuid, moduleUuid, materialUuid);
      await refreshCourse();
      emitAppRefresh({ scope: "course:materials", courseUuid: course.courseUuid, moduleUuid });
      emitAppRefresh({ scope: "course:detail", courseUuid: course.courseUuid, moduleUuid });
      setPendingMaterialDelete(null);
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
          <span className="course-surface-badge">资料</span>
          <h1>资料清单</h1>
          <p>查看哪些资源已关联到模块，以及仍有哪些缺口。</p>
        </div>
      </div>

      {deleteError ? (
        <div className="course-management-inline-alert">
          <strong>无法删除资料。</strong>
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
                            openMaterialDelete(
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
            <strong>暂无已关联资料</strong>
            <p>模块拥有资源后，会在这里以教师友好的清单视图展示。</p>
          </div>
        )}
      </div>

      {pendingMaterialDelete ? (
        <div className="course-management-modal-overlay" role="presentation">
          <div
            className="course-management-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-material-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="course-management-modal-header">
              <div>
                <span className="course-surface-badge">删除资料</span>
                <h3 id="delete-material-title">删除这份资料？</h3>
                <p className="course-management-modal-status">这会从模块中删除资料文件和记录。
                </p>
              </div>
              <button
                type="button"
                className="course-management-modal-close"
                onClick={closeMaterialDelete}
                aria-label="关闭删除资料窗口"
                disabled={deletingMaterialKey !== null}
              >
                <LuX size={18} aria-hidden="true" />
              </button>
            </div>

            <div className="course-management-form course-management-form-single">
              <div className="course-management-inline-alert course-management-field-full">
                <strong>{pendingMaterialDelete.materialTitle}</strong>
                <span>所属模块： {pendingMaterialDelete.moduleTitle}</span>
              </div>

              {deleteError ? (
                <div className="course-management-inline-alert course-management-field-full">
                  <strong>无法删除资料。</strong>
                  <span>{deleteError}</span>
                </div>
              ) : null}

              <div className="course-management-form-actions course-management-field-full">
                <button
                  type="button"
                  className="course-management-action-button"
                  onClick={closeMaterialDelete}
                  disabled={deletingMaterialKey !== null}
                >保留资料
                </button>
                <button
                  type="button"
                  className="course-management-action-button course-management-action-button-danger"
                  onClick={() => void handleMaterialDelete()}
                  disabled={deletingMaterialKey !== null}
                >
                  {deletingMaterialKey ? "Deleting..." : "永久删除"}
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}

export default CourseManagementMaterialsPage;

import { useCallback, useEffect, useState } from "react";
import { LuX } from "react-icons/lu";
import { useNavigate, useOutletContext } from "react-router-dom";

import CourseManagementModulesPage from "./CourseManagementModulesPage";
import { createManagedModule } from "../../services/course";
import type { CourseManagementOutletContext } from "./CourseManagementLayout";

function CourseManagementModuleCreatePage() {
  const navigate = useNavigate();
  const { course, refreshCourse, managementSearchSuffix } = useOutletContext<CourseManagementOutletContext>();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [content, setContent] = useState("");
  const [estimatedMinutes, setEstimatedMinutes] = useState("");
  const [isCreatingModule, setIsCreatingModule] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [didAttemptSubmit, setDidAttemptSubmit] = useState(false);

  const closeCreateModal = useCallback(() => {
    navigate(`/course/${course.courseUuid}/management/modules${managementSearchSuffix}`, { replace: true });
  }, [course.courseUuid, managementSearchSuffix, navigate]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closeCreateModal();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [closeCreateModal]);

  const isTitleInvalid = didAttemptSubmit && !title.trim();
  const isContentInvalid = didAttemptSubmit && !content.trim();

  const handleCreateModule = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setDidAttemptSubmit(true);

    if (!title.trim() || !content.trim()) {
      setCreateError("Please complete the required fields before creating the module.");
      return;
    }

    setIsCreatingModule(true);
    setCreateError(null);

    try {
      const createdModule = await createManagedModule(course.courseUuid, {
        title,
        description,
        content,
        estimatedMinutes: estimatedMinutes.trim() ? Number(estimatedMinutes) : null,
      });
      await refreshCourse();
      navigate(`/course/${course.courseUuid}/management/modules/${createdModule.moduleUuid}${managementSearchSuffix}`, { replace: true });
    } catch (error) {
      setCreateError(error instanceof Error ? error.message : "Failed to create module.");
    } finally {
      setIsCreatingModule(false);
    }
  };

  return (
    <>
      <CourseManagementModulesPage />

      <div className="course-management-modal-overlay" role="presentation">
        <div
          className="course-management-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="create-module-title"
          onClick={(event) => event.stopPropagation()}
        >
          <div className="course-management-modal-header">
            <div>
              <span className="course-surface-badge">Create Module</span>
              <h3 id="create-module-title">Create a new module</h3>
            </div>
            <button
              type="button"
              className="course-management-modal-close"
              onClick={closeCreateModal}
              aria-label="Close create module dialog"
            >
              <LuX size={18} aria-hidden="true" />
            </button>
          </div>

          <form className="course-management-form" onSubmit={handleCreateModule}>
            <label className="course-management-field course-management-field-full">
              <span>
                Title <em className="course-management-required-indicator">*</em>
              </span>
              <input
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                className={isTitleInvalid ? "course-management-input-invalid" : undefined}
                aria-invalid={isTitleInvalid}
                required
              />
              {isTitleInvalid ? <small className="course-management-field-error">Title is required.</small> : null}
            </label>

            <label className="course-management-field course-management-field-full">
              <span>Description</span>
              <textarea value={description} onChange={(event) => setDescription(event.target.value)} rows={4} />
            </label>

            <label className="course-management-field course-management-field-full">
              <span>
                Content <em className="course-management-required-indicator">*</em>
              </span>
              <textarea
                value={content}
                onChange={(event) => setContent(event.target.value)}
                rows={8}
                className={isContentInvalid ? "course-management-input-invalid" : undefined}
                aria-invalid={isContentInvalid}
                required
              />
              {isContentInvalid ? <small className="course-management-field-error">Content is required.</small> : null}
            </label>

            <label className="course-management-field">
              <span>Estimated minutes</span>
              <input
                type="number"
                min="1"
                value={estimatedMinutes}
                onChange={(event) => setEstimatedMinutes(event.target.value)}
              />
            </label>

            {createError ? (
              <div className="course-management-inline-alert course-management-field-full">
                <strong>Unable to create module.</strong>
                <span>{createError}</span>
              </div>
            ) : null}

            <div className="course-management-form-actions course-management-field-full">
              <button
                type="submit"
                className="course-management-action-button course-management-action-button-primary"
                disabled={isCreatingModule}
              >
                {isCreatingModule ? "Creating..." : "Create module"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </>
  );
}

export default CourseManagementModuleCreatePage;

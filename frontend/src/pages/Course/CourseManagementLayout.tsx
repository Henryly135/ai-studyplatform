import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, Navigate, NavLink, Outlet, useLocation, useNavigate, useParams } from "react-router-dom";
import { LuX } from "react-icons/lu";

import LocalizedFileInput from "../../components/common/LocalizedFileInput";
import HomeNotificationsMenu from "../../components/home/HomeNotificationsMenu";
import ManagementSidebarMeta from "../../components/course-management/ManagementSidebarMeta";
import ManagementSidebarSummary from "../../components/course-management/ManagementSidebarSummary";
import { useLocale } from "../../i18n/locale";
import {
  deleteManagedCourse,
  getManagedCourseByUuid,
  publishManagedCourse,
  updateManagedCourse,
  uploadManagedCourseCover,
} from "../../services/course";
import type { CurrentUserResponse } from "../../types/auth";
import type { CourseRecord } from "../../types/course";
import { emitAppRefresh, subscribeAppRefresh } from "../../utils/refreshEvents";
import "./CoursePages.css";

export type CourseManagementOutletContext = {
  course: CourseRecord;
  refreshCourse: () => Promise<void>;
  managementSearchSuffix: string;
};

function formatStatusLabel(status?: string) {
  if (!status) {
    return "Draft";
  }

  return status.charAt(0).toUpperCase() + status.slice(1);
}

function getManagementStatusClassName(status?: string) {
  const normalizedStatus = status?.toLowerCase() ?? "draft";

  if (normalizedStatus === "published") {
    return "course-management-status-pill-published";
  }

  if (normalizedStatus === "archived") {
    return "course-management-status-pill-archived";
  }

  return "course-management-status-pill-draft";
}

function getPublishedTextClassName(status?: string) {
  return status?.toLowerCase() === "published" ? "course-text-published" : undefined;
}

function moduleHasPublishableMaterial(materialCount: number) {
  return materialCount > 0;
}

const COURSE_DIFFICULTY_OPTIONS = [
  { value: "beginner", label: "Beginner" },
  { value: "intermediate", label: "Intermediate" },
  { value: "advanced", label: "Advanced" },
] as const;

type CourseEditFormState = {
  title: string;
  subtitle: string;
  description: string;
  category: string;
  difficultyLevel: string;
  languageCode: string;
  estimatedMinutes: string;
  learningPathTitle: string;
  learningPathDescription: string;
  coverImage: File | null;
  currentCoverImageUrl: string | null;
};

function buildEditFormState(course: CourseRecord): CourseEditFormState {
  return {
    title: course.title,
    subtitle: course.subtitle,
    description: course.description,
    category: course.category,
    difficultyLevel: course.difficultyLevel,
    languageCode: course.languageCode,
    estimatedMinutes: course.estimatedMinutes ? String(course.estimatedMinutes) : "",
    learningPathTitle: course.learningPathTitle || "",
    learningPathDescription: course.learningPathDescription || "",
    coverImage: null,
    currentCoverImageUrl: course.coverImageUrl,
  };
}

function isSameEditFormState(left: CourseEditFormState | null, right: CourseEditFormState | null) {
  if (!left || !right) {
    return false;
  }

  return (
    left.title === right.title &&
    left.subtitle === right.subtitle &&
    left.description === right.description &&
    left.category === right.category &&
    left.difficultyLevel === right.difficultyLevel &&
    left.languageCode === right.languageCode &&
    left.estimatedMinutes === right.estimatedMinutes &&
    left.learningPathTitle === right.learningPathTitle &&
    left.learningPathDescription === right.learningPathDescription &&
    left.currentCoverImageUrl === right.currentCoverImageUrl &&
    left.coverImage === right.coverImage
  );
}

function getCoverFileName(coverImageUrl: string | null) {
  if (!coverImageUrl) {
    return null;
  }

  try {
    const parsedUrl = new URL(coverImageUrl);
    const pathname = parsedUrl.pathname;
    const lastSegment = pathname.split("/").pop()?.trim() ?? "";
    return lastSegment || null;
  } catch {
    const lastSegment = coverImageUrl.split("/").pop()?.split("?")[0]?.trim() ?? "";
    return lastSegment || null;
  }
}

function CourseManagementLayout() {
  const { text } = useLocale();
  const { courseUuid } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const currentUser = useMemo(() => {
    const raw = localStorage.getItem("currentUser");
    if (!raw) {
      return null;
    }

    try {
      return JSON.parse(raw) as CurrentUserResponse;
    } catch {
      return null;
    }
  }, []);
  const canUseNotifications =
    currentUser?.identity === "Learner" || currentUser?.identity === "Educator";
  const [course, setCourse] = useState<CourseRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editForm, setEditForm] = useState<CourseEditFormState | null>(null);
  const [initialEditForm, setInitialEditForm] = useState<CourseEditFormState | null>(null);
  const [isSavingEdit, setIsSavingEdit] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [isPublishModalOpen, setIsPublishModalOpen] = useState(false);
  const [selectedModuleUuids, setSelectedModuleUuids] = useState<string[]>([]);
  const [isPublishingCourse, setIsPublishingCourse] = useState(false);
  const [publishError, setPublishError] = useState<string | null>(null);
  const [publishToastSuccess, setPublishToastSuccess] = useState<string | null>(null);
  const [isDeletingCourse, setIsDeletingCourse] = useState(false);
  const [deleteCourseError, setDeleteCourseError] = useState<string | null>(null);
  const searchParams = new URLSearchParams(location.search);
  const source = searchParams.get("from");
  const isAdminCourseManagementSource = source === "course-management";
  const managementSearchSuffix = isAdminCourseManagementSource ? "?from=course-management" : "";
  const backLink = isAdminCourseManagementSource ? "/home/course-management" : "/home/managed-courses";
  const backLabel = isAdminCourseManagementSource ? "Back to course management" : "Back to managed courses";

  const refreshCourse = useCallback(async () => {
    if (!courseUuid) {
      return;
    }

    const data = await getManagedCourseByUuid(courseUuid);
    setCourse(data);
  }, [courseUuid]);

  useEffect(() => {
    let cancelled = false;

    const loadCourse = async () => {
      if (!courseUuid) {
        setLoading(false);
        return;
      }

      try {
        const data = await getManagedCourseByUuid(courseUuid);
        if (!cancelled) {
          setCourse(data);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void loadCourse();

    return () => {
      cancelled = true;
    };
  }, [courseUuid, refreshCourse]);

  useEffect(() => {
    return subscribeAppRefresh(
      ["course:managed", "course:materials", "course:quiz", "course:detail"],
      (detail) => {
        if (!courseUuid || (detail.courseUuid && detail.courseUuid !== courseUuid)) {
          return;
        }
        void refreshCourse();
      }
    );
  }, [courseUuid, refreshCourse]);

  const activeSectionTitle = useMemo(() => {
    if (location.pathname.endsWith("/modules")) {
      return "Learning Paths & Modules";
    }

    if (location.pathname.endsWith("/modules/new")) {
      return "Learning Paths & Modules";
    }

    if (location.pathname.endsWith("/materials")) {
      return "Material Inventory";
    }

    if (location.pathname.endsWith("/enrolments")) {
      return "User Enrolments";
    }

    if (location.pathname.includes("/management/modules/")) {
      return "Module Editor";
    }

    if (location.pathname.endsWith("/publishing")) {
      return "Publishing Control";
    }

    return "Course Overview";
  }, [location.pathname]);

  const shouldHideCourseHeaderActions = location.pathname.includes("/management/modules/");

  const closeEditModal = () => {
    setIsEditModalOpen(false);
    setEditError(null);
  };

  const closePublishModal = () => {
    setIsPublishModalOpen(false);
    setPublishError(null);
  };

  useEffect(() => {
    if (!isEditModalOpen && !isPublishModalOpen) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        if (isEditModalOpen) {
          closeEditModal();
        }
        if (isPublishModalOpen) {
          closePublishModal();
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isEditModalOpen, isPublishModalOpen]);

  useEffect(() => {
    if (!publishToastSuccess) {
      return;
    }

    const timer = window.setTimeout(() => {
      setPublishToastSuccess(null);
    }, 2400);

    return () => {
      window.clearTimeout(timer);
    };
  }, [publishToastSuccess]);

  if (loading) {
    return (
      <div className="course-management-shell course-management-shell-loading">
        <div className="home-loading">Loading managed course...</div>
      </div>
    );
  }

  if (!course || !courseUuid) {
    return <Navigate to="/home/managed-courses" replace />;
  }

  const openEditModal = () => {
    const nextEditForm = buildEditFormState(course);
    setEditForm(nextEditForm);
    setInitialEditForm(nextEditForm);
    setEditError(null);
    setIsEditModalOpen(true);
  };

  const openPublishModal = () => {
    setSelectedModuleUuids(
      course.modules.filter((module) => moduleHasPublishableMaterial(module.materials.length)).map((module) => module.moduleUuid)
    );
    setPublishError(null);
    setIsPublishModalOpen(true);
  };

  const handleEditFieldChange = (field: keyof CourseEditFormState, value: string | boolean | File | null) => {
    setEditForm((current) => (current ? { ...current, [field]: value } : current));
  };

  const handleEditSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!editForm) {
      return;
    }

    setIsSavingEdit(true);
    setEditError(null);

    try {
      let updatedCourse = await updateManagedCourse(course.courseUuid, {
        title: editForm.title.trim(),
        subtitle: editForm.subtitle.trim(),
        description: editForm.description.trim(),
        category: editForm.category.trim(),
        difficultyLevel: editForm.difficultyLevel.trim(),
        languageCode: editForm.languageCode.trim(),
        estimatedMinutes: editForm.estimatedMinutes.trim() ? Number(editForm.estimatedMinutes) : null,
        learningPathTitle: editForm.learningPathTitle.trim(),
        learningPathDescription: editForm.learningPathDescription.trim(),
        coverImageUrl: editForm.currentCoverImageUrl ?? "",
        isPublic: true,
      });

      setCourse(updatedCourse);

      if (editForm.coverImage) {
        updatedCourse = await uploadManagedCourseCover(course.courseUuid, editForm.coverImage);
      }

      setCourse(updatedCourse);
      setIsEditModalOpen(false);
      emitAppRefresh({ scope: "course:managed", courseUuid: course.courseUuid });
      emitAppRefresh({ scope: "course:catalog", courseUuid: course.courseUuid });
    } catch (error) {
      setEditError(error instanceof Error ? error.message : "Failed to update course.");
    } finally {
      setIsSavingEdit(false);
    }
  };

  const isPublished = course.status?.toLowerCase() === "published";
  const hasUnsavedChanges = isEditModalOpen && !isSameEditFormState(editForm, initialEditForm);
  const managementStatusClassName = getManagementStatusClassName(course.status);
  const publishedTextClassName = getPublishedTextClassName(course.status);
  const canSubmitPublish = selectedModuleUuids.length > 0 && !isPublished;

  const handlePublishModuleToggle = (moduleUuid: string, checked: boolean) => {
    setSelectedModuleUuids((current) => {
      if (checked) {
        return current.includes(moduleUuid) ? current : [...current, moduleUuid];
      }

      return current.filter((item) => item !== moduleUuid);
    });
  };

  const handlePublishSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmitPublish) {
      return;
    }

    setIsPublishingCourse(true);
    setPublishError(null);

    try {
      await publishManagedCourse(course.courseUuid, selectedModuleUuids);
      await refreshCourse();
      closePublishModal();
      setPublishToastSuccess("Course published successfully.");
      emitAppRefresh({ scope: "course:managed", courseUuid: course.courseUuid });
      emitAppRefresh({ scope: "course:catalog", courseUuid: course.courseUuid });
      emitAppRefresh({ scope: "course:detail", courseUuid: course.courseUuid });
    } catch (error) {
      setPublishError(error instanceof Error ? error.message : "Failed to publish course.");
    } finally {
      setIsPublishingCourse(false);
    }
  };

  const handleDeleteCourse = async () => {
    const confirmed = window.confirm(
      `Delete "${course.title}"? This will permanently remove the course, modules, materials, and related course data.`
    );
    if (!confirmed || isDeletingCourse) {
      return;
    }

    setIsDeletingCourse(true);
    setDeleteCourseError(null);

    try {
      await deleteManagedCourse(course.courseUuid);
      navigate(backLink, { replace: true });
    } catch (error) {
      setDeleteCourseError(error instanceof Error ? error.message : "Failed to delete course.");
    } finally {
      setIsDeletingCourse(false);
    }
  };

  return (
    <>
      {publishToastSuccess ? (
        <div className="course-management-toast course-management-toast-success" role="status" aria-live="polite">
          <strong>Publish complete</strong>
          <span>{publishToastSuccess}</span>
        </div>
      ) : null}

      <div className="course-management-shell">
        <aside className="course-management-sidebar">
          <Link to={backLink} className="course-layout-back-link">
            {backLabel}
          </Link>

          <ManagementSidebarSummary
            title={course.title}
            summary={course.subtitle || course.description || "No management summary available yet."}
          />

          <ManagementSidebarMeta
            items={[
              { label: "Course status", value: formatStatusLabel(course.status), valueClassName: publishedTextClassName },
              { label: "Modules", value: String(course.moduleCount ?? course.modules.length) },
            ]}
          />

          <nav className="course-management-nav" aria-label="Course management navigation">
            <NavLink
              to={`/course/${course.courseUuid}/management${managementSearchSuffix}`}
              end
              className={({ isActive }) =>
                isActive ? "course-management-nav-item course-management-nav-item-active" : "course-management-nav-item"
              }
            >
              <span>Course Info</span>
              <small>Metadata and learning path</small>
            </NavLink>

            <NavLink
              to={`/course/${course.courseUuid}/management/modules${managementSearchSuffix}`}
              className={({ isActive }) =>
                isActive ? "course-management-nav-item course-management-nav-item-active" : "course-management-nav-item"
              }
            >
              <span>Modules</span>
              <small>Structure and readiness</small>
            </NavLink>

            <NavLink
              to={`/course/${course.courseUuid}/management/enrolments${managementSearchSuffix}`}
              className={({ isActive }) =>
                isActive ? "course-management-nav-item course-management-nav-item-active" : "course-management-nav-item"
              }
            >
              <span>User enrolments</span>
              <small>Current learner roster</small>
            </NavLink>

            <NavLink
              to={`/course/${course.courseUuid}/management/materials${managementSearchSuffix}`}
              className={({ isActive }) =>
                isActive ? "course-management-nav-item course-management-nav-item-active" : "course-management-nav-item"
              }
            >
              <span>Materials</span>
              <small>Attached learning assets</small>
            </NavLink>

            {!isAdminCourseManagementSource ? (
              <NavLink
                to={`/course/${course.courseUuid}/forum?from=managed-courses`}
                className={({ isActive }) =>
                  isActive ? "course-management-nav-item course-management-nav-item-active" : "course-management-nav-item"
                }
              >
                <span>Forum</span>
                <small>Open the course discussion board</small>
              </NavLink>
            ) : null}

            <NavLink
              to={`/course/${course.courseUuid}/management/publishing${managementSearchSuffix}`}
              className={({ isActive }) =>
                isActive ? "course-management-nav-item course-management-nav-item-active" : "course-management-nav-item"
              }
            >
              <span>Publishing</span>
              <small>Status checks and release</small>
            </NavLink>
          </nav>
        </aside>

        <div className="course-management-main">
          <header className="course-management-header">
            <div className="course-management-header-title-group">
              <span className="home-topbar-label">Managed Course</span>
              <div className="course-management-header-title-row">
                <h2>{activeSectionTitle}</h2>
                {!location.pathname.includes("/management/modules/") ? (
                  <span className={`course-management-status-pill ${managementStatusClassName}`}>
                    {formatStatusLabel(course.status)}
                  </span>
                ) : null}
              </div>
            </div>

            {!shouldHideCourseHeaderActions ? (
              <div className="course-management-header-actions">
                {canUseNotifications ? <HomeNotificationsMenu /> : null}
                <button
                  type="button"
                  className="course-management-action-button course-management-action-button-danger"
                  onClick={handleDeleteCourse}
                  disabled={isDeletingCourse}
                >
                  {isDeletingCourse ? "Deleting..." : "Delete Course"}
                </button>
                <button type="button" className="course-management-action-button" onClick={openEditModal}>
                  Edit Course
                </button>
                <span
                  className="course-management-tooltip-wrapper"
                  title={
                    isPublished
                      ? "This course has already been published."
                      : "Choose which modules should be published with this course."
                  }
                >
                  <button
                    type="button"
                    className="course-management-action-button course-management-action-button-primary"
                    disabled={isPublished}
                    onClick={openPublishModal}
                  >
                    Publish
                  </button>
                </span>
              </div>
            ) : null}
          </header>

          <main className="course-management-content">
            <div className="course-management-content-scroll">
              {deleteCourseError ? (
                <div className="course-management-inline-alert">
                  <strong>Unable to delete course.</strong>
                  <span>{deleteCourseError}</span>
                </div>
              ) : null}
              <Outlet context={{ course, refreshCourse, managementSearchSuffix }} />
            </div>
          </main>
        </div>
      </div>

      {isEditModalOpen && editForm ? (
        <div className="course-management-modal-overlay" role="presentation">
          <div
            className="course-management-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="edit-course-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="course-management-modal-header">
              <div>
                <span className="course-surface-badge">Edit Course</span>
                <h3 id="edit-course-title">Update course information</h3>
                {hasUnsavedChanges ? <p className="course-management-modal-status">Unsaved changes</p> : null}
              </div>
              <button
                type="button"
                className="course-management-modal-close"
                onClick={closeEditModal}
                aria-label="Close edit course dialog"
              >
                <LuX size={18} aria-hidden="true" />
              </button>
            </div>

            <form className="course-management-form" onSubmit={handleEditSubmit}>
              <label className="course-management-field">
                <span>Title</span>
                <input
                  value={editForm.title}
                  onChange={(event) => handleEditFieldChange("title", event.target.value)}
                  required
                />
              </label>

              <label className="course-management-field">
                <span>Subtitle</span>
                <input
                  value={editForm.subtitle}
                  onChange={(event) => handleEditFieldChange("subtitle", event.target.value)}
                />
              </label>

              <label className="course-management-field course-management-field-full">
                <span>Description</span>
                <textarea
                  value={editForm.description}
                  onChange={(event) => handleEditFieldChange("description", event.target.value)}
                  rows={4}
                />
              </label>

              <label className="course-management-field">
                <span>Category</span>
                <input
                  value={editForm.category}
                  onChange={(event) => handleEditFieldChange("category", event.target.value)}
                />
              </label>

              <label className="course-management-field">
                <span>Difficulty</span>
                <select
                  value={editForm.difficultyLevel}
                  onChange={(event) => handleEditFieldChange("difficultyLevel", event.target.value)}
                >
                  <option value="">Select difficulty</option>
                  {COURSE_DIFFICULTY_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="course-management-field">
                <span>Language</span>
                <input
                  value={editForm.languageCode}
                  onChange={(event) => handleEditFieldChange("languageCode", event.target.value)}
                />
              </label>

              <label className="course-management-field">
                <span>Estimated minutes</span>
                <input
                  type="number"
                  min="1"
                  value={editForm.estimatedMinutes}
                  onChange={(event) => handleEditFieldChange("estimatedMinutes", event.target.value)}
                />
              </label>

              <label className="course-management-field course-management-field-full">
                <span>Learning path title</span>
                <input
                  value={editForm.learningPathTitle}
                  onChange={(event) => handleEditFieldChange("learningPathTitle", event.target.value)}
                />
              </label>

              <label className="course-management-field course-management-field-full">
                <span>Learning path description</span>
                <textarea
                  value={editForm.learningPathDescription}
                  onChange={(event) => handleEditFieldChange("learningPathDescription", event.target.value)}
                  rows={4}
                />
              </label>

              <label className="course-management-field course-management-field-full">
                <span>{text.upload.coverImageLabel}</span>
                <LocalizedFileInput
                  accept="image/*"
                  selectedFileName={editForm.coverImage?.name ?? getCoverFileName(editForm.currentCoverImageUrl)}
                  onFileChange={(file) => handleEditFieldChange("coverImage", file)}
                />
              </label>

              {editError ? (
                <div className="course-management-inline-alert course-management-field-full">
                  <strong>Unable to update course.</strong>
                  <span>{editError}</span>
                </div>
              ) : null}

              <div className="course-management-form-actions course-management-field-full">
                <button type="button" className="course-management-action-button" onClick={closeEditModal}>
                  Cancel
                </button>
                <button
                  type="submit"
                  className="course-management-action-button course-management-action-button-primary"
                  disabled={isSavingEdit}
                >
                  {isSavingEdit ? "Saving..." : "Save changes"}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}

      {isPublishModalOpen ? (
        <div className="course-management-modal-overlay" role="presentation">
          <div
            className="course-management-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="publish-course-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="course-management-modal-header">
              <div>
                <span className="course-surface-badge">Publish Course</span>
                <h3 id="publish-course-title">Choose modules to publish</h3>
                <p className="course-management-modal-status">
                  Selected modules will be published together with this course.
                </p>
              </div>
              <button
                type="button"
                className="course-management-modal-close"
                onClick={closePublishModal}
                aria-label="Close publish course dialog"
              >
                <LuX size={18} aria-hidden="true" />
              </button>
            </div>

            <form
              className="course-management-form course-management-form-single course-management-publish-form"
              onSubmit={handlePublishSubmit}
            >
              <div className="course-management-inline-note course-management-field-full">
                <strong>Publishing rule</strong>
                <span>Each selected module must have content and at least one attached material before publishing.</span>
              </div>

              <div className="course-management-module-selection course-management-field-full">
                {course.modules.map((module) => (
                  <label
                    key={module.moduleUuid}
                    className={`course-management-module-selection-item${
                      moduleHasPublishableMaterial(module.materials.length)
                        ? ""
                        : " course-management-module-selection-item-disabled"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={selectedModuleUuids.includes(module.moduleUuid)}
                      disabled={!moduleHasPublishableMaterial(module.materials.length)}
                      onChange={(event) => handlePublishModuleToggle(module.moduleUuid, event.target.checked)}
                    />
                    <div className="course-management-module-selection-copy">
                      <strong>{module.title}</strong>
                      <span>
                        {module.materials.length} material{module.materials.length === 1 ? "" : "s"} •{" "}
                        {formatStatusLabel(module.status)}
                      </span>
                      {!moduleHasPublishableMaterial(module.materials.length) ? (
                        <em className="course-management-module-selection-warning">
                          Upload at least one material before this module can be published.
                        </em>
                      ) : null}
                    </div>
                  </label>
                ))}
              </div>

              {publishError ? (
                <div className="course-management-inline-alert course-management-field-full">
                  <strong>Unable to publish course.</strong>
                  <span>{publishError}</span>
                </div>
              ) : null}

              <div className="course-management-form-actions course-management-field-full">
                <button type="button" className="course-management-action-button" onClick={closePublishModal}>
                  Cancel
                </button>
                <button
                  type="submit"
                  className="course-management-action-button course-management-action-button-primary"
                  disabled={!canSubmitPublish || isPublishingCourse}
                >
                  {isPublishingCourse ? "Publishing..." : "Publish course"}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </>
  );
}

export default CourseManagementLayout;

import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, Navigate, NavLink, Outlet, useLocation, useNavigate, useParams } from "react-router-dom";
import { LuX } from "react-icons/lu";

import LocalizedFileInput from "../../components/common/LocalizedFileInput";
import HomeNotificationsMenu from "../../components/home/HomeNotificationsMenu";
import ManagementSidebarMeta from "../../components/course-management/ManagementSidebarMeta";
import ManagementSidebarSummary from "../../components/course-management/ManagementSidebarSummary";
import { useLocale } from "../../i18n/locale";
import { getStoredCurrentUser } from "../../services/api";
import {
  deleteManagedCourse,
  getManagedCourseByUuid,
  publishManagedCourse,
  updateManagedCourse,
  uploadManagedCourseCover,
} from "../../services/course";
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
    return "草稿";
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
  { value: "beginner", label: "入门" },
  { value: "intermediate", label: "中级" },
  { value: "advanced", label: "高级" },
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
  const currentUser = useMemo(() => getStoredCurrentUser(), []);
  const canUseNotifications =
    currentUser?.identity === "Learner" ||
    currentUser?.identity === "Educator" ||
    currentUser?.identity === "Admin";
  const canAccessCourseManagement =
    currentUser?.identity === "Educator" || currentUser?.identity === "Admin";
  const [course, setCourse] = useState<CourseRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
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
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [isDeletingCourse, setIsDeletingCourse] = useState(false);
  const [deleteCourseError, setDeleteCourseError] = useState<string | null>(null);
  const searchParams = new URLSearchParams(location.search);
  const source = searchParams.get("from");
  const isAdminCourseManagementSource = source === "course-management";
  const managementSearchSuffix = isAdminCourseManagementSource ? "?from=course-management" : "";
  const backLink = isAdminCourseManagementSource ? "/home/course-management" : "/home/managed-courses";
  const backLabel = isAdminCourseManagementSource ? "Back to course management" : "返回管理课程";

  const refreshCourse = useCallback(async () => {
    if (!courseUuid || !canAccessCourseManagement) {
      return;
    }

    const data = await getManagedCourseByUuid(courseUuid);
    setCourse(data);
  }, [canAccessCourseManagement, courseUuid]);

  useEffect(() => {
    let cancelled = false;

    const loadCourse = async () => {
      if (!canAccessCourseManagement) {
        setLoading(false);
        return;
      }

      if (!courseUuid) {
        setLoading(false);
        return;
      }

      try {
        const data = await getManagedCourseByUuid(courseUuid);
        if (!cancelled) {
          setCourse(data);
          setLoadError(null);
        }
      } catch (error) {
        if (!cancelled) {
          setCourse(null);
          setLoadError(error instanceof Error ? error.message : "Failed to load managed course.");
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
  }, [canAccessCourseManagement, courseUuid, refreshCourse]);

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
      return "学习路径与模块";
    }

    if (location.pathname.endsWith("/modules/new")) {
      return "学习路径与模块";
    }

    if (location.pathname.endsWith("/materials")) {
      return "Material Inventory";
    }

    if (location.pathname.endsWith("/enrolments")) {
      return "用户报名";
    }

    if (location.pathname.includes("/management/modules/")) {
      return "Module Editor";
    }

    if (location.pathname.endsWith("/publishing")) {
      return "Publishing Control";
    }

    return "课程概览";
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

  const closeDeleteModal = useCallback(() => {
    if (isDeletingCourse) {
      return;
    }

    setIsDeleteModalOpen(false);
    setDeleteCourseError(null);
  }, [isDeletingCourse]);

  useEffect(() => {
    if (!isEditModalOpen && !isPublishModalOpen && !isDeleteModalOpen) {
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
        if (isDeleteModalOpen) {
          closeDeleteModal();
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [closeDeleteModal, isDeleteModalOpen, isEditModalOpen, isPublishModalOpen]);

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
        <div className="home-loading">正在加载管理课程...</div>
      </div>
    );
  }

  if (!canAccessCourseManagement) {
    return <Navigate to="/home" replace />;
  }

  if (loadError) {
    return (
      <div className="course-management-shell course-management-shell-loading">
        <div className="course-management-inline-alert">
          <strong>无法加载管理课程。</strong>
          <span>{loadError}</span>
          <Link to="/home/managed-courses" className="course-management-back-link">返回管理课程
          </Link>
        </div>
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

  const openDeleteModal = () => {
    setDeleteCourseError(null);
    setIsDeleteModalOpen(true);
  };

  const handleDeleteCourse = async () => {
    if (isDeletingCourse) {
      return;
    }

    setIsDeletingCourse(true);
    setDeleteCourseError(null);

    try {
      await deleteManagedCourse(course.courseUuid);
      setIsDeleteModalOpen(false);
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
          <strong>发布完成</strong>
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
              { label: "课程状态", value: formatStatusLabel(course.status), valueClassName: publishedTextClassName },
              { label: "模块", value: String(course.moduleCount ?? course.modules.length) },
            ]}
          />

          <nav className="course-management-nav" aria-label="课程管理导航">
            <NavLink
              to={`/course/${course.courseUuid}/management${managementSearchSuffix}`}
              end
              className={({ isActive }) =>
                isActive ? "course-management-nav-item course-management-nav-item-active" : "course-management-nav-item"
              }
            >
              <span>课程信息</span>
              <small>元数据和学习路径</small>
            </NavLink>

            <NavLink
              to={`/course/${course.courseUuid}/management/modules${managementSearchSuffix}`}
              className={({ isActive }) =>
                isActive ? "course-management-nav-item course-management-nav-item-active" : "course-management-nav-item"
              }
            >
              <span>模块</span>
              <small>结构和发布准备度</small>
            </NavLink>

            <NavLink
              to={`/course/${course.courseUuid}/management/enrolments${managementSearchSuffix}`}
              className={({ isActive }) =>
                isActive ? "course-management-nav-item course-management-nav-item-active" : "course-management-nav-item"
              }
            >
              <span>用户报名</span>
              <small>当前学生名单</small>
            </NavLink>

            <NavLink
              to={`/course/${course.courseUuid}/management/materials${managementSearchSuffix}`}
              className={({ isActive }) =>
                isActive ? "course-management-nav-item course-management-nav-item-active" : "course-management-nav-item"
              }
            >
              <span>资料</span>
              <small>已关联学习资源</small>
            </NavLink>

            {!isAdminCourseManagementSource ? (
              <NavLink
                to={`/course/${course.courseUuid}/forum?from=managed-courses`}
                className={({ isActive }) =>
                  isActive ? "course-management-nav-item course-management-nav-item-active" : "course-management-nav-item"
                }
              >
                <span>论坛</span>
                <small>打开课程讨论区</small>
              </NavLink>
            ) : null}

            <NavLink
              to={`/course/${course.courseUuid}/management/publishing${managementSearchSuffix}`}
              className={({ isActive }) =>
                isActive ? "course-management-nav-item course-management-nav-item-active" : "course-management-nav-item"
              }
            >
              <span>发布</span>
              <small>状态检查和发布</small>
            </NavLink>
          </nav>
        </aside>

        <div className="course-management-main">
          <header className="course-management-header">
            <div className="course-management-header-title-group">
              <span className="home-topbar-label">管理课程</span>
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
                  onClick={openDeleteModal}
                  disabled={isDeletingCourse}
                >
                  {isDeletingCourse ? "Deleting..." : "删除课程"}
                </button>
                <button type="button" className="course-management-action-button" onClick={openEditModal}>编辑课程
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
                  >发布
                  </button>
                </span>
              </div>
            ) : null}
          </header>

          <main className="course-management-content">
            <div className="course-management-content-scroll">
              {deleteCourseError ? (
                <div className="course-management-inline-alert">
                  <strong>无法删除课程。</strong>
                  <span>{deleteCourseError}</span>
                </div>
              ) : null}
              <Outlet context={{ course, refreshCourse, managementSearchSuffix }} />
            </div>
          </main>
        </div>
      </div>

      {isDeleteModalOpen ? (
        <div className="course-management-modal-overlay" role="presentation">
          <div
            className="course-management-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-course-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="course-management-modal-header">
              <div>
                <span className="course-surface-badge">删除课程</span>
                <h3 id="delete-course-title">删除这门课程？</h3>
                <p className="course-management-modal-status">这将永久删除课程、模块、资料和相关课程数据。
                </p>
              </div>
              <button
                type="button"
                className="course-management-modal-close"
                onClick={closeDeleteModal}
                aria-label="关闭删除课程窗口"
                disabled={isDeletingCourse}
              >
                <LuX size={18} aria-hidden="true" />
              </button>
            </div>

            <div className="course-management-form course-management-form-single">
              <div className="course-management-inline-alert course-management-field-full">
                <strong>{course.title}</strong>
                <span>此操作无法撤销。学生将无法再访问该课程空间。</span>
              </div>

              {deleteCourseError ? (
                <div className="course-management-inline-alert course-management-field-full">
                  <strong>无法删除课程。</strong>
                  <span>{deleteCourseError}</span>
                </div>
              ) : null}

              <div className="course-management-form-actions course-management-field-full">
                <button
                  type="button"
                  className="course-management-action-button"
                  onClick={closeDeleteModal}
                  disabled={isDeletingCourse}
                >保留课程
                </button>
                <button
                  type="button"
                  className="course-management-action-button course-management-action-button-danger"
                  onClick={() => void handleDeleteCourse()}
                  disabled={isDeletingCourse}
                >
                  {isDeletingCourse ? "Deleting..." : "永久删除"}
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}

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
                <span className="course-surface-badge">编辑课程</span>
                <h3 id="edit-course-title">更新课程信息</h3>
                {hasUnsavedChanges ? <p className="course-management-modal-status">未保存的更改</p> : null}
              </div>
              <button
                type="button"
                className="course-management-modal-close"
                onClick={closeEditModal}
                aria-label="关闭编辑课程窗口"
              >
                <LuX size={18} aria-hidden="true" />
              </button>
            </div>

            <form className="course-management-form" onSubmit={handleEditSubmit}>
              <label className="course-management-field">
                <span>标题</span>
                <input
                  value={editForm.title}
                  onChange={(event) => handleEditFieldChange("title", event.target.value)}
                  required
                />
              </label>

              <label className="course-management-field">
                <span>副标题</span>
                <input
                  value={editForm.subtitle}
                  onChange={(event) => handleEditFieldChange("subtitle", event.target.value)}
                />
              </label>

              <label className="course-management-field course-management-field-full">
                <span>描述</span>
                <textarea
                  value={editForm.description}
                  onChange={(event) => handleEditFieldChange("description", event.target.value)}
                  rows={4}
                />
              </label>

              <label className="course-management-field">
                <span>分类</span>
                <input
                  value={editForm.category}
                  onChange={(event) => handleEditFieldChange("category", event.target.value)}
                />
              </label>

              <label className="course-management-field">
                <span>难度</span>
                <select
                  value={editForm.difficultyLevel}
                  onChange={(event) => handleEditFieldChange("difficultyLevel", event.target.value)}
                >
                  <option value="">选择难度</option>
                  {COURSE_DIFFICULTY_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="course-management-field">
                <span>语言</span>
                <input
                  value={editForm.languageCode}
                  onChange={(event) => handleEditFieldChange("languageCode", event.target.value)}
                />
              </label>

              <label className="course-management-field">
                <span>预计分钟数</span>
                <input
                  type="number"
                  min="1"
                  value={editForm.estimatedMinutes}
                  onChange={(event) => handleEditFieldChange("estimatedMinutes", event.target.value)}
                />
              </label>

              <label className="course-management-field course-management-field-full">
                <span>学习路径标题</span>
                <input
                  value={editForm.learningPathTitle}
                  onChange={(event) => handleEditFieldChange("learningPathTitle", event.target.value)}
                />
              </label>

              <label className="course-management-field course-management-field-full">
                <span>学习路径描述</span>
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
                  <strong>无法更新课程。</strong>
                  <span>{editError}</span>
                </div>
              ) : null}

              <div className="course-management-form-actions course-management-field-full">
                <button type="button" className="course-management-action-button" onClick={closeEditModal}>取消
                </button>
                <button
                  type="submit"
                  className="course-management-action-button course-management-action-button-primary"
                  disabled={isSavingEdit}
                >
                  {isSavingEdit ? "保存中..." : "保存修改"}
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
                <span className="course-surface-badge">发布课程</span>
                <h3 id="publish-course-title">选择要发布的模块</h3>
                <p className="course-management-modal-status">所选模块会随课程一起发布。
                </p>
              </div>
              <button
                type="button"
                className="course-management-modal-close"
                onClick={closePublishModal}
                aria-label="关闭发布课程窗口"
              >
                <LuX size={18} aria-hidden="true" />
              </button>
            </div>

            <form
              className="course-management-form course-management-form-single course-management-publish-form"
              onSubmit={handlePublishSubmit}
            >
              <div className="course-management-inline-note course-management-field-full">
                <strong>发布规则</strong>
                <span>每个选中模块在发布前都必须有内容，并至少关联一份资料。</span>
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
                        {module.materials.length}份资料{module.materials.length === 1 ? "" : "s"} •{" "}
                        {formatStatusLabel(module.status)}
                      </span>
                      {!moduleHasPublishableMaterial(module.materials.length) ? (
                        <em className="course-management-module-selection-warning">请至少上传一份资料后再发布该模块。
                        </em>
                      ) : null}
                    </div>
                  </label>
                ))}
              </div>

              {publishError ? (
                <div className="course-management-inline-alert course-management-field-full">
                  <strong>无法发布课程。</strong>
                  <span>{publishError}</span>
                </div>
              ) : null}

              <div className="course-management-form-actions course-management-field-full">
                <button type="button" className="course-management-action-button" onClick={closePublishModal}>取消
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

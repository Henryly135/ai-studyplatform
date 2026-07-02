import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { LuChevronLeft, LuChevronRight, LuX } from "react-icons/lu";

import { createManagedCourse, getManagedCourses } from "../../services/course";
import LocalizedFileInput from "../../components/common/LocalizedFileInput";
import { useLocale } from "../../i18n/locale";
import type { CourseRecord } from "../../types/course";
import { emitAppRefresh, subscribeAppRefresh } from "../../utils/refreshEvents";
import { useGridColumnCount } from "./useGridColumnCount";
import "./CoursePages.css";

const FALLBACK_COVER_THEMES = ["teal", "prism", "ocean", "neon"];
const COURSE_ROWS_PER_PAGE = 4;
const COURSE_DIFFICULTY_OPTIONS = [
  { value: "beginner", label: "入门" },
  { value: "intermediate", label: "中级" },
  { value: "advanced", label: "高级" },
] as const;

type CreateCourseFormState = {
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
};

const INITIAL_CREATE_COURSE_FORM: CreateCourseFormState = {
  title: "",
  subtitle: "",
  description: "",
  category: "",
  difficultyLevel: "",
  languageCode: "",
  estimatedMinutes: "",
  learningPathTitle: "",
  learningPathDescription: "",
  coverImage: null,
};

function getCoverTheme(index: number) {
  return FALLBACK_COVER_THEMES[index % FALLBACK_COVER_THEMES.length];
}

function formatHourLabel(minutes: number | null) {
  if (!minutes || minutes <= 0) {
    return "";
  }

  if (minutes < 60) {
    return `${minutes} 分钟`;
  }

  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return remainingMinutes > 0 ? `${hours} 小时 ${remainingMinutes} 分钟` : `${hours} 小时`;
}

function formatPublishedLabel(value?: string | null) {
  if (!value) {
    return "未发布";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "已发布";
  }

  return `已发布 ${date.toLocaleDateString()}`;
}

function formatDifficultyLabel(value?: string | null) {
  if (!value) {
    return "未设置";
  }

  switch (value.toLowerCase()) {
    case "beginner":
      return "入门";
    case "intermediate":
      return "中级";
    case "advanced":
      return "高级";
    default:
      return value;
  }
}

function formatCreatorLabel(course: CourseRecord) {
  const parts = [course.educatorEmail?.trim(), course.educatorUserName?.trim()].filter(Boolean);
  if (parts.length > 0) {
    return `创建者：${parts.join(" | ")}`;
  }

  if (course.educatorName?.trim()) {
    return `创建者：${course.educatorName.trim()}`;
  }

  return "创建者：教师";
}

function formatStatusLabel(status?: string) {
  if (!status) {
    return "草稿";
  }

  switch (status.toLowerCase()) {
    case "published":
      return "已发布";
    case "archived":
      return "已归档";
    case "draft":
      return "草稿";
    default:
      return status;
  }
}

function buildPagination(currentPage: number, totalPages: number) {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }

  if (currentPage <= 4) {
    return [1, 2, 3, 4, 5, "ellipsis", totalPages] as const;
  }

  if (currentPage >= totalPages - 3) {
    return [1, "ellipsis", totalPages - 4, totalPages - 3, totalPages - 2, totalPages - 1, totalPages] as const;
  }

  return [1, "ellipsis", currentPage - 1, currentPage, currentPage + 1, "ellipsis", totalPages] as const;
}

type ManagedCoursesPageVariant = "educator" | "admin";

function ManagedCourseCardShell({
  course,
  index,
  managementSearchSuffix,
  body,
}: {
  course: CourseRecord;
  index: number;
  managementSearchSuffix: string;
  body: React.ReactNode;
}) {
  const coverTheme = getCoverTheme(index);
  const normalizedStatus = course.status?.toLowerCase() ?? "draft";
  const statusClassName =
    normalizedStatus === "published"
      ? "course-status-chip-published"
      : normalizedStatus === "draft"
        ? "course-status-chip-draft"
        : "course-status-chip-archived";

  return (
    <article className="course-card managed-course-card">
      <Link to={`/course/${course.courseUuid}/management${managementSearchSuffix}`} className="course-card-clickable-shell">
        <div className={`course-card-cover course-card-cover-${coverTheme}`}>
          <div className="course-card-cover-top">
            <span className={`course-status-chip ${statusClassName}`}>{formatStatusLabel(course.status)}</span>
            {course.courseCode ? <div className="course-card-term">{course.courseCode}</div> : null}
          </div>

          {course.coverImageUrl ? (
            <img src={course.coverImageUrl} alt={course.title} className="course-card-cover-image" />
          ) : null}
        </div>

        <div className="course-card-body managed-course-card-body">
          {body}
        </div>
      </Link>
    </article>
  );
}

function EducatorManagedCourseCard({
  course,
  index,
  managementSearchSuffix,
}: {
  course: CourseRecord;
  index: number;
  managementSearchSuffix: string;
}) {
  return (
    <ManagedCourseCardShell
      course={course}
      index={index}
      managementSearchSuffix={managementSearchSuffix}
      body={
        <div className="managed-course-card-layout managed-course-card-layout-educator">
          <div className="managed-course-card-topline">
            <span>{course.category || "Uncategorized"}</span>
            <strong>{formatDifficultyLabel(course.difficultyLevel)}</strong>
          </div>

          <div className="course-card-body-top">
            <h3>{course.title}</h3>
          </div>

          <div className="managed-course-card-spacer" />

          <div className="managed-course-card-bottom managed-course-card-bottom-educator">
            <div className="course-card-footer managed-course-card-info-row">
              <span>{course.moduleCount ?? course.modules.length} 个模块</span>
              {formatHourLabel(course.estimatedMinutes) ? <strong>{formatHourLabel(course.estimatedMinutes)}</strong> : null}
            </div>

            <div className="course-card-supporting managed-course-card-supporting managed-course-card-info-row">
              <span>{formatPublishedLabel(course.publishedAt)}</span>
            </div>
          </div>
        </div>
      }
    />
  );
}

function AdminManagedCourseCard({
  course,
  index,
  managementSearchSuffix,
}: {
  course: CourseRecord;
  index: number;
  managementSearchSuffix: string;
}) {
  return (
    <ManagedCourseCardShell
      course={course}
      index={index}
      managementSearchSuffix={managementSearchSuffix}
      body={
        <div className="managed-course-card-layout managed-course-card-layout-admin">
          <div className="managed-course-card-topline">
            <span>{course.category || "Uncategorized"}</span>
            <strong>{formatDifficultyLabel(course.difficultyLevel)}</strong>
          </div>

          <div className="course-card-body-top">
            <h3>{course.title}</h3>
          </div>

          <div className="managed-course-card-spacer" />

          <div className="managed-course-card-bottom managed-course-card-bottom-admin">
            <div className="course-card-footer managed-course-card-info-row">
              <span>{course.moduleCount ?? course.modules.length} 个模块</span>
              {formatHourLabel(course.estimatedMinutes) ? <strong>{formatHourLabel(course.estimatedMinutes)}</strong> : null}
            </div>

            <div className="course-card-supporting managed-course-card-supporting managed-course-card-info-row">
              <span>{formatPublishedLabel(course.publishedAt)}</span>
            </div>

            <div className="course-card-supporting managed-course-card-supporting managed-course-card-info-row">
              <span>{formatCreatorLabel(course)}</span>
            </div>
          </div>
        </div>
      }
    />
  );
}

function ManagedCoursesHintBox({
  query,
  loading,
  variant,
}: {
  query: string;
  loading: boolean;
  variant: ManagedCoursesPageVariant;
}) {
  const hasQuery = query.trim().length > 0;
  const title = loading
    ? "Loading your managed courses..."
    : hasQuery
      ? "No courses match this search yet."
      : variant === "admin"
        ? "All educator course records will appear here."
        : "Your managed courses will appear here.";
  const description = loading
    ? variant === "admin"
      ? "We are syncing the latest course records across all educators."
      : "We are syncing the latest managed courses for this educator account."
    : hasQuery
      ? "Try a different title, course code, category, or school to find a course."
      : variant === "admin"
        ? "As courses are created by educators, they will appear in this catalog for review."
        : "Once a course is linked to this educator account, it will show up here.";
  const meta = loading ? "Refreshing list" : hasQuery ? "0 matches" : "0 courses";

  return (
    <div className="managed-course-hint-box" aria-live="polite">
      <div className="managed-course-hint-box-body">
        <div className="managed-course-hint-box-header">
          <span className="managed-course-hint-box-badge">{loading ? "加载中" : hasQuery ? "搜索" : "Waiting"}</span>
          <strong>{meta}</strong>
        </div>

        <h3>{title}</h3>
        <p>{description}</p>
      </div>
    </div>
  );
}

function ManagedCoursesPage({ variant = "educator" }: { variant?: ManagedCoursesPageVariant }) {
  const { text } = useLocale();
  const gridRef = useRef<HTMLDivElement | null>(null);
  const columnCount = useGridColumnCount(gridRef);
  const totalSlotsPerPage = columnCount > 0 ? columnCount * COURSE_ROWS_PER_PAGE : 0;
  const [courses, setCourses] = useState<CourseRecord[]>([]);
  const [query, setQuery] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [totalCourses, setTotalCourses] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [createForm, setCreateForm] = useState<CreateCourseFormState>(INITIAL_CREATE_COURSE_FORM);
  const [isCreatingCourse, setIsCreatingCourse] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [didAttemptCreateSubmit, setDidAttemptCreateSubmit] = useState(false);
  const isAdminView = variant === "admin";
  const firstPageCoursesPerPage =
    totalSlotsPerPage > 0 ? (isAdminView ? totalSlotsPerPage : Math.max(totalSlotsPerPage - 1, 1)) : 0;
  const subsequentCoursesPerPage = totalSlotsPerPage;
  const managementSearchSuffix = isAdminView ? "?from=course-management" : "";

  const loadManagedCourses = useCallback(async (searchQuery: string, cancelled = false, pageOverride?: number) => {
    if (firstPageCoursesPerPage === 0 || subsequentCoursesPerPage === 0) {
      return;
    }

    setLoading(true);
    const targetPage = pageOverride ?? currentPage;
    const targetPageSize =
      targetPage === 1 ? firstPageCoursesPerPage : subsequentCoursesPerPage;
    const targetOffset =
      targetPage === 1
        ? 0
        : firstPageCoursesPerPage + (targetPage - 2) * subsequentCoursesPerPage;

    try {
      const data = await getManagedCourses({
        search: searchQuery,
        page: targetPage,
        pageSize: targetPageSize,
        offset: targetOffset,
      });
      if (!cancelled) {
        setCourses(data.items);
        setTotalCourses(data.total);
        setError(null);
      }
    } catch (loadError) {
      if (!cancelled) {
        setCourses([]);
        setTotalCourses(0);
        setError(loadError instanceof Error ? loadError.message : "Failed to load managed courses.");
      }
    } finally {
      if (!cancelled) {
        setLoading(false);
      }
    }
  }, [currentPage, firstPageCoursesPerPage, subsequentCoursesPerPage]);

  useEffect(() => {
    if (firstPageCoursesPerPage === 0 || subsequentCoursesPerPage === 0) {
      return undefined;
    }

    let cancelled = false;

    const timer = window.setTimeout(() => {
      void loadManagedCourses(query, cancelled);
    }, 250);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [currentPage, firstPageCoursesPerPage, loadManagedCourses, query, subsequentCoursesPerPage]);

  useEffect(() => {
    return subscribeAppRefresh(["course:managed", "course:catalog"], () => {
      void loadManagedCourses(query, false);
    });
  }, [loadManagedCourses, query]);

  useEffect(() => {
    if (!isCreateModalOpen) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsCreateModalOpen(false);
        setCreateError(null);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isCreateModalOpen]);

  useEffect(() => {
    if (firstPageCoursesPerPage === 0 || subsequentCoursesPerPage === 0) {
      return;
    }

    setCurrentPage(1);
  }, [firstPageCoursesPerPage, query, subsequentCoursesPerPage]);

  const draftCount = courses.filter((course) => (course.status?.toLowerCase() ?? "draft") === "draft").length;
  const publishedCount = courses.filter((course) => course.status?.toLowerCase() === "published").length;
  const totalPages =
    firstPageCoursesPerPage === 0 || subsequentCoursesPerPage === 0
      ? 1
      : totalCourses <= firstPageCoursesPerPage
      ? 1
      : 1 + Math.ceil((totalCourses - firstPageCoursesPerPage) / subsequentCoursesPerPage);
  const safeCurrentPage = Math.min(currentPage, Math.max(1, totalPages));
  const startIndex =
    totalCourses === 0
      ? 0
      : safeCurrentPage === 1
        ? 0
        : firstPageCoursesPerPage + (safeCurrentPage - 2) * subsequentCoursesPerPage;
  const endIndex = startIndex + courses.length;
  const paginationItems = buildPagination(safeCurrentPage, Math.max(1, totalPages));

  useEffect(() => {
    if (currentPage !== safeCurrentPage) {
      setCurrentPage(safeCurrentPage);
    }
  }, [currentPage, safeCurrentPage]);

  const openCreateModal = () => {
    setCreateForm(INITIAL_CREATE_COURSE_FORM);
    setCreateError(null);
    setDidAttemptCreateSubmit(false);
    setIsCreateModalOpen(true);
  };

  const closeCreateModal = () => {
    setIsCreateModalOpen(false);
    setCreateError(null);
    setDidAttemptCreateSubmit(false);
  };

  const handleCreateFieldChange = (field: keyof CreateCourseFormState, value: string | boolean | File | null) => {
    setCreateForm((current) => ({ ...current, [field]: value }));
  };

  const handleCreateCourseSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setDidAttemptCreateSubmit(true);

    const hasMissingRequiredField =
      !createForm.title.trim() ||
      !createForm.category.trim() ||
      !createForm.difficultyLevel.trim() ||
      !createForm.languageCode.trim() ||
      !createForm.estimatedMinutes.trim();

    if (hasMissingRequiredField) {
      setCreateError("Please complete the required fields before creating the course.");
      return;
    }

    setIsCreatingCourse(true);
    setCreateError(null);

    try {
      await createManagedCourse({
        title: createForm.title,
        subtitle: createForm.subtitle,
        description: createForm.description,
        category: createForm.category,
        difficultyLevel: createForm.difficultyLevel,
        languageCode: createForm.languageCode,
        estimatedMinutes: createForm.estimatedMinutes.trim() ? Number(createForm.estimatedMinutes) : null,
        learningPathTitle: createForm.learningPathTitle,
        learningPathDescription: createForm.learningPathDescription,
        isPublic: true,
        coverImage: createForm.coverImage,
      });

      setCurrentPage(1);
      await loadManagedCourses(query, false, 1);
      emitAppRefresh({ scope: "course:managed" });
      emitAppRefresh({ scope: "course:catalog" });
      setIsCreateModalOpen(false);
      setCreateForm(INITIAL_CREATE_COURSE_FORM);
      setDidAttemptCreateSubmit(false);
    } catch (submitError) {
      setCreateError(submitError instanceof Error ? submitError.message : "Failed to create course.");
    } finally {
      setIsCreatingCourse(false);
    }
  };

  const isCreateTitleInvalid = didAttemptCreateSubmit && !createForm.title.trim();
  const isCreateCategoryInvalid = didAttemptCreateSubmit && !createForm.category.trim();
  const isCreateDifficultyInvalid = didAttemptCreateSubmit && !createForm.difficultyLevel.trim();
  const isCreateLanguageInvalid = didAttemptCreateSubmit && !createForm.languageCode.trim();
  const isCreateEstimatedMinutesInvalid = didAttemptCreateSubmit && !createForm.estimatedMinutes.trim();

  return (
    <>
      <section className="course-center-page">
        <div className="course-center-hero">
          <div>
            <span className="course-surface-badge">{isAdminView ? "课程管理" : "管理课程"}</span>
            <h1>{isAdminView ? "Review All Educator Courses" : "Manage Your Own Courses"}</h1>
            <p>
              {isAdminView
                ? "Inspect course records across all educators and open the management workspace for any course."
                : "Review all courses you are managing."}
            </p>
          </div>

          <label className="course-search-card">
            <span>{isAdminView ? "Search all courses" : "Search your courses"}</span>
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="按标题、代码、分类或学院搜索..."
            />
          </label>
        </div>

        <div className="course-center-toolbar">
          <strong>{loading ? "Loading managed courses..." : `${totalCourses} courses found`}</strong>
        </div>

        <div ref={gridRef} className="course-grid managed-course-grid">
          {!isAdminView && safeCurrentPage === 1 ? (
            <>
              <button type="button" className="managed-course-create-card" onClick={openCreateModal}>
                <span className="managed-course-create-plus">+</span>
                <strong>创建新课程</strong>
                <p>创建新的草稿课程，定义学习路径，并从零开始构建模块。</p>
              </button>

              {(loading || (!error && totalCourses === 0)) ? (
                <ManagedCoursesHintBox query={query} loading={loading} variant={variant} />
              ) : null}
            </>
          ) : null}

          {courses.map((course, index) => (
            isAdminView ? (
              <AdminManagedCourseCard
                key={`${course.courseUuid}-${course.title}`}
                course={course}
                index={startIndex + index}
                managementSearchSuffix={managementSearchSuffix}
              />
            ) : (
              <EducatorManagedCourseCard
                key={`${course.courseUuid}-${course.title}`}
                course={course}
                index={startIndex + index}
                managementSearchSuffix={managementSearchSuffix}
              />
            )
          ))}
        </div>

        {!loading && totalCourses > 0 ? (
          <div className="course-pagination">
            <span className="course-pagination-summary">显示 {startIndex + 1}-{Math.min(endIndex, totalCourses)}共 {totalCourses}门课程 · {publishedCount}已发布 · {draftCount}草稿
            </span>
            {firstPageCoursesPerPage > 0 && totalCourses > firstPageCoursesPerPage ? (
              <nav className="course-pagination-nav" aria-label="管理课程分页">
                <button
                  type="button"
                  className="course-pagination-button"
                  onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
                  disabled={safeCurrentPage === 1}
                  aria-label="上一页管理课程"
                >
                  <LuChevronLeft size={18} aria-hidden="true" />
                </button>

                <div className="course-pagination-pages">
                  {paginationItems.map((item, index) =>
                    item === "ellipsis" ? (
                      <span key={`ellipsis-${index}`} className="course-pagination-ellipsis" aria-hidden="true">
                        ...
                      </span>
                    ) : (
                      <button
                        key={item}
                        type="button"
                        className={`course-pagination-button${item === safeCurrentPage ? " course-pagination-button-active" : ""}`}
                        onClick={() => setCurrentPage(item)}
                        aria-current={item === safeCurrentPage ? "page" : undefined}
                      >
                        {item}
                      </button>
                    )
                  )}
                </div>

                <button
                  type="button"
                  className="course-pagination-button"
                  onClick={() => setCurrentPage((page) => Math.min(Math.max(1, totalPages), page + 1))}
                  disabled={safeCurrentPage === Math.max(1, totalPages)}
                  aria-label="下一页管理课程"
                >
                  <LuChevronRight size={18} aria-hidden="true" />
                </button>
              </nav>
            ) : null}
          </div>
        ) : null}

        {!loading && error ? (
          <div className="course-empty-state">
            <strong>无法加载管理课程</strong>
            <p>{error}</p>
          </div>
        ) : null}
      </section>

      {!isAdminView && isCreateModalOpen ? (
        <div className="course-management-modal-overlay" role="presentation">
          <div
            className="course-management-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="create-course-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="course-management-modal-header">
              <div>
                <span className="course-surface-badge">创建课程</span>
                <h3 id="create-course-title">创建新的草稿课程</h3>
              </div>
              <button
                type="button"
                className="course-management-modal-close"
                onClick={closeCreateModal}
                aria-label="关闭创建课程窗口"
              >
                <LuX size={18} aria-hidden="true" />
              </button>
            </div>

            <form className="course-management-form" onSubmit={handleCreateCourseSubmit}>
              <label className="course-management-field">
                <span>标题 <em className="course-management-required-indicator">*</em>
                </span>
                <input
                  className={isCreateTitleInvalid ? "course-management-input-invalid" : undefined}
                  value={createForm.title}
                  onChange={(event) => handleCreateFieldChange("title", event.target.value)}
                  aria-invalid={isCreateTitleInvalid}
                  required
                />
                {isCreateTitleInvalid ? (
                  <small className="course-management-field-error">标题为必填项。</small>
                ) : null}
              </label>

              <label className="course-management-field">
                <span>副标题</span>
                <input
                  value={createForm.subtitle}
                  onChange={(event) => handleCreateFieldChange("subtitle", event.target.value)}
                />
              </label>

              <label className="course-management-field course-management-field-full">
                <span>描述</span>
                <textarea
                  value={createForm.description}
                  onChange={(event) => handleCreateFieldChange("description", event.target.value)}
                  rows={4}
                />
              </label>

              <label className="course-management-field">
                <span>分类 <em className="course-management-required-indicator">*</em>
                </span>
                <input
                  className={isCreateCategoryInvalid ? "course-management-input-invalid" : undefined}
                  value={createForm.category}
                  onChange={(event) => handleCreateFieldChange("category", event.target.value)}
                  aria-invalid={isCreateCategoryInvalid}
                  required
                />
                {isCreateCategoryInvalid ? (
                  <small className="course-management-field-error">分类为必填项。</small>
                ) : null}
              </label>

              <label className="course-management-field">
                <span>难度 <em className="course-management-required-indicator">*</em>
                </span>
                <select
                  className={isCreateDifficultyInvalid ? "course-management-input-invalid" : undefined}
                  value={createForm.difficultyLevel}
                  onChange={(event) => handleCreateFieldChange("difficultyLevel", event.target.value)}
                  aria-invalid={isCreateDifficultyInvalid}
                  required
                >
                  <option value="">选择难度</option>
                  {COURSE_DIFFICULTY_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                {isCreateDifficultyInvalid ? (
                  <small className="course-management-field-error">难度为必填项。</small>
                ) : null}
              </label>

              <label className="course-management-field">
                <span>语言 <em className="course-management-required-indicator">*</em>
                </span>
                <input
                  className={isCreateLanguageInvalid ? "course-management-input-invalid" : undefined}
                  value={createForm.languageCode}
                  onChange={(event) => handleCreateFieldChange("languageCode", event.target.value)}
                  aria-invalid={isCreateLanguageInvalid}
                  required
                />
                {isCreateLanguageInvalid ? (
                  <small className="course-management-field-error">语言为必填项。</small>
                ) : null}
              </label>

              <label className="course-management-field">
                <span>预计分钟数 <em className="course-management-required-indicator">*</em>
                </span>
                <input
                  type="number"
                  min="1"
                  className={isCreateEstimatedMinutesInvalid ? "course-management-input-invalid" : undefined}
                  value={createForm.estimatedMinutes}
                  onChange={(event) => handleCreateFieldChange("estimatedMinutes", event.target.value)}
                  aria-invalid={isCreateEstimatedMinutesInvalid}
                  required
                />
                {isCreateEstimatedMinutesInvalid ? (
                  <small className="course-management-field-error">预计分钟数为必填项。</small>
                ) : null}
              </label>

              <label className="course-management-field course-management-field-full">
                <span>学习路径标题</span>
                <input
                  value={createForm.learningPathTitle}
                  onChange={(event) => handleCreateFieldChange("learningPathTitle", event.target.value)}
                />
              </label>

              <label className="course-management-field course-management-field-full">
                <span>学习路径描述</span>
                <textarea
                  value={createForm.learningPathDescription}
                  onChange={(event) => handleCreateFieldChange("learningPathDescription", event.target.value)}
                  rows={4}
                />
              </label>

              <label className="course-management-field course-management-field-full">
                <span>{text.upload.coverImageLabel}</span>
                <LocalizedFileInput
                  accept="image/*"
                  selectedFileName={createForm.coverImage?.name ?? null}
                  onFileChange={(file) => handleCreateFieldChange("coverImage", file)}
                />
              </label>

              {createError ? (
                <div className="course-management-inline-alert course-management-field-full">
                  <strong>无法创建课程。</strong>
                  <span>{createError}</span>
                </div>
              ) : null}

              <div className="course-management-form-actions course-management-field-full">
                <button type="button" className="course-management-action-button" onClick={closeCreateModal}>取消
                </button>
                <button
                  type="submit"
                  className="course-management-action-button course-management-action-button-primary"
                  disabled={isCreatingCourse}
                >
                  {isCreatingCourse ? "创建中..." : "创建课程"}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </>
  );
}

export default ManagedCoursesPage;

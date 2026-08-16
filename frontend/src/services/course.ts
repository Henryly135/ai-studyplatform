import type {
  CourseEnrollmentLearnerRecord,
  CourseMaterial,
  CourseModule,
  CourseRecord,
  EducatorAnalytics,
  EducatorCourseAnalyticsItem,
  EducatorMaterialBriefItem,
  EducatorMaterialBriefs,
  EducatorQuizAnalytics,
  EducatorTeachingInsights,
  LearnerProgressActivityItem,
  LearnerProgressCourseItem,
  LearnerProgressOverview,
  LearnerProgressQuizSummary,
  QuizAuthoringGenerationResult,
  QuizGenerationProgressEvent,
  QuizGenerationRun,
  QuizModuleStatsItem,
  QuizRecord,
  QuizQuestionDraft,
  QuizQuestionPage,
  QuizAttemptSession,
  QuizAttemptResult,
  QuizAttemptHistory,
  TeachingInsightItem,
} from "../types/course";
import type {
  CourseInviteLinkResponse,
  CourseInviteValidateResponse,
  CourseInviteEnrolResponse,
} from "../types/admin";
import {
  buildAuthHeaders,
  handleAuthenticationFailureFromResponse,
  parseJsonText,
} from "./api";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";
const COURSE_API_BASE_URL = API_BASE_URL.startsWith("/api")
  ? `${API_BASE_URL}/learning`
  : `${API_BASE_URL.replace(/\/$/, "")}/learning`;
const AI_API_BASE_URL = API_BASE_URL.startsWith("/api")
  ? `${API_BASE_URL}/ai`
  : `${API_BASE_URL.replace(/\/$/, "")}/ai`;

type ApiCourse = {
  course_id?: number;
  courseId?: number;
  course_uuid?: string;
  courseUuid?: string;
  educator_id?: number;
  educatorId?: number;
  educator_uuid?: string;
  educatorUuid?: string;
  title?: string;
  subtitle?: string | null;
  description?: string | null;
  cover_image_url?: string | null;
  coverImageUrl?: string | null;
  difficulty_level?: string | null;
  difficultyLevel?: string | null;
  estimated_minutes?: number | null;
  estimatedMinutes?: number | null;
  category?: string | null;
  language_code?: string | null;
  languageCode?: string | null;
  is_public?: boolean;
  isPublic?: boolean;
  educator_name?: string | null;
  educatorName?: string | null;
  educator_email?: string | null;
  educatorEmail?: string | null;
  educator_user_name?: string | null;
  educatorUserName?: string | null;
  term_label?: string | null;
  termLabel?: string | null;
  course_code?: string | null;
  courseCode?: string | null;
  school_name?: string | null;
  schoolName?: string | null;
  status?: string | null;
  published_at?: string | null;
  publishedAt?: string | null;
  learning_path_id?: number | null;
  learningPathId?: number | null;
  learning_path_title?: string | null;
  learningPathTitle?: string | null;
  learning_path_description?: string | null;
  learningPathDescription?: string | null;
  module_count?: number | null;
  moduleCount?: number | null;
  modules?: ApiModule[];
};

type ApiModule = {
  module_id?: number | string;
  moduleId?: number | string;
  module_uuid?: string;
  moduleUuid?: string;
  sort_order?: number | null;
  sortOrder?: number | null;
  title?: string;
  description?: string | null;
  content?: string | null;
  slug?: string | null;
  estimated_minutes?: number | null;
  estimatedMinutes?: number | null;
  status?: string | null;
  visibility?: string | null;
  class_id?: string | null;
  classId?: string | null;
  prerequisite_module_uuid?: string | null;
  prerequisiteModuleUuid?: string | null;
  prerequisite_module_title?: string | null;
  prerequisiteModuleTitle?: string | null;
  is_locked?: boolean;
  isLocked?: boolean;
  lock_message?: string | null;
  lockMessage?: string | null;
  is_published?: boolean;
  isPublished?: boolean;
  materials?: ApiMaterial[];
  has_published_quiz?: boolean;
  hasPublishedQuiz?: boolean;
  quiz_title?: string | null;
  quizTitle?: string | null;
  quiz_time_limit_seconds?: number | null;
  quizTimeLimitSeconds?: number | null;
  progress_status?: string | null;
  progressStatus?: string | null;
  is_completed?: boolean;
  isCompleted?: boolean;
  completed_at?: string | null;
  completedAt?: string | null;
};

type ApiMaterial = {
  material_id?: number | string;
  materialId?: number | string;
  material_uuid?: string;
  materialUuid?: string;
  title?: string;
  material_type?: string | null;
  materialType?: string | null;
  resource_url?: string | null;
  resourceUrl?: string | null;
  download_url?: string | null;
  downloadUrl?: string | null;
  sort_order?: number | null;
  sortOrder?: number | null;
  metadata_json?: Record<string, unknown> | null;
  metadataJson?: Record<string, unknown> | null;
};

type PaginatedCourseListResult = {
  items: CourseRecord[];
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
};

type ApiCourseEnrollmentLearner = {
  enrollmentId?: number;
  enrollment_id?: number;
  courseId?: number;
  course_id?: number;
  courseUuid?: string;
  course_uuid?: string;
  learnerId?: number;
  learner_id?: number;
  learnerUuid?: string;
  learner_uuid?: string;
  learnerName?: string | null;
  learner_name?: string | null;
  learnerEmail?: string | null;
  learner_email?: string | null;
  learnerIdentity?: string | null;
  learner_identity?: string | null;
  learnerAccountStatus?: string | null;
  learner_account_status?: string | null;
  learnerEmailVerified?: boolean | null;
  learner_email_verified?: boolean | null;
  enrollmentStatus?: string | null;
  enrollment_status?: string | null;
  progressPercent?: string | number | null;
  progress_percent?: string | number | null;
  completedModuleCount?: number | null;
  completed_module_count?: number | null;
  totalModuleCount?: number | null;
  total_module_count?: number | null;
  enrolledAt?: string | null;
  enrolled_at?: string | null;
  lastAccessedAt?: string | null;
  last_accessed_at?: string | null;
  completedAt?: string | null;
  completed_at?: string | null;
};

function extractErrorMessage(payload: unknown, fallbackMessage: string) {
  if (payload && typeof payload === "object") {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }

    const error = (payload as { error?: unknown }).error;
    if (error && typeof error === "object") {
      const message = (error as { message?: unknown }).message;
      if (typeof message === "string" && message.trim()) {
        return message;
      }
    }
  }

  return fallbackMessage;
}

function formatMinutes(minutes: number | null | undefined) {
  return !minutes || minutes <= 0 ? null : minutes;
}

function normalizeMaterial(material: ApiMaterial, index: number): CourseMaterial {
  return {
    materialUuid: String(
      material.materialUuid ?? material.material_uuid ?? material.materialId ?? material.material_id ?? index + 1
    ),
    materialId:
      typeof material.materialId === "number"
        ? material.materialId
        : typeof material.material_id === "number"
          ? material.material_id
          : undefined,
    title: material.title?.trim() || `Material ${index + 1}`,
    materialType: material.materialType?.trim() || material.material_type?.trim() || "",
    resourceUrl: material.resourceUrl?.trim() || material.resource_url?.trim() || "",
    downloadUrl: material.downloadUrl?.trim() || material.download_url?.trim() || null,
    sortOrder: material.sortOrder ?? material.sort_order ?? index + 1,
    metadataJson: material.metadataJson ?? material.metadata_json ?? null,
  };
}

function normalizeModule(courseUuid: string, module: ApiModule, index: number): CourseModule {
  const estimatedMinutes = formatMinutes(module.estimatedMinutes ?? module.estimated_minutes);
  const title = module.title?.trim() || `Module ${index + 1}`;
  const normalizedStatus = module.status?.trim().toLowerCase() || "";
  const visibility = module.visibility?.trim().toLowerCase() || normalizedStatus;
  const isLocked = module.isLocked ?? module.is_locked ?? false;
  const status: CourseModule["status"] =
    visibility === "draft" || visibility === "archived" || normalizedStatus === "draft" || normalizedStatus === "archived"
      ? "draft"
      : isLocked
        ? "locked"
        : normalizedStatus === "published"
          ? "available"
          : module.isPublished === false || module.is_published === false
          ? "draft"
          : "available";
  return {
    moduleUuid: String(
      module.moduleUuid ?? module.module_uuid ?? module.moduleId ?? module.module_id ?? `${courseUuid}-${index + 1}`
    ),
    moduleId:
      typeof module.moduleId === "number"
        ? module.moduleId
        : typeof module.module_id === "number"
          ? module.module_id
          : undefined,
    sortOrder: module.sortOrder ?? module.sort_order ?? index + 1,
    slug: module.slug?.trim() || encodeURIComponent(title.toLowerCase().replace(/\s+/g, "-")),
    title,
    summary: module.description?.trim() || "Module details will be available soon.",
    content: module.content?.trim() || "",
    durationLabel: estimatedMinutes ? `${estimatedMinutes} min` : "",
    status,
    visibility: visibility || undefined,
    classId: module.classId?.trim() || module.class_id?.trim() || null,
    prerequisiteModuleUuid:
      module.prerequisiteModuleUuid?.trim() || module.prerequisite_module_uuid?.trim() || null,
    prerequisiteModuleTitle:
      module.prerequisiteModuleTitle?.trim() || module.prerequisite_module_title?.trim() || null,
    isLocked,
    lockMessage: module.lockMessage?.trim() || module.lock_message?.trim() || null,
    materials: Array.isArray(module.materials)
      ? module.materials.map((material, materialIndex) => normalizeMaterial(material, materialIndex))
      : [],
    hasPublishedQuiz: Boolean(module.hasPublishedQuiz ?? module.has_published_quiz ?? false),
    quizTitle: (module.quizTitle ?? module.quiz_title ?? null) as string | null,
    quizTimeLimitSeconds: (module.quizTimeLimitSeconds ?? module.quiz_time_limit_seconds ?? null) as number | null,
    progressStatus: (module.progressStatus ?? module.progress_status ?? null) as string | null,
    isCompleted: Boolean(module.isCompleted ?? module.is_completed ?? false),
    completedAt: (module.completedAt ?? module.completed_at ?? null) as string | null,
  };
}

function normalizeCourse(course: ApiCourse, index: number): CourseRecord {
  const courseId = course.courseId ?? course.course_id ?? index + 1;
  const courseUuid = String(course.courseUuid ?? course.course_uuid ?? courseId);
  const title = course.title?.trim() || `Course ${courseId}`;
  const category = course.category?.trim() || "";
  const estimatedMinutes = formatMinutes(course.estimatedMinutes ?? course.estimated_minutes);

  return {
    courseUuid,
    courseId,
    educatorUuid: String(
      course.educatorUuid ?? course.educator_uuid ?? course.educatorId ?? course.educator_id ?? "unknown-educator"
    ),
    educatorId:
      typeof course.educatorId === "number"
        ? course.educatorId
        : typeof course.educator_id === "number"
          ? course.educator_id
          : undefined,
    title,
    subtitle: course.subtitle?.trim() || "",
    description: course.description?.trim() || "",
    category,
    languageCode: course.languageCode?.trim() || course.language_code?.trim() || "",
    estimatedMinutes,
    difficultyLevel: course.difficultyLevel?.trim() || course.difficulty_level?.trim() || "",
    isPublic: true,
    coverImageUrl: course.coverImageUrl?.trim() || course.cover_image_url?.trim() || null,
    educatorName: course.educatorName?.trim() || course.educator_name?.trim() || "",
    educatorEmail: course.educatorEmail?.trim() || course.educator_email?.trim() || "",
    educatorUserName: course.educatorUserName?.trim() || course.educator_user_name?.trim() || "",
    termLabel: course.termLabel?.trim() || course.term_label?.trim() || "",
    courseCode: course.courseCode?.trim() || course.course_code?.trim() || "",
    schoolName: course.schoolName?.trim() || course.school_name?.trim() || "",
    status: course.status?.trim() || undefined,
    publishedAt: course.publishedAt?.trim() || course.published_at?.trim() || null,
    moduleCount: course.moduleCount ?? course.module_count ?? 0,
    learningPathId: course.learningPathId ?? course.learning_path_id ?? null,
    learningPathTitle: course.learningPathTitle?.trim() || course.learning_path_title?.trim() || "",
    learningPathDescription:
      course.learningPathDescription?.trim() || course.learning_path_description?.trim() || "",
    modules:
      course.modules && course.modules.length > 0
        ? course.modules.map((module, moduleIndex) =>
            normalizeModule(courseUuid, module, moduleIndex)
          )
        : [],
  };
}

function normalizeCourseEnrollmentLearner(
  enrollment: ApiCourseEnrollmentLearner
): CourseEnrollmentLearnerRecord {
  return {
    enrollmentId: enrollment.enrollmentId ?? enrollment.enrollment_id ?? 0,
    courseId: enrollment.courseId ?? enrollment.course_id ?? 0,
    courseUuid: String(enrollment.courseUuid ?? enrollment.course_uuid ?? ""),
    learnerId: enrollment.learnerId ?? enrollment.learner_id ?? 0,
    learnerUuid: String(enrollment.learnerUuid ?? enrollment.learner_uuid ?? ""),
    learnerName: enrollment.learnerName?.trim() || enrollment.learner_name?.trim() || "Unknown learner",
    learnerEmail: enrollment.learnerEmail?.trim() || enrollment.learner_email?.trim() || "",
    learnerIdentity: enrollment.learnerIdentity?.trim() || enrollment.learner_identity?.trim() || "",
    learnerAccountStatus:
      enrollment.learnerAccountStatus?.trim() || enrollment.learner_account_status?.trim() || "",
    learnerEmailVerified:
      enrollment.learnerEmailVerified ?? enrollment.learner_email_verified ?? null,
    enrollmentStatus: enrollment.enrollmentStatus?.trim() || enrollment.enrollment_status?.trim() || "",
    progressPercent: String(
      enrollment.progressPercent ?? enrollment.progress_percent ?? "0"
    ),
    completedModuleCount:
      enrollment.completedModuleCount ?? enrollment.completed_module_count ?? 0,
    totalModuleCount: enrollment.totalModuleCount ?? enrollment.total_module_count ?? 0,
    enrolledAt: enrollment.enrolledAt?.trim() || enrollment.enrolled_at?.trim() || "",
    lastAccessedAt: enrollment.lastAccessedAt?.trim() || enrollment.last_accessed_at?.trim() || null,
    completedAt: enrollment.completedAt?.trim() || enrollment.completed_at?.trim() || null,
  };
}

function extractCourseArray(payload: unknown): ApiCourse[] {
  if (Array.isArray(payload)) {
    return payload as ApiCourse[];
  }

  if (payload && typeof payload === "object") {
    const data = payload as { items?: unknown; courses?: unknown; data?: unknown };

    if (Array.isArray(data.items)) {
      return data.items as ApiCourse[];
    }

    if (Array.isArray(data.courses)) {
      return data.courses as ApiCourse[];
    }

    if (Array.isArray(data.data)) {
      return data.data as ApiCourse[];
    }
  }

  return [];
}

function normalizePaginatedCoursePayload(payload: unknown): PaginatedCourseListResult {
  const defaultResult: PaginatedCourseListResult = {
    items: [],
    page: 1,
    pageSize: 24,
    total: 0,
    totalPages: 1,
  };

  if (!payload || typeof payload !== "object") {
    return defaultResult;
  }

  const data = payload as {
    items?: unknown;
    courses?: unknown;
    data?: unknown;
    page?: unknown;
    pageSize?: unknown;
    total?: unknown;
    totalPages?: unknown;
  };

  const items = extractCourseArray(payload).map((course, index) => normalizeCourse(course, index));
  const total = toNonNegativeNumber(data.total, items.length);
  const pageSize = toFiniteNumber(data.pageSize, defaultResult.pageSize, 1);
  const totalPages = toFiniteNumber(
    data.totalPages,
    Math.max(1, Math.ceil(total / pageSize)),
    1
  );
  const page = toFiniteNumber(data.page, 1, 1);

  return {
    items,
    page,
    pageSize,
    total,
    totalPages,
  };
}

export async function getCourses(options?: {
  search?: string;
  page?: number;
  pageSize?: number;
}): Promise<PaginatedCourseListResult> {
  const search = options?.search?.trim() || "";
  const page = options?.page ?? 1;
  const pageSize = options?.pageSize ?? 24;
  const params = new URLSearchParams();

  if (search) {
    params.set("search", search);
  }
  params.set("page", String(page));
  params.set("pageSize", String(pageSize));

  const queryString = params.toString();
  const response = await fetch(`${COURSE_API_BASE_URL}/courses${queryString ? `?${queryString}` : ""}`, {
    method: "GET",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
  });

  handleAuthenticationFailureFromResponse(response.status, null);

  if (!response.ok) {
    throw new Error("获取课程失败。");
  }

  const text = await response.text();
  const payload = parseJsonText(text);
  return normalizePaginatedCoursePayload(payload);
}

export async function searchCourses(query: string): Promise<CourseRecord[]> {
  const normalizedQuery = query.trim();
  if (!normalizedQuery) {
    return (await getCourses()).items;
  }

  const response = await fetch(
    `${COURSE_API_BASE_URL}/courses/search?q=${encodeURIComponent(normalizedQuery)}`,
    {
      method: "GET",
      headers: buildAuthHeaders({
        "Content-Type": "application/json",
      }),
    }
  );

  const text = await response.text();
  const payload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, payload);

  if (!response.ok) {
    throw new Error("搜索课程失败。");
  }

  return extractCourseArray(payload)
    .map((course, index) => normalizeCourse(course, index));
}

export async function getCourseByUuid(courseUuid: string): Promise<CourseRecord | null> {
  const response = await fetch(`${COURSE_API_BASE_URL}/courses/${courseUuid}`, {
    method: "GET",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
  });

  handleAuthenticationFailureFromResponse(response.status, null);

  if (!response.ok) {
    return null;
  }

  const text = await response.text();
  const payload = parseJsonText(text);
  if (!payload || typeof payload !== "object") {
    return null;
  }

  return normalizeCourse(payload as ApiCourse, 0);
}

export async function enrollInCourse(courseUuid: string): Promise<void> {
  const response = await fetch(`${COURSE_API_BASE_URL}/courses/${courseUuid}/enrolments`, {
    method: "POST",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
  });

  const text = await response.text();
  const payload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, payload);

  if (!response.ok) {
    throw new Error(extractErrorMessage(payload, "报名课程失败。"));
  }
}

export async function dropMyEnrollment(courseUuid: string): Promise<void> {
  const response = await fetch(`${COURSE_API_BASE_URL}/courses/${courseUuid}/enrolments/me`, {
    method: "DELETE",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
  });

  const text = await response.text();
  const payload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, payload);

  if (!response.ok) {
    throw new Error(extractErrorMessage(payload, "取消报名失败。"));
  }
}

export async function getMyEnrolledCourseUuids(): Promise<Set<string>> {
  const response = await fetch(`${COURSE_API_BASE_URL}/courses/me/enrolled`, {
    method: "GET",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
  });

  const text = await response.text();
  const payload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, payload);

  if (!response.ok) {
    throw new Error(extractErrorMessage(payload, "加载已加入课程失败。"));
  }

  return new Set(
    extractCourseArray(payload).map((course, index) => normalizeCourse(course, index).courseUuid)
  );
}

export async function getMyEnrolledCourses(search = ""): Promise<CourseRecord[]> {
  const normalizedSearch = search.trim();
  const params = new URLSearchParams();
  if (normalizedSearch) {
    params.set("search", normalizedSearch);
  }

  const response = await fetch(
    `${COURSE_API_BASE_URL}/courses/me/enrolled${params.toString() ? `?${params.toString()}` : ""}`,
    {
      method: "GET",
      headers: buildAuthHeaders({
        "Content-Type": "application/json",
      }),
    }
  );

  const text = await response.text();
  const payload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, payload);

  if (!response.ok) {
    throw new Error(extractErrorMessage(payload, "加载已加入课程失败。"));
  }

  return extractCourseArray(payload).map((course, index) => normalizeCourse(course, index));
}

function pickProgress(obj: Record<string, unknown>, ...keys: string[]): unknown {
  for (const key of keys) {
    if (obj[key] !== undefined) return obj[key];
  }
  return undefined;
}

function progressRecord(payload: unknown): Record<string, unknown> {
  return payload && typeof payload === "object" ? (payload as Record<string, unknown>) : {};
}

function toFiniteNumber(value: unknown, fallback: number, minimum?: number, maximum?: number) {
  const parsed =
    typeof value === "number"
      ? value
      : typeof value === "string" && value.trim()
        ? Number(value)
        : fallback;

  if (!Number.isFinite(parsed)) {
    return fallback;
  }

  const withMinimum = minimum === undefined ? parsed : Math.max(minimum, parsed);
  return maximum === undefined ? withMinimum : Math.min(maximum, withMinimum);
}

function toNonNegativeNumber(value: unknown, fallback = 0) {
  return toFiniteNumber(value, fallback, 0);
}

function toPercentNumber(value: unknown, fallback = 0) {
  return toFiniteNumber(value, fallback, 0, 100);
}

function toNullablePercentNumber(value: unknown) {
  if (value === null || value === undefined) {
    return null;
  }

  const parsed = toFiniteNumber(value, Number.NaN, 0, 100);
  return Number.isFinite(parsed) ? parsed : null;
}

function toScorePercentString(value: unknown) {
  return String(toPercentNumber(value));
}

function toNullableNonNegativeNumber(value: unknown) {
  if (value === null || value === undefined) {
    return null;
  }

  const parsed =
    typeof value === "number"
      ? value
      : typeof value === "string" && value.trim()
        ? Number(value)
        : Number.NaN;
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
}

function toBooleanValue(value: unknown, fallback = false) {
  if (typeof value === "boolean") {
    return value;
  }

  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (["true", "1", "yes"].includes(normalized)) {
      return true;
    }
    if (["false", "0", "no"].includes(normalized)) {
      return false;
    }
  }

  return fallback;
}

function asNullableString(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function asNullableDisplayString(value: unknown): string | null {
  if (value === null || value === undefined) {
    return null;
  }

  const normalized = String(value);
  return normalized.length > 0 ? normalized : null;
}

function normalizeString(value: unknown, fallback = "") {
  return value === null || value === undefined ? fallback : String(value);
}

function normalizeCourseInviteLink(payload: unknown): CourseInviteLinkResponse {
  const data = progressRecord(payload);
  const inviteUrl = pickProgress(data, "inviteUrl", "invite_url");

  return {
    inviteUuid: normalizeString(pickProgress(data, "inviteUuid", "invite_uuid")),
    courseUuid: normalizeString(pickProgress(data, "courseUuid", "course_uuid")),
    ...(inviteUrl === null || inviteUrl === undefined ? {} : { inviteUrl: String(inviteUrl) }),
    isActive: toBooleanValue(pickProgress(data, "isActive", "is_active")),
    createdAt: normalizeString(pickProgress(data, "createdAt", "created_at")),
    expiresAt: asNullableString(pickProgress(data, "expiresAt", "expires_at")),
  };
}

function isUsableCourseInviteLink(link: CourseInviteLinkResponse) {
  return Boolean(link.inviteUuid && link.courseUuid);
}

function normalizeCourseInviteLinkList(payload: unknown): CourseInviteLinkResponse[] {
  return Array.isArray(payload)
    ? payload.map(normalizeCourseInviteLink).filter(isUsableCourseInviteLink)
    : [];
}

function normalizeCourseInviteValidation(payload: unknown): CourseInviteValidateResponse {
  const data = progressRecord(payload);
  const result = {
    valid: toBooleanValue(pickProgress(data, "valid")),
    courseUuid: normalizeString(pickProgress(data, "courseUuid", "course_uuid")),
    courseTitle: normalizeString(pickProgress(data, "courseTitle", "course_title")),
    inviteUuid: normalizeString(pickProgress(data, "inviteUuid", "invite_uuid")),
  };

  if (!result.valid || !result.courseUuid || !result.courseTitle || !result.inviteUuid) {
    throw new Error("Invalid or expired invite link.");
  }

  return result;
}

function normalizeCourseInviteEnrolment(payload: unknown): CourseInviteEnrolResponse {
  const data = progressRecord(payload);
  const courseUuid = normalizeString(pickProgress(data, "courseUuid", "course_uuid"));

  if (!courseUuid) {
    throw new Error("Course invite enrolment response was invalid. Please try again.");
  }

  return {
    detail: normalizeString(pickProgress(data, "detail"), "Enrolled successfully."),
    courseUuid,
    courseTitle: normalizeString(pickProgress(data, "courseTitle", "course_title"), "Course"),
  };
}

function normalizeProgressQuizSummary(payload: unknown): LearnerProgressQuizSummary {
  const data = progressRecord(payload);
  const averageBestScore = pickProgress(data, "averageBestScorePercent", "average_best_score_percent");
  const latestScore = pickProgress(data, "latestScorePercent", "latest_score_percent");

  return {
    totalQuizzes: toNonNegativeNumber(pickProgress(data, "totalQuizzes", "total_quizzes")),
    attemptedQuizzes: toNonNegativeNumber(pickProgress(data, "attemptedQuizzes", "attempted_quizzes")),
    passedQuizzes: toNonNegativeNumber(pickProgress(data, "passedQuizzes", "passed_quizzes")),
    totalAttempts: toNonNegativeNumber(pickProgress(data, "totalAttempts", "total_attempts")),
    averageBestScorePercent: toNullablePercentNumber(averageBestScore),
    latestScorePercent: toNullablePercentNumber(latestScore),
    latestSubmittedAt: asNullableString(pickProgress(data, "latestSubmittedAt", "latest_submitted_at")),
  };
}

function normalizeProgressCourse(payload: unknown): LearnerProgressCourseItem {
  const data = progressRecord(payload);
  const nextModule = progressRecord(pickProgress(data, "nextModule", "next_module"));

  return {
    courseId: toNonNegativeNumber(pickProgress(data, "courseId", "course_id")),
    courseUuid: String(pickProgress(data, "courseUuid", "course_uuid") ?? ""),
    title: String(pickProgress(data, "title") ?? "Course"),
    courseCode: asNullableString(pickProgress(data, "courseCode", "course_code")),
    category: asNullableString(pickProgress(data, "category")),
    enrollmentStatus: String(pickProgress(data, "enrollmentStatus", "enrollment_status") ?? "active"),
    progressPercent: toPercentNumber(pickProgress(data, "progressPercent", "progress_percent")),
    completedModuleCount: toNonNegativeNumber(
      pickProgress(data, "completedModuleCount", "completed_module_count")
    ),
    totalModuleCount: toNonNegativeNumber(pickProgress(data, "totalModuleCount", "total_module_count")),
    lastAccessedAt: asNullableString(pickProgress(data, "lastAccessedAt", "last_accessed_at")),
    completedAt: asNullableString(pickProgress(data, "completedAt", "completed_at")),
    nextModule: Object.keys(nextModule).length > 0
      ? {
          moduleId: toNonNegativeNumber(pickProgress(nextModule, "moduleId", "module_id")),
          moduleUuid: String(pickProgress(nextModule, "moduleUuid", "module_uuid") ?? ""),
          title: String(pickProgress(nextModule, "title") ?? "Module"),
        }
      : null,
    quiz: normalizeProgressQuizSummary(pickProgress(data, "quiz")),
  };
}

function normalizeProgressActivity(payload: unknown): LearnerProgressActivityItem {
  const data = progressRecord(payload);
  const isPassed = pickProgress(data, "isPassed", "is_passed");
  const score = pickProgress(data, "scorePercent", "score_percent");
  const moduleId = pickProgress(data, "moduleId", "module_id");

  return {
    activityType: String(pickProgress(data, "activityType", "activity_type") ?? "activity"),
    occurredAt: String(pickProgress(data, "occurredAt", "occurred_at") ?? ""),
    courseId: toNonNegativeNumber(pickProgress(data, "courseId", "course_id")),
    courseUuid: String(pickProgress(data, "courseUuid", "course_uuid") ?? ""),
    courseTitle: String(pickProgress(data, "courseTitle", "course_title") ?? "Course"),
    moduleId:
      moduleId === null || moduleId === undefined ? null : toNonNegativeNumber(moduleId),
    moduleUuid: asNullableString(pickProgress(data, "moduleUuid", "module_uuid")),
    moduleTitle: asNullableString(pickProgress(data, "moduleTitle", "module_title")),
    title: String(pickProgress(data, "title") ?? "Activity"),
    detail: asNullableString(pickProgress(data, "detail")),
    scorePercent: toNullablePercentNumber(score),
    isPassed: typeof isPassed === "boolean" ? isPassed : null,
  };
}

function normalizeProgressOverview(payload: unknown): LearnerProgressOverview {
  const data = progressRecord(payload);
  const courses = Array.isArray(pickProgress(data, "courses"))
    ? (pickProgress(data, "courses") as unknown[])
    : [];
  const recentActivity = Array.isArray(pickProgress(data, "recentActivity", "recent_activity"))
    ? (pickProgress(data, "recentActivity", "recent_activity") as unknown[])
    : [];
  return {
    totalCourses: toNonNegativeNumber(pickProgress(data, "totalCourses", "total_courses")),
    totalModules: toNonNegativeNumber(pickProgress(data, "totalModules", "total_modules")),
    completedModules: toNonNegativeNumber(pickProgress(data, "completedModules", "completed_modules")),
    averageProgressPercent: toPercentNumber(
      pickProgress(data, "averageProgressPercent", "average_progress_percent")
    ),
    quiz: normalizeProgressQuizSummary(pickProgress(data, "quiz")),
    courses: courses.map(normalizeProgressCourse),
    recentActivity: recentActivity.map(normalizeProgressActivity),
  };
}

function normalizeEducatorAnalyticsCourse(payload: unknown, index: number): EducatorCourseAnalyticsItem {
  const data = progressRecord(payload);

  return {
    courseUuid: normalizeString(pickProgress(data, "courseUuid", "course_uuid"), `course-${index + 1}`),
    courseTitle: normalizeString(pickProgress(data, "courseTitle", "course_title"), `Course ${index + 1}`),
    status: normalizeString(pickProgress(data, "status"), "unknown"),
    totalEnrollments: toNonNegativeNumber(pickProgress(data, "totalEnrollments", "total_enrollments")),
    activeEnrollments: toNonNegativeNumber(pickProgress(data, "activeEnrollments", "active_enrollments")),
    completedEnrollments: toNonNegativeNumber(pickProgress(data, "completedEnrollments", "completed_enrollments")),
    avgProgressPercent: toNullablePercentNumber(pickProgress(data, "avgProgressPercent", "avg_progress_percent")),
  };
}

function normalizeEducatorAnalytics(payload: unknown): EducatorAnalytics {
  const data = progressRecord(payload);
  const courses = Array.isArray(pickProgress(data, "courses"))
    ? (pickProgress(data, "courses") as unknown[]).map(normalizeEducatorAnalyticsCourse)
    : [];

  return {
    courses,
    totalCourses: toNonNegativeNumber(pickProgress(data, "totalCourses", "total_courses"), courses.length),
    totalEnrollments: toNonNegativeNumber(pickProgress(data, "totalEnrollments", "total_enrollments")),
    totalActiveEnrollments: toNonNegativeNumber(
      pickProgress(data, "totalActiveEnrollments", "total_active_enrollments")
    ),
    totalCompletedEnrollments: toNonNegativeNumber(
      pickProgress(data, "totalCompletedEnrollments", "total_completed_enrollments")
    ),
  };
}

function normalizeQuizModuleStats(payload: unknown, index: number): QuizModuleStatsItem {
  const data = progressRecord(payload);

  return {
    courseUuid: normalizeString(pickProgress(data, "courseUuid", "course_uuid"), `course-${index + 1}`),
    courseTitle: normalizeString(pickProgress(data, "courseTitle", "course_title"), `Course ${index + 1}`),
    moduleUuid: normalizeString(pickProgress(data, "moduleUuid", "module_uuid"), `module-${index + 1}`),
    moduleTitle: normalizeString(pickProgress(data, "moduleTitle", "module_title"), `Module ${index + 1}`),
    quizTitle: normalizeString(pickProgress(data, "quizTitle", "quiz_title"), "Quiz"),
    totalAttempts: toNonNegativeNumber(pickProgress(data, "totalAttempts", "total_attempts")),
    uniqueLearners: toNonNegativeNumber(pickProgress(data, "uniqueLearners", "unique_learners")),
    avgScorePercent: toNullablePercentNumber(pickProgress(data, "avgScorePercent", "avg_score_percent")),
    passRate: toNullablePercentNumber(pickProgress(data, "passRate", "pass_rate")),
    avgDurationSeconds: toNullableNonNegativeNumber(
      pickProgress(data, "avgDurationSeconds", "avg_duration_seconds")
    ),
  };
}

function normalizeEducatorQuizAnalytics(payload: unknown): EducatorQuizAnalytics {
  const data = progressRecord(payload);
  const items = Array.isArray(pickProgress(data, "items"))
    ? (pickProgress(data, "items") as unknown[]).map(normalizeQuizModuleStats)
    : [];

  return { items };
}

function normalizeTeachingInsight(payload: unknown, index: number): TeachingInsightItem {
  const data = progressRecord(payload);

  return {
    insightId: normalizeString(pickProgress(data, "insightId", "insight_id"), `insight-${index + 1}`),
    priority: normalizeString(pickProgress(data, "priority"), "low"),
    category: normalizeString(pickProgress(data, "category"), "general"),
    title: normalizeString(pickProgress(data, "title"), `Insight ${index + 1}`),
    detail: normalizeString(pickProgress(data, "detail")),
    actionLabel: normalizeString(pickProgress(data, "actionLabel", "action_label"), "Review"),
    courseUuid: asNullableString(pickProgress(data, "courseUuid", "course_uuid")),
    courseTitle: asNullableString(pickProgress(data, "courseTitle", "course_title")),
    moduleUuid: asNullableString(pickProgress(data, "moduleUuid", "module_uuid")),
    moduleTitle: asNullableString(pickProgress(data, "moduleTitle", "module_title")),
    metricLabel: asNullableDisplayString(pickProgress(data, "metricLabel", "metric_label")),
    metricValue: asNullableDisplayString(pickProgress(data, "metricValue", "metric_value")),
  };
}

function normalizeEducatorTeachingInsights(payload: unknown): EducatorTeachingInsights {
  const data = progressRecord(payload);
  const items = Array.isArray(pickProgress(data, "items"))
    ? (pickProgress(data, "items") as unknown[]).map(normalizeTeachingInsight)
    : [];

  return {
    generatedAt: normalizeString(pickProgress(data, "generatedAt", "generated_at")),
    totalInsights: toNonNegativeNumber(pickProgress(data, "totalInsights", "total_insights"), items.length),
    highPriorityCount: toNonNegativeNumber(pickProgress(data, "highPriorityCount", "high_priority_count")),
    items,
  };
}

function normalizeMaterialBrief(payload: unknown, index: number): EducatorMaterialBriefItem {
  const data = progressRecord(payload);
  const rawMaterialTypes = pickProgress(data, "materialTypes", "material_types");

  return {
    briefId: normalizeString(pickProgress(data, "briefId", "brief_id"), `brief-${index + 1}`),
    priority: normalizeString(pickProgress(data, "priority"), "low"),
    courseUuid: normalizeString(pickProgress(data, "courseUuid", "course_uuid"), `course-${index + 1}`),
    courseTitle: normalizeString(pickProgress(data, "courseTitle", "course_title"), `Course ${index + 1}`),
    moduleUuid: normalizeString(pickProgress(data, "moduleUuid", "module_uuid"), `module-${index + 1}`),
    moduleTitle: normalizeString(pickProgress(data, "moduleTitle", "module_title"), `Module ${index + 1}`),
    moduleStatus: normalizeString(pickProgress(data, "moduleStatus", "module_status"), "unknown"),
    materialCount: toNonNegativeNumber(pickProgress(data, "materialCount", "material_count")),
    materialTypes: Array.isArray(rawMaterialTypes)
      ? rawMaterialTypes.map((item) => String(item)).filter(Boolean)
      : [],
    quizTitle: asNullableString(pickProgress(data, "quizTitle", "quiz_title")),
    passRate: toNullablePercentNumber(pickProgress(data, "passRate", "pass_rate")),
    averageScorePercent: toNullablePercentNumber(
      pickProgress(data, "averageScorePercent", "average_score_percent")
    ),
    summary: normalizeString(pickProgress(data, "summary")),
    difficultySignal: normalizeString(pickProgress(data, "difficultySignal", "difficulty_signal")),
    recommendedAction: normalizeString(pickProgress(data, "recommendedAction", "recommended_action"), "Review"),
  };
}

function normalizeEducatorMaterialBriefs(payload: unknown): EducatorMaterialBriefs {
  const data = progressRecord(payload);
  const items = Array.isArray(pickProgress(data, "items"))
    ? (pickProgress(data, "items") as unknown[]).map(normalizeMaterialBrief)
    : [];

  return {
    generatedAt: normalizeString(pickProgress(data, "generatedAt", "generated_at")),
    totalBriefs: toNonNegativeNumber(pickProgress(data, "totalBriefs", "total_briefs"), items.length),
    highPriorityCount: toNonNegativeNumber(pickProgress(data, "highPriorityCount", "high_priority_count")),
    items,
  };
}

export async function getMyProgressOverview(): Promise<LearnerProgressOverview> {
  const response = await fetch(`${COURSE_API_BASE_URL}/courses/me/progress-overview`, {
    method: "GET",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
  });

  const text = await response.text();
  const payload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, payload);

  if (!response.ok) {
    throw new Error(extractErrorMessage(payload, "加载进度概览失败。"));
  }

  return normalizeProgressOverview(payload);
}

export async function getEducatorAnalytics(): Promise<EducatorAnalytics> {
  const response = await fetch(`${COURSE_API_BASE_URL}/courses/me/analytics`, {
    method: "GET",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
  });

  const text = await response.text();
  const payload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, payload);

  if (!response.ok) {
    throw new Error(extractErrorMessage(payload, "加载教师分析失败。"));
  }

  return normalizeEducatorAnalytics(payload);
}

export async function getEducatorQuizAnalytics(): Promise<EducatorQuizAnalytics> {
  const response = await fetch(`${COURSE_API_BASE_URL}/courses/me/analytics/quiz`, {
    method: "GET",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
  });

  const text = await response.text();
  const payload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, payload);

  if (!response.ok) {
    throw new Error(extractErrorMessage(payload, "加载教师测验分析失败。"));
  }

  return normalizeEducatorQuizAnalytics(payload);
}

export async function getEducatorTeachingInsights(): Promise<EducatorTeachingInsights> {
  const response = await fetch(`${COURSE_API_BASE_URL}/courses/me/analytics/teaching-insights`, {
    method: "GET",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
  });

  const text = await response.text();
  const payload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, payload);

  if (!response.ok) {
    throw new Error(extractErrorMessage(payload, "加载教学洞察失败。"));
  }

  return normalizeEducatorTeachingInsights(payload);
}

export async function getEducatorMaterialBriefs(): Promise<EducatorMaterialBriefs> {
  const response = await fetch(`${COURSE_API_BASE_URL}/courses/me/analytics/material-briefs`, {
    method: "GET",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
  });

  const text = await response.text();
  const payload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, payload);

  if (!response.ok) {
    throw new Error(extractErrorMessage(payload, "加载资料摘要失败。"));
  }

  return normalizeEducatorMaterialBriefs(payload);
}

export async function getManagedCourseEnrollments(
  courseUuid: string
): Promise<CourseEnrollmentLearnerRecord[]> {
  const response = await fetch(`${COURSE_API_BASE_URL}/courses/${courseUuid}/enrolments`, {
    method: "GET",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
  });

  const text = await response.text();
  const payload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, payload);

  if (!response.ok) {
    throw new Error(extractErrorMessage(payload, "加载课程报名失败。"));
  }

  if (!Array.isArray(payload)) {
    return [];
  }

  return payload.map((item) =>
    normalizeCourseEnrollmentLearner(item as ApiCourseEnrollmentLearner)
  );
}

export async function getManagedCourses(options?: {
  search?: string;
  page?: number;
  pageSize?: number;
  offset?: number;
}): Promise<PaginatedCourseListResult> {
  const normalizedSearch = options?.search?.trim() || "";
  const page = options?.page ?? 1;
  const pageSize = options?.pageSize ?? 23;
  const offset = options?.offset;
  const params = new URLSearchParams();

  if (normalizedSearch) {
    params.set("search", normalizedSearch);
  }
  params.set("page", String(page));
  params.set("pageSize", String(pageSize));
  if (typeof offset === "number" && offset >= 0) {
    params.set("offset", String(offset));
  }

  const response = await fetch(`${COURSE_API_BASE_URL}/courses/me/managed?${params.toString()}`, {
    method: "GET",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
  });

  const text = await response.text();
  const payload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, payload);

  if (!response.ok) {
    throw new Error("获取管理课程失败。");
  }

  return normalizePaginatedCoursePayload(payload);
}

export async function getAllManagedCourses(options?: { search?: string }): Promise<CourseRecord[]> {
  const firstPage = await getManagedCourses({ search: options?.search, page: 1, pageSize: 100 });
  if (firstPage.totalPages <= 1) {
    return firstPage.items;
  }
  const remainingPages = await Promise.all(
    Array.from({ length: firstPage.totalPages - 1 }, (_, index) =>
      getManagedCourses({ search: options?.search, page: index + 2, pageSize: 100 })
    )
  );
  return [firstPage, ...remainingPages].flatMap((page) => page.items);
}

export async function getManagedCourseByUuid(courseUuid: string): Promise<CourseRecord | null> {
  const response = await fetch(`${COURSE_API_BASE_URL}/courses/${courseUuid}/management`, {
    method: "GET",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
  });

  handleAuthenticationFailureFromResponse(response.status, null);

  if (!response.ok) {
    return null;
  }

  const text = await response.text();
  const payload = parseJsonText(text);
  if (!payload || typeof payload !== "object") {
    return null;
  }

  return normalizeCourse(payload as ApiCourse, 0);
}

export async function reorderCourseModules(
  courseUuid: string,
  modules: Array<{ moduleUuid: string; sortOrder: number }>
): Promise<void> {
  const response = await fetch(`${COURSE_API_BASE_URL}/courses/${courseUuid}/modules/reorder`, {
    method: "PATCH",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify({ modules }),
  });

  handleAuthenticationFailureFromResponse(response.status, null);

  if (!response.ok) {
    throw new Error("调整模块顺序失败。");
  }
}

export type UpdateCoursePayload = {
  title?: string;
  subtitle?: string;
  description?: string;
  difficultyLevel?: string;
  estimatedMinutes?: number | null;
  category?: string;
  languageCode?: string;
  isPublic?: boolean;
  learningPathTitle?: string;
  learningPathDescription?: string;
  coverImageUrl?: string;
};

export async function updateManagedCourse(
  courseUuid: string,
  payload: UpdateCoursePayload
): Promise<CourseRecord> {
  const response = await fetch(`${COURSE_API_BASE_URL}/courses/${courseUuid}`, {
    method: "PATCH",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify(payload),
  });

  const text = await response.text();
  const parsedPayload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, parsedPayload);

  if (!response.ok) {
    throw new Error(extractErrorMessage(parsedPayload, "更新课程失败。"));
  }

  if (!parsedPayload || typeof parsedPayload !== "object") {
    throw new Error("Invalid course update response.");
  }

  return normalizeCourse(parsedPayload as ApiCourse, 0);
}

export async function deleteManagedCourse(courseUuid: string): Promise<void> {
  const response = await fetch(`${COURSE_API_BASE_URL}/courses/${courseUuid}`, {
    method: "DELETE",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
  });

  const text = await response.text();
  const parsedPayload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, parsedPayload);

  if (!response.ok) {
    throw new Error(extractErrorMessage(parsedPayload, "删除课程失败。"));
  }
}

export async function uploadManagedCourseCover(courseUuid: string, coverImage: File): Promise<CourseRecord> {
  const formData = new FormData();
  formData.set("coverImage", coverImage);

  const response = await fetch(`${COURSE_API_BASE_URL}/courses/${courseUuid}/cover`, {
    method: "POST",
    headers: buildAuthHeaders(),
    body: formData,
  });

  const text = await response.text();
  const parsedPayload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, parsedPayload);

  if (!response.ok) {
    throw new Error(extractErrorMessage(parsedPayload, "更新课程封面失败。"));
  }

  if (!parsedPayload || typeof parsedPayload !== "object") {
    throw new Error("Invalid course cover update response.");
  }

  return normalizeCourse(parsedPayload as ApiCourse, 0);
}

export type CreateCoursePayload = {
  title: string;
  subtitle?: string;
  description?: string;
  difficultyLevel?: string;
  estimatedMinutes?: number | null;
  category?: string;
  languageCode?: string;
  isPublic?: boolean;
  learningPathTitle?: string;
  learningPathDescription?: string;
  coverImage?: File | null;
};

export async function createManagedCourse(payload: CreateCoursePayload): Promise<CourseRecord> {
  const formData = new FormData();
  formData.set("title", payload.title.trim());

  if (payload.subtitle?.trim()) {
    formData.set("subtitle", payload.subtitle.trim());
  }
  if (payload.description?.trim()) {
    formData.set("description", payload.description.trim());
  }
  if (payload.difficultyLevel?.trim()) {
    formData.set("difficultyLevel", payload.difficultyLevel.trim());
  }
  if (payload.estimatedMinutes && payload.estimatedMinutes > 0) {
    formData.set("estimatedMinutes", String(payload.estimatedMinutes));
  }
  if (payload.category?.trim()) {
    formData.set("category", payload.category.trim());
  }
  if (payload.languageCode?.trim()) {
    formData.set("languageCode", payload.languageCode.trim());
  }
  formData.set("isPublic", "true");
  if (payload.learningPathTitle?.trim()) {
    formData.set("learningPathTitle", payload.learningPathTitle.trim());
  }
  if (payload.learningPathDescription?.trim()) {
    formData.set("learningPathDescription", payload.learningPathDescription.trim());
  }
  if (payload.coverImage) {
    formData.set("coverImage", payload.coverImage);
  }

  const response = await fetch(`${COURSE_API_BASE_URL}/courses`, {
    method: "POST",
    headers: buildAuthHeaders(),
    body: formData,
  });

  const text = await response.text();
  const parsedPayload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, parsedPayload);

  if (!response.ok) {
    throw new Error(extractErrorMessage(parsedPayload, "创建课程失败。"));
  }

  if (!parsedPayload || typeof parsedPayload !== "object") {
    throw new Error("Invalid course creation response.");
  }

  return normalizeCourse(parsedPayload as ApiCourse, 0);
}

export type UpdateModulePayload = {
  title?: string;
  description?: string;
  content?: string;
  estimatedMinutes?: number | null;
  sortOrder?: number;
};

export type CreateModulePayload = {
  title: string;
  description?: string;
  content: string;
  estimatedMinutes?: number | null;
  sortOrder?: number | null;
};

export type ManagedModuleAuthoringRecord = {
  moduleUuid: string;
  sortOrder: number;
};

export async function createManagedModule(
  courseUuid: string,
  payload: CreateModulePayload
): Promise<ManagedModuleAuthoringRecord> {
  const response = await fetch(`${COURSE_API_BASE_URL}/courses/${courseUuid}/modules`, {
    method: "POST",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify({
      title: payload.title.trim(),
      description: payload.description?.trim() || null,
      content: payload.content.trim(),
      estimatedMinutes: payload.estimatedMinutes ?? null,
      sortOrder: payload.sortOrder ?? null,
    }),
  });

  const text = await response.text();
  const parsedPayload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, parsedPayload);

  if (!response.ok) {
    throw new Error(extractErrorMessage(parsedPayload, "创建模块失败。"));
  }

  return {
    moduleUuid: String((parsedPayload as { moduleUuid?: string }).moduleUuid ?? ""),
    sortOrder: Number((parsedPayload as { sortOrder?: number }).sortOrder ?? 0),
  };
}

export async function updateManagedModule(
  courseUuid: string,
  moduleUuid: string,
  payload: UpdateModulePayload
): Promise<void> {
  const response = await fetch(`${COURSE_API_BASE_URL}/courses/${courseUuid}/modules/${moduleUuid}`, {
    method: "PATCH",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify(payload),
  });

  const text = await response.text();
  const parsedPayload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, parsedPayload);

  if (!response.ok) {
    throw new Error(extractErrorMessage(parsedPayload, "更新模块失败。"));
  }
}

export async function setModulePrerequisite(
  courseUuid: string,
  moduleUuid: string,
  prerequisiteModuleUuid: string
): Promise<void> {
  const response = await fetch(
    `${COURSE_API_BASE_URL}/courses/${courseUuid}/modules/${moduleUuid}/prerequisite`,
    {
      method: "PUT",
      headers: buildAuthHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ prerequisiteModuleUuid }),
    }
  );

  const text = await response.text();
  const parsedPayload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, parsedPayload);

  if (!response.ok) {
    throw new Error(extractErrorMessage(parsedPayload, "设置模块前置条件失败。"));
  }
}

export async function removeModulePrerequisite(courseUuid: string, moduleUuid: string): Promise<void> {
  const response = await fetch(
    `${COURSE_API_BASE_URL}/courses/${courseUuid}/modules/${moduleUuid}/prerequisite`,
    {
      method: "DELETE",
      headers: buildAuthHeaders({ "Content-Type": "application/json" }),
    }
  );

  const text = await response.text();
  const parsedPayload = text ? parseJsonText(text) : null;
  handleAuthenticationFailureFromResponse(response.status, parsedPayload);

  if (!response.ok) {
    throw new Error(extractErrorMessage(parsedPayload, "移除模块前置条件失败。"));
  }
}

export async function deleteManagedModule(courseUuid: string, moduleUuid: string): Promise<void> {
  const response = await fetch(`${COURSE_API_BASE_URL}/courses/${courseUuid}/modules/${moduleUuid}`, {
    method: "DELETE",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
  });

  const text = await response.text();
  const parsedPayload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, parsedPayload);

  if (!response.ok) {
    throw new Error(extractErrorMessage(parsedPayload, "删除模块失败。"));
  }
}

export async function publishManagedModule(courseUuid: string, moduleUuid: string): Promise<void> {
  const response = await fetch(`${COURSE_API_BASE_URL}/courses/${courseUuid}/modules/${moduleUuid}/publish`, {
    method: "POST",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify({
      status: "published",
    }),
  });

  const text = await response.text();
  const parsedPayload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, parsedPayload);

  if (!response.ok) {
    throw new Error(extractErrorMessage(parsedPayload, "发布模块失败。"));
  }
}

export async function publishManagedCourse(courseUuid: string, moduleUuids: string[]): Promise<CourseRecord> {
  const response = await fetch(`${COURSE_API_BASE_URL}/courses/${courseUuid}/publish`, {
    method: "POST",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify({
      moduleUuids,
    }),
  });

  const text = await response.text();
  const parsedPayload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, parsedPayload);

  if (!response.ok || !parsedPayload || typeof parsedPayload !== "object") {
    throw new Error(extractErrorMessage(parsedPayload, "发布课程失败。"));
  }

  return normalizeCourse(parsedPayload as ApiCourse, 0);
}

export type UploadModuleMaterialPayload = {
  title?: string;
  materialType?: string;
  sortOrder?: number | null;
  file: File;
};

export type MultipartModuleMaterialUploadInitPayload = {
  title?: string;
  materialType?: string;
  sortOrder?: number | null;
  fileName: string;
  contentType?: string | null;
  sizeBytes: number;
};

export type MultipartModuleMaterialUploadInitResponse = {
  uploadSessionUuid: string;
  uploadId: string;
  bucket: string | null;
  objectKey: string;
  storageProvider: string;
  partUrlExpiresSeconds: number;
};

export type MultipartModuleMaterialUploadPartUrlResponse = {
  uploadSessionUuid: string;
  partNumber: number;
  method: string;
  uploadUrl: string;
  expiresSeconds: number;
};

export type MultipartModuleMaterialUploadCompletedPart = {
  partNumber: number;
  etag: string;
};

function readRequiredMultipartString(
  data: Record<string, unknown>,
  errorMessage: string,
  ...keys: string[]
) {
  const value = pickProgress(data, ...keys);
  if (typeof value !== "string" || !value.trim()) {
    throw new Error(errorMessage);
  }

  return value.trim();
}

function readOptionalMultipartString(data: Record<string, unknown>, ...keys: string[]) {
  const value = pickProgress(data, ...keys);
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function readPositiveMultipartInteger(data: Record<string, unknown>, errorMessage: string, ...keys: string[]) {
  const value = pickProgress(data, ...keys);
  const parsed =
    typeof value === "number"
      ? value
      : typeof value === "string" && value.trim()
        ? Number(value)
        : Number.NaN;

  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new Error(errorMessage);
  }

  return parsed;
}

function assertUsableMultipartUploadUrl(uploadUrl: string, errorMessage: string) {
  if (uploadUrl.startsWith("/")) {
    return;
  }

  try {
    const parsedUrl = new URL(uploadUrl);
    if (parsedUrl.protocol === "http:" || parsedUrl.protocol === "https:") {
      return;
    }
  } catch {
    // Fall through to the shared invalid-response error.
  }

  throw new Error(errorMessage);
}

function normalizeMultipartUploadInitResponse(payload: unknown): MultipartModuleMaterialUploadInitResponse {
  const data = progressRecord(payload);
  const errorMessage = "Multipart upload initialization response was invalid. Please try again.";

  return {
    uploadSessionUuid: readRequiredMultipartString(data, errorMessage, "uploadSessionUuid", "upload_session_uuid"),
    uploadId: readRequiredMultipartString(data, errorMessage, "uploadId", "upload_id"),
    bucket: readOptionalMultipartString(data, "bucket"),
    objectKey: readRequiredMultipartString(data, errorMessage, "objectKey", "object_key"),
    storageProvider: readRequiredMultipartString(data, errorMessage, "storageProvider", "storage_provider"),
    partUrlExpiresSeconds: readPositiveMultipartInteger(
      data,
      errorMessage,
      "partUrlExpiresSeconds",
      "part_url_expires_seconds"
    ),
  };
}

function normalizeMultipartUploadPartUrlResponse(
  payload: unknown,
  expectedUploadSessionUuid: string,
  expectedPartNumber: number
): MultipartModuleMaterialUploadPartUrlResponse {
  const data = progressRecord(payload);
  const errorMessage = "Multipart upload URL response was invalid. Please try again.";
  const uploadSessionUuid = readRequiredMultipartString(
    data,
    errorMessage,
    "uploadSessionUuid",
    "upload_session_uuid"
  );
  const partNumber = readPositiveMultipartInteger(data, errorMessage, "partNumber", "part_number");
  const method = readRequiredMultipartString(data, errorMessage, "method").toUpperCase();
  const uploadUrl = readRequiredMultipartString(data, errorMessage, "uploadUrl", "upload_url");
  const expiresSeconds = readPositiveMultipartInteger(data, errorMessage, "expiresSeconds", "expires_seconds");

  if (uploadSessionUuid !== expectedUploadSessionUuid || partNumber !== expectedPartNumber || method !== "PUT") {
    throw new Error(errorMessage);
  }

  assertUsableMultipartUploadUrl(uploadUrl, errorMessage);

  return {
    uploadSessionUuid,
    partNumber,
    method,
    uploadUrl,
    expiresSeconds,
  };
}

export async function uploadManagedModuleMaterial(
  courseUuid: string,
  moduleUuid: string,
  payload: UploadModuleMaterialPayload
): Promise<void> {
  const formData = new FormData();
  if (payload.title?.trim()) {
    formData.set("title", payload.title.trim());
  }
  if (payload.materialType?.trim()) {
    formData.set("materialType", payload.materialType.trim());
  }
  if (payload.sortOrder && payload.sortOrder > 0) {
    formData.set("sortOrder", String(payload.sortOrder));
  }
  formData.set("file", payload.file);

  const response = await fetch(`${COURSE_API_BASE_URL}/courses/${courseUuid}/modules/${moduleUuid}/materials/upload`, {
    method: "POST",
    headers: buildAuthHeaders(),
    body: formData,
  });

  const text = await response.text();
  const parsedPayload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, parsedPayload);

  if (!response.ok) {
    throw new Error(extractErrorMessage(parsedPayload, "上传模块资料失败。"));
  }
}

export async function initMultipartManagedModuleMaterialUpload(
  courseUuid: string,
  moduleUuid: string,
  payload: MultipartModuleMaterialUploadInitPayload
): Promise<MultipartModuleMaterialUploadInitResponse> {
  const response = await fetch(`${COURSE_API_BASE_URL}/courses/${courseUuid}/modules/${moduleUuid}/materials/uploads/init`, {
    method: "POST",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify({
      title: payload.title?.trim() || null,
      materialType: payload.materialType?.trim() || null,
      sortOrder: payload.sortOrder ?? null,
      fileName: payload.fileName,
      contentType: payload.contentType?.trim() || null,
      sizeBytes: payload.sizeBytes,
    }),
  });

  const text = await response.text();
  const parsedPayload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, parsedPayload);

  if (!response.ok || !parsedPayload || typeof parsedPayload !== "object") {
    throw new Error(extractErrorMessage(parsedPayload, "初始化分片上传失败。"));
  }

  return normalizeMultipartUploadInitResponse(parsedPayload);
}

export async function getMultipartManagedModuleMaterialPartUploadUrl(
  courseUuid: string,
  moduleUuid: string,
  uploadSessionUuid: string,
  partNumber: number
): Promise<MultipartModuleMaterialUploadPartUrlResponse> {
  const response = await fetch(
    `${COURSE_API_BASE_URL}/courses/${courseUuid}/modules/${moduleUuid}/materials/uploads/${uploadSessionUuid}/parts/${partNumber}`,
    {
      method: "GET",
      headers: buildAuthHeaders({
        "Content-Type": "application/json",
      }),
    }
  );

  const text = await response.text();
  const parsedPayload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, parsedPayload);

  if (!response.ok || !parsedPayload || typeof parsedPayload !== "object") {
    throw new Error(extractErrorMessage(parsedPayload, "获取分片上传地址失败。"));
  }

  return normalizeMultipartUploadPartUrlResponse(parsedPayload, uploadSessionUuid, partNumber);
}

export async function completeMultipartManagedModuleMaterialUpload(
  courseUuid: string,
  moduleUuid: string,
  uploadSessionUuid: string,
  parts: MultipartModuleMaterialUploadCompletedPart[]
): Promise<void> {
  const response = await fetch(
    `${COURSE_API_BASE_URL}/courses/${courseUuid}/modules/${moduleUuid}/materials/uploads/${uploadSessionUuid}/complete`,
    {
      method: "POST",
      headers: buildAuthHeaders({
        "Content-Type": "application/json",
      }),
      body: JSON.stringify({ parts }),
    }
  );

  const text = await response.text();
  const parsedPayload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, parsedPayload);

  if (!response.ok) {
    throw new Error(extractErrorMessage(parsedPayload, "完成分片上传失败。"));
  }
}

export async function abortMultipartManagedModuleMaterialUpload(
  courseUuid: string,
  moduleUuid: string,
  uploadSessionUuid: string
): Promise<void> {
  const response = await fetch(
    `${COURSE_API_BASE_URL}/courses/${courseUuid}/modules/${moduleUuid}/materials/uploads/${uploadSessionUuid}`,
    {
      method: "DELETE",
      headers: buildAuthHeaders({
        "Content-Type": "application/json",
      }),
    }
  );

  const text = await response.text();
  const parsedPayload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, parsedPayload);

  if (!response.ok) {
    throw new Error(extractErrorMessage(parsedPayload, "取消分片上传失败。"));
  }
}

export async function deleteManagedModuleMaterial(
  courseUuid: string,
  moduleUuid: string,
  materialUuid: string
): Promise<void> {
  const response = await fetch(
    `${COURSE_API_BASE_URL}/courses/${courseUuid}/modules/${moduleUuid}/materials/${materialUuid}`,
    {
      method: "DELETE",
      headers: buildAuthHeaders({
        "Content-Type": "application/json",
      }),
    }
  );

  const text = await response.text();
  const parsedPayload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, parsedPayload);

  if (!response.ok) {
    throw new Error(extractErrorMessage(parsedPayload, "删除模块资料失败。"));
  }
}

export function abortMultipartManagedModuleMaterialUploadBestEffort(
  courseUuid: string,
  moduleUuid: string,
  uploadSessionUuid: string
): void {
  void fetch(
    `${COURSE_API_BASE_URL}/courses/${courseUuid}/modules/${moduleUuid}/materials/uploads/${uploadSessionUuid}`,
    {
      method: "DELETE",
      headers: buildAuthHeaders({
        "Content-Type": "application/json",
      }),
      keepalive: true,
    }
  ).catch(() => {
    // Best-effort cleanup for page unload; the backend TTL remains the source of truth.
  });
}

// ---------------------------------------------------------------------------
// Quiz management (educator authoring)
// ---------------------------------------------------------------------------

function normalizeQuiz(payload: unknown): QuizRecord {
  const data = (payload ?? {}) as Record<string, unknown>;
  const rawQuestions = Array.isArray(data.questions) ? (data.questions as Record<string, unknown>[]) : [];

  const questions = rawQuestions.map((q, qi) => normalizeQuizQuestion(q, qi));

  return {
    quizUuid: String(data.quizUuid ?? data.quiz_uuid ?? ""),
    title: String(data.title ?? ""),
    description: String(data.description ?? ""),
    status: (data.status as QuizRecord["status"]) ?? "draft",
    timeLimitSeconds:
      typeof data.timeLimitSeconds === "number"
        ? data.timeLimitSeconds
        : typeof data.time_limit_seconds === "number"
          ? data.time_limit_seconds
          : null,
    questionCountPerAttempt:
      typeof data.questionCountPerAttempt === "number"
        ? data.questionCountPerAttempt
        : typeof data.question_count_per_attempt === "number"
          ? data.question_count_per_attempt
          : 1,
    availableQuestionCount:
      typeof data.availableQuestionCount === "number"
        ? data.availableQuestionCount
        : typeof data.available_question_count === "number"
          ? data.available_question_count
          : questions.filter((q) => q.isActive).length,
    shuffleQuestions:
      typeof data.shuffleQuestions === "boolean"
        ? data.shuffleQuestions
        : typeof data.shuffle_questions === "boolean"
          ? data.shuffle_questions
          : true,
    shuffleOptions:
      typeof data.shuffleOptions === "boolean"
        ? data.shuffleOptions
        : typeof data.shuffle_options === "boolean"
          ? data.shuffle_options
          : false,
    questions,
  };
}

function normalizeQuizQuestion(q: Record<string, unknown>, qi: number): QuizQuestionDraft {
  const rawOptions = Array.isArray(q.options) ? (q.options as Record<string, unknown>[]) : [];
  return {
    questionUuid: String(q.questionUuid ?? q.question_uuid ?? ""),
    questionText: String(q.questionText ?? q.question_text ?? ""),
    explanationText: String(q.explanationText ?? q.explanation_text ?? ""),
    sortOrder: typeof q.sortOrder === "number" ? q.sortOrder : typeof q.sort_order === "number" ? q.sort_order : qi + 1,
    isActive: (q.isActive ?? q.is_active ?? true) as boolean,
    options: rawOptions.map((o, oi) => ({
      optionUuid: String(o.optionUuid ?? o.option_uuid ?? ""),
      optionLabel: String(o.optionLabel ?? o.option_label ?? ""),
      optionText: String(o.optionText ?? o.option_text ?? ""),
      sortOrder: typeof o.sortOrder === "number" ? o.sortOrder : typeof o.sort_order === "number" ? o.sort_order : oi + 1,
      isCorrect: (o.isCorrect ?? o.is_correct ?? false) as boolean,
    })),
  };
}

function normalizeQuizQuestionPage(payload: unknown): QuizQuestionPage {
  const data = (payload ?? {}) as Record<string, unknown>;
  const rawItems = Array.isArray(data.items) ? (data.items as Record<string, unknown>[]) : [];
  const pageSize = toFiniteNumber(pick(data, "pageSize", "page_size"), 20, 1);
  const total = toNonNegativeNumber(data.total, rawItems.length);
  return {
    items: rawItems.map((item, index) => normalizeQuizQuestion(item, index)),
    page: toFiniteNumber(data.page, 1, 1),
    pageSize,
    total,
    totalPages:
      toFiniteNumber(
        pick(data, "totalPages", "total_pages"),
        Math.max(1, Math.ceil(total / pageSize)),
        1
      ),
  };
}

export async function getQuizAuthoring(
  courseUuid: string,
  moduleUuid: string,
  options?: { includeQuestions?: boolean }
): Promise<QuizRecord | null> {
  const params = new URLSearchParams();
  if (options?.includeQuestions === false) {
    params.set("include_questions", "false");
  }
  const queryString = params.toString();
  const response = await fetch(
    `${COURSE_API_BASE_URL}/courses/${courseUuid}/modules/${moduleUuid}/quiz/management${queryString ? `?${queryString}` : ""}`,
    { method: "GET", headers: buildAuthHeaders({ "Content-Type": "application/json" }) }
  );

  if (response.status === 404) return null;

  const text = await response.text();
  const payload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, payload);

  if (!response.ok) {
    throw new Error(extractErrorMessage(payload, "加载测验失败。"));
  }

  return normalizeQuiz(payload);
}

export async function listQuizAuthoringQuestions(
  courseUuid: string,
  moduleUuid: string,
  options?: { page?: number; pageSize?: number; query?: string }
): Promise<QuizQuestionPage> {
  const params = new URLSearchParams();
  params.set("page", String(options?.page ?? 1));
  params.set("page_size", String(options?.pageSize ?? 20));
  const query = options?.query?.trim() ?? "";
  if (query) {
    params.set("query", query);
  }
  const response = await fetch(
    `${COURSE_API_BASE_URL}/courses/${courseUuid}/modules/${moduleUuid}/quiz/management/questions?${params.toString()}`,
    { method: "GET", headers: buildAuthHeaders({ "Content-Type": "application/json" }) }
  );

  const text = await response.text();
  const payload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, payload);

  if (!response.ok) {
    throw new Error(extractErrorMessage(payload, "加载测验题目失败。"));
  }

  return normalizeQuizQuestionPage(payload);
}

export type UpsertQuizPayload = {
  title: string;
  description?: string | null;
  timeLimitSeconds?: number | null;
  questionCountPerAttempt: number;
  shuffleQuestions: boolean;
  shuffleOptions: boolean;
  questions: QuizQuestionDraft[];
};

export async function upsertQuiz(
  courseUuid: string,
  moduleUuid: string,
  payload: UpsertQuizPayload,
  options?: { includeQuestions?: boolean }
): Promise<QuizRecord> {
  const params = new URLSearchParams();
  if (options?.includeQuestions === false) {
    params.set("include_questions", "false");
  }
  const queryString = params.toString();
  const response = await fetch(
    `${COURSE_API_BASE_URL}/courses/${courseUuid}/modules/${moduleUuid}/quiz${queryString ? `?${queryString}` : ""}`,
    {
      method: "PUT",
      headers: buildAuthHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        title: payload.title.trim(),
        description: payload.description?.trim() || null,
        timeLimitSeconds: payload.timeLimitSeconds || null,
        questionCountPerAttempt: payload.questionCountPerAttempt,
        shuffleQuestions: payload.shuffleQuestions,
        shuffleOptions: payload.shuffleOptions,
        questions: payload.questions.map((q) => ({
          questionUuid: q.questionUuid || null,
          questionText: q.questionText.trim(),
          explanationText: q.explanationText.trim() || null,
          sortOrder: q.sortOrder,
          isActive: q.isActive,
          options: q.options.map((o) => ({
            optionUuid: o.optionUuid || null,
            optionLabel: o.optionLabel.trim() || null,
            optionText: o.optionText.trim(),
            sortOrder: o.sortOrder,
            isCorrect: o.isCorrect,
          })),
        })),
      }),
    }
  );

  const text = await response.text();
  const parsedPayload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, parsedPayload);

  if (!response.ok) {
    throw new Error(extractErrorMessage(parsedPayload, "保存测验失败。"));
  }

  return normalizeQuiz(parsedPayload);
}

export async function publishQuiz(
  courseUuid: string,
  moduleUuid: string,
  status: "published" | "draft" | "archived",
  options?: { includeQuestions?: boolean }
): Promise<QuizRecord> {
  const params = new URLSearchParams();
  if (options?.includeQuestions === false) {
    params.set("include_questions", "false");
  }
  const queryString = params.toString();
  const response = await fetch(
    `${COURSE_API_BASE_URL}/courses/${courseUuid}/modules/${moduleUuid}/quiz/publish${queryString ? `?${queryString}` : ""}`,
    {
      method: "POST",
      headers: buildAuthHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ status }),
    }
  );

  const text = await response.text();
  const parsedPayload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, parsedPayload);

  if (!response.ok) {
    throw new Error(extractErrorMessage(parsedPayload, "更新测验状态失败。"));
  }

  return normalizeQuiz(parsedPayload);
}

function normalizeQuizAuthoringGenerationResult(payload: unknown): QuizAuthoringGenerationResult {
  const data = (payload ?? {}) as Record<string, unknown>;
  const rawCreatedQuestions = Array.isArray(data.createdQuestions)
    ? (data.createdQuestions as Record<string, unknown>[])
    : [];
  const plan = (data.plan && typeof data.plan === "object" ? data.plan : {}) as Record<string, unknown>;
  const retrieval = (data.retrievalContext && typeof data.retrievalContext === "object"
    ? data.retrievalContext
    : {}) as Record<string, unknown>;

  return {
    createdQuestionCount: rawCreatedQuestions.length,
    createdQuestionUuids: rawCreatedQuestions
      .map((question) => question.questionUuid ?? question.question_uuid)
      .filter((value): value is string => typeof value === "string" && value.length > 0),
    plannedQuestionCount:
      typeof plan.plannedQuestionCount === "number"
        ? plan.plannedQuestionCount
        : typeof plan.planned_question_count === "number"
          ? plan.planned_question_count
          : rawCreatedQuestions.length,
    usedRetrieval: Boolean(retrieval.usedRetrieval ?? retrieval.used_retrieval ?? false),
    retrievalChunkCount:
      typeof retrieval.chunkCount === "number"
        ? retrieval.chunkCount
        : typeof retrieval.chunk_count === "number"
          ? retrieval.chunk_count
          : 0,
    planOverview: String(plan.overview ?? ""),
  };
}

export async function generateQuizAuthoringQuestions(
  courseUuid: string,
  moduleUuid: string,
  payload?: { additionalInstructions?: string | null }
): Promise<QuizAuthoringGenerationResult> {
  const response = await fetch(
    `${AI_API_BASE_URL}/courses/${courseUuid}/modules/${moduleUuid}/quiz/authoring/generate`,
    {
      method: "POST",
      headers: buildAuthHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        additionalInstructions: payload?.additionalInstructions?.trim() || null,
      }),
    }
  );

  const text = await response.text();
  const parsedPayload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, parsedPayload);

  if (!response.ok) {
    throw new Error(extractErrorMessage(parsedPayload, "生成测验草稿题目失败。"));
  }

  return normalizeQuizAuthoringGenerationResult(parsedPayload);
}

// ---------------------------------------------------------------------------
// Quiz learner APIs
// ---------------------------------------------------------------------------

function pick(obj: Record<string, unknown>, ...keys: string[]): unknown {
  for (const key of keys) {
    if (obj[key] !== undefined) return obj[key];
  }
  return undefined;
}

function normalizeAttemptSession(payload: unknown): QuizAttemptSession {
  const d = progressRecord(payload);
  const rawQs = Array.isArray(d.questions) ? (d.questions as Record<string, unknown>[]) : [];
  return {
    quizUuid: String(pick(d, "quizUuid", "quiz_uuid") ?? ""),
    moduleUuid: String(pick(d, "moduleUuid", "module_uuid") ?? ""),
    attemptSessionToken: String(pick(d, "attemptSessionToken", "attempt_session_token") ?? ""),
    attemptNumber: toFiniteNumber(pick(d, "attemptNumber", "attempt_number"), 1, 1),
    questionCount: toNonNegativeNumber(pick(d, "questionCount", "question_count"), rawQs.length),
    timeLimitSeconds: toNullableNonNegativeNumber(pick(d, "timeLimitSeconds", "time_limit_seconds")),
    startedAt: String(pick(d, "startedAt", "started_at") ?? ""),
    expiresAt: (pick(d, "expiresAt", "expires_at") as string | null) ?? null,
    questions: rawQs.map((q) => {
      const rawOpts = Array.isArray(q.options) ? (q.options as Record<string, unknown>[]) : [];
      return {
        questionId: toNonNegativeNumber(pick(q, "questionId", "question_id")),
        questionUuid: String(pick(q, "questionUuid", "question_uuid") ?? ""),
        questionText: String(pick(q, "questionText", "question_text") ?? ""),
        explanationText: (pick(q, "explanationText", "explanation_text") as string | null) ?? null,
        questionOrder: toFiniteNumber(pick(q, "questionOrder", "question_order"), 1, 1),
        options: rawOpts.map((o) => ({
          optionId: toNonNegativeNumber(pick(o, "optionId", "option_id")),
          optionUuid: String(pick(o, "optionUuid", "option_uuid") ?? ""),
          optionLabel: (pick(o, "optionLabel", "option_label") as string | null) ?? null,
          optionText: String(pick(o, "optionText", "option_text") ?? ""),
          sortOrder: toNonNegativeNumber(pick(o, "sortOrder", "sort_order")),
        })),
      };
    }),
  };
}

function normalizeAttemptResult(payload: unknown): QuizAttemptResult {
  const d = progressRecord(payload);
  const rawAnswers = Array.isArray(d.answers) ? (d.answers as Record<string, unknown>[]) : [];
  return {
    quizAttemptUuid: String(pick(d, "quizAttemptUuid", "quiz_attempt_uuid") ?? ""),
    quizUuid: String(pick(d, "quizUuid", "quiz_uuid") ?? ""),
    moduleUuid: String(pick(d, "moduleUuid", "module_uuid") ?? ""),
    attemptNumber: toFiniteNumber(pick(d, "attemptNumber", "attempt_number"), 1, 1),
    questionCount: toNonNegativeNumber(pick(d, "questionCount", "question_count")),
    correctCount: toNonNegativeNumber(pick(d, "correctCount", "correct_count")),
    scorePercent: toScorePercentString(pick(d, "scorePercent", "score_percent")),
    isPassed: toBooleanValue(pick(d, "isPassed", "is_passed")),
    isTimedOut: toBooleanValue(pick(d, "isTimedOut", "is_timed_out")),
    moduleCompleted: toBooleanValue(pick(d, "moduleCompleted", "module_completed")),
    timeLimitSeconds: toNullableNonNegativeNumber(pick(d, "timeLimitSeconds", "time_limit_seconds")),
    startedAt: String(pick(d, "startedAt", "started_at") ?? ""),
    submittedAt: String(pick(d, "submittedAt", "submitted_at") ?? ""),
    durationSeconds: toNullableNonNegativeNumber(pick(d, "durationSeconds", "duration_seconds")),
    answers: rawAnswers.map((a) => ({
      questionUuid: String(pick(a, "questionUuid", "question_uuid") ?? ""),
      questionOrder: toNonNegativeNumber(pick(a, "questionOrder", "question_order")),
      questionText: String(pick(a, "questionText", "question_text") ?? ""),
      explanationText: (pick(a, "explanationText", "explanation_text") as string | null) ?? null,
      selectedOptionUuid: (pick(a, "selectedOptionUuid", "selected_option_uuid") as string | null) ?? null,
      selectedOptionText: (pick(a, "selectedOptionText", "selected_option_text") as string | null) ?? null,
      correctOptionUuid: String(pick(a, "correctOptionUuid", "correct_option_uuid") ?? ""),
      correctOptionText: String(pick(a, "correctOptionText", "correct_option_text") ?? ""),
      isCorrect: toBooleanValue(pick(a, "isCorrect", "is_correct")),
    })),
  };
}

export async function getActiveQuizSession(courseUuid: string, moduleUuid: string): Promise<QuizAttemptSession | null> {
  const response = await fetch(
    `${COURSE_API_BASE_URL}/courses/${courseUuid}/modules/${moduleUuid}/quiz/active-session`,
    { method: "GET", headers: buildAuthHeaders({ "Content-Type": "application/json" }) }
  );
  if (response.status === 404 || response.status === 204) return null;
  const text = await response.text();
  const payload = text ? parseJsonText(text) : null;
  handleAuthenticationFailureFromResponse(response.status, payload);
  if (!response.ok) {
    throw new Error(extractErrorMessage(payload, "加载活动测验会话失败。"));
  }
  if (!text) return null;
  return normalizeAttemptSession(payload);
}

export async function startQuizAttempt(courseUuid: string, moduleUuid: string): Promise<QuizAttemptSession> {
  const response = await fetch(
    `${COURSE_API_BASE_URL}/courses/${courseUuid}/modules/${moduleUuid}/quiz/attempt-sessions`,
    { method: "POST", headers: buildAuthHeaders({ "Content-Type": "application/json" }) }
  );
  const text = await response.text();
  const payload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, payload);
  if (!response.ok) throw new Error(extractErrorMessage(payload, "开始测验失败。"));
  return normalizeAttemptSession(payload);
}

export async function startAutoGeneratedQuizAttemptWithProgress(
  courseUuid: string,
  moduleUuid: string,
  options?: {
    additionalInstructions?: string | null;
    onEvent?: (event: QuizGenerationProgressEvent) => void;
  }
): Promise<QuizAttemptSession> {
  const response = await fetch(
    `${AI_API_BASE_URL}/courses/${courseUuid}/modules/${moduleUuid}/quiz/generated-attempt-sessions/auto/stream`,
    {
      method: "POST",
      headers: buildAuthHeaders({
        "Content-Type": "application/json",
        Accept: "application/x-ndjson",
      }),
      body: JSON.stringify({
        additionalInstructions: options?.additionalInstructions?.trim() || null,
      }),
    }
  );

  if (!response.ok) {
    const text = await response.text();
    const payload = parseJsonText(text);
    handleAuthenticationFailureFromResponse(response.status, payload);
    throw new Error(extractErrorMessage(payload, "生成测验失败。"));
  }

  if (!response.body) {
    throw new Error("测验生成流不可用。");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let resultSession: QuizAttemptSession | null = null;
  let streamErrorMessage: string | null = null;

  const processLine = (line: string) => {
    const trimmed = line.trim();
    if (!trimmed) return;

    const parsed = parseJsonText(trimmed) as QuizGenerationProgressEvent | null;
    if (!parsed || typeof parsed !== "object") return;

    options?.onEvent?.(parsed);

    if (parsed.event === "result") {
      const data = parsed.data as { attemptStartResponse?: unknown };
      if (data.attemptStartResponse) {
        resultSession = normalizeAttemptSession(data.attemptStartResponse);
      }
    }

    if (parsed.event === "error") {
      streamErrorMessage = parsed.message || "测验生成失败。";
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });

    let newlineIndex = buffer.indexOf("\n");
    while (newlineIndex >= 0) {
      processLine(buffer.slice(0, newlineIndex));
      buffer = buffer.slice(newlineIndex + 1);
      newlineIndex = buffer.indexOf("\n");
    }

    if (done) break;
  }

  if (buffer.trim()) {
    processLine(buffer);
  }

  if (streamErrorMessage) {
    throw new Error(streamErrorMessage);
  }

  if (!resultSession) {
    throw new Error("测验生成结束，但未开始测验会话。");
  }

  return resultSession;
}

function normalizeQuizGenerationRun(payload: unknown): QuizGenerationRun {
  const data = (payload ?? {}) as Record<string, unknown>;
  const rawEvents = Array.isArray(data.events) ? (data.events as Record<string, unknown>[]) : [];
  const attemptPayload = pick(data, "attemptStartResponse", "attempt_start_response");
  return {
    runId: String(pick(data, "runId", "run_id") ?? ""),
    status: (String(pick(data, "status") ?? "failed") as QuizGenerationRun["status"]),
    currentStep: (pick(data, "currentStep", "current_step") as string | null) ?? null,
    message: (pick(data, "message") as string | null) ?? null,
    error: (pick(data, "error") as string | null) ?? null,
    attemptStartResponse: attemptPayload ? normalizeAttemptSession(attemptPayload) : null,
    events: rawEvents.map((event) => ({
      event: String(pick(event, "event") ?? ""),
      message: String(pick(event, "message") ?? ""),
      step: (pick(event, "step") as string | null) ?? null,
      timestamp: String(pick(event, "timestamp") ?? ""),
      data: (pick(event, "data") as Record<string, unknown> | null) ?? {},
    })),
  };
}

export async function createAutoGeneratedQuizAttemptRun(
  courseUuid: string,
  moduleUuid: string,
  options?: { additionalInstructions?: string | null }
): Promise<{ runId: string; status: QuizGenerationRun["status"] }> {
  const response = await fetch(
    `${AI_API_BASE_URL}/courses/${courseUuid}/modules/${moduleUuid}/quiz/generated-attempt-sessions/auto/runs`,
    {
      method: "POST",
      headers: buildAuthHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        additionalInstructions: options?.additionalInstructions?.trim() || null,
      }),
    }
  );
  const text = await response.text();
  const payload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, payload);
  if (!response.ok) throw new Error(extractErrorMessage(payload, "启动测验生成失败。"));
  const data = (payload ?? {}) as Record<string, unknown>;
  return {
    runId: String(pick(data, "runId", "run_id") ?? ""),
    status: (String(pick(data, "status") ?? "queued") as QuizGenerationRun["status"]),
  };
}

export async function getAutoGeneratedQuizAttemptRun(
  courseUuid: string,
  moduleUuid: string,
  runId: string
): Promise<QuizGenerationRun> {
  const response = await fetch(
    `${AI_API_BASE_URL}/courses/${courseUuid}/modules/${moduleUuid}/quiz/generated-attempt-sessions/auto/runs/${runId}`,
    { method: "GET", headers: buildAuthHeaders({ "Content-Type": "application/json" }) }
  );
  const text = await response.text();
  const payload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, payload);
  if (!response.ok) throw new Error(extractErrorMessage(payload, "加载测验生成状态失败。"));
  return normalizeQuizGenerationRun(payload);
}

export async function getActiveAutoGeneratedQuizAttemptRun(
  courseUuid: string,
  moduleUuid: string
): Promise<QuizGenerationRun | null> {
  const response = await fetch(
    `${AI_API_BASE_URL}/courses/${courseUuid}/modules/${moduleUuid}/quiz/generated-attempt-sessions/auto/runs/active`,
    { method: "GET", headers: buildAuthHeaders({ "Content-Type": "application/json" }) }
  );
  if (response.status === 404 || response.status === 204) return null;
  const text = await response.text();
  const payload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, payload);
  if (!response.ok) throw new Error(extractErrorMessage(payload, "加载活动测验生成任务失败。"));
  return normalizeQuizGenerationRun(payload);
}

export async function submitQuizAttempt(
  courseUuid: string,
  moduleUuid: string,
  token: string,
  answers: { questionUuid: string; selectedOptionUuid: string | null }[],
  options?: { timedOut?: boolean }
): Promise<QuizAttemptResult> {
  const response = await fetch(
    `${COURSE_API_BASE_URL}/courses/${courseUuid}/modules/${moduleUuid}/quiz/attempt-sessions/${token}/submit`,
    {
      method: "POST",
      headers: buildAuthHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ answers, timedOut: Boolean(options?.timedOut) }),
    }
  );
  const text = await response.text();
  const payload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, payload);
  if (!response.ok) throw new Error(extractErrorMessage(payload, "提交测验失败。"));
  return normalizeAttemptResult(payload);
}

export async function getQuizAttemptHistory(courseUuid: string, moduleUuid: string): Promise<QuizAttemptHistory | null> {
  const response = await fetch(
    `${COURSE_API_BASE_URL}/courses/${courseUuid}/modules/${moduleUuid}/quiz/attempts`,
    { method: "GET", headers: buildAuthHeaders({ "Content-Type": "application/json" }) }
  );
  if (response.status === 404) return null;
  const text = await response.text();
  const payload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, payload);
  if (!response.ok) throw new Error(extractErrorMessage(payload, "加载测验历史失败。"));
  const d = progressRecord(payload);
  const rawAttempts = Array.isArray(d.attempts) ? (d.attempts as Record<string, unknown>[]) : [];
  return {
    quizUuid: String(pick(d, "quizUuid", "quiz_uuid") ?? ""),
    moduleUuid: String(pick(d, "moduleUuid", "module_uuid") ?? ""),
    title: String(pick(d, "title") ?? "Quiz"),
    timeLimitSeconds: toNullableNonNegativeNumber(pick(d, "timeLimitSeconds", "time_limit_seconds")),
    passedOnce: toBooleanValue(pick(d, "passedOnce", "passed_once")),
    attempts: rawAttempts.map((a) => ({
      quizAttemptUuid: String(pick(a, "quizAttemptUuid", "quiz_attempt_uuid") ?? ""),
      attemptNumber: toNonNegativeNumber(pick(a, "attemptNumber", "attempt_number")),
      questionCount: toNonNegativeNumber(pick(a, "questionCount", "question_count")),
      correctCount: toNonNegativeNumber(pick(a, "correctCount", "correct_count")),
      scorePercent: toScorePercentString(pick(a, "scorePercent", "score_percent")),
      isPassed: toBooleanValue(pick(a, "isPassed", "is_passed")),
      isTimedOut: toBooleanValue(pick(a, "isTimedOut", "is_timed_out")),
      startedAt: String(pick(a, "startedAt", "started_at") ?? ""),
      submittedAt: String(pick(a, "submittedAt", "submitted_at") ?? ""),
      durationSeconds: toNullableNonNegativeNumber(pick(a, "durationSeconds", "duration_seconds")),
    })),
  };
}

export async function getQuizAttemptDetail(
  courseUuid: string,
  moduleUuid: string,
  quizAttemptUuid: string
): Promise<QuizAttemptResult> {
  const response = await fetch(
    `${COURSE_API_BASE_URL}/courses/${courseUuid}/modules/${moduleUuid}/quiz/attempts/${quizAttemptUuid}`,
    { method: "GET", headers: buildAuthHeaders({ "Content-Type": "application/json" }) }
  );
  const text = await response.text();
  const payload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, payload);
  if (!response.ok) throw new Error(extractErrorMessage(payload, "加载测验尝试详情失败。"));
  return normalizeAttemptResult(payload);
}

export async function generateCourseInviteLink(courseUuid: string): Promise<CourseInviteLinkResponse> {
  const response = await fetch(
    `${COURSE_API_BASE_URL}/courses/${courseUuid}/invite-links`,
    { method: "POST", headers: buildAuthHeaders({ "Content-Type": "application/json" }) }
  );
  const text = await response.text();
  const payload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, payload);
  if (!response.ok) throw new Error(extractErrorMessage(payload, "生成邀请链接失败。"));
  const inviteLink = normalizeCourseInviteLink(payload);
  if (!isUsableCourseInviteLink(inviteLink)) {
    throw new Error("Invite link response was invalid. Please try again.");
  }
  return inviteLink;
}

export async function listCourseInviteLinks(courseUuid: string): Promise<CourseInviteLinkResponse[]> {
  const response = await fetch(
    `${COURSE_API_BASE_URL}/courses/${courseUuid}/invite-links`,
    { method: "GET", headers: buildAuthHeaders({ "Content-Type": "application/json" }) }
  );
  const text = await response.text();
  const payload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, payload);
  if (!response.ok) throw new Error(extractErrorMessage(payload, "获取邀请链接失败。"));
  return normalizeCourseInviteLinkList(payload);
}

export async function deactivateCourseInviteLink(inviteUuid: string): Promise<{ detail: string }> {
  const response = await fetch(
    `${COURSE_API_BASE_URL}/courses/invite-links/${inviteUuid}`,
    { method: "DELETE", headers: buildAuthHeaders({ "Content-Type": "application/json" }) }
  );
  const text = await response.text();
  const payload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, payload);
  if (!response.ok) throw new Error(extractErrorMessage(payload, "停用邀请链接失败。"));
  return { detail: normalizeString(progressRecord(payload).detail, "Invite link deactivated") };
}

export async function validateCourseInviteToken(token: string): Promise<CourseInviteValidateResponse> {
  const response = await fetch(
    `${COURSE_API_BASE_URL}/invite/course/validate?${new URLSearchParams({ token })}`,
    { method: "GET" }
  );
  const text = await response.text();
  const payload = parseJsonText(text);
  if (!response.ok) throw new Error(extractErrorMessage(payload, "Invalid or expired invite link."));
  return normalizeCourseInviteValidation(payload);
}

export async function enrolViaCourseInvite(token: string): Promise<CourseInviteEnrolResponse> {
  const response = await fetch(
    `${COURSE_API_BASE_URL}/invite/course/enrol?${new URLSearchParams({ token })}`,
    { method: "POST", headers: buildAuthHeaders({ "Content-Type": "application/json" }) }
  );
  const text = await response.text();
  const payload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, payload);
  if (!response.ok) throw new Error(extractErrorMessage(payload, "通过邀请链接加入课程失败。"));
  return normalizeCourseInviteEnrolment(payload);
}

export async function updateModuleProgress(
  courseUuid: string,
  moduleUuid: string,
  progressStatus: "not_started" | "in_progress" | "completed"
): Promise<void> {
  const response = await fetch(
    `${COURSE_API_BASE_URL}/courses/${courseUuid}/modules/${moduleUuid}/progress`,
    {
      method: "POST",
      headers: buildAuthHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ progressStatus }),
    }
  );
  const text = await response.text();
  const payload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, payload);
  if (!response.ok) throw new Error(extractErrorMessage(payload, "更新模块进度失败。"));
}

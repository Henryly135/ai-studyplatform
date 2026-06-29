import type {
  CourseEnrollmentLearnerRecord,
  CourseMaterial,
  CourseModule,
  CourseRecord,
  EducatorAnalytics,
  EducatorQuizAnalytics,
  QuizGenerationProgressEvent,
  QuizGenerationRun,
  QuizRecord,
  EducatorQuizDraftPayload,
  EducatorQuizDraftPreview,
  QuizQuestionDraft,
  QuizQuestionPage,
  QuizAttemptSession,
  QuizAttemptResult,
  QuizAttemptHistory,
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
  const total = typeof data.total === "number" ? data.total : items.length;
  const pageSize = typeof data.pageSize === "number" ? data.pageSize : defaultResult.pageSize;
  const totalPages =
    typeof data.totalPages === "number"
      ? data.totalPages
      : Math.max(1, Math.ceil(total / Math.max(1, pageSize)));
  const page = typeof data.page === "number" ? data.page : 1;

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
    throw new Error("Failed to fetch courses.");
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
    throw new Error("Failed to search courses.");
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
    throw new Error(extractErrorMessage(payload, "Failed to enroll in course."));
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
    throw new Error(extractErrorMessage(payload, "Failed to cancel enrollment."));
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
    throw new Error(extractErrorMessage(payload, "Failed to load enrolled courses."));
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
    throw new Error(extractErrorMessage(payload, "Failed to load enrolled courses."));
  }

  return extractCourseArray(payload).map((course, index) => normalizeCourse(course, index));
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
    throw new Error(extractErrorMessage(payload, "Failed to load educator analytics."));
  }

  return payload as EducatorAnalytics;
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
    throw new Error(extractErrorMessage(payload, "Failed to load educator quiz analytics."));
  }

  return payload as EducatorQuizAnalytics;
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
    throw new Error(extractErrorMessage(payload, "Failed to load course enrollments."));
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
    throw new Error("Failed to fetch managed courses.");
  }

  return normalizePaginatedCoursePayload(payload);
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
    throw new Error("Failed to reorder modules.");
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
    throw new Error(extractErrorMessage(parsedPayload, "Failed to update course."));
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
    throw new Error(extractErrorMessage(parsedPayload, "Failed to delete course."));
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
    throw new Error(extractErrorMessage(parsedPayload, "Failed to update course cover."));
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
    throw new Error(extractErrorMessage(parsedPayload, "Failed to create course."));
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
    throw new Error(extractErrorMessage(parsedPayload, "Failed to create module."));
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
    throw new Error(extractErrorMessage(parsedPayload, "Failed to update module."));
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
    throw new Error(extractErrorMessage(parsedPayload, "Failed to set module prerequisite."));
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
    throw new Error(extractErrorMessage(parsedPayload, "Failed to remove module prerequisite."));
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
    throw new Error(extractErrorMessage(parsedPayload, "Failed to delete module."));
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
    throw new Error(extractErrorMessage(parsedPayload, "Failed to publish module."));
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
    throw new Error(extractErrorMessage(parsedPayload, "Failed to publish course."));
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
    throw new Error(extractErrorMessage(parsedPayload, "Failed to upload module material."));
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
    throw new Error(extractErrorMessage(parsedPayload, "Failed to initialize multipart upload."));
  }

  return parsedPayload as MultipartModuleMaterialUploadInitResponse;
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
    throw new Error(extractErrorMessage(parsedPayload, "Failed to get multipart upload URL."));
  }

  return parsedPayload as MultipartModuleMaterialUploadPartUrlResponse;
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
    throw new Error(extractErrorMessage(parsedPayload, "Failed to complete multipart upload."));
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
    throw new Error(extractErrorMessage(parsedPayload, "Failed to abort multipart upload."));
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
    throw new Error(extractErrorMessage(parsedPayload, "Failed to delete module material."));
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
    sourceGrounding: String(q.sourceGrounding ?? q.source_grounding ?? ""),
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

function normalizeEducatorQuizDraftPreview(payload: unknown): EducatorQuizDraftPreview {
  const data = (payload ?? {}) as Record<string, unknown>;
  const rawCandidateSet = (data.candidateSet ?? data.candidate_set ?? {}) as Record<string, unknown>;
  const rawQuestions = Array.isArray(rawCandidateSet.questions)
    ? (rawCandidateSet.questions as Record<string, unknown>[])
    : [];
  const questions = rawQuestions.map((q, index) => normalizeQuizQuestion(q, index));
  const candidateQuestionCount =
    typeof rawCandidateSet.questionCount === "number"
      ? rawCandidateSet.questionCount
      : typeof rawCandidateSet.question_count === "number"
        ? rawCandidateSet.question_count
        : questions.length;

  return {
    title: String(data.title ?? ""),
    questionCount:
      typeof data.questionCount === "number"
        ? data.questionCount
        : typeof data.question_count === "number"
          ? data.question_count
          : candidateQuestionCount,
    difficulty: (data.difficulty as EducatorQuizDraftPreview["difficulty"]) ?? "mixed",
    questionTypes: Array.isArray(data.questionTypes)
      ? (data.questionTypes as EducatorQuizDraftPreview["questionTypes"])
      : Array.isArray(data.question_types)
        ? (data.question_types as EducatorQuizDraftPreview["questionTypes"])
        : ["multiple_choice"],
    replaceExistingQuestions:
      typeof data.replaceExistingQuestions === "boolean"
        ? data.replaceExistingQuestions
        : typeof data.replace_existing_questions === "boolean"
          ? data.replace_existing_questions
          : true,
    timeLimitSeconds:
      typeof data.timeLimitSeconds === "number"
        ? data.timeLimitSeconds
        : typeof data.time_limit_seconds === "number"
          ? data.time_limit_seconds
          : null,
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
    retrievalUsed:
      typeof data.retrievalUsed === "boolean"
        ? data.retrievalUsed
        : typeof data.retrieval_used === "boolean"
          ? data.retrieval_used
          : false,
    sourceChunkCount:
      typeof data.sourceChunkCount === "number"
        ? data.sourceChunkCount
        : typeof data.source_chunk_count === "number"
          ? data.source_chunk_count
          : 0,
    candidateSet: {
      questionCount: candidateQuestionCount,
      questions,
    },
  };
}

function normalizeQuizQuestionPage(payload: unknown): QuizQuestionPage {
  const data = (payload ?? {}) as Record<string, unknown>;
  const rawItems = Array.isArray(data.items) ? (data.items as Record<string, unknown>[]) : [];
  const pageSize = typeof data.pageSize === "number" ? data.pageSize : typeof data.page_size === "number" ? data.page_size : 20;
  const total = typeof data.total === "number" ? data.total : rawItems.length;
  return {
    items: rawItems.map((item, index) => normalizeQuizQuestion(item, index)),
    page: typeof data.page === "number" ? data.page : 1,
    pageSize,
    total,
    totalPages:
      typeof data.totalPages === "number"
        ? data.totalPages
        : typeof data.total_pages === "number"
          ? data.total_pages
          : Math.max(1, Math.ceil(total / Math.max(1, pageSize))),
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
    throw new Error(extractErrorMessage(payload, "Failed to load quiz."));
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
    throw new Error(extractErrorMessage(payload, "Failed to load quiz questions."));
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
          sourceGrounding: q.sourceGrounding.trim() || null,
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
    throw new Error(extractErrorMessage(parsedPayload, "Failed to save quiz."));
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
    throw new Error(extractErrorMessage(parsedPayload, "Failed to update quiz status."));
  }

  return normalizeQuiz(parsedPayload);
}

export async function generateEducatorQuizDraftPreview(
  courseUuid: string,
  moduleUuid: string,
  payload: EducatorQuizDraftPayload
): Promise<EducatorQuizDraftPreview> {
  const response = await fetch(
    `${COURSE_API_BASE_URL}/courses/${courseUuid}/modules/${moduleUuid}/quiz/management/ai-draft`,
    {
      method: "POST",
      headers: buildAuthHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        title: payload.title?.trim() || null,
        questionCount: payload.questionCount,
        difficulty: payload.difficulty,
        questionTypes: payload.questionTypes,
        learningObjectives: payload.learningObjectives.map((objective) => objective.trim()).filter(Boolean),
        materialScope: payload.materialScope?.trim() || null,
        additionalInstructions: payload.additionalInstructions?.trim() || null,
        replaceExistingQuestions: payload.replaceExistingQuestions,
        timeLimitSeconds: payload.timeLimitSeconds || null,
        shuffleQuestions: payload.shuffleQuestions,
        shuffleOptions: payload.shuffleOptions,
      }),
    }
  );

  const text = await response.text();
  const parsedPayload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, parsedPayload);

  if (!response.ok) {
    throw new Error(extractErrorMessage(parsedPayload, "Failed to generate quiz draft."));
  }

  return normalizeEducatorQuizDraftPreview(parsedPayload);
}

export async function acceptEducatorQuizDraft(
  courseUuid: string,
  moduleUuid: string,
  preview: EducatorQuizDraftPreview,
  options?: { includeQuestions?: boolean }
): Promise<QuizRecord> {
  const params = new URLSearchParams();
  if (options?.includeQuestions === false) {
    params.set("include_questions", "false");
  }
  const queryString = params.toString();
  const response = await fetch(
    `${COURSE_API_BASE_URL}/courses/${courseUuid}/modules/${moduleUuid}/quiz/management/ai-draft/accept${queryString ? `?${queryString}` : ""}`,
    {
      method: "POST",
      headers: buildAuthHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        title: preview.title.trim() || null,
        replaceExistingQuestions: preview.replaceExistingQuestions,
        timeLimitSeconds: preview.timeLimitSeconds || null,
        shuffleQuestions: preview.shuffleQuestions,
        shuffleOptions: preview.shuffleOptions,
        candidateSet: {
          questionCount: preview.candidateSet.questionCount,
          questions: preview.candidateSet.questions.map((q, questionIndex) => ({
            questionText: q.questionText.trim(),
            explanationText: q.explanationText.trim() || null,
            sourceGrounding: q.sourceGrounding.trim(),
            sortOrder: questionIndex + 1,
            isActive: true,
            options: q.options.map((o, optionIndex) => ({
              optionLabel: o.optionLabel.trim() || null,
              optionText: o.optionText.trim(),
              sortOrder: optionIndex + 1,
              isCorrect: o.isCorrect,
            })),
          })),
        },
      }),
    }
  );

  const text = await response.text();
  const parsedPayload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, parsedPayload);

  if (!response.ok) {
    throw new Error(extractErrorMessage(parsedPayload, "Failed to accept quiz draft."));
  }

  return normalizeQuiz(parsedPayload);
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
  const d = (payload ?? {}) as Record<string, unknown>;
  const rawQs = Array.isArray(d.questions) ? (d.questions as Record<string, unknown>[]) : [];
  return {
    quizUuid: String(pick(d, "quizUuid", "quiz_uuid") ?? ""),
    moduleUuid: String(pick(d, "moduleUuid", "module_uuid") ?? ""),
    attemptSessionToken: String(pick(d, "attemptSessionToken", "attempt_session_token") ?? ""),
    attemptNumber: Number(pick(d, "attemptNumber", "attempt_number") ?? 1),
    questionCount: Number(pick(d, "questionCount", "question_count") ?? rawQs.length),
    timeLimitSeconds: (pick(d, "timeLimitSeconds", "time_limit_seconds") as number | null) ?? null,
    startedAt: String(pick(d, "startedAt", "started_at") ?? ""),
    expiresAt: (pick(d, "expiresAt", "expires_at") as string | null) ?? null,
    questions: rawQs.map((q) => {
      const rawOpts = Array.isArray(q.options) ? (q.options as Record<string, unknown>[]) : [];
      return {
        questionId: Number(pick(q, "questionId", "question_id") ?? 0),
        questionUuid: String(pick(q, "questionUuid", "question_uuid") ?? ""),
        questionText: String(pick(q, "questionText", "question_text") ?? ""),
        explanationText: (pick(q, "explanationText", "explanation_text") as string | null) ?? null,
        questionOrder: Number(pick(q, "questionOrder", "question_order") ?? 1),
        options: rawOpts.map((o) => ({
          optionId: Number(pick(o, "optionId", "option_id") ?? 0),
          optionUuid: String(pick(o, "optionUuid", "option_uuid") ?? ""),
          optionLabel: (pick(o, "optionLabel", "option_label") as string | null) ?? null,
          optionText: String(pick(o, "optionText", "option_text") ?? ""),
          sortOrder: Number(pick(o, "sortOrder", "sort_order") ?? 0),
        })),
      };
    }),
  };
}

function normalizeAttemptResult(payload: unknown): QuizAttemptResult {
  const d = (payload ?? {}) as Record<string, unknown>;
  const rawAnswers = Array.isArray(d.answers) ? (d.answers as Record<string, unknown>[]) : [];
  return {
    quizAttemptUuid: String(pick(d, "quizAttemptUuid", "quiz_attempt_uuid") ?? ""),
    quizUuid: String(pick(d, "quizUuid", "quiz_uuid") ?? ""),
    moduleUuid: String(pick(d, "moduleUuid", "module_uuid") ?? ""),
    attemptNumber: Number(pick(d, "attemptNumber", "attempt_number") ?? 1),
    questionCount: Number(pick(d, "questionCount", "question_count") ?? 0),
    correctCount: Number(pick(d, "correctCount", "correct_count") ?? 0),
    scorePercent: String(pick(d, "scorePercent", "score_percent") ?? "0"),
    isPassed: Boolean(pick(d, "isPassed", "is_passed") ?? false),
    isTimedOut: Boolean(pick(d, "isTimedOut", "is_timed_out") ?? false),
    moduleCompleted: Boolean(pick(d, "moduleCompleted", "module_completed") ?? false),
    timeLimitSeconds: (pick(d, "timeLimitSeconds", "time_limit_seconds") as number | null) ?? null,
    startedAt: String(pick(d, "startedAt", "started_at") ?? ""),
    submittedAt: String(pick(d, "submittedAt", "submitted_at") ?? ""),
    durationSeconds: (pick(d, "durationSeconds", "duration_seconds") as number | null) ?? null,
    answers: rawAnswers.map((a) => ({
      questionUuid: String(pick(a, "questionUuid", "question_uuid") ?? ""),
      questionOrder: Number(pick(a, "questionOrder", "question_order") ?? 0),
      questionText: String(pick(a, "questionText", "question_text") ?? ""),
      explanationText: (pick(a, "explanationText", "explanation_text") as string | null) ?? null,
      selectedOptionUuid: (pick(a, "selectedOptionUuid", "selected_option_uuid") as string | null) ?? null,
      selectedOptionText: (pick(a, "selectedOptionText", "selected_option_text") as string | null) ?? null,
      correctOptionUuid: String(pick(a, "correctOptionUuid", "correct_option_uuid") ?? ""),
      correctOptionText: String(pick(a, "correctOptionText", "correct_option_text") ?? ""),
      isCorrect: Boolean(pick(a, "isCorrect", "is_correct") ?? false),
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
  if (!text) return null;
  const payload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, payload);
  if (!response.ok) return null;
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
  if (!response.ok) throw new Error(extractErrorMessage(payload, "Failed to start quiz."));
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
    throw new Error(extractErrorMessage(payload, "Failed to generate quiz."));
  }

  if (!response.body) {
    throw new Error("Quiz generation stream is unavailable.");
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
      streamErrorMessage = parsed.message || "Quiz generation failed.";
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
    throw new Error("Quiz generation finished without starting a quiz session.");
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
  if (!response.ok) throw new Error(extractErrorMessage(payload, "Failed to start quiz generation."));
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
  if (!response.ok) throw new Error(extractErrorMessage(payload, "Failed to load quiz generation status."));
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
  if (!response.ok) throw new Error(extractErrorMessage(payload, "Failed to load active quiz generation."));
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
  if (!response.ok) throw new Error(extractErrorMessage(payload, "Failed to submit quiz."));
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
  if (!response.ok) throw new Error(extractErrorMessage(payload, "Failed to load quiz history."));
  const d = (payload ?? {}) as Record<string, unknown>;
  const rawAttempts = Array.isArray(d.attempts) ? (d.attempts as Record<string, unknown>[]) : [];
  return {
    quizUuid: String(pick(d, "quizUuid", "quiz_uuid") ?? ""),
    moduleUuid: String(pick(d, "moduleUuid", "module_uuid") ?? ""),
    title: String(pick(d, "title") ?? "Quiz"),
    timeLimitSeconds: (pick(d, "timeLimitSeconds", "time_limit_seconds") as number | null) ?? null,
    passedOnce: Boolean(pick(d, "passedOnce", "passed_once") ?? false),
    attempts: rawAttempts.map((a) => ({
      quizAttemptUuid: String(pick(a, "quizAttemptUuid", "quiz_attempt_uuid") ?? ""),
      attemptNumber: Number(pick(a, "attemptNumber", "attempt_number") ?? 0),
      questionCount: Number(pick(a, "questionCount", "question_count") ?? 0),
      correctCount: Number(pick(a, "correctCount", "correct_count") ?? 0),
      scorePercent: String(pick(a, "scorePercent", "score_percent") ?? "0"),
      isPassed: Boolean(pick(a, "isPassed", "is_passed") ?? false),
      isTimedOut: Boolean(pick(a, "isTimedOut", "is_timed_out") ?? false),
      startedAt: String(pick(a, "startedAt", "started_at") ?? ""),
      submittedAt: String(pick(a, "submittedAt", "submitted_at") ?? ""),
      durationSeconds: (pick(a, "durationSeconds", "duration_seconds") as number | null) ?? null,
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
  if (!response.ok) throw new Error(extractErrorMessage(payload, "Failed to load quiz attempt detail."));
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
  if (!response.ok) throw new Error(extractErrorMessage(payload, "Failed to generate invite link."));
  return payload as CourseInviteLinkResponse;
}

export async function listCourseInviteLinks(courseUuid: string): Promise<CourseInviteLinkResponse[]> {
  const response = await fetch(
    `${COURSE_API_BASE_URL}/courses/${courseUuid}/invite-links`,
    { method: "GET", headers: buildAuthHeaders({ "Content-Type": "application/json" }) }
  );
  const text = await response.text();
  const payload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, payload);
  if (!response.ok) throw new Error(extractErrorMessage(payload, "Failed to fetch invite links."));
  return (payload as CourseInviteLinkResponse[]) ?? [];
}

export async function deactivateCourseInviteLink(inviteUuid: string): Promise<{ detail: string }> {
  const response = await fetch(
    `${COURSE_API_BASE_URL}/courses/invite-links/${inviteUuid}`,
    { method: "DELETE", headers: buildAuthHeaders({ "Content-Type": "application/json" }) }
  );
  const text = await response.text();
  const payload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, payload);
  if (!response.ok) throw new Error(extractErrorMessage(payload, "Failed to deactivate invite link."));
  return payload as { detail: string };
}

export async function validateCourseInviteToken(token: string): Promise<CourseInviteValidateResponse> {
  const response = await fetch(
    `${COURSE_API_BASE_URL}/invite/course/validate?${new URLSearchParams({ token })}`,
    { method: "GET" }
  );
  const text = await response.text();
  const payload = parseJsonText(text);
  if (!response.ok) throw new Error(extractErrorMessage(payload, "Invalid or expired invite link."));
  return payload as CourseInviteValidateResponse;
}

export async function enrolViaCourseInvite(token: string): Promise<CourseInviteEnrolResponse> {
  const response = await fetch(
    `${COURSE_API_BASE_URL}/invite/course/enrol?${new URLSearchParams({ token })}`,
    { method: "POST", headers: buildAuthHeaders({ "Content-Type": "application/json" }) }
  );
  const text = await response.text();
  const payload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, payload);
  if (!response.ok) throw new Error(extractErrorMessage(payload, "Failed to enrol via invite link."));
  return payload as CourseInviteEnrolResponse;
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
  if (!response.ok) throw new Error(extractErrorMessage(payload, "Failed to update module progress."));
}

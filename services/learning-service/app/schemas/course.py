from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CoursePublishRequest(BaseModel):
    moduleUuids: list[str] = Field(..., min_length=1)


class CourseUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    subtitle: str | None = Field(default=None, max_length=255)
    description: str | None = None
    coverImageUrl: str | None = Field(default=None, max_length=500)
    difficultyLevel: str | None = None
    estimatedMinutes: int | None = Field(default=None, ge=1)
    category: str | None = Field(default=None, max_length=100)
    languageCode: str | None = Field(default=None, max_length=20)
    isPublic: bool | None = None
    learningPathTitle: str | None = Field(default=None, max_length=200)
    learningPathDescription: str | None = None


class CourseCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    subtitle: str | None = Field(default=None, max_length=255)
    description: str | None = None
    difficultyLevel: str | None = None
    estimatedMinutes: int | None = Field(default=None, ge=1)
    category: str | None = Field(default=None, max_length=100)
    languageCode: str | None = Field(default=None, max_length=20)
    isPublic: bool = False
    learningPathTitle: str | None = Field(default=None, max_length=200)
    learningPathDescription: str | None = None


class MaterialResponse(BaseModel):
    materialId: int
    materialUuid: str
    moduleId: int
    title: str
    materialType: str
    resourceUrl: str
    sortOrder: int
    metadataJson: dict[str, Any] | None


class ModuleResponse(BaseModel):
    moduleId: int
    moduleUuid: str
    title: str
    description: str | None
    content: str | None
    sortOrder: int
    estimatedMinutes: int | None
    status: str
    classId: str | None
    prerequisiteModuleUuid: str | None
    prerequisiteModuleTitle: str | None
    isLocked: bool
    lockMessage: str | None
    slug: str
    materials: list[MaterialResponse]
    hasPublishedQuiz: bool = False
    quizTitle: str | None = None
    quizTimeLimitSeconds: int | None = None
    progressStatus: str | None = None
    isCompleted: bool = False
    completedAt: datetime | None = None


class CourseSummaryResponse(BaseModel):
    courseId: int
    courseUuid: str
    educatorId: int
    educatorUuid: str
    educatorName: str | None
    educatorEmail: str | None = None
    educatorUserName: str | None = None
    title: str
    subtitle: str | None
    description: str | None
    coverImageUrl: str | None
    status: str
    difficultyLevel: str | None
    estimatedMinutes: int | None
    category: str | None
    languageCode: str | None
    isPublic: bool
    publishedAt: datetime | None
    termLabel: str | None
    courseCode: str | None
    schoolName: str | None
    moduleCount: int


class PaginatedCourseSummaryResponse(BaseModel):
    items: list[CourseSummaryResponse]
    page: int
    pageSize: int
    total: int
    totalPages: int


class CourseDetailResponse(CourseSummaryResponse):
    learningPathId: int | None
    learningPathTitle: str | None
    learningPathDescription: str | None
    modules: list[ModuleResponse]


class CourseEnrollmentResponse(BaseModel):
    enrollmentId: int
    courseId: int
    courseUuid: str
    learnerId: int
    learnerUuid: str
    enrollmentStatus: str
    progressPercent: str
    completedModuleCount: int
    totalModuleCount: int
    enrolledAt: datetime
    lastAccessedAt: datetime | None
    completedAt: datetime | None


class CourseEnrollmentLearnerResponse(CourseEnrollmentResponse):
    learnerName: str | None = None
    learnerEmail: str | None = None
    learnerIdentity: str | None = None
    learnerAccountStatus: str | None = None
    learnerEmailVerified: bool | None = None


class CourseEnrollmentStatusUpdateRequest(BaseModel):
    enrollmentStatus: str = Field(..., min_length=1, max_length=20)
    reason: str | None = Field(default=None, max_length=1000)


class AdminCourseEnrollmentManageRequest(BaseModel):
    enrollmentStatus: str = Field(..., min_length=1, max_length=20)
    reason: str | None = Field(default=None, max_length=1000)


class EducatorCourseAnalyticsItem(BaseModel):
    courseUuid: str
    courseTitle: str
    status: str
    totalEnrollments: int
    activeEnrollments: int
    completedEnrollments: int
    avgProgressPercent: float | None


class EducatorAnalyticsResponse(BaseModel):
    courses: list[EducatorCourseAnalyticsItem]
    totalCourses: int
    totalEnrollments: int
    totalActiveEnrollments: int
    totalCompletedEnrollments: int


class QuizModuleStatsItem(BaseModel):
    courseUuid: str
    courseTitle: str
    moduleUuid: str
    moduleTitle: str
    quizTitle: str
    totalAttempts: int
    uniqueLearners: int
    avgScorePercent: float | None
    passRate: float | None
    avgDurationSeconds: float | None


class EducatorQuizAnalyticsResponse(BaseModel):
    items: list[QuizModuleStatsItem]

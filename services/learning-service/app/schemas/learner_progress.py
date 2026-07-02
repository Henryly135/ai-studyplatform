from datetime import datetime

from pydantic import BaseModel


class LearnerProgressQuizSummary(BaseModel):
    totalQuizzes: int
    attemptedQuizzes: int
    passedQuizzes: int
    totalAttempts: int
    averageBestScorePercent: float | None = None
    latestScorePercent: float | None = None
    latestSubmittedAt: datetime | None = None


class LearnerProgressNextModule(BaseModel):
    moduleId: int
    moduleUuid: str
    title: str


class LearnerProgressCourseItem(BaseModel):
    courseId: int
    courseUuid: str
    title: str
    courseCode: str | None = None
    category: str | None = None
    enrollmentStatus: str
    progressPercent: float
    completedModuleCount: int
    totalModuleCount: int
    lastAccessedAt: datetime | None = None
    completedAt: datetime | None = None
    nextModule: LearnerProgressNextModule | None = None
    quiz: LearnerProgressQuizSummary


class LearnerProgressActivityItem(BaseModel):
    activityType: str
    occurredAt: datetime
    courseId: int
    courseUuid: str
    courseTitle: str
    moduleId: int | None = None
    moduleUuid: str | None = None
    moduleTitle: str | None = None
    title: str
    detail: str | None = None
    scorePercent: float | None = None
    isPassed: bool | None = None


class LearnerProgressOverviewResponse(BaseModel):
    totalCourses: int
    totalModules: int
    completedModules: int
    averageProgressPercent: float
    quiz: LearnerProgressQuizSummary
    courses: list[LearnerProgressCourseItem]
    recentActivity: list[LearnerProgressActivityItem]

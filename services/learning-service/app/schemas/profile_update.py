from datetime import datetime

from pydantic import BaseModel, Field


class SignalTimeWindowRead(BaseModel):
    startAt: datetime
    endAt: datetime


class QuizSignalQuestionEvidenceRead(BaseModel):
    questionOrder: int = Field(..., ge=1)
    questionText: str
    explanationText: str | None = None
    selectedOptionText: str | None = None
    correctOptionText: str
    isCorrect: bool


class QuizSignalSummaryDetailRead(BaseModel):
    quizAttemptId: int
    attemptNumber: int
    scorePercent: float = Field(..., ge=0, le=100)
    questionCount: int = Field(..., ge=0)
    correctCount: int = Field(..., ge=0)
    incorrectCount: int = Field(..., ge=0)
    isPassed: bool
    isTimedOut: bool
    durationSeconds: int | None = Field(default=None, ge=0)
    avgTimePerQuestionSec: float | None = Field(default=None, ge=0)
    changeSignificance: str
    confidenceShiftHint: str
    supportNeedShiftHint: str
    repeatedErrorPatterns: list[str]
    recommendedFocusCandidates: list[str]
    recentTrendSummary: str | None = None
    questionEvidence: list[QuizSignalQuestionEvidenceRead]


class QuizSignalSummaryRequest(BaseModel):
    courseId: int = Field(..., ge=1)
    moduleId: int = Field(..., ge=1)
    learnerId: int = Field(..., ge=1)
    maxAttempts: int = Field(default=2, ge=1, le=5)


class QuizSignalSummaryResponse(BaseModel):
    source: str = "quiz"
    available: bool = True
    unavailableReason: str | None = None
    signalStrength: str
    summaryVersion: str = "v1"
    evidenceCount: int = Field(..., ge=0)
    timeWindow: SignalTimeWindowRead | None = None
    summary: QuizSignalSummaryDetailRead | None = None

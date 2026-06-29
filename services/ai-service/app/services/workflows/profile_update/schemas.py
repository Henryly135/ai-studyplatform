from datetime import datetime
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.profiles import ModuleProfileRead


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


class QuizSignalSummaryRead(BaseModel):
    source: str = "quiz"
    available: bool = True
    unavailableReason: str | None = None
    signalStrength: str
    summaryVersion: str = "v1"
    evidenceCount: int = Field(..., ge=0)
    timeWindow: SignalTimeWindowRead | None = None
    summary: QuizSignalSummaryDetailRead | None = None


class ChatSignalSummaryDetailRead(BaseModel):
    sessionCount: int = Field(..., ge=0)
    messageCount: int = Field(..., ge=0)
    userMessageCount: int = Field(..., ge=0)
    thresholdRule: str
    thresholdReached: bool
    latestSessionSummaries: list[str]
    dominantTopics: list[str]
    repeatedConfusions: list[str]
    preferredResponseStyleSignals: list[str]
    frustrationSignals: list[str]
    engagementPatternHint: str
    responsePreferenceShiftHint: str
    supportNeedShiftHint: str
    changeSignificance: str
    reasonForTrigger: str


class ChatSignalSummaryRead(BaseModel):
    source: str = "chat"
    available: bool = True
    unavailableReason: str | None = None
    signalStrength: str
    summaryVersion: str = "v1"
    evidenceCount: int = Field(..., ge=0)
    timeWindow: SignalTimeWindowRead | None = None
    summary: ChatSignalSummaryDetailRead | None = None


class ModuleUpdateContextScopeRead(BaseModel):
    learnerId: int = Field(..., ge=1)
    courseUuid: str
    moduleUuid: str


class ModuleUpdateTriggerRead(BaseModel):
    source: Literal["quiz", "chat", "progress", "manual", "system"]
    reason: str


class BaseProfileContextRead(BaseModel):
    profileExists: bool
    baseProfileSource: Literal["active", "default"]
    profileType: str = "module_profile"
    version: int | None = None
    objectKey: str | None = None
    currentProfile: dict[str, Any]
    createdAt: datetime | None = None
    updatedAt: datetime | None = None


class RecentHistorySummaryRead(BaseModel):
    hasPriorActiveProfile: bool
    latestVersion: int | None = None
    latestUpdatedAt: datetime | None = None
    latestProfileStatus: str


class UpdateModeDefinitionRead(BaseModel):
    mode: Literal["no_update", "light_update", "full_rewrite"]
    description: str


class NumericConstraintRead(BaseModel):
    field: str
    minValue: float | None = None
    maxValue: float | None = None


class ListConstraintRead(BaseModel):
    field: str
    maxItems: int
    maxItemLength: int


class UpdateConstraintsRead(BaseModel):
    allowedPatchFields: list[str]
    disallowedFields: list[str]
    updateModes: list[UpdateModeDefinitionRead]
    patchGuidance: list[str]
    numericConstraints: list[NumericConstraintRead]
    listConstraints: list[ListConstraintRead]


class ExpectedActionRead(BaseModel):
    submissionType: str = "patch"
    steps: list[str]
    outputShape: dict[str, Any]


class ModuleUpdateContextRequest(BaseModel):
    learnerId: int = Field(..., ge=1)
    courseUuid: str = Field(..., min_length=1)
    moduleUuid: str = Field(..., min_length=1)
    triggerSource: Literal["quiz", "chat", "progress", "manual", "system"]


class ModuleUpdateContextResponse(BaseModel):
    scope: ModuleUpdateContextScopeRead
    trigger: ModuleUpdateTriggerRead
    baseProfile: BaseProfileContextRead
    quizSignalSummary: QuizSignalSummaryRead
    chatSignalSummary: ChatSignalSummaryRead
    recentHistorySummary: RecentHistorySummaryRead
    updateConstraints: UpdateConstraintsRead
    expectedAction: ExpectedActionRead


class ModuleProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    learning_style: str | None = Field(default=None, min_length=1, max_length=100)
    response_preference: str | None = Field(default=None, min_length=1, max_length=100)
    knowledge_stability: str | None = Field(default=None, min_length=1, max_length=100)
    engagement_pattern: str | None = Field(default=None, min_length=1, max_length=100)
    common_error_patterns: list[str] | None = Field(default=None, max_length=10)
    support_need_level: str | None = Field(default=None, min_length=1, max_length=100)
    confidence_estimate: float | None = Field(default=None, ge=0.0, le=1.0)
    weak_points: list[str] | None = Field(default=None, max_length=10)
    strong_points: list[str] | None = Field(default=None, max_length=10)
    recent_confusions: list[str] | None = Field(default=None, max_length=10)
    recommended_focus: list[str] | None = Field(default=None, max_length=10)

    @model_validator(mode="after")
    def validate_non_empty_patch(self) -> "ModuleProfilePatch":
        if not self.model_dump(exclude_none=True):
            raise ValueError("At least one patch field must be provided")
        return self


class ModuleProfileCandidateUpdateRequest(BaseModel):
    learnerId: int = Field(..., ge=1)
    courseUuid: str = Field(..., min_length=1)
    moduleUuid: str = Field(..., min_length=1)
    source: Literal["quiz", "chat", "progress", "manual", "system"]
    updateMode: Literal["light_update", "full_rewrite"]
    reason: str = Field(..., min_length=1, max_length=1000)
    patch: ModuleProfilePatch


class ModuleProfileCandidateUpdateResponse(BaseModel):
    accepted: bool
    retryable: bool = False
    code: str
    message: str
    changedFields: list[str]
    profile: ModuleProfileRead | None = None


class ModuleProfileUpdateCheckDecision(BaseModel):
    should_update: bool
    update_mode: Literal["light_update", "full_rewrite"] | None = None
    reason: str = Field(..., min_length=1, max_length=1000)
    patch: dict[str, Any]


class ModuleProfileUpdateCheckRequest(BaseModel):
    learnerId: int = Field(..., ge=1)
    courseUuid: str = Field(..., min_length=1)
    moduleUuid: str = Field(..., min_length=1)
    triggerSource: Literal["quiz", "chat", "progress", "manual", "system"]


class ModuleProfileUpdateCheckResponse(BaseModel):
    decision: ModuleProfileUpdateCheckDecision
    candidateResult: ModuleProfileCandidateUpdateResponse | None = None

class ProfileUpdateWorkflowState(TypedDict, total=False):
    request: ModuleProfileUpdateCheckRequest
    context: ModuleUpdateContextResponse
    decision: ModuleProfileUpdateCheckDecision
    candidateRequest: ModuleProfileCandidateUpdateRequest
    candidateResult: ModuleProfileCandidateUpdateResponse | None
    validationFeedback: list[str]
    attemptCount: int
    result: ModuleProfileUpdateCheckResponse

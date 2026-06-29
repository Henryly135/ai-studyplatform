from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from fastapi import status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.time import now_local
from app.core.uuid_codec import decode_course_uuid, decode_module_uuid, encode_module_uuid
from app.models.course_enrollments import EnrollmentStatus
from app.models.courses import CourseStatus
from app.models.modules import Module, ModuleStatus
from app.models.short_answer_assessments import ShortAnswerAssessment, ShortAnswerAssessmentStatus
from app.models.short_answer_submissions import ShortAnswerSubmission, ShortAnswerSubmissionStatus
from app.repositories.course_enrollment_repository import CourseEnrollmentRepository
from app.repositories.course_repository import CourseRepository
from app.repositories.learning_path_repository import LearningPathRepository
from app.repositories.module_repository import ModuleRepository
from app.repositories.short_answer_assessment_repository import ShortAnswerAssessmentRepository
from app.repositories.short_answer_submission_repository import ShortAnswerSubmissionRepository
from app.schemas.short_answer import (
    ShortAnswerAISuggestionResponse,
    ShortAnswerAssessmentResponse,
    ShortAnswerAssessmentUpsertRequest,
    ShortAnswerEvaluationRequest,
    ShortAnswerEvaluationResponse,
    ShortAnswerLearnerAssessmentResponse,
    ShortAnswerSubmissionCreateRequest,
    ShortAnswerSubmissionResponse,
    ShortAnswerSubmissionReviewRequest,
)
from app.services.module_unlocking_service import ModuleUnlockingService
from app.services.short_answer_ai_client import ShortAnswerAIClient
from platform_common.errors import http_error, invalid_identity_response_error, invalid_request_error


class ShortAnswerService:
    def __init__(self, session: Session, *, ai_client: ShortAnswerAIClient | None = None) -> None:
        self.session = session
        self.courses = CourseRepository(session)
        self.learning_paths = LearningPathRepository(session)
        self.modules = ModuleRepository(session)
        self.enrollments = CourseEnrollmentRepository(session)
        self.assessments = ShortAnswerAssessmentRepository(session)
        self.submissions = ShortAnswerSubmissionRepository(session)
        self.unlocking = ModuleUnlockingService(session)
        self.ai_client = ai_client or ShortAnswerAIClient()

    def upsert_assessment(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        payload: ShortAnswerAssessmentUpsertRequest,
        current_user: dict,
    ) -> ShortAnswerAssessmentResponse:
        actor_id = self._require_actor_id(current_user)
        course = self._get_manageable_course(course_uuid=course_uuid, current_user=current_user)
        module = self._get_course_module(course_id=course.course_id, module_uuid=module_uuid)
        status_value = ShortAnswerAssessmentStatus(payload.status)
        published_at = now_local() if status_value == ShortAnswerAssessmentStatus.PUBLISHED else None
        existing = self.assessments.get_by_module_id(module.module_id)

        if existing is None:
            assessment = self.assessments.create(
                module_id=module.module_id,
                title=self._required_text(payload.title, "title"),
                prompt_text=self._required_text(payload.promptText, "promptText"),
                rubric_text=self._required_text(payload.rubricText, "rubricText"),
                max_score=self._quantize_score(payload.maxScore),
                status=status_value,
                created_by=actor_id,
                updated_by=actor_id,
                published_at=published_at,
            )
        else:
            if status_value == ShortAnswerAssessmentStatus.PUBLISHED and existing.published_at is not None:
                published_at = existing.published_at
            assessment = self.assessments.update(
                existing,
                title=self._required_text(payload.title, "title"),
                prompt_text=self._required_text(payload.promptText, "promptText"),
                rubric_text=self._required_text(payload.rubricText, "rubricText"),
                max_score=self._quantize_score(payload.maxScore),
                status=status_value,
                updated_by=actor_id,
                published_at=published_at,
            )

        self.session.commit()
        self.session.refresh(assessment)
        return self._to_assessment_response(assessment, module=module)

    def get_management_assessment(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        current_user: dict,
    ) -> ShortAnswerAssessmentResponse:
        course = self._get_manageable_course(course_uuid=course_uuid, current_user=current_user)
        module = self._get_course_module(course_id=course.course_id, module_uuid=module_uuid)
        return self._to_assessment_response(
            self._get_module_assessment(module.module_id),
            module=module,
        )

    def get_learner_assessment(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        current_user: dict,
    ) -> ShortAnswerLearnerAssessmentResponse:
        learner_id = self._require_learner_id(current_user)
        course = self._get_course(course_uuid)
        module = self._get_course_module(course_id=course.course_id, module_uuid=module_uuid)
        self._ensure_learner_can_access_module(course=course, module=module, learner_id=learner_id)
        self._ensure_module_unlocked(module_id=module.module_id, learner_id=learner_id)
        assessment = self._get_published_module_assessment(module.module_id)
        latest = self.submissions.get_latest_by_assessment_and_learner(
            assessment.short_answer_assessment_id,
            learner_id,
        )
        return ShortAnswerLearnerAssessmentResponse(
            assessment=self._to_assessment_response(assessment, module=module),
            latestSubmission=self._to_submission_response(latest, assessment=assessment, include_private_review=False)
            if latest is not None
            else None,
        )

    def submit_answer(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        payload: ShortAnswerSubmissionCreateRequest,
        current_user: dict,
    ) -> ShortAnswerSubmissionResponse:
        learner_id = self._require_learner_id(current_user)
        course = self._get_course(course_uuid)
        module = self._get_course_module(course_id=course.course_id, module_uuid=module_uuid)
        self._ensure_learner_can_access_module(course=course, module=module, learner_id=learner_id)
        self._ensure_module_unlocked(module_id=module.module_id, learner_id=learner_id)
        assessment = self._get_published_module_assessment(module.module_id)
        answer_text = self._required_text(payload.answerText, "answerText")
        ai_suggestion = self._evaluate_with_ai(assessment=assessment, answer_text=answer_text)
        submission = self.submissions.create(
            assessment_id=assessment.short_answer_assessment_id,
            learner_id=learner_id,
            answer_text=answer_text,
            ai_score_suggestion=ai_suggestion.scoreSuggestion,
            ai_feedback_text=ai_suggestion.feedbackText,
            ai_strengths_json=ai_suggestion.strengths,
            ai_improvements_json=ai_suggestion.improvements,
            ai_provider_name=ai_suggestion.provider,
            ai_provider_model=ai_suggestion.model,
            status=ShortAnswerSubmissionStatus.AI_SUGGESTED,
        )
        self.session.commit()
        self.session.refresh(submission)
        return self._to_submission_response(submission, assessment=assessment)

    def list_submissions(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        current_user: dict,
    ) -> list[ShortAnswerSubmissionResponse]:
        course = self._get_manageable_course(course_uuid=course_uuid, current_user=current_user)
        module = self._get_course_module(course_id=course.course_id, module_uuid=module_uuid)
        assessment = self._get_module_assessment(module.module_id)
        return [
            self._to_submission_response(submission, assessment=assessment)
            for submission in self.submissions.list_by_assessment(assessment.short_answer_assessment_id)
        ]

    def review_submission(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        submission_uuid: str,
        payload: ShortAnswerSubmissionReviewRequest,
        current_user: dict,
    ) -> ShortAnswerSubmissionResponse:
        reviewer_id = self._require_actor_id(current_user)
        course = self._get_manageable_course(course_uuid=course_uuid, current_user=current_user)
        module = self._get_course_module(course_id=course.course_id, module_uuid=module_uuid)
        assessment = self._get_module_assessment(module.module_id)
        submission = self.submissions.get_by_uuid(submission_uuid)
        if submission is None or submission.assessment_id != assessment.short_answer_assessment_id:
            raise http_error(
                status_code=status.HTTP_404_NOT_FOUND,
                code="SHORT_ANSWER_SUBMISSION_NOT_FOUND",
                message="Short-answer submission not found",
            )
        final_score = self._quantize_score(payload.finalScore)
        if final_score > assessment.max_score:
            raise invalid_request_error("finalScore cannot exceed the assessment maxScore")
        reviewed = self.submissions.update_review(
            submission,
            final_score=final_score,
            final_feedback_text=self._required_text(payload.finalFeedbackText, "finalFeedbackText"),
            review_notes=payload.reviewNotes,
            reviewer_id=reviewer_id,
            reviewed_at=now_local(),
        )
        self.session.commit()
        self.session.refresh(reviewed)
        return self._to_submission_response(reviewed, assessment=assessment)

    def _evaluate_with_ai(self, *, assessment: ShortAnswerAssessment, answer_text: str) -> ShortAnswerEvaluationResponse:
        payload = ShortAnswerEvaluationRequest(
            assessmentUuid=assessment.assessment_uuid,
            title=assessment.title,
            promptText=assessment.prompt_text,
            rubricText=assessment.rubric_text,
            maxScore=assessment.max_score,
            answerText=answer_text,
        )
        response = self.ai_client.evaluate_submission(payload)
        try:
            suggestion = ShortAnswerEvaluationResponse.model_validate(response)
        except (TypeError, ValidationError) as exc:
            raise http_error(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="INVALID_AI_SHORT_ANSWER_RESPONSE",
                message="AI service returned an invalid short-answer evaluation",
            ) from exc
        if suggestion.scoreSuggestion > assessment.max_score:
            raise http_error(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="INVALID_AI_SHORT_ANSWER_RESPONSE",
                message="AI service returned an invalid short-answer evaluation",
            )
        return suggestion

    def _to_assessment_response(self, assessment: ShortAnswerAssessment, *, module: Module) -> ShortAnswerAssessmentResponse:
        return ShortAnswerAssessmentResponse(
            assessmentUuid=assessment.assessment_uuid,
            moduleId=module.module_id,
            moduleUuid=encode_module_uuid(module.module_id),
            title=assessment.title,
            promptText=assessment.prompt_text,
            rubricText=assessment.rubric_text,
            maxScore=assessment.max_score,
            status=assessment.status.value if isinstance(assessment.status, ShortAnswerAssessmentStatus) else str(assessment.status),
            publishedAt=assessment.published_at,
            createdAt=assessment.created_at,
            updatedAt=assessment.updated_at,
        )

    def _to_submission_response(
        self,
        submission: ShortAnswerSubmission,
        *,
        assessment: ShortAnswerAssessment,
        include_private_review: bool = True,
    ) -> ShortAnswerSubmissionResponse:
        return ShortAnswerSubmissionResponse(
            submissionUuid=submission.submission_uuid,
            assessmentUuid=assessment.assessment_uuid,
            learnerId=submission.learner_id,
            answerText=submission.answer_text,
            status=submission.status.value if isinstance(submission.status, ShortAnswerSubmissionStatus) else str(submission.status),
            aiSuggestion=ShortAnswerAISuggestionResponse(
                scoreSuggestion=submission.ai_score_suggestion,
                feedbackText=submission.ai_feedback_text,
                strengths=submission.ai_strengths_json or [],
                improvements=submission.ai_improvements_json or [],
                provider=submission.ai_provider_name,
                model=submission.ai_provider_model,
            ),
            finalScore=submission.final_score,
            finalFeedbackText=submission.final_feedback_text,
            reviewNotes=submission.review_notes if include_private_review else None,
            reviewerId=submission.reviewer_id if include_private_review else None,
            reviewedAt=submission.reviewed_at,
            createdAt=submission.created_at,
            updatedAt=submission.updated_at,
        )

    def _get_course(self, course_uuid: str):
        course = self.courses.get_by_id(decode_course_uuid(course_uuid))
        if course is None:
            raise http_error(status_code=status.HTTP_404_NOT_FOUND, code="COURSE_NOT_FOUND", message="Course not found")
        return course

    def _get_course_module(self, *, course_id: int, module_uuid: str) -> Module:
        learning_path = self.learning_paths.get_by_course_id(course_id)
        if learning_path is None:
            raise http_error(status_code=status.HTTP_404_NOT_FOUND, code="LEARNING_PATH_NOT_FOUND", message="Learning path not found")
        module = self.modules.get_by_id(decode_module_uuid(module_uuid))
        if module is None or module.learning_path_id != learning_path.learning_path_id:
            raise http_error(status_code=status.HTTP_404_NOT_FOUND, code="MODULE_NOT_FOUND", message="Module not found")
        return module

    def _get_manageable_course(self, *, course_uuid: str, current_user: dict):
        actor_id = self._require_actor_id(current_user)
        course = self._get_course(course_uuid)
        if current_user.get("identity") == "Admin":
            return course
        if current_user.get("identity") == "Educator" and course.educator_id == actor_id:
            return course
        raise http_error(
            status_code=status.HTTP_403_FORBIDDEN,
            code="COURSE_OWNERSHIP_REQUIRED",
            message="You can only manage short-answer assessments for your own courses",
        )

    def _get_module_assessment(self, module_id: int) -> ShortAnswerAssessment:
        assessment = self.assessments.get_by_module_id(module_id)
        if assessment is None:
            raise http_error(
                status_code=status.HTTP_404_NOT_FOUND,
                code="SHORT_ANSWER_ASSESSMENT_NOT_FOUND",
                message="Short-answer assessment not found",
            )
        return assessment

    def _get_published_module_assessment(self, module_id: int) -> ShortAnswerAssessment:
        assessment = self._get_module_assessment(module_id)
        if assessment.status != ShortAnswerAssessmentStatus.PUBLISHED:
            raise http_error(
                status_code=status.HTTP_404_NOT_FOUND,
                code="SHORT_ANSWER_ASSESSMENT_NOT_AVAILABLE",
                message="Short-answer assessment is not available",
            )
        return assessment

    def _require_actor_id(self, current_user: dict) -> int:
        actor_id = current_user.get("id")
        if not isinstance(actor_id, int):
            raise invalid_identity_response_error()
        return actor_id

    def _require_learner_id(self, current_user: dict) -> int:
        learner_id = self._require_actor_id(current_user)
        if current_user.get("identity") != "Learner":
            raise http_error(
                status_code=status.HTTP_403_FORBIDDEN,
                code="LEARNER_ONLY",
                message="Only learners can submit short-answer assessments",
            )
        return learner_id

    def _ensure_learner_can_access_module(self, *, course, module: Module, learner_id: int) -> None:
        if course.status != CourseStatus.PUBLISHED:
            raise http_error(
                status_code=status.HTTP_404_NOT_FOUND,
                code="SHORT_ANSWER_ASSESSMENT_NOT_AVAILABLE",
                message="Short-answer assessment is not available",
            )
        enrollment = self.enrollments.get_by_course_and_learner(course_id=course.course_id, learner_id=learner_id)
        if enrollment is None or enrollment.enrollment_status == EnrollmentStatus.DROPPED:
            raise http_error(
                status_code=status.HTTP_403_FORBIDDEN,
                code="ENROLLMENT_REQUIRED",
                message="Learner must be enrolled before submitting this assessment",
            )
        if module.status != ModuleStatus.PUBLISHED:
            raise http_error(
                status_code=status.HTTP_404_NOT_FOUND,
                code="SHORT_ANSWER_ASSESSMENT_NOT_AVAILABLE",
                message="Short-answer assessment is not available",
            )

    def _ensure_module_unlocked(self, *, module_id: int, learner_id: int) -> None:
        self.unlocking.ensure_module_unlocked(
            module_id=module_id,
            learner_id=learner_id,
            resource_name="short-answer assessment",
        )

    def _required_text(self, value: str | None, field_name: str) -> str:
        normalized = (value or "").strip()
        if not normalized:
            raise invalid_request_error(f"Short-answer assessment {field_name} is required")
        return normalized

    def _quantize_score(self, value: Decimal) -> Decimal:
        return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

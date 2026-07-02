import random
import secrets
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import status
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.time import now_local
from app.core.uuid_codec import (
    decode_course_uuid,
    decode_module_uuid,
    decode_quiz_attempt_uuid,
    decode_quiz_option_uuid,
    decode_quiz_question_uuid,
    encode_module_uuid,
    encode_quiz_attempt_uuid,
    encode_quiz_option_uuid,
    encode_quiz_question_uuid,
    encode_quiz_uuid,
)
from app.models.courses import CourseStatus
from app.models.course_enrollments import EnrollmentStatus
from app.models.module_progress import ProgressStatus
from app.models.modules import Module, ModuleStatus
from app.models.quizzes import Quiz, QuizPassingRule, QuizStatus
from app.repositories.course_enrollment_repository import CourseEnrollmentRepository
from app.repositories.course_repository import CourseRepository
from app.repositories.learning_path_repository import LearningPathRepository
from app.repositories.module_prerequisite_repository import ModulePrerequisiteRepository
from app.repositories.module_progress_repository import ModuleProgressRepository
from app.repositories.module_repository import ModuleRepository
from app.repositories.quiz_attempt_answer_repository import QuizAttemptAnswerRepository
from app.repositories.quiz_attempt_repository import QuizAttemptRepository
from app.repositories.quiz_question_option_repository import QuizQuestionOptionRepository
from app.repositories.quiz_question_repository import QuizQuestionRepository
from app.repositories.quiz_repository import QuizRepository
from app.schemas.quiz import (
    QuizAttemptHistoryResponse,
    QuizAttemptResultResponse,
    QuizAttemptStartQuestionResponse,
    QuizAttemptStartResponse,
    QuizAttemptSubmitRequest,
    QuizAttemptSummaryResponse,
    QuizAuthoringResponse,
    QuizOptionResponse,
    QuizPublishRequest,
    QuizQuestionResponse,
    QuizQuestionPageResponse,
    QuizQuestionWriteRequest,
    QuizUpsertRequest,
)
from app.schemas.quiz_generation import (
    GeneratedQuizAttemptStartRequest,
    GeneratedQuizQuestionRefResponse,
    GeneratedQuizQuestionsCreateResponse,
    QuizGenerationContextResponse,
)
from app.services.course_enrollment_aggregate_service import CourseEnrollmentAggregateService
from app.services.module_profile_trigger_service import ModuleProfileTriggerService
from app.services.module_unlocking_service import ModuleUnlockingService
from app.services.quiz_attempt_session_store import QuizAttemptSessionData, QuizAttemptSessionStore
from platform_common.errors import http_error, invalid_identity_response_error, invalid_request_error


ARCHIVED_QUIZ_SORT_ORDER_BASE = 10_000_000
GENERATED_ATTEMPT_QUIZ_SORT_ORDER_BASE = 1_000_000_000


class QuizService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.random = random.SystemRandom()
        self.courses = CourseRepository(session)
        self.learning_paths = LearningPathRepository(session)
        self.modules = ModuleRepository(session)
        self.module_prerequisites = ModulePrerequisiteRepository(session)
        self.module_progress = ModuleProgressRepository(session)
        self.enrollments = CourseEnrollmentRepository(session)
        self.quizzes = QuizRepository(session)
        self.questions = QuizQuestionRepository(session)
        self.options = QuizQuestionOptionRepository(session)
        self.attempts = QuizAttemptRepository(session)
        self.attempt_answers = QuizAttemptAnswerRepository(session)
        self.enrollment_aggregates = CourseEnrollmentAggregateService(session)
        self.unlocking = ModuleUnlockingService(session)
        self.profile_triggers = ModuleProfileTriggerService(session)
        self.attempt_sessions = QuizAttemptSessionStore()

    def upsert_quiz(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        payload: QuizUpsertRequest,
        current_user: dict,
        include_questions: bool = True,
    ) -> QuizAuthoringResponse:
        course = self._get_manageable_course(course_uuid=course_uuid, current_user=current_user)
        module = self._get_course_module(course_id=course.course_id, module_uuid=module_uuid)

        quiz = self.quizzes.get_by_module_id(module.module_id)
        if quiz is not None:
            self.quizzes.update(
                quiz,
                title=self._normalize_required_text(payload.title, field_name="title"),
                description=self._normalize_optional_text(payload.description),
                status=QuizStatus.DRAFT,
                time_limit_seconds=payload.timeLimitSeconds,
                question_count_per_attempt=payload.questionCountPerAttempt,
                shuffle_questions=payload.shuffleQuestions,
                shuffle_options=payload.shuffleOptions,
                published_at=None,
            )
        else:
            quiz = self.quizzes.create(
                module_id=module.module_id,
                title=self._normalize_required_text(payload.title, field_name="title"),
                description=self._normalize_optional_text(payload.description),
                status=QuizStatus.DRAFT,
                time_limit_seconds=payload.timeLimitSeconds,
                question_count_per_attempt=payload.questionCountPerAttempt,
                shuffle_questions=payload.shuffleQuestions,
                shuffle_options=payload.shuffleOptions,
            )

        for question_payload in payload.questions:
            self._apply_question_write(quiz=quiz, payload=question_payload)

        self._touch_quiz_as_draft(quiz=quiz, course=course)
        self.session.commit()
        self.session.refresh(quiz)
        return self._to_quiz_authoring_response(quiz=quiz, module=module, include_questions=include_questions)

    def create_question(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        payload: QuizQuestionWriteRequest,
        current_user: dict,
    ) -> QuizAuthoringResponse:
        course = self._get_manageable_course(course_uuid=course_uuid, current_user=current_user)
        module = self._get_course_module(course_id=course.course_id, module_uuid=module_uuid)
        quiz = self._get_module_quiz(module.module_id)
        if payload.questionUuid:
            raise invalid_request_error("questionUuid must be empty when creating a new question")
        self._apply_question_write(quiz=quiz, payload=payload)
        self._touch_quiz_as_draft(quiz=quiz, course=course)
        self.session.commit()
        self.session.refresh(quiz)
        return self._to_quiz_authoring_response(quiz=quiz, module=module)

    def update_question(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        question_uuid: str,
        payload: QuizQuestionWriteRequest,
        current_user: dict,
    ) -> QuizAuthoringResponse:
        course = self._get_manageable_course(course_uuid=course_uuid, current_user=current_user)
        module = self._get_course_module(course_id=course.course_id, module_uuid=module_uuid)
        quiz = self._get_module_quiz(module.module_id)
        payload_question_uuid = payload.questionUuid or question_uuid
        if payload.questionUuid and payload.questionUuid != question_uuid:
            raise invalid_request_error("questionUuid in payload must match the request path")
        self._apply_question_write(quiz=quiz, payload=payload, question_uuid=payload_question_uuid)
        self._touch_quiz_as_draft(quiz=quiz, course=course)
        self.session.commit()
        self.session.refresh(quiz)
        return self._to_quiz_authoring_response(quiz=quiz, module=module)

    def publish_quiz(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        payload: QuizPublishRequest,
        current_user: dict,
        include_questions: bool = True,
    ) -> QuizAuthoringResponse:
        course = self._get_manageable_course(course_uuid=course_uuid, current_user=current_user)
        module = self._get_course_module(course_id=course.course_id, module_uuid=module_uuid)
        quiz = self._get_module_quiz(module.module_id)
        next_status = self._parse_quiz_status(payload.status)
        if next_status == QuizStatus.PUBLISHED:
            if module.status != ModuleStatus.PUBLISHED:
                raise invalid_request_error("Module must be published before the quiz can be published")
            self._ensure_quiz_publishable(quiz)
        self.quizzes.update(quiz, status=next_status, published_at=now_local() if next_status == QuizStatus.PUBLISHED else None)
        self.courses.touch(course)
        self.session.commit()
        self.session.refresh(quiz)
        return self._to_quiz_authoring_response(quiz=quiz, module=module, include_questions=include_questions)

    def get_quiz_authoring_detail(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        current_user: dict,
        include_questions: bool = True,
    ) -> QuizAuthoringResponse:
        course = self._get_manageable_course(course_uuid=course_uuid, current_user=current_user)
        module = self._get_course_module(course_id=course.course_id, module_uuid=module_uuid)
        return self._to_quiz_authoring_response(
            quiz=self._get_module_quiz(module.module_id),
            module=module,
            include_questions=include_questions,
        )

    def list_quiz_authoring_questions(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        current_user: dict,
        page: int,
        page_size: int,
        query: str | None,
    ) -> QuizQuestionPageResponse:
        course = self._get_manageable_course(course_uuid=course_uuid, current_user=current_user)
        module = self._get_course_module(course_id=course.course_id, module_uuid=module_uuid)
        quiz = self._get_module_quiz(module.module_id)
        safe_page = max(1, page)
        safe_page_size = min(100, max(1, page_size))
        question_rows, total = self.questions.list_by_quiz_page(
            quiz.quiz_id,
            page=safe_page,
            page_size=safe_page_size,
            query=query,
        )
        total_pages = max(1, (total + safe_page_size - 1) // safe_page_size)
        return QuizQuestionPageResponse(
            items=[self._to_question_response(question) for question in question_rows],
            page=safe_page,
            pageSize=safe_page_size,
            total=total,
            totalPages=total_pages,
        )

    def get_quiz_generation_context(self, *, course_uuid: str, module_uuid: str) -> QuizGenerationContextResponse:
        course = self._get_course(course_uuid)
        module = self._get_course_module(course_id=course.course_id, module_uuid=module_uuid)
        quiz = self._get_module_quiz(module.module_id)
        authoring = self._to_quiz_authoring_response(quiz=quiz, module=module, include_questions=False)
        return QuizGenerationContextResponse(
            courseId=course.course_id,
            moduleId=module.module_id,
            courseUuid=course_uuid,
            moduleUuid=module_uuid,
            courseTitle=course.title,
            moduleTitle=module.title,
            quizId=authoring.quizId,
            quizUuid=authoring.quizUuid,
            quizTitle=authoring.title,
            quizDescription=authoring.description,
            quizStatus=authoring.status,
            questionCountPerAttempt=authoring.questionCountPerAttempt,
            timeLimitSeconds=authoring.timeLimitSeconds,
            shuffleQuestions=authoring.shuffleQuestions,
            shuffleOptions=authoring.shuffleOptions,
            availableQuestionCount=authoring.availableQuestionCount,
        )

    def ensure_learner_quiz_access(self, *, course_uuid: str, module_uuid: str, learner_id: int) -> None:
        course = self._get_course(course_uuid)
        module = self._get_course_module(course_id=course.course_id, module_uuid=module_uuid)
        quiz = self._get_module_quiz(module.module_id)
        if quiz.status != QuizStatus.PUBLISHED:
            raise http_error(status_code=status.HTTP_404_NOT_FOUND, code="QUIZ_NOT_AVAILABLE", message="Quiz is not available")

        self._ensure_learner_can_access_module(course=course, module=module, learner_id=learner_id)
        self._ensure_module_unlocked(module_id=module.module_id, learner_id=learner_id)

    def ensure_authoring_quiz_access(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        actor_id: int,
        actor_identity: str,
    ) -> None:
        course = self._get_manageable_course(
            course_uuid=course_uuid,
            current_user={"id": actor_id, "identity": actor_identity},
        )
        self._get_course_module(course_id=course.course_id, module_uuid=module_uuid)

    def batch_create_generated_questions(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        purpose: str = "authoring",
        questions: list[QuizQuestionWriteRequest],
    ) -> GeneratedQuizQuestionsCreateResponse:
        course = self._get_course(course_uuid)
        module = self._get_course_module(course_id=course.course_id, module_uuid=module_uuid)
        quiz = self._get_module_quiz(module.module_id)
        normalized_purpose = purpose.strip().lower()
        if normalized_purpose not in {"authoring", "attempt"}:
            raise invalid_request_error("Generated quiz question purpose must be authoring or attempt")
        if normalized_purpose == "attempt":
            next_sort_order = max(
                (
                    question.sort_order
                    for question in self.questions.list_by_quiz(quiz.quiz_id)
                    if question.sort_order >= GENERATED_ATTEMPT_QUIZ_SORT_ORDER_BASE
                ),
                default=GENERATED_ATTEMPT_QUIZ_SORT_ORDER_BASE,
            )
        else:
            next_sort_order = max(
                (
                    question.sort_order
                    for question in self.questions.list_by_quiz(quiz.quiz_id)
                    if question.sort_order < ARCHIVED_QUIZ_SORT_ORDER_BASE
                ),
                default=0,
            )

        created_questions: list[GeneratedQuizQuestionRefResponse] = []
        for offset, question_payload in enumerate(questions, start=1):
            generated_payload = QuizQuestionWriteRequest(
                questionUuid=None,
                questionText=question_payload.questionText,
                explanationText=question_payload.explanationText,
                sortOrder=next_sort_order + offset,
                isActive=question_payload.isActive if normalized_purpose == "authoring" else False,
                options=[
                    {
                        "optionUuid": None,
                        "optionLabel": option.optionLabel,
                        "optionText": option.optionText,
                        "sortOrder": option.sortOrder,
                        "isCorrect": option.isCorrect,
                    }
                    for option in question_payload.options
                ],
            )
            created_question = self._create_question(quiz=quiz, payload=generated_payload)
            created_questions.append(
                GeneratedQuizQuestionRefResponse(
                    questionId=created_question.quiz_question_id,
                    questionUuid=encode_quiz_question_uuid(created_question.quiz_question_id),
                    sortOrder=created_question.sort_order,
                )
            )

        if normalized_purpose == "authoring":
            self._touch_quiz_as_draft(quiz=quiz, course=course)
        else:
            self.courses.touch(course)
        self.session.commit()
        self.session.refresh(quiz)
        return GeneratedQuizQuestionsCreateResponse(
            quizId=quiz.quiz_id,
            quizUuid=encode_quiz_uuid(quiz.quiz_id),
            createdQuestions=created_questions,
        )

    def _apply_question_write(
        self,
        *,
        quiz: Quiz,
        payload: QuizQuestionWriteRequest,
        question_uuid: str | None = None,
    ) -> None:
        target_uuid = question_uuid or payload.questionUuid
        if target_uuid:
            question_id = decode_quiz_question_uuid(target_uuid)
            existing_question = self.questions.get_by_id(question_id)
            if existing_question is None or existing_question.quiz_id != quiz.quiz_id:
                raise http_error(status_code=status.HTTP_404_NOT_FOUND, code="QUIZ_QUESTION_NOT_FOUND", message="Quiz question not found")
            if self.attempt_answers.count_by_question(existing_question.quiz_question_id) > 0:
                self._archive_question(existing_question)
                if payload.isActive:
                    self._ensure_question_sort_order_available(
                        quiz_id=quiz.quiz_id,
                        sort_order=payload.sortOrder,
                    )
                    self._create_question(quiz=quiz, payload=payload)
                return
            if not payload.isActive:
                self._archive_question(existing_question)
                return
            self._ensure_question_sort_order_available(
                quiz_id=quiz.quiz_id,
                sort_order=payload.sortOrder,
                exclude_question_ids={existing_question.quiz_question_id},
            )
            self._update_question_in_place(question=existing_question, payload=payload)
            return

        self._ensure_question_sort_order_available(quiz_id=quiz.quiz_id, sort_order=payload.sortOrder)
        self._create_question(quiz=quiz, payload=payload)

    def _create_question(self, *, quiz: Quiz, payload: QuizQuestionWriteRequest):
        question = self.questions.create(
            quiz_id=quiz.quiz_id,
            question_text=self._normalize_required_text(payload.questionText, field_name="questionText"),
            explanation_text=self._normalize_optional_text(payload.explanationText),
            sort_order=payload.sortOrder,
            is_active=payload.isActive,
        )
        self._replace_question_options(question_id=question.quiz_question_id, payload=payload)
        return question

    def _update_question_in_place(self, *, question, payload: QuizQuestionWriteRequest) -> None:
        self.questions.update(
            question,
            question_text=self._normalize_required_text(payload.questionText, field_name="questionText"),
            explanation_text=self._normalize_optional_text(payload.explanationText),
            sort_order=payload.sortOrder,
            is_active=payload.isActive,
        )
        self._replace_question_options(question_id=question.quiz_question_id, payload=payload)

    def _replace_question_options(self, *, question_id: int, payload: QuizQuestionWriteRequest) -> None:
        self.options.delete_by_question(question_id)
        for option_payload in payload.options:
            self.options.create(
                quiz_question_id=question_id,
                option_label=self._normalize_optional_text(option_payload.optionLabel),
                option_text=self._normalize_required_text(option_payload.optionText, field_name="optionText"),
                sort_order=option_payload.sortOrder,
                is_correct=option_payload.isCorrect,
            )

    def _archive_question(self, question) -> None:
        archived_sort_order = ARCHIVED_QUIZ_SORT_ORDER_BASE + int(question.quiz_question_id)
        self.questions.update(
            question,
            question_text=question.question_text,
            explanation_text=question.explanation_text,
            sort_order=archived_sort_order,
            is_active=False,
        )

    def _touch_quiz_as_draft(self, *, quiz: Quiz, course) -> None:
        self.quizzes.update(quiz, status=QuizStatus.DRAFT, published_at=None)
        self.courses.touch(course)

    def _ensure_question_sort_order_available(
        self,
        *,
        quiz_id: int,
        sort_order: int,
        exclude_question_ids: set[int] | None = None,
    ) -> None:
        excluded = exclude_question_ids or set()
        for question in self.questions.list_by_quiz(quiz_id):
            if question.quiz_question_id in excluded:
                continue
            if question.sort_order == sort_order:
                raise invalid_request_error("Question sortOrder must be unique within the quiz")

    def get_active_attempt_session(self, *, course_uuid: str, module_uuid: str, current_user: dict) -> QuizAttemptStartResponse | None:
        learner_id = self._require_learner_id(current_user)
        course = self._get_course(course_uuid)
        module = self._get_course_module(course_id=course.course_id, module_uuid=module_uuid)
        quiz = self.quizzes.get_by_module_id(module.module_id)
        if quiz is None:
            return None
        self._ensure_learner_can_access_module(course=course, module=module, learner_id=learner_id)
        active_session = self.attempt_sessions.get_active_session(quiz.quiz_id, learner_id)
        if active_session is None:
            return None
        return self._session_data_to_start_response(active_session)

    def _session_data_to_start_response(self, session: "QuizAttemptSessionData") -> QuizAttemptStartResponse:
        return QuizAttemptStartResponse(
            quizId=session.quiz_id,
            quizUuid=encode_quiz_uuid(session.quiz_id),
            moduleId=session.module_id,
            moduleUuid=encode_module_uuid(session.module_id),
            attemptSessionToken=session.session_token,
            attemptNumber=session.attempt_number,
            questionCount=session.question_count,
            timeLimitSeconds=session.time_limit_seconds,
            startedAt=session.started_at,
            expiresAt=session.expires_at,
            questions=[
                QuizAttemptStartQuestionResponse(
                    questionId=row["questionId"],
                    questionUuid=encode_quiz_question_uuid(row["questionId"]),
                    questionText=row["questionText"],
                    explanationText=row["explanationText"],
                    questionOrder=row["questionOrder"],
                    options=[
                        QuizOptionResponse(
                            optionId=opt["optionId"],
                            optionUuid=encode_quiz_option_uuid(opt["optionId"]),
                            optionLabel=opt["optionLabel"],
                            optionText=opt["optionText"],
                            sortOrder=opt["sortOrder"],
                        )
                        for opt in row["options"]
                    ],
                )
                for row in session.questions
            ],
        )

    def start_attempt(self, *, course_uuid: str, module_uuid: str, current_user: dict) -> QuizAttemptStartResponse:
        learner_id = self._require_learner_id(current_user)
        course = self._get_course(course_uuid)
        module = self._get_course_module(course_id=course.course_id, module_uuid=module_uuid)
        quiz = self._get_module_quiz(module.module_id)
        if quiz.status != QuizStatus.PUBLISHED:
            raise http_error(status_code=status.HTTP_404_NOT_FOUND, code="QUIZ_NOT_AVAILABLE", message="Quiz is not available")

        self._ensure_learner_can_access_module(course=course, module=module, learner_id=learner_id)
        self._ensure_module_unlocked(module_id=module.module_id, learner_id=learner_id)
        self._ensure_quiz_publishable(quiz)

        selected_questions = list(self.questions.list_active_by_quiz(quiz.quiz_id))
        if quiz.shuffle_questions:
            selected_questions = self.random.sample(selected_questions, quiz.question_count_per_attempt)
        else:
            selected_questions = selected_questions[: quiz.question_count_per_attempt]

        question_set_json: list[dict[str, Any]] = []
        for order_index, question in enumerate(selected_questions, start=1):
            option_rows = list(self.options.list_by_question(question.quiz_question_id))
            if quiz.shuffle_options:
                self.random.shuffle(option_rows)
            correct_option = next((option for option in option_rows if option.is_correct), None)
            if correct_option is None:
                raise invalid_request_error("Each quiz attempt question must have exactly one correct option before starting an attempt")
            question_set_json.append(
                {
                    "questionId": question.quiz_question_id,
                    "questionText": question.question_text,
                    "explanationText": question.explanation_text,
                    "questionOrder": order_index,
                    "correctOptionId": correct_option.quiz_question_option_id,
                    "correctOptionText": correct_option.option_text,
                    "options": [
                        {
                            "optionId": option.quiz_question_option_id,
                            "optionLabel": option.option_label,
                            "optionText": option.option_text,
                            "sortOrder": position,
                        }
                        for position, option in enumerate(option_rows, start=1)
                    ],
                }
            )

        started_at = now_local()
        expires_at = started_at + timedelta(seconds=quiz.time_limit_seconds) if quiz.time_limit_seconds is not None else None
        attempt_number = self.attempt_sessions.issue_attempt_number(
            quiz_id=quiz.quiz_id,
            learner_id=learner_id,
            base_attempt_number=self.attempts.get_max_attempt_number(quiz_id=quiz.quiz_id, learner_id=learner_id),
        )
        attempt_session = QuizAttemptSessionData(
            session_token=secrets.token_urlsafe(24),
            quiz_id=quiz.quiz_id,
            module_id=module.module_id,
            course_id=course.course_id,
            learner_id=learner_id,
            attempt_number=attempt_number,
            question_count=len(question_set_json),
            time_limit_seconds=quiz.time_limit_seconds,
            started_at=started_at,
            expires_at=expires_at,
            questions=question_set_json,
        )
        self.attempt_sessions.create_session(attempt_session)
        if quiz.time_limit_seconds is not None:
            celery_app.send_task(
                "app.tasks.quiz_attempts.auto_submit_quiz_attempt_task",
                args=[attempt_session.session_token],
                countdown=quiz.time_limit_seconds + 10,  # Grace period: let frontend submit first
                queue=settings.celery_task_default_queue,
            )
        self.session.commit()
        return self._session_data_to_start_response(attempt_session)

    def start_generated_attempt(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        payload: GeneratedQuizAttemptStartRequest,
        current_user: dict,
    ) -> QuizAttemptStartResponse:
        learner_id = self._require_learner_id(current_user)
        return self._start_generated_attempt_for_learner(
            course_uuid=course_uuid,
            module_uuid=module_uuid,
            learner_id=learner_id,
            question_uuids=payload.questionUuids,
        )

    def start_generated_attempt_internal(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        learner_id: int,
        question_uuids: list[str],
    ) -> QuizAttemptStartResponse:
        return self._start_generated_attempt_for_learner(
            course_uuid=course_uuid,
            module_uuid=module_uuid,
            learner_id=learner_id,
            question_uuids=question_uuids,
        )

    def _start_generated_attempt_for_learner(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        learner_id: int,
        question_uuids: list[str],
    ) -> QuizAttemptStartResponse:
        course = self._get_course(course_uuid)
        module = self._get_course_module(course_id=course.course_id, module_uuid=module_uuid)
        quiz = self._get_module_quiz(module.module_id)
        if quiz.status != QuizStatus.PUBLISHED:
            raise http_error(status_code=status.HTTP_404_NOT_FOUND, code="QUIZ_NOT_AVAILABLE", message="Quiz is not available")

        self._ensure_learner_can_access_module(course=course, module=module, learner_id=learner_id)
        self._ensure_module_unlocked(module_id=module.module_id, learner_id=learner_id)
        self._ensure_quiz_publishable(quiz)

        question_ids = [decode_quiz_question_uuid(question_uuid) for question_uuid in question_uuids]
        selected_questions = self.questions.list_by_ids(question_ids)
        questions_by_id = {question.quiz_question_id: question for question in selected_questions}
        ordered_questions = []
        for question_id in question_ids:
            question = questions_by_id.get(question_id)
            if question is None or question.quiz_id != quiz.quiz_id or not self._is_generated_attempt_question(question):
                raise http_error(
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="QUIZ_QUESTION_NOT_FOUND",
                    message="Generated quiz question not found for this quiz",
                )
            ordered_questions.append(question)

        if len(ordered_questions) != quiz.question_count_per_attempt:
            raise invalid_request_error("Generated question count must match quiz questionCountPerAttempt")

        attempt_session = self._build_attempt_session_from_questions(
            course=course,
            module=module,
            quiz=quiz,
            learner_id=learner_id,
            selected_questions=ordered_questions,
            preserve_order=True,
        )
        self.session.commit()
        return self._session_data_to_start_response(attempt_session)

    def submit_attempt(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        attempt_session_token: str,
        payload: QuizAttemptSubmitRequest,
        current_user: dict,
    ) -> QuizAttemptResultResponse:
        learner_id = self._require_learner_id(current_user)
        course = self._get_course(course_uuid)
        module = self._get_course_module(course_id=course.course_id, module_uuid=module_uuid)
        self._ensure_learner_can_access_module(course=course, module=module, learner_id=learner_id)
        attempt_session = self.attempt_sessions.get_session(attempt_session_token)
        if attempt_session is None or attempt_session.course_id != course.course_id or attempt_session.module_id != module.module_id or attempt_session.learner_id != learner_id:
            raise http_error(status_code=status.HTTP_404_NOT_FOUND, code="QUIZ_ATTEMPT_SESSION_NOT_FOUND", message="Quiz attempt session not found")
        answers_by_question_id: dict[int, int | None] = {}
        for answer in payload.answers:
            question_id = decode_quiz_question_uuid(answer.questionUuid)
            option_id = decode_quiz_option_uuid(answer.selectedOptionUuid) if answer.selectedOptionUuid else None
            if question_id in answers_by_question_id:
                raise invalid_request_error("Duplicate answers for the same question are not allowed")
            answers_by_question_id[question_id] = option_id

        session_question_ids = {int(row["questionId"]) for row in attempt_session.questions}
        submitted_question_ids = set(answers_by_question_id.keys())
        if submitted_question_ids - session_question_ids:
            raise invalid_request_error("Submitted answers contain questions that do not belong to this attempt")
        return self._finalize_attempt(
            attempt_session_token=attempt_session_token,
            submitted_answers=answers_by_question_id,
            submission_mode="timeout" if payload.timedOut else "manual",
            expected_course_id=course.course_id,
            expected_module_id=module.module_id,
            expected_learner_id=learner_id,
        )

    def auto_submit_attempt(self, *, session_token: str) -> QuizAttemptResultResponse | None:
        return self._finalize_attempt(
            attempt_session_token=session_token,
            submitted_answers={},
            submission_mode="timeout",
            expected_course_id=None,
            expected_module_id=None,
            expected_learner_id=None,
        )

    def list_attempt_history(self, *, course_uuid: str, module_uuid: str, current_user: dict) -> QuizAttemptHistoryResponse:
        learner_id = self._require_learner_id(current_user)
        course = self._get_course(course_uuid)
        module = self._get_course_module(course_id=course.course_id, module_uuid=module_uuid)
        quiz = self._get_module_quiz(module.module_id)
        self._ensure_learner_can_access_module(course=course, module=module, learner_id=learner_id)
        attempts = self.attempts.list_by_quiz_and_learner(quiz_id=quiz.quiz_id, learner_id=learner_id)
        return QuizAttemptHistoryResponse(
            quizId=quiz.quiz_id,
            quizUuid=encode_quiz_uuid(quiz.quiz_id),
            moduleId=module.module_id,
            moduleUuid=encode_module_uuid(module.module_id),
            title=quiz.title,
            timeLimitSeconds=quiz.time_limit_seconds,
            passedOnce=any(attempt.is_passed for attempt in attempts),
            attempts=[
                QuizAttemptSummaryResponse(
                    quizAttemptId=attempt.quiz_attempt_id,
                    quizAttemptUuid=encode_quiz_attempt_uuid(attempt.quiz_attempt_id),
                    attemptNumber=attempt.attempt_number,
                    questionCount=attempt.question_count,
                    correctCount=attempt.correct_count,
                    scorePercent=str(attempt.score_percent),
                    isPassed=attempt.is_passed,
                    isTimedOut=attempt.is_timed_out,
                    startedAt=attempt.started_at,
                    submittedAt=attempt.submitted_at,
                    durationSeconds=attempt.duration_seconds,
                )
                for attempt in attempts
            ],
        )

    def get_attempt_detail(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        quiz_attempt_uuid: str,
        current_user: dict,
    ) -> QuizAttemptResultResponse:
        learner_id = self._require_learner_id(current_user)
        course = self._get_course(course_uuid)
        module = self._get_course_module(course_id=course.course_id, module_uuid=module_uuid)
        quiz = self._get_module_quiz(module.module_id)
        self._ensure_learner_can_access_module(course=course, module=module, learner_id=learner_id)

        attempt_id = decode_quiz_attempt_uuid(quiz_attempt_uuid)
        attempt = self.attempts.get_by_id(attempt_id)
        if (
            attempt is None
            or attempt.quiz_id != quiz.quiz_id
            or attempt.module_id != module.module_id
            or attempt.learner_id != learner_id
        ):
            raise http_error(
                status_code=status.HTTP_404_NOT_FOUND,
                code="QUIZ_ATTEMPT_NOT_FOUND",
                message="Quiz attempt not found",
            )

        return self._to_attempt_result_response(
            attempt=attempt,
            quiz=quiz,
            module=module,
            module_completed=False,
        )

    def _finalize_attempt(
        self,
        *,
        attempt_session_token: str,
        submitted_answers: dict[int, int | None],
        submission_mode: str,
        expected_course_id: int | None,
        expected_module_id: int | None,
        expected_learner_id: int | None,
    ) -> QuizAttemptResultResponse | None:
        lock_value = self.attempt_sessions.acquire_submit_lock(attempt_session_token)
        if lock_value is None:
            if submission_mode == "manual":
                raise invalid_request_error("Quiz attempt is already being submitted")
            return None

        try:
            attempt_session = self.attempt_sessions.get_session(attempt_session_token)
            if attempt_session is None:
                if submission_mode == "manual":
                    raise http_error(
                        status_code=status.HTTP_410_GONE,
                        code="QUIZ_ATTEMPT_SESSION_EXPIRED",
                        message="Quiz attempt session has expired or has already been submitted",
                    )
                return None

            if expected_course_id is not None and attempt_session.course_id != expected_course_id:
                raise http_error(status_code=status.HTTP_404_NOT_FOUND, code="QUIZ_ATTEMPT_SESSION_NOT_FOUND", message="Quiz attempt session not found")
            if expected_module_id is not None and attempt_session.module_id != expected_module_id:
                raise http_error(status_code=status.HTTP_404_NOT_FOUND, code="QUIZ_ATTEMPT_SESSION_NOT_FOUND", message="Quiz attempt session not found")
            if expected_learner_id is not None and attempt_session.learner_id != expected_learner_id:
                raise http_error(status_code=status.HTTP_404_NOT_FOUND, code="QUIZ_ATTEMPT_SESSION_NOT_FOUND", message="Quiz attempt session not found")

            course = self.courses.get_by_id(attempt_session.course_id)
            module = self.modules.get_by_id(attempt_session.module_id)
            if course is None or module is None:
                if submission_mode == "manual":
                    raise http_error(status_code=status.HTTP_404_NOT_FOUND, code="MODULE_NOT_FOUND", message="Module not found")
                return None

            quiz = self._get_module_quiz(module.module_id)
            submitted_at = now_local()
            is_timed_out = submission_mode == "timeout" or bool(
                attempt_session.expires_at and submitted_at > attempt_session.expires_at
            )
            duration_seconds = max(0, int((submitted_at - attempt_session.started_at).total_seconds()))

            correct_count = 0
            answer_snapshots: list[dict[str, Any]] = []
            for row in attempt_session.questions:
                question_id = int(row["questionId"])
                selected_option_id = submitted_answers.get(question_id)
                available_option_ids = {int(option["optionId"]) for option in row["options"]}
                if selected_option_id is not None and selected_option_id not in available_option_ids:
                    raise invalid_request_error("Submitted option does not belong to the selected question set")
                is_correct = selected_option_id is not None and selected_option_id == int(row["correctOptionId"])
                if is_correct:
                    correct_count += 1
                selected_option_text = next(
                    (option["optionText"] for option in row["options"] if int(option["optionId"]) == selected_option_id),
                    None,
                )
                answer_snapshots.append(
                    {
                        "quiz_question_id": question_id,
                        "selected_option_id": selected_option_id,
                        "is_correct": is_correct,
                        "question_order": int(row["questionOrder"]),
                        "question_text_snapshot": str(row["questionText"]),
                        "explanation_text_snapshot": row.get("explanationText"),
                        "selected_option_text_snapshot": selected_option_text,
                        "correct_option_id_snapshot": int(row["correctOptionId"]),
                        "correct_option_text_snapshot": str(row["correctOptionText"]),
                        "option_order_snapshot_json": [int(option["optionId"]) for option in row["options"]],
                        "option_texts_snapshot_json": row["options"],
                    }
                )

            question_count = len(attempt_session.questions)
            score_percent = (
                (Decimal(correct_count) / Decimal(question_count)) * Decimal("100")
                if question_count
                else Decimal("0.00")
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            is_passed = (
                not is_timed_out
                and quiz.passing_rule == QuizPassingRule.ALL_CORRECT
                and correct_count == question_count
            )

            attempt = self.attempts.create(
                quiz_id=quiz.quiz_id,
                module_id=module.module_id,
                learner_id=attempt_session.learner_id,
                attempt_number=attempt_session.attempt_number,
                question_count=question_count,
                correct_count=correct_count,
                score_percent=score_percent,
                is_passed=is_passed,
                is_timed_out=is_timed_out,
                time_limit_seconds_snapshot=attempt_session.time_limit_seconds,
                started_at=attempt_session.started_at,
                submitted_at=submitted_at,
                duration_seconds=duration_seconds,
            )
            for snapshot in answer_snapshots:
                self.attempt_answers.create(quiz_attempt_id=attempt.quiz_attempt_id, **snapshot)

            module_completed = self._sync_progress_after_attempt(
                course_id=course.course_id,
                module=module,
                learner_id=attempt_session.learner_id,
                accessed_at=submitted_at,
                passed=is_passed,
            )
            self.session.commit()
            if module_completed:
                self.profile_triggers.initialize_newly_unlocked_after_completion(
                    course_id=course.course_id,
                    completed_module_id=module.module_id,
                    learner_id=attempt_session.learner_id,
                )
            self.attempt_sessions.delete_session(attempt_session_token)
            self.session.refresh(attempt)
            return self._to_attempt_result_response(
                attempt=attempt,
                quiz=quiz,
                module=module,
                module_completed=module_completed,
            )
        finally:
            self.attempt_sessions.release_submit_lock(attempt_session_token, lock_value)

    def _build_attempt_session_from_questions(
        self,
        *,
        course,
        module: Module,
        quiz: Quiz,
        learner_id: int,
        selected_questions: list,
        preserve_order: bool,
    ) -> QuizAttemptSessionData:
        question_set_json: list[dict[str, Any]] = []
        for order_index, question in enumerate(selected_questions, start=1):
            option_rows = list(self.options.list_by_question(question.quiz_question_id))
            if quiz.shuffle_options:
                self.random.shuffle(option_rows)
            correct_option = next((option for option in option_rows if option.is_correct), None)
            if correct_option is None:
                raise invalid_request_error("Each quiz attempt question must have exactly one correct option before starting an attempt")
            question_set_json.append(
                {
                    "questionId": question.quiz_question_id,
                    "questionText": question.question_text,
                    "explanationText": question.explanation_text,
                    "questionOrder": order_index if preserve_order else question.sort_order,
                    "correctOptionId": correct_option.quiz_question_option_id,
                    "correctOptionText": correct_option.option_text,
                    "options": [
                        {
                            "optionId": option.quiz_question_option_id,
                            "optionLabel": option.option_label,
                            "optionText": option.option_text,
                            "sortOrder": position,
                        }
                        for position, option in enumerate(option_rows, start=1)
                    ],
                }
            )

        started_at = now_local()
        expires_at = started_at + timedelta(seconds=quiz.time_limit_seconds) if quiz.time_limit_seconds is not None else None
        attempt_number = self.attempt_sessions.issue_attempt_number(
            quiz_id=quiz.quiz_id,
            learner_id=learner_id,
            base_attempt_number=self.attempts.get_max_attempt_number(quiz_id=quiz.quiz_id, learner_id=learner_id),
        )
        attempt_session = QuizAttemptSessionData(
            session_token=secrets.token_urlsafe(24),
            quiz_id=quiz.quiz_id,
            module_id=module.module_id,
            course_id=course.course_id,
            learner_id=learner_id,
            attempt_number=attempt_number,
            question_count=len(question_set_json),
            time_limit_seconds=quiz.time_limit_seconds,
            started_at=started_at,
            expires_at=expires_at,
            questions=question_set_json,
        )
        self.attempt_sessions.create_session(attempt_session)
        if quiz.time_limit_seconds is not None:
            celery_app.send_task(
                "app.tasks.quiz_attempts.auto_submit_quiz_attempt_task",
                args=[attempt_session.session_token],
                countdown=quiz.time_limit_seconds + 10,
                queue=settings.celery_task_default_queue,
            )
        return attempt_session

    def _sync_progress_after_attempt(self, *, course_id: int, module: Module, learner_id: int, accessed_at, passed: bool) -> bool:
        progress = self.module_progress.get_by_module_and_learner(module.module_id, learner_id)
        just_completed = False
        if progress is None:
            self.module_progress.create(
                module_id=module.module_id,
                learner_id=learner_id,
                progress_status=ProgressStatus.COMPLETED if passed else ProgressStatus.IN_PROGRESS,
                progress_percent=Decimal("100.00") if passed else Decimal("0.00"),
                time_spent_seconds=0,
                started_at=accessed_at,
                last_accessed_at=accessed_at,
                completed_at=accessed_at if passed else None,
            )
            just_completed = passed
        elif passed and progress.progress_status != ProgressStatus.COMPLETED:
            self.module_progress.update_progress(
                progress,
                progress_status=ProgressStatus.COMPLETED,
                progress_percent=Decimal("100.00"),
                time_spent_seconds=progress.time_spent_seconds,
                started_at=progress.started_at or accessed_at,
                last_accessed_at=accessed_at,
                completed_at=accessed_at,
            )
            just_completed = True
        else:
            self.module_progress.touch_last_accessed(progress, accessed_at=accessed_at)
        self.enrollment_aggregates.sync_learner_progress_for_course(course_id=course_id, learner_id=learner_id, accessed_at=accessed_at)
        return just_completed

    def _ensure_quiz_publishable(self, quiz: Quiz) -> None:
        active_questions = self.questions.list_active_by_quiz(quiz.quiz_id)
        if len(active_questions) < quiz.question_count_per_attempt:
            raise invalid_request_error("Active question count must be greater than or equal to questionCountPerAttempt before publishing")
        for question in active_questions:
            option_rows = self.options.list_by_question(question.quiz_question_id)
            if len(option_rows) < 2 or sum(1 for option in option_rows if option.is_correct) != 1:
                raise invalid_request_error("Every active question must have at least two options and exactly one correct option")

    def _to_question_response(self, question) -> QuizQuestionResponse:
        return QuizQuestionResponse(
            questionId=question.quiz_question_id,
            questionUuid=encode_quiz_question_uuid(question.quiz_question_id),
            questionText=question.question_text,
            explanationText=question.explanation_text,
            sortOrder=question.sort_order,
            isActive=question.is_active,
            options=[
                QuizOptionResponse(
                    optionId=option.quiz_question_option_id,
                    optionUuid=encode_quiz_option_uuid(option.quiz_question_option_id),
                    optionLabel=option.option_label,
                    optionText=option.option_text,
                    sortOrder=option.sort_order,
                    isCorrect=option.is_correct,
                )
                for option in self.options.list_by_question(question.quiz_question_id)
            ],
        )

    def _to_quiz_authoring_response(self, *, quiz: Quiz, module: Module, include_questions: bool = True) -> QuizAuthoringResponse:
        questions: list[QuizQuestionResponse] = []
        if include_questions:
            for question in self.questions.list_by_quiz(quiz.quiz_id):
                if question.sort_order >= ARCHIVED_QUIZ_SORT_ORDER_BASE:
                    continue  # Skip archived/tombstoned questions
                questions.append(self._to_question_response(question))

        return QuizAuthoringResponse(
            quizId=quiz.quiz_id,
            quizUuid=encode_quiz_uuid(quiz.quiz_id),
            moduleId=module.module_id,
            moduleUuid=encode_module_uuid(module.module_id),
            title=quiz.title,
            description=quiz.description,
            status=quiz.status.value,
            timeLimitSeconds=quiz.time_limit_seconds,
            questionCountPerAttempt=quiz.question_count_per_attempt,
            availableQuestionCount=self.questions.count_by_quiz(quiz.quiz_id, active_only=True),
            shuffleQuestions=quiz.shuffle_questions,
            shuffleOptions=quiz.shuffle_options,
            passingRule=quiz.passing_rule.value,
            publishedAt=quiz.published_at,
            createdAt=quiz.created_at,
            updatedAt=quiz.updated_at,
            questions=questions,
        )

    def _is_generated_attempt_question(self, question) -> bool:
        return bool(
            not question.is_active
            and int(question.sort_order) >= GENERATED_ATTEMPT_QUIZ_SORT_ORDER_BASE
        )

    def _to_attempt_result_response(self, *, attempt, quiz: Quiz, module: Module, module_completed: bool) -> QuizAttemptResultResponse:
        answers = self.attempt_answers.list_by_attempt(attempt.quiz_attempt_id)
        return QuizAttemptResultResponse(
            quizAttemptId=attempt.quiz_attempt_id,
            quizAttemptUuid=encode_quiz_attempt_uuid(attempt.quiz_attempt_id),
            quizId=quiz.quiz_id,
            quizUuid=encode_quiz_uuid(quiz.quiz_id),
            moduleId=module.module_id,
            moduleUuid=encode_module_uuid(module.module_id),
            learnerId=attempt.learner_id,
            attemptNumber=attempt.attempt_number,
            questionCount=attempt.question_count,
            correctCount=attempt.correct_count,
            scorePercent=str(attempt.score_percent),
            isPassed=attempt.is_passed,
            isTimedOut=attempt.is_timed_out,
            moduleCompleted=module_completed,
            timeLimitSeconds=attempt.time_limit_seconds_snapshot,
            startedAt=attempt.started_at,
            submittedAt=attempt.submitted_at,
            durationSeconds=attempt.duration_seconds,
            answers=[
                {
                    "questionId": answer.quiz_question_id,
                    "questionUuid": encode_quiz_question_uuid(answer.quiz_question_id),
                    "questionOrder": answer.question_order,
                    "questionText": answer.question_text_snapshot,
                    "explanationText": answer.explanation_text_snapshot,
                    "selectedOptionId": answer.selected_option_id,
                    "selectedOptionUuid": encode_quiz_option_uuid(answer.selected_option_id) if answer.selected_option_id is not None else None,
                    "selectedOptionText": answer.selected_option_text_snapshot,
                    "correctOptionId": answer.correct_option_id_snapshot,
                    "correctOptionUuid": encode_quiz_option_uuid(answer.correct_option_id_snapshot),
                    "correctOptionText": answer.correct_option_text_snapshot,
                    "isCorrect": answer.is_correct,
                    "optionOrderSnapshot": answer.option_order_snapshot_json,
                    "optionTextsSnapshot": answer.option_texts_snapshot_json,
                }
                for answer in answers
            ],
        )

    def _get_course(self, course_uuid: str):
        course_id = decode_course_uuid(course_uuid)
        course = self.courses.get_by_id(course_id)
        if course is None:
            raise http_error(status_code=status.HTTP_404_NOT_FOUND, code="COURSE_NOT_FOUND", message="Course not found")
        return course

    def _get_course_module(self, *, course_id: int, module_uuid: str) -> Module:
        learning_path = self.learning_paths.get_by_course_id(course_id)
        if learning_path is None:
            raise http_error(status_code=status.HTTP_404_NOT_FOUND, code="LEARNING_PATH_NOT_FOUND", message="Learning path not found")
        module_id = decode_module_uuid(module_uuid)
        module = self.modules.get_by_id(module_id)
        if module is None or module.learning_path_id != learning_path.learning_path_id:
            raise http_error(status_code=status.HTTP_404_NOT_FOUND, code="MODULE_NOT_FOUND", message="Module not found")
        return module

    def _get_module_quiz(self, module_id: int) -> Quiz:
        quiz = self.quizzes.get_by_module_id(module_id)
        if quiz is None:
            raise http_error(status_code=status.HTTP_404_NOT_FOUND, code="QUIZ_NOT_FOUND", message="Quiz not found")
        return quiz

    def _get_manageable_course(self, *, course_uuid: str, current_user: dict):
        actor_id = current_user.get("id")
        if not isinstance(actor_id, int):
            raise invalid_identity_response_error()
        course = self._get_course(course_uuid)
        if current_user.get("identity") == "Admin":
            return course
        if current_user.get("identity") == "Educator" and course.educator_id == actor_id:
            return course
        raise http_error(status_code=status.HTTP_403_FORBIDDEN, code="COURSE_OWNERSHIP_REQUIRED", message="You can only manage quizzes for your own courses")

    def _require_learner_id(self, current_user: dict) -> int:
        learner_id = current_user.get("id")
        if not isinstance(learner_id, int):
            raise invalid_identity_response_error()
        if current_user.get("identity") != "Learner":
            raise http_error(status_code=status.HTTP_403_FORBIDDEN, code="LEARNER_ONLY", message="Only learners can access quiz attempts")
        return learner_id

    def _ensure_learner_can_access_module(self, *, course, module: Module, learner_id: int) -> None:
        if course.status != CourseStatus.PUBLISHED:
            raise http_error(status_code=status.HTTP_404_NOT_FOUND, code="QUIZ_NOT_AVAILABLE", message="Quiz is not available")

        enrollment = self.enrollments.get_by_course_and_learner(course_id=course.course_id, learner_id=learner_id)
        if enrollment is None or enrollment.enrollment_status == EnrollmentStatus.DROPPED:
            raise http_error(status_code=status.HTTP_403_FORBIDDEN, code="ENROLLMENT_REQUIRED", message="Learner must be enrolled before attempting this quiz")
        if module.status != ModuleStatus.PUBLISHED:
            raise http_error(status_code=status.HTTP_404_NOT_FOUND, code="QUIZ_NOT_AVAILABLE", message="Quiz is not available")

    def _ensure_module_unlocked(self, *, module_id: int, learner_id: int) -> None:
        self.unlocking.ensure_module_unlocked(
            module_id=module_id,
            learner_id=learner_id,
            resource_name="quiz",
        )

    def _parse_quiz_status(self, status_value: str) -> QuizStatus:
        try:
            return QuizStatus(status_value.strip().lower())
        except ValueError as exc:
            raise invalid_request_error("status must be one of draft, published, archived") from exc

    def _normalize_required_text(self, value: str | None, *, field_name: str) -> str:
        normalized = self._normalize_optional_text(value)
        if not normalized:
            raise invalid_request_error(f"Quiz {field_name} is required")
        return normalized

    def _normalize_optional_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

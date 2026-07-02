from __future__ import annotations

from datetime import datetime, timezone
import json
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import require_identity_permission
from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.session import get_db_session
from app.services.orchestration.langgraph.checkpointer import build_graph_config, get_langgraph_checkpointer
from app.services.orchestration.langgraph.generated_quiz_attempt_graph import GeneratedQuizAttemptGraphRunner
from app.services.orchestration.langgraph.quiz_generation_graph import QuizGenerationGraphRunner
from app.services.workflows.quiz_generation.services.generation_service import QuizCandidateGenerationService
from app.services.workflows.quiz_generation.services.generation_run_store import QuizGenerationRunStore
from app.services.workflows.quiz_generation.services.learning_quiz_generation_client import LearningQuizGenerationClient
from app.services.workflows.quiz_generation.services.load_inputs_service import QuizGenerationInputService
from app.services.workflows.quiz_generation.services.planning_service import QuizGenerationPlanningService
from app.services.workflows.quiz_generation.services.publishing_service import QuizGenerationPublishingService
from app.services.workflows.quiz_generation.services.retrieval_service import QuizGenerationRetrievalService
from app.services.workflows.quiz_generation.services.validation_service import QuizGenerationValidationService
from app.services.workflows.quiz_generation.schemas import (
    QuizGenerationAuthoringRequest,
    QuizGeneratedAttemptStartResponse,
    QuizGenerationAutoStartRequest,
    QuizGenerationAutoStartRunRequest,
    QuizGenerationRequest,
    QuizGenerationRunStartResponse,
    QuizGenerationRunResponse,
    QuizGenerationRunStatusResponse,
)
from platform_common.permissions.codes import MODULE_UPDATE, QUIZ_ATTEMPT


router = APIRouter(tags=["quiz-generation"])
require_quiz_attempt_permission = require_identity_permission(QUIZ_ATTEMPT)
require_quiz_authoring_permission = require_identity_permission(MODULE_UPDATE)


def _ensure_run_owner(run: dict, *, current_user: dict, course_uuid: str | None = None, module_uuid: str | None = None) -> None:
    if int(run.get("actorId", 0)) != int(current_user["id"]):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz generation run not found.")
    if course_uuid is not None and run.get("courseUuid") != course_uuid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz generation run not found.")
    if module_uuid is not None and run.get("moduleUuid") != module_uuid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz generation run not found.")


def _stream_event(
    *,
    event: str,
    message: str,
    step: str | None = None,
    data: dict | None = None,
) -> bytes:
    payload = {
        "event": event,
        "message": message,
        "step": step,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "data": data or {},
    }
    return (json.dumps(payload, ensure_ascii=True) + "\n").encode("utf-8")


@router.post(
    "/courses/{course_uuid}/modules/{module_uuid}/quiz/authoring/generate",
    response_model=QuizGenerationRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_authoring_quiz_questions(
    course_uuid: str,
    module_uuid: str,
    payload: QuizGenerationAuthoringRequest = Body(default_factory=QuizGenerationAuthoringRequest),
    current_user: dict = Depends(require_quiz_authoring_permission),
    session: Session = Depends(get_db_session),
) -> QuizGenerationRunResponse:
    actor_id = current_user.get("id")
    if not isinstance(actor_id, int):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authenticated user.")
    actor_identity = str(current_user.get("identity") or "")
    LearningQuizGenerationClient().ensure_authoring_quiz_access(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        actor_id=actor_id,
        actor_identity=actor_identity,
    )
    request = QuizGenerationRequest(
        courseUuid=course_uuid,
        moduleUuid=module_uuid,
        educatorId=actor_id,
        additionalInstructions=payload.additionalInstructions,
    )
    thread_id = f"quiz-generation:{actor_id}:{course_uuid}:{module_uuid}:authoring:{uuid4().hex}"
    config = build_graph_config(thread_id=thread_id, checkpoint_ns="quiz_generation")
    return QuizGenerationGraphRunner(
        session,
        checkpointer=get_langgraph_checkpointer(),
    ).run(payload=request, config=config)


@router.post(
    "/courses/{course_uuid}/modules/{module_uuid}/quiz/generated-attempt-sessions/auto/runs",
    response_model=QuizGenerationRunStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_auto_generated_quiz_attempt_run(
    course_uuid: str,
    module_uuid: str,
    payload: QuizGenerationAutoStartRequest = Body(default_factory=QuizGenerationAutoStartRequest),
    current_user: dict = Depends(require_quiz_attempt_permission),
) -> QuizGenerationRunStartResponse:
    actor_id = int(current_user["id"])
    LearningQuizGenerationClient().ensure_learner_quiz_access(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        learner_id=actor_id,
    )
    run, created = QuizGenerationRunStore().create_or_get_active_run(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        actor_id=actor_id,
        additional_instructions=payload.additionalInstructions,
    )
    if created:
        celery_app.send_task(
            "app.tasks.quiz_generation.generate_quiz_attempt_run_task",
            args=[run["runId"]],
            queue=settings.celery_task_default_queue,
        )
    return QuizGenerationRunStartResponse(runId=run["runId"], status=run["status"])


@router.get(
    "/courses/{course_uuid}/modules/{module_uuid}/quiz/generated-attempt-sessions/auto/runs/active",
    response_model=QuizGenerationRunStatusResponse,
)
def get_active_course_quiz_generation_run(
    course_uuid: str,
    module_uuid: str,
    current_user: dict = Depends(require_quiz_attempt_permission),
) -> QuizGenerationRunStatusResponse:
    run = QuizGenerationRunStore().get_active_run(
        actor_id=int(current_user["id"]),
        course_uuid=course_uuid,
        module_uuid=module_uuid,
    )
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz generation run not found.")
    _ensure_run_owner(run, current_user=current_user, course_uuid=course_uuid, module_uuid=module_uuid)
    return QuizGenerationRunStatusResponse.model_validate(run)


@router.get(
    "/quiz-generation/runs/{run_id}",
    response_model=QuizGenerationRunStatusResponse,
)
def get_quiz_generation_run(
    run_id: str,
    current_user: dict = Depends(require_quiz_attempt_permission),
) -> QuizGenerationRunStatusResponse:
    run = QuizGenerationRunStore().get_run(run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz generation run not found.")
    _ensure_run_owner(run, current_user=current_user)
    return QuizGenerationRunStatusResponse.model_validate(run)


@router.get(
    "/courses/{course_uuid}/modules/{module_uuid}/quiz/generated-attempt-sessions/auto/runs/{run_id}",
    response_model=QuizGenerationRunStatusResponse,
)
def get_course_quiz_generation_run(
    course_uuid: str,
    module_uuid: str,
    run_id: str,
    current_user: dict = Depends(require_quiz_attempt_permission),
) -> QuizGenerationRunStatusResponse:
    run = QuizGenerationRunStore().get_run(run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz generation run not found.")
    _ensure_run_owner(run, current_user=current_user, course_uuid=course_uuid, module_uuid=module_uuid)
    return QuizGenerationRunStatusResponse.model_validate(run)


@router.post(
    "/courses/{course_uuid}/modules/{module_uuid}/quiz/generated-attempt-sessions/auto",
    response_model=QuizGeneratedAttemptStartResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def start_auto_generated_quiz_attempt(
    course_uuid: str,
    module_uuid: str,
    payload: QuizGenerationAutoStartRequest = Body(default_factory=QuizGenerationAutoStartRequest),
    current_user: dict = Depends(require_quiz_attempt_permission),
    session: Session = Depends(get_db_session),
) -> QuizGeneratedAttemptStartResponse:
    request = QuizGenerationAutoStartRunRequest.model_validate(
        {
            "courseUuid": course_uuid,
            "moduleUuid": module_uuid,
            "actorId": int(current_user["id"]),
            "additionalInstructions": payload.additionalInstructions,
        }
    )
    LearningQuizGenerationClient().ensure_learner_quiz_access(
        course_uuid=request.courseUuid,
        module_uuid=request.moduleUuid,
        learner_id=request.actorId,
    )

    thread_id = (
        f"quiz-generation:{request.actorId}:{request.courseUuid}:{request.moduleUuid}:"
        f"learner-start:{uuid4().hex}"
    )
    config = build_graph_config(thread_id=thread_id, checkpoint_ns="quiz_generation")
    return GeneratedQuizAttemptGraphRunner(
        session,
        checkpointer=get_langgraph_checkpointer(),
    ).run(payload=request, config=config)


@router.post(
    "/courses/{course_uuid}/modules/{module_uuid}/quiz/generated-attempt-sessions/auto/stream",
    status_code=status.HTTP_200_OK,
)
def stream_auto_generated_quiz_attempt(
    course_uuid: str,
    module_uuid: str,
    payload: QuizGenerationAutoStartRequest = Body(default_factory=QuizGenerationAutoStartRequest),
    current_user: dict = Depends(require_quiz_attempt_permission),
    session: Session = Depends(get_db_session),
) -> StreamingResponse:
    actor_id = int(current_user["id"])
    LearningQuizGenerationClient().ensure_learner_quiz_access(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        learner_id=actor_id,
    )

    def event_stream():
        try:
            request = QuizGenerationAutoStartRunRequest.model_validate(
                {
                    "courseUuid": course_uuid,
                    "moduleUuid": module_uuid,
                    "actorId": actor_id,
                    "additionalInstructions": payload.additionalInstructions,
                }
            )
            generation_request = QuizGenerationRequest(
                courseUuid=request.courseUuid,
                moduleUuid=request.moduleUuid,
                educatorId=request.actorId,
                learnerId=request.actorId,
                additionalInstructions=request.additionalInstructions,
            )

            yield _stream_event(
                event="started",
                step="graph",
                message="Starting generated quiz attempt graph.",
                data={
                    "courseUuid": request.courseUuid,
                    "moduleUuid": request.moduleUuid,
                    "actorId": request.actorId,
                },
            )

            yield _stream_event(event="step_started", step="load_inputs", message="Loading quiz generation context.")
            input_service = QuizGenerationInputService(session=session)
            context = input_service.load_context(payload=generation_request)
            profile_context = input_service.load_profile_context(payload=generation_request)
            yield _stream_event(
                event="step_completed",
                step="load_inputs",
                message="Loaded quiz configuration.",
                data={
                    "quizTitle": context.quizTitle,
                    "questionCountPerAttempt": context.questionCountPerAttempt,
                    "availableQuestionCount": context.availableQuestionCount,
                    "profileContextLoaded": profile_context is not None,
                },
            )

            yield _stream_event(event="step_started", step="retrieve_context", message="Retrieving supporting module context.")
            retrieval_context = QuizGenerationRetrievalService(session).load_context(
                educator_id=generation_request.educatorId,
                course_uuid=generation_request.courseUuid,
                module_uuid=generation_request.moduleUuid,
                quiz_title=context.quizTitle,
                module_title=context.moduleTitle,
                question_count=context.questionCountPerAttempt,
                additional_instructions=generation_request.additionalInstructions,
            )
            yield _stream_event(
                event="step_completed",
                step="retrieve_context",
                message="Retrieved module context for question generation.",
                data={
                    "usedRetrieval": retrieval_context.usedRetrieval,
                    "chunkCount": retrieval_context.chunkCount,
                    "topK": retrieval_context.topK,
                },
            )

            yield _stream_event(event="step_started", step="plan_quiz", message="Planning quiz structure with the AI model.")
            plan = QuizGenerationPlanningService().build_plan(
                request=generation_request,
                context=context,
                retrieval_context=retrieval_context,
                profile_context=profile_context,
            )
            yield _stream_event(
                event="step_completed",
                step="plan_quiz",
                message="Quiz plan created.",
                data={
                    "plannedQuestionCount": plan.plannedQuestionCount,
                    "titleSuggestion": plan.titleSuggestion,
                },
            )

            yield _stream_event(event="step_started", step="generate_quiz", message="Generating quiz questions.")
            candidate_set = QuizCandidateGenerationService().generate_candidates(
                request=generation_request,
                context=context,
                retrieval_context=retrieval_context,
                plan=plan,
                profile_context=profile_context,
            )
            yield _stream_event(
                event="step_completed",
                step="generate_quiz",
                message="Generated candidate questions.",
                data={"questionCount": candidate_set.questionCount},
            )

            yield _stream_event(event="step_started", step="validate_quiz", message="Validating generated questions.")
            validated_candidate_set = QuizGenerationValidationService().validate_candidate_set(
                candidate_set=candidate_set,
                required_question_count=context.questionCountPerAttempt,
            )
            yield _stream_event(
                event="step_completed",
                step="validate_quiz",
                message="Generated questions passed validation.",
                data={"questionCount": validated_candidate_set.questionCount},
            )

            yield _stream_event(event="step_started", step="publish_quiz", message="Saving generated questions.")
            created_questions = QuizGenerationPublishingService().publish_generated_questions(
                course_uuid=generation_request.courseUuid,
                module_uuid=generation_request.moduleUuid,
                candidate_set=validated_candidate_set,
                purpose="attempt",
            )
            yield _stream_event(
                event="step_completed",
                step="publish_quiz",
                message="Saved generated quiz questions.",
                data={"createdQuestionCount": len(created_questions)},
            )

            yield _stream_event(event="step_started", step="start_generated_attempt", message="Starting generated quiz session.")
            attempt_start_response = LearningQuizGenerationClient().start_generated_attempt_internal(
                course_uuid=request.courseUuid,
                module_uuid=request.moduleUuid,
                learner_id=request.actorId,
                question_uuids=[question.questionUuid for question in created_questions],
            )
            yield _stream_event(
                event="step_completed",
                step="start_generated_attempt",
                message="Generated quiz session is ready.",
                data={
                    "attemptNumber": attempt_start_response.attemptNumber,
                    "questionCount": attempt_start_response.questionCount,
                },
            )

            yield _stream_event(
                event="result",
                step="graph",
                message="Generated quiz attempt graph completed.",
                data={"attemptStartResponse": attempt_start_response.model_dump(mode="json")},
            )
        except Exception as exc:
            yield _stream_event(
                event="error",
                step="graph",
                message=str(exc) or "Quiz generation failed.",
            )

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

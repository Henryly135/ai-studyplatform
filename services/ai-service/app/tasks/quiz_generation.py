from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.workflows.quiz_generation.schemas import (
    QuizGenerationAutoStartRunRequest,
    QuizGenerationRequest,
)
from app.services.workflows.quiz_generation.services.generation_run_store import QuizGenerationRunStore
from app.services.workflows.quiz_generation.services.generation_service import QuizCandidateGenerationService
from app.services.workflows.quiz_generation.services.learning_quiz_generation_client import LearningQuizGenerationClient
from app.services.workflows.quiz_generation.services.load_inputs_service import QuizGenerationInputService
from app.services.workflows.quiz_generation.services.planning_service import QuizGenerationPlanningService
from app.services.workflows.quiz_generation.services.publishing_service import QuizGenerationPublishingService
from app.services.workflows.quiz_generation.services.retrieval_service import QuizGenerationRetrievalService
from app.services.workflows.quiz_generation.services.validation_service import QuizGenerationValidationService


@celery_app.task(name="app.tasks.quiz_generation.generate_quiz_attempt_run_task")
def generate_quiz_attempt_run_task(run_id: str) -> dict[str, object]:
    store = QuizGenerationRunStore()
    run = store.get_run(run_id)
    if not run:
        return {"status": "not_found", "runId": run_id}

    session: Session = SessionLocal()
    try:
        request = QuizGenerationAutoStartRunRequest.model_validate(
            {
                "courseUuid": run["courseUuid"],
                "moduleUuid": run["moduleUuid"],
                "actorId": run["actorId"],
                "additionalInstructions": run.get("additionalInstructions"),
            }
        )
        generation_request = QuizGenerationRequest(
            courseUuid=request.courseUuid,
            moduleUuid=request.moduleUuid,
            educatorId=request.actorId,
            learnerId=request.actorId,
            additionalInstructions=request.additionalInstructions,
        )

        store.mark_running(run_id, step="load_inputs", message="Loading quiz generation context.")
        input_service = QuizGenerationInputService(session=session)
        context = input_service.load_context(payload=generation_request)
        profile_context = input_service.load_profile_context(payload=generation_request)
        store.mark_step_completed(
            run_id,
            step="load_inputs",
            message="Loaded quiz configuration.",
            data={
                "quizTitle": context.quizTitle,
                "questionCountPerAttempt": context.questionCountPerAttempt,
                "availableQuestionCount": context.availableQuestionCount,
                "profileContextLoaded": profile_context is not None,
            },
        )

        store.mark_running(run_id, step="retrieve_context", message="Retrieving supporting module context.")
        retrieval_context = QuizGenerationRetrievalService(session).load_context(
            educator_id=generation_request.educatorId,
            course_uuid=generation_request.courseUuid,
            module_uuid=generation_request.moduleUuid,
            quiz_title=context.quizTitle,
            module_title=context.moduleTitle,
            question_count=context.questionCountPerAttempt,
            additional_instructions=generation_request.additionalInstructions,
        )
        store.mark_step_completed(
            run_id,
            step="retrieve_context",
            message="Retrieved module context for question generation.",
            data={
                "usedRetrieval": retrieval_context.usedRetrieval,
                "chunkCount": retrieval_context.chunkCount,
                "topK": retrieval_context.topK,
            },
        )

        store.mark_running(run_id, step="plan_quiz", message="Planning quiz structure with the AI model.")
        plan = QuizGenerationPlanningService().build_plan(
            request=generation_request,
            context=context,
            retrieval_context=retrieval_context,
            profile_context=profile_context,
        )
        store.mark_step_completed(
            run_id,
            step="plan_quiz",
            message="Quiz plan created.",
            data={"plannedQuestionCount": plan.plannedQuestionCount, "titleSuggestion": plan.titleSuggestion},
        )

        store.mark_running(run_id, step="generate_quiz", message="Generating quiz questions.")
        candidate_set = QuizCandidateGenerationService().generate_candidates(
            request=generation_request,
            context=context,
            retrieval_context=retrieval_context,
            plan=plan,
            profile_context=profile_context,
        )
        store.mark_step_completed(
            run_id,
            step="generate_quiz",
            message="Generated candidate questions.",
            data={"questionCount": candidate_set.questionCount},
        )

        store.mark_running(run_id, step="validate_quiz", message="Validating generated questions.")
        validated_candidate_set = QuizGenerationValidationService().validate_candidate_set(
            candidate_set=candidate_set,
            required_question_count=context.questionCountPerAttempt,
        )
        store.mark_step_completed(
            run_id,
            step="validate_quiz",
            message="Generated questions passed validation.",
            data={"questionCount": validated_candidate_set.questionCount},
        )

        store.mark_running(run_id, step="publish_quiz", message="Saving generated questions.")
        created_questions = QuizGenerationPublishingService().publish_generated_questions(
            course_uuid=generation_request.courseUuid,
            module_uuid=generation_request.moduleUuid,
            candidate_set=validated_candidate_set,
            purpose="attempt",
        )
        store.mark_step_completed(
            run_id,
            step="publish_quiz",
            message="Saved generated quiz questions.",
            data={"createdQuestionCount": len(created_questions)},
        )

        store.mark_running(run_id, step="start_generated_attempt", message="Starting generated quiz session.")
        attempt_start_response = LearningQuizGenerationClient().start_generated_attempt_internal(
            course_uuid=request.courseUuid,
            module_uuid=request.moduleUuid,
            learner_id=request.actorId,
            question_uuids=[question.questionUuid for question in created_questions],
        )
        attempt_payload = attempt_start_response.model_dump(mode="json")
        store.mark_step_completed(
            run_id,
            step="start_generated_attempt",
            message="Generated quiz session is ready.",
            data={
                "attemptNumber": attempt_start_response.attemptNumber,
                "questionCount": attempt_start_response.questionCount,
            },
        )
        store.complete_run(run_id, attempt_start_response=attempt_payload)
        return {"status": "completed", "runId": run_id}
    except Exception as exc:
        message = str(exc) or "Quiz generation failed."
        store.fail_run(run_id, message=message)
        return {"status": "failed", "runId": run_id, "error": message}
    finally:
        session.close()

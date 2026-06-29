from __future__ import annotations

from fastapi import status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models.study_plans import StudyPlan, StudyPlanStatus
from app.repositories.study_plan_repository import StudyPlanRepository
from app.schemas.study_planner import (
    StudyPlanContent,
    StudyPlanCreateRequest,
    StudyPlanGenerationMetadata,
    StudyPlanResponse,
    StudyPlanUpdateRequest,
)
from app.services.study_planner_ai_client import StudyPlannerAIClient
from platform_common.errors import http_error, invalid_identity_response_error


class StudyPlannerService:
    def __init__(self, session: Session, *, ai_client: StudyPlannerAIClient | None = None) -> None:
        self.session = session
        self.plans = StudyPlanRepository(session)
        self.ai_client = ai_client or StudyPlannerAIClient()

    def create_plan(self, *, payload: StudyPlanCreateRequest, current_user: dict) -> StudyPlanResponse:
        learner_id = self._require_learner(current_user)
        generation = self.ai_client.generate_plan(payload)
        plan_content = self._extract_plan_content(generation)
        title = self._title_from_goal(payload.goal)
        plan = self.plans.create(
            learner_id=learner_id,
            title=title,
            input_json=payload.model_dump(mode="json"),
            plan_json=plan_content.model_dump(),
            provider_name=self._optional_str(generation.get("provider")),
            provider_model=self._optional_str(generation.get("model")),
            used_fallback=bool(generation.get("usedFallback", False)),
            fallback_reason=self._optional_str(generation.get("fallbackReason")),
        )
        self.session.commit()
        return self.to_response(plan)

    def list_plans(self, *, current_user: dict) -> list[StudyPlanResponse]:
        learner_id = self._require_learner(current_user)
        return [self.to_response(plan) for plan in self.plans.list_by_learner(learner_id)]

    def get_plan(self, *, plan_uuid: str, current_user: dict) -> StudyPlanResponse:
        learner_id = self._require_learner(current_user)
        return self.to_response(self._get_owned_plan(plan_uuid=plan_uuid, learner_id=learner_id))

    def update_plan(
        self,
        *,
        plan_uuid: str,
        payload: StudyPlanUpdateRequest,
        current_user: dict,
    ) -> StudyPlanResponse:
        learner_id = self._require_learner(current_user)
        plan = self._get_owned_plan(plan_uuid=plan_uuid, learner_id=learner_id)
        update_kwargs = {}
        if payload.title is not None:
            update_kwargs["title"] = payload.title
        if payload.status is not None:
            update_kwargs["status"] = StudyPlanStatus(payload.status)
        if payload.planContent is not None:
            update_kwargs["plan_json"] = payload.planContent.model_dump()
        if "adjustmentNotes" in payload.model_fields_set:
            update_kwargs["adjustment_notes"] = payload.adjustmentNotes
        updated = self.plans.update(plan, **update_kwargs)
        self.session.commit()
        return self.to_response(updated)

    def regenerate_plan(self, *, plan_uuid: str, current_user: dict) -> StudyPlanResponse:
        learner_id = self._require_learner(current_user)
        plan = self._get_owned_plan(plan_uuid=plan_uuid, learner_id=learner_id)
        payload = StudyPlanCreateRequest.model_validate(plan.input_json)
        generation = self.ai_client.generate_plan(payload)
        plan_content = self._extract_plan_content(generation)
        updated = self.plans.update(
            plan,
            plan_json=plan_content.model_dump(),
            provider_name=self._optional_str(generation.get("provider")),
            provider_model=self._optional_str(generation.get("model")),
            used_fallback=bool(generation.get("usedFallback", False)),
            fallback_reason=self._optional_str(generation.get("fallbackReason")),
        )
        self.session.commit()
        return self.to_response(updated)

    def to_response(self, plan: StudyPlan) -> StudyPlanResponse:
        return StudyPlanResponse(
            planUuid=plan.plan_uuid,
            learnerId=plan.learner_id,
            title=plan.title,
            status=plan.status.value if isinstance(plan.status, StudyPlanStatus) else str(plan.status),
            input=plan.input_json,
            planContent=StudyPlanContent.model_validate(plan.plan_json),
            generation=StudyPlanGenerationMetadata(
                provider=plan.provider_name,
                model=plan.provider_model,
                usedFallback=plan.used_fallback,
                fallbackReason=plan.fallback_reason,
            ),
            adjustmentNotes=plan.adjustment_notes,
            createdAt=plan.created_at,
            updatedAt=plan.updated_at,
        )

    def _require_learner(self, current_user: dict) -> int:
        learner_id = current_user.get("id")
        if not isinstance(learner_id, int):
            raise invalid_identity_response_error()
        if current_user.get("identity") != "Learner":
            raise http_error(
                status_code=status.HTTP_403_FORBIDDEN,
                code="LEARNER_REQUIRED",
                message="Study Planner is available to learner accounts only",
            )
        return learner_id

    def _get_owned_plan(self, *, plan_uuid: str, learner_id: int) -> StudyPlan:
        plan = self.plans.get_by_uuid(plan_uuid)
        if not plan or plan.learner_id != learner_id:
            raise http_error(
                status_code=status.HTTP_404_NOT_FOUND,
                code="STUDY_PLAN_NOT_FOUND",
                message="Study plan not found",
            )
        return plan

    def _extract_plan_content(self, generation: dict) -> StudyPlanContent:
        plan_content = generation.get("planContent")
        if not isinstance(plan_content, dict):
            raise http_error(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="INVALID_AI_STUDY_PLAN_RESPONSE",
                message="AI service returned an invalid study plan",
            )
        try:
            return StudyPlanContent.model_validate(plan_content)
        except ValidationError as exc:
            raise http_error(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="INVALID_AI_STUDY_PLAN_RESPONSE",
                message="AI service returned an invalid study plan",
            ) from exc

    def _title_from_goal(self, goal: str) -> str:
        normalized = " ".join(goal.split())
        if len(normalized) <= 80:
            return normalized
        return normalized[:77].rstrip() + "..."

    def _optional_str(self, value: object) -> str | None:
        return value if isinstance(value, str) and value else None

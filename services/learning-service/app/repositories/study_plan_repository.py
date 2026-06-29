from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.study_plans import StudyPlan, StudyPlanStatus

_UNSET = object()


class StudyPlanRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_uuid(self, plan_uuid: str) -> StudyPlan | None:
        stmt = select(StudyPlan).where(StudyPlan.plan_uuid == plan_uuid)
        return self.session.scalar(stmt)

    def list_by_learner(self, learner_id: int) -> list[StudyPlan]:
        stmt = (
            select(StudyPlan)
            .where(StudyPlan.learner_id == learner_id)
            .order_by(StudyPlan.updated_at.desc(), StudyPlan.plan_id.desc())
        )
        return list(self.session.scalars(stmt))

    def create(
        self,
        *,
        learner_id: int,
        title: str,
        input_json: dict[str, Any],
        plan_json: dict[str, Any],
        provider_name: str | None,
        provider_model: str | None,
        used_fallback: bool,
        fallback_reason: str | None,
    ) -> StudyPlan:
        plan = StudyPlan(
            learner_id=learner_id,
            title=title,
            status=StudyPlanStatus.ACTIVE,
            input_json=input_json,
            plan_json=plan_json,
            provider_name=provider_name,
            provider_model=provider_model,
            used_fallback=used_fallback,
            fallback_reason=fallback_reason,
        )
        self.session.add(plan)
        self.session.flush()
        return plan

    def update(
        self,
        plan: StudyPlan,
        *,
        title: str | object = _UNSET,
        status: StudyPlanStatus | object = _UNSET,
        plan_json: dict[str, Any] | object = _UNSET,
        provider_name: str | None | object = _UNSET,
        provider_model: str | None | object = _UNSET,
        used_fallback: bool | object = _UNSET,
        fallback_reason: str | None | object = _UNSET,
        adjustment_notes: str | None | object = _UNSET,
    ) -> StudyPlan:
        if title is not _UNSET:
            plan.title = title
        if status is not _UNSET:
            plan.status = status
        if plan_json is not _UNSET:
            plan.plan_json = plan_json
        if provider_name is not _UNSET:
            plan.provider_name = provider_name
        if provider_model is not _UNSET:
            plan.provider_model = provider_model
        if used_fallback is not _UNSET:
            plan.used_fallback = used_fallback
        if fallback_reason is not _UNSET:
            plan.fallback_reason = fallback_reason
        if adjustment_notes is not _UNSET:
            plan.adjustment_notes = adjustment_notes
        self.session.flush()
        return plan

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.short_answer_assessments import ShortAnswerAssessment, ShortAnswerAssessmentStatus

_UNSET = object()


class ShortAnswerAssessmentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, assessment_id: int) -> ShortAnswerAssessment | None:
        return self.session.get(ShortAnswerAssessment, assessment_id)

    def get_by_uuid(self, assessment_uuid: str) -> ShortAnswerAssessment | None:
        stmt = select(ShortAnswerAssessment).where(ShortAnswerAssessment.assessment_uuid == assessment_uuid)
        return self.session.scalar(stmt)

    def get_by_module_id(self, module_id: int) -> ShortAnswerAssessment | None:
        stmt = select(ShortAnswerAssessment).where(ShortAnswerAssessment.module_id == module_id)
        return self.session.scalar(stmt)

    def create(
        self,
        *,
        module_id: int,
        title: str,
        prompt_text: str,
        rubric_text: str,
        max_score: Decimal,
        status: ShortAnswerAssessmentStatus,
        created_by: int | None,
        updated_by: int | None,
        published_at: datetime | None,
    ) -> ShortAnswerAssessment:
        assessment = ShortAnswerAssessment(
            module_id=module_id,
            title=title,
            prompt_text=prompt_text,
            rubric_text=rubric_text,
            max_score=max_score,
            status=status,
            created_by=created_by,
            updated_by=updated_by,
            published_at=published_at,
        )
        self.session.add(assessment)
        self.session.flush()
        return assessment

    def update(
        self,
        assessment: ShortAnswerAssessment,
        *,
        title: str | object = _UNSET,
        prompt_text: str | object = _UNSET,
        rubric_text: str | object = _UNSET,
        max_score: Decimal | object = _UNSET,
        status: ShortAnswerAssessmentStatus | object = _UNSET,
        updated_by: int | None | object = _UNSET,
        published_at: datetime | None | object = _UNSET,
    ) -> ShortAnswerAssessment:
        if title is not _UNSET:
            assessment.title = title
        if prompt_text is not _UNSET:
            assessment.prompt_text = prompt_text
        if rubric_text is not _UNSET:
            assessment.rubric_text = rubric_text
        if max_score is not _UNSET:
            assessment.max_score = max_score
        if status is not _UNSET:
            assessment.status = status
        if updated_by is not _UNSET:
            assessment.updated_by = updated_by
        if published_at is not _UNSET:
            assessment.published_at = published_at
        self.session.flush()
        return assessment

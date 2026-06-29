from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.educator_content_drafts import EducatorContentDraft, EducatorContentDraftType

_UNSET = object()


class EducatorContentDraftRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, draft_id: int) -> EducatorContentDraft | None:
        return self.session.get(EducatorContentDraft, draft_id)

    def list_by_module(self, module_id: int) -> list[EducatorContentDraft]:
        stmt = (
            select(EducatorContentDraft)
            .where(EducatorContentDraft.module_id == module_id)
            .order_by(EducatorContentDraft.updated_at.desc(), EducatorContentDraft.content_draft_id.desc())
        )
        return list(self.session.scalars(stmt))

    def create(
        self,
        *,
        module_id: int,
        content_type: EducatorContentDraftType,
        title: str,
        teacher_prompt: str | None,
        material_scope: str | None,
        structured_content_json: dict[str, Any],
        grounding_json: list[dict[str, Any]],
        confidence_score: Decimal,
        is_fallback: bool,
        fallback_reason: str | None,
        provider_name: str | None,
        provider_model: str | None,
        created_by: int | None,
        updated_by: int | None,
    ) -> EducatorContentDraft:
        draft = EducatorContentDraft(
            module_id=module_id,
            content_type=content_type,
            title=title,
            teacher_prompt=teacher_prompt,
            material_scope=material_scope,
            structured_content_json=structured_content_json,
            grounding_json=grounding_json,
            confidence_score=confidence_score,
            is_fallback=is_fallback,
            fallback_reason=fallback_reason,
            provider_name=provider_name,
            provider_model=provider_model,
            created_by=created_by,
            updated_by=updated_by,
        )
        self.session.add(draft)
        self.session.flush()
        return draft

    def update(
        self,
        draft: EducatorContentDraft,
        *,
        title: str | object = _UNSET,
        structured_content_json: dict[str, Any] | object = _UNSET,
        grounding_json: list[dict[str, Any]] | object = _UNSET,
        updated_by: int | None | object = _UNSET,
    ) -> EducatorContentDraft:
        if title is not _UNSET:
            draft.title = title
        if structured_content_json is not _UNSET:
            draft.structured_content_json = structured_content_json
        if grounding_json is not _UNSET:
            draft.grounding_json = grounding_json
        if updated_by is not _UNSET:
            draft.updated_by = updated_by
        self.session.flush()
        return draft

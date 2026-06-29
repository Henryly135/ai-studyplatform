from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import re
from typing import Any

from fastapi import status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.uuid_codec import decode_content_draft_uuid, decode_course_uuid, decode_module_uuid, encode_content_draft_uuid, encode_module_uuid
from app.models.educator_content_drafts import EducatorContentDraft, EducatorContentDraftType
from app.models.module_materials import ModuleMaterial
from app.models.modules import Module
from app.repositories.course_repository import CourseRepository
from app.repositories.educator_content_draft_repository import EducatorContentDraftRepository
from app.repositories.learning_path_repository import LearningPathRepository
from app.repositories.module_material_repository import ModuleMaterialRepository
from app.repositories.module_repository import ModuleRepository
from app.schemas.content_generation import (
    ContentDraftAIResponse,
    ContentDraftGenerateRequest,
    ContentDraftGroundingItem,
    ContentDraftResponse,
    ContentDraftUpdateRequest,
)
from app.services.educator_content_generation_ai_client import EducatorContentGenerationAIClient
from platform_common.errors import http_error, invalid_identity_response_error, invalid_request_error


class EducatorContentDraftService:
    def __init__(self, session: Session, *, ai_client: EducatorContentGenerationAIClient | None = None) -> None:
        self.session = session
        self.courses = CourseRepository(session)
        self.learning_paths = LearningPathRepository(session)
        self.modules = ModuleRepository(session)
        self.materials = ModuleMaterialRepository(session)
        self.drafts = EducatorContentDraftRepository(session)
        self.ai_client = ai_client or EducatorContentGenerationAIClient()

    def generate_draft(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        payload: ContentDraftGenerateRequest,
        current_user: dict,
    ) -> ContentDraftResponse:
        actor_id = self._require_actor_id(current_user)
        course = self._get_manageable_course(course_uuid=course_uuid, current_user=current_user)
        module = self._get_course_module(course_id=course.course_id, module_uuid=module_uuid)
        material_rows = self.materials.list_by_module(module.module_id)
        teacher_prompt = self._normalize_optional_text(payload.teacherPrompt)
        material_scope = self._normalize_optional_text(payload.materialScope)

        if not teacher_prompt and not material_rows and not self._normalize_optional_text(module.content):
            raise invalid_request_error("teacherPrompt, module content, or module materials are required")

        generation = self._generate_with_ai(
            course_uuid=course_uuid,
            module_uuid=module_uuid,
            actor_id=actor_id,
            course_title=course.title,
            module=module,
            content_type=payload.contentType,
            material_scope=material_scope,
            teacher_prompt=teacher_prompt,
            materials=material_rows,
        )
        title = self._normalize_optional_text(payload.title) or generation.title

        try:
            draft = self.drafts.create(
                module_id=module.module_id,
                content_type=EducatorContentDraftType(payload.contentType),
                title=title,
                teacher_prompt=teacher_prompt,
                material_scope=material_scope,
                structured_content_json=generation.structuredContent,
                grounding_json=[item.model_dump(mode="json") for item in generation.grounding],
                confidence_score=self._quantize_confidence(generation.confidenceScore),
                is_fallback=generation.isFallback,
                fallback_reason=generation.fallbackReason,
                provider_name=generation.provider,
                provider_model=generation.model,
                created_by=actor_id,
                updated_by=actor_id,
            )
            self.session.commit()
            self.session.refresh(draft)
        except Exception:
            if hasattr(self.session, "rollback"):
                self.session.rollback()
            raise

        return self._to_response(draft, module=module)

    def list_drafts(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        current_user: dict,
    ) -> list[ContentDraftResponse]:
        course = self._get_manageable_course(course_uuid=course_uuid, current_user=current_user)
        module = self._get_course_module(course_id=course.course_id, module_uuid=module_uuid)
        return [self._to_response(draft, module=module) for draft in self.drafts.list_by_module(module.module_id)]

    def get_draft(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        draft_uuid: str,
        current_user: dict,
    ) -> ContentDraftResponse:
        course = self._get_manageable_course(course_uuid=course_uuid, current_user=current_user)
        module = self._get_course_module(course_id=course.course_id, module_uuid=module_uuid)
        draft = self._get_module_draft(module_id=module.module_id, draft_uuid=draft_uuid)
        return self._to_response(draft, module=module)

    def update_draft(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        draft_uuid: str,
        payload: ContentDraftUpdateRequest,
        current_user: dict,
    ) -> ContentDraftResponse:
        actor_id = self._require_actor_id(current_user)
        course = self._get_manageable_course(course_uuid=course_uuid, current_user=current_user)
        module = self._get_course_module(course_id=course.course_id, module_uuid=module_uuid)
        draft = self._get_module_draft(module_id=module.module_id, draft_uuid=draft_uuid)

        update_kwargs: dict[str, Any] = {"updated_by": actor_id}
        if payload.title is not None:
            update_kwargs["title"] = self._normalize_required_text(payload.title, "title")
        if payload.structuredContent is not None:
            update_kwargs["structured_content_json"] = payload.structuredContent
        if payload.grounding is not None:
            update_kwargs["grounding_json"] = [item.model_dump(mode="json") for item in payload.grounding]
        updated = self.drafts.update(draft, **update_kwargs)
        self.session.commit()
        self.session.refresh(updated)
        return self._to_response(updated, module=module)

    def _generate_with_ai(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        actor_id: int,
        course_title: str,
        module: Module,
        content_type: str,
        material_scope: str | None,
        teacher_prompt: str | None,
        materials: list[ModuleMaterial],
    ) -> ContentDraftAIResponse:
        response = self.ai_client.generate_draft(
            course_uuid=course_uuid,
            module_uuid=module_uuid,
            educator_id=actor_id,
            course_title=course_title,
            module_title=module.title,
            module_description=module.description,
            module_content=module.content,
            content_type=content_type,
            material_scope=material_scope,
            teacher_prompt=teacher_prompt,
            materials=[self._material_payload(material) for material in materials],
        )
        try:
            generation = ContentDraftAIResponse.model_validate(response)
        except (TypeError, ValidationError) as exc:
            raise http_error(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="INVALID_AI_CONTENT_DRAFT_RESPONSE",
                message="AI service returned an invalid content draft",
            ) from exc
        if generation.contentType != content_type:
            raise http_error(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="INVALID_AI_CONTENT_DRAFT_RESPONSE",
                message="AI service returned an invalid content draft",
            )
        if not self._grounding_matches_module(generation, module=module, materials=materials):
            raise http_error(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="INVALID_AI_CONTENT_DRAFT_RESPONSE",
                message="AI service returned ungrounded content draft sources",
            )
        return generation

    def _grounding_matches_module(
        self,
        generation: ContentDraftAIResponse,
        *,
        module: Module,
        materials: list[ModuleMaterial],
    ) -> bool:
        allowed_titles = [module.title, *(material.title for material in materials)]
        return all(self._source_title_matches(item.sourceTitle, allowed_titles) for item in generation.grounding)

    def _source_title_matches(self, source_title: str, allowed_titles: list[str]) -> bool:
        normalized_source = self._normalize_match_text(source_title)
        if not normalized_source:
            return False
        for title in allowed_titles:
            normalized_title = self._normalize_match_text(title)
            if normalized_title and (
                normalized_source == normalized_title
                or normalized_title in normalized_source
                or normalized_source in normalized_title
            ):
                return True
        return False

    def _material_payload(self, material: ModuleMaterial) -> dict[str, Any]:
        metadata = material.metadata_json if isinstance(material.metadata_json, dict) else {}
        summary = self._first_string(metadata, ("summary", "description", "textPreview", "text_preview", "extractedText"))
        return {
            "materialId": material.material_id,
            "title": material.title,
            "materialType": material.material_type.value if hasattr(material.material_type, "value") else str(material.material_type),
            "resourceUrl": material.resource_url,
            "summary": summary,
        }

    def _first_string(self, data: dict[str, Any], keys: tuple[str, ...]) -> str | None:
        for key in keys:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _to_response(self, draft: EducatorContentDraft, *, module: Module) -> ContentDraftResponse:
        content_type = draft.content_type.value if isinstance(draft.content_type, EducatorContentDraftType) else str(draft.content_type)
        return ContentDraftResponse(
            draftUuid=encode_content_draft_uuid(draft.content_draft_id),
            moduleId=module.module_id,
            moduleUuid=encode_module_uuid(module.module_id),
            contentType=content_type,
            title=draft.title,
            teacherPrompt=draft.teacher_prompt,
            materialScope=draft.material_scope,
            structuredContent=draft.structured_content_json,
            grounding=[ContentDraftGroundingItem.model_validate(item) for item in (draft.grounding_json or [])],
            confidenceScore=draft.confidence_score,
            isFallback=draft.is_fallback,
            fallbackReason=draft.fallback_reason,
            provider=draft.provider_name,
            model=draft.provider_model,
            createdBy=draft.created_by,
            updatedBy=draft.updated_by,
            createdAt=draft.created_at,
            updatedAt=draft.updated_at,
        )

    def _get_manageable_course(self, *, course_uuid: str, current_user: dict):
        actor_id = self._require_actor_id(current_user)
        course = self.courses.get_by_id(decode_course_uuid(course_uuid))
        if course is None:
            raise http_error(status_code=status.HTTP_404_NOT_FOUND, code="COURSE_NOT_FOUND", message="Course not found")
        if current_user.get("identity") == "Admin":
            return course
        if current_user.get("identity") == "Educator" and course.educator_id == actor_id:
            return course
        raise http_error(
            status_code=status.HTTP_403_FORBIDDEN,
            code="COURSE_OWNERSHIP_REQUIRED",
            message="You can only manage content drafts for your own courses",
        )

    def _get_course_module(self, *, course_id: int, module_uuid: str) -> Module:
        learning_path = self.learning_paths.get_by_course_id(course_id)
        if learning_path is None:
            raise http_error(status_code=status.HTTP_404_NOT_FOUND, code="LEARNING_PATH_NOT_FOUND", message="Learning path not found")
        module = self.modules.get_by_id(decode_module_uuid(module_uuid))
        if module is None or module.learning_path_id != learning_path.learning_path_id:
            raise http_error(status_code=status.HTTP_404_NOT_FOUND, code="MODULE_NOT_FOUND", message="Module not found")
        return module

    def _get_module_draft(self, *, module_id: int, draft_uuid: str) -> EducatorContentDraft:
        draft = self.drafts.get_by_id(decode_content_draft_uuid(draft_uuid))
        if draft is None or draft.module_id != module_id:
            raise http_error(status_code=status.HTTP_404_NOT_FOUND, code="CONTENT_DRAFT_NOT_FOUND", message="Content draft not found")
        return draft

    def _require_actor_id(self, current_user: dict) -> int:
        actor_id = current_user.get("id")
        if not isinstance(actor_id, int):
            raise invalid_identity_response_error()
        return actor_id

    def _normalize_optional_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    def _normalize_required_text(self, value: str | None, field_name: str) -> str:
        normalized = self._normalize_optional_text(value)
        if not normalized:
            raise invalid_request_error(f"Content draft {field_name} is required")
        return normalized

    def _quantize_confidence(self, value: Decimal) -> Decimal:
        return Decimal(value).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    def _normalize_match_text(self, value: str) -> str:
        return re.sub(r"\s+", " ", value.strip().lower())

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.ai_knowledge_sources import (
    AIKnowledgeSource,
    AIKnowledgeSourceType,
    AIPublishStatus,
    AIVisibilityScope,
)


class AIKnowledgeSourcesRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, source_id: int) -> AIKnowledgeSource | None:
        return self.session.get(AIKnowledgeSource, source_id)

    def get_by_type_and_ref(
        self,
        *,
        source_type: AIKnowledgeSourceType,
        source_ref_id: str,
    ) -> AIKnowledgeSource | None:
        stmt = select(AIKnowledgeSource).where(
            AIKnowledgeSource.source_type == source_type,
            AIKnowledgeSource.source_ref_id == source_ref_id,
        )
        return self.session.scalar(stmt)

    def list_by_course_id(self, course_id: int) -> list[AIKnowledgeSource]:
        stmt = (
            select(AIKnowledgeSource)
            .where(AIKnowledgeSource.course_id == course_id)
            .order_by(AIKnowledgeSource.updated_at.desc(), AIKnowledgeSource.source_id.desc())
        )
        return list(self.session.scalars(stmt))

    def list_by_module_id(self, module_id: int) -> list[AIKnowledgeSource]:
        stmt = (
            select(AIKnowledgeSource)
            .where(AIKnowledgeSource.module_id == module_id)
            .order_by(AIKnowledgeSource.updated_at.desc(), AIKnowledgeSource.source_id.desc())
        )
        return list(self.session.scalars(stmt))

    def list_by_material_id(self, material_id: int) -> list[AIKnowledgeSource]:
        stmt = (
            select(AIKnowledgeSource)
            .where(AIKnowledgeSource.material_id == material_id)
            .order_by(AIKnowledgeSource.updated_at.desc(), AIKnowledgeSource.source_id.desc())
        )
        return list(self.session.scalars(stmt))

    def create(
        self,
        *,
        source_type: AIKnowledgeSourceType,
        source_ref_id: str,
        course_id: int | None,
        module_id: int | None,
        material_id: int | None,
        title: str | None,
        content_text: str,
        content_markdown: str | None,
        language_code: str | None,
        visibility_scope: AIVisibilityScope,
        publish_status: AIPublishStatus,
        content_hash: str,
        embedding_model: str | None,
        embedding_version: str | None,
        source_version: str | None,
        metadata_json: dict | list | None,
        created_by: int | None,
        updated_by: int | None,
        origin_event_id: str | None,
    ) -> AIKnowledgeSource:
        source = AIKnowledgeSource(
            source_type=source_type,
            source_ref_id=source_ref_id,
            course_id=course_id,
            module_id=module_id,
            material_id=material_id,
            title=title,
            content_text=content_text,
            content_markdown=content_markdown,
            language_code=language_code,
            visibility_scope=visibility_scope,
            publish_status=publish_status,
            content_hash=content_hash,
            embedding_model=embedding_model,
            embedding_version=embedding_version,
            source_version=source_version,
            metadata_json=metadata_json,
            created_by=created_by,
            updated_by=updated_by,
            origin_event_id=origin_event_id,
        )
        self.session.add(source)
        self.session.flush()
        return source

    def update(
        self,
        source: AIKnowledgeSource,
        *,
        title: str | None,
        content_text: str,
        content_markdown: str | None,
        language_code: str | None,
        visibility_scope: AIVisibilityScope,
        publish_status: AIPublishStatus,
        content_hash: str,
        embedding_model: str | None,
        embedding_version: str | None,
        source_version: str | None,
        metadata_json: dict | list | None,
        updated_by: int | None,
        origin_event_id: str | None,
    ) -> AIKnowledgeSource:
        source.title = title
        source.content_text = content_text
        source.content_markdown = content_markdown
        source.language_code = language_code
        source.visibility_scope = visibility_scope
        source.publish_status = publish_status
        source.content_hash = content_hash
        source.embedding_model = embedding_model
        source.embedding_version = embedding_version
        source.source_version = source_version
        source.metadata_json = metadata_json
        source.updated_by = updated_by
        source.origin_event_id = origin_event_id
        self.session.flush()
        return source

    def delete(self, source: AIKnowledgeSource) -> None:
        self.session.delete(source)
        self.session.flush()

    def delete_by_type_and_ref(
        self,
        *,
        source_type: AIKnowledgeSourceType,
        source_ref_id: str,
    ) -> int:
        stmt = delete(AIKnowledgeSource).where(
            AIKnowledgeSource.source_type == source_type,
            AIKnowledgeSource.source_ref_id == source_ref_id,
        )
        result = self.session.execute(stmt)
        self.session.flush()
        return int(result.rowcount or 0)

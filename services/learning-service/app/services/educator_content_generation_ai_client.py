from __future__ import annotations

from typing import Any

from app.core.config import settings
from platform_common.http import post_json


class EducatorContentGenerationAIClient:
    def _internal_headers(self) -> dict[str, str]:
        return {"X-Internal-Token": settings.internal_api_token}

    def generate_draft(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        educator_id: int,
        course_title: str,
        module_title: str,
        module_description: str | None,
        module_content: str | None,
        content_type: str,
        material_scope: str | None,
        teacher_prompt: str | None,
        materials: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return post_json(
            url=f"{settings.ai_service_url}/internal/content-generation/educator-draft",
            payload={
                "courseUuid": course_uuid,
                "moduleUuid": module_uuid,
                "educatorId": educator_id,
                "courseTitle": course_title,
                "moduleTitle": module_title,
                "moduleDescription": module_description,
                "moduleContent": module_content,
                "contentType": content_type,
                "materialScope": material_scope,
                "teacherPrompt": teacher_prompt,
                "materials": materials,
            },
            headers=self._internal_headers(),
            timeout=30,
        )

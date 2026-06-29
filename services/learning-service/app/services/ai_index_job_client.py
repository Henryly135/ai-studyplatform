from __future__ import annotations

from app.core.config import settings
from platform_common.http import post_json


class AIIndexJobClient:
    def _internal_headers(self) -> dict[str, str]:
        return {"X-Internal-Token": settings.internal_api_token}

    def register_material_job(
        self,
        *,
        course_id: int,
        module_id: int,
        material_id: int,
        educator_id: int | None,
        title: str,
        material_type: str,
        resource_url: str,
        storage_path: str,
        absolute_path: str | None,
        content_type: str | None,
        size_bytes: int,
        module_status: str,
        storage_provider: str,
        storage_bucket: str | None,
        object_key: str,
    ) -> dict[str, object]:
        return post_json(
            url=f"{settings.ai_service_url}/internal/index-jobs/material",
            payload={
                "courseId": course_id,
                "moduleId": module_id,
                "materialId": material_id,
                "educatorId": educator_id,
                "title": title,
                "materialType": material_type,
                "resourceUrl": resource_url,
                "storagePath": storage_path,
                "absolutePath": absolute_path,
                "contentType": content_type,
                "sizeBytes": size_bytes,
                "moduleStatus": module_status,
                "storageProvider": storage_provider,
                "storageBucket": storage_bucket,
                "objectKey": object_key,
            },
            headers=self._internal_headers(),
        )

    def release_blocked_jobs(
        self,
        *,
        course_id: int,
        module_ids: list[int],
    ) -> dict[str, object]:
        return post_json(
            url=f"{settings.ai_service_url}/internal/index-jobs/release",
            payload={
                "courseId": course_id,
                "moduleIds": module_ids,
            },
            headers=self._internal_headers(),
        )

    def delete_material_index(
        self,
        *,
        material_id: int,
    ) -> dict[str, object]:
        return post_json(
            url=f"{settings.ai_service_url}/internal/index-jobs/material/delete",
            payload={
                "materialId": material_id,
            },
            headers=self._internal_headers(),
        )

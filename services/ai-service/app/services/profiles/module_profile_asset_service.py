from __future__ import annotations

import json
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from minio.error import S3Error

from app.core.config import settings
from platform_common.storage import build_minio_client, ensure_bucket_exists


@dataclass(frozen=True)
class StoredModuleProfileAsset:
    object_key: str
    content: dict


class ModuleProfileAssetService:
    DEFAULT_TEMPLATE_OBJECT_KEY = "templates/module/default_module_profile_v1.json"

    def __init__(self) -> None:
        self.provider = settings.object_storage_provider.strip().lower()
        if self.provider not in {"local", "minio"}:
            raise ValueError("OBJECT_STORAGE_PROVIDER must be one of local or minio")

    def get_profile_object_key(self, *, learner_id: int, course_id: int, module_id: int, version: int) -> str:
        return f"module/{learner_id}/{course_id}/{module_id}/profile_v{version}.json"

    def ensure_default_template_asset(self, *, content: dict) -> str:
        serialized = self._serialize(content)
        if self.provider == "minio":
            client = self._build_minio_client()
            ensure_bucket_exists(client, settings.ai_profile_bucket)
            if not self._object_exists(bucket=settings.ai_profile_bucket, object_key=self.DEFAULT_TEMPLATE_OBJECT_KEY):
                payload = serialized.encode("utf-8")
                client.put_object(
                    settings.ai_profile_bucket,
                    self.DEFAULT_TEMPLATE_OBJECT_KEY,
                    data=BytesIO(payload),
                    length=len(payload),
                    content_type="application/json; charset=utf-8",
                )
            return self.DEFAULT_TEMPLATE_OBJECT_KEY

        target_path = self._local_root_path() / self.DEFAULT_TEMPLATE_OBJECT_KEY
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if not target_path.exists():
            target_path.write_text(serialized, encoding="utf-8")
        return self.DEFAULT_TEMPLATE_OBJECT_KEY

    def save_profile(self, *, object_key: str, content: dict) -> StoredModuleProfileAsset:
        serialized = self._serialize(content)
        if self.provider == "minio":
            client = self._build_minio_client()
            ensure_bucket_exists(client, settings.ai_profile_bucket)
            payload = serialized.encode("utf-8")
            client.put_object(
                settings.ai_profile_bucket,
                object_key,
                data=BytesIO(payload),
                length=len(payload),
                content_type="application/json; charset=utf-8",
            )
            return StoredModuleProfileAsset(object_key=object_key, content=content)

        target_path = self._local_root_path() / object_key
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(serialized, encoding="utf-8")
        return StoredModuleProfileAsset(object_key=object_key, content=content)

    def load_profile(self, *, object_key: str) -> dict:
        if self.provider == "minio":
            client = self._build_minio_client()
            response = client.get_object(settings.ai_profile_bucket, object_key)
            try:
                return json.loads(response.read().decode("utf-8"))
            finally:
                response.close()
                response.release_conn()

        target_path = self._local_root_path() / object_key
        return json.loads(target_path.read_text(encoding="utf-8"))

    def _object_exists(self, *, bucket: str, object_key: str) -> bool:
        client = self._build_minio_client()
        try:
            client.stat_object(bucket, object_key)
            return True
        except S3Error as exc:
            if exc.code in {"NoSuchKey", "NoSuchObject", "NoSuchBucket"}:
                return False
            raise

    def _build_minio_client(self):
        return build_minio_client(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
        )

    def _local_root_path(self) -> Path:
        return Path(settings.ai_profile_root_path).resolve()

    def _serialize(self, content: dict) -> str:
        return json.dumps(content, ensure_ascii=True, indent=2)

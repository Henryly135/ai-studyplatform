from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile, status
from sqlalchemy.orm import Session

from app.core.uuid_codec import (
    decode_course_uuid,
    decode_material_uuid,
    decode_module_uuid,
    encode_course_uuid,
    encode_module_uuid,
)
from app.core.config import settings
from app.models.courses import Course
from app.models.module_material_upload_sessions import MaterialUploadSessionStatus, ModuleMaterialUploadSession
from app.models.module_materials import MaterialType, ModuleMaterial
from app.models.modules import Module
from app.repositories.course_repository import CourseRepository
from app.repositories.learning_path_repository import LearningPathRepository
from app.repositories.module_material_repository import ModuleMaterialRepository
from app.repositories.module_material_upload_session_repository import ModuleMaterialUploadSessionRepository
from app.repositories.module_repository import ModuleRepository
from app.services.ai_index_job_client import AIIndexJobClient
from app.services.storage_service import StorageService, StoredFile
from platform_common.errors import http_error, invalid_identity_response_error, invalid_request_error

_MATERIAL_TYPE_BY_CONTENT_TYPE = {
    "application/pdf": MaterialType.PDF,
}
_VIDEO_PREFIX = "video/"


class ModuleMaterialService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.courses = CourseRepository(session)
        self.learning_paths = LearningPathRepository(session)
        self.modules = ModuleRepository(session)
        self.materials = ModuleMaterialRepository(session)
        self.upload_sessions = ModuleMaterialUploadSessionRepository(session)
        self.ai_index_jobs = AIIndexJobClient()
        self.storage = StorageService()

    def delete_material(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        material_uuid: str,
        current_user: dict,
    ) -> None:
        course = self._get_manageable_course(course_uuid=course_uuid, current_user=current_user)
        module = self._get_manageable_module(course=course, module_uuid=module_uuid)
        material_id = decode_material_uuid(material_uuid)
        material = self.materials.get_by_id(material_id)
        if material is None or material.module_id != module.module_id:
            raise http_error(
                status_code=status.HTTP_404_NOT_FOUND,
                code="MATERIAL_NOT_FOUND",
                message="Material not found",
            )

        self.delete_material_record(material=material, course=course)
        self.session.commit()

    def delete_material_record(
        self,
        *,
        material: ModuleMaterial,
        course: Course,
    ) -> None:
        self.cleanup_material_dependencies(material=material)
        self.materials.delete(material)
        self.courses.touch(course)

    def upload_material(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        title: str | None,
        material_type: str | None,
        sort_order: int | None,
        file: UploadFile,
        current_user: dict,
    ) -> ModuleMaterial:
        course = self._get_manageable_course(course_uuid=course_uuid, current_user=current_user)
        module = self._get_manageable_module(course=course, module_uuid=module_uuid)

        normalized_title = self._normalize_title(title=title, upload=file)
        parsed_material_type = self._parse_material_type(material_type=material_type, upload=file)
        target_sort_order = self._resolve_target_sort_order(module.module_id, requested_sort_order=sort_order)

        stored_file = self.storage.store_module_material(
            course_uuid=encode_course_uuid(course.course_id),
            module_uuid=encode_module_uuid(module.module_id),
            upload=file,
        )

        metadata = {
            "storageProvider": stored_file.provider,
            "bucket": stored_file.bucket,
            "objectKey": stored_file.object_key,
            "originalFilename": stored_file.original_filename,
            "storedRelativePath": stored_file.object_key,
            "contentType": stored_file.content_type,
            "sizeBytes": stored_file.size_bytes,
        }
        try:
            material = self.materials.create(
                module_id=module.module_id,
                title=normalized_title,
                material_type=parsed_material_type,
                resource_url=stored_file.public_url,
                sort_order=target_sort_order,
                metadata_json=metadata,
            )
            self._register_ai_index_job(
                course=course,
                module=module,
                material=material,
                stored_file=stored_file,
            )
            self.courses.touch(course)
            self.session.commit()
            self.session.refresh(material)
        except Exception:
            self.session.rollback()
            raise

        return material

    def initiate_multipart_upload(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        title: str | None,
        material_type: str | None,
        sort_order: int | None,
        file_name: str,
        content_type: str | None,
        size_bytes: int,
        current_user: dict,
    ) -> ModuleMaterialUploadSession:
        self._ensure_multipart_storage_supported()
        actor_id = self._get_actor_id(current_user)
        course = self._get_manageable_course(course_uuid=course_uuid, current_user=current_user)
        module = self._get_manageable_module(course=course, module_uuid=module_uuid)

        normalized_title = self._normalize_title_from_filename(title=title, filename=file_name)
        parsed_material_type = self._parse_material_type_from_name(
            material_type=material_type,
            filename=file_name,
            content_type=content_type,
        )
        target_sort_order = self._resolve_target_sort_order(module.module_id, requested_sort_order=sort_order)

        multipart_target = self.storage.initiate_module_material_multipart_upload(
            course_uuid=encode_course_uuid(course.course_id),
            module_uuid=encode_module_uuid(module.module_id),
            filename=file_name,
            content_type=content_type,
        )
        upload_session = self.upload_sessions.create(
            session_uuid=uuid4().hex,
            module_id=module.module_id,
            created_by_user_id=actor_id,
            title=normalized_title,
            material_type=parsed_material_type,
            sort_order=target_sort_order,
            original_filename=Path(file_name).name or "material",
            content_type=content_type,
            size_bytes=size_bytes,
            storage_provider=multipart_target.provider,
            bucket=multipart_target.bucket,
            object_key=multipart_target.object_key,
            multipart_upload_id=multipart_target.upload_id,
            metadata_json={
                "storageProvider": multipart_target.provider,
                "bucket": multipart_target.bucket,
                "objectKey": multipart_target.object_key,
                "originalFilename": Path(file_name).name or "material",
                "contentType": content_type,
                "sizeBytes": size_bytes,
            },
        )
        self.session.commit()
        self.session.refresh(upload_session)
        return upload_session

    def get_multipart_upload_part_url(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        upload_session_uuid: str,
        part_number: int,
        current_user: dict,
    ) -> str:
        self._ensure_multipart_storage_supported()
        course = self._get_manageable_course(course_uuid=course_uuid, current_user=current_user)
        module = self._get_manageable_module(course=course, module_uuid=module_uuid)
        upload_session = self._get_manageable_upload_session(module=module, upload_session_uuid=upload_session_uuid)
        if self._expire_upload_session_if_stale(upload_session):
            self.session.commit()
            raise invalid_request_error("Upload session expired. Please start the upload again.")
        self._ensure_upload_session_open(upload_session)

        if upload_session.status == MaterialUploadSessionStatus.INITIATED:
            self.upload_sessions.update(upload_session, status=MaterialUploadSessionStatus.UPLOADING)
            self.session.commit()

        return self.storage.get_multipart_part_upload_url(
            bucket=upload_session.bucket,
            object_key=upload_session.object_key,
            upload_id=upload_session.multipart_upload_id,
            part_number=part_number,
        )

    def complete_multipart_upload(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        upload_session_uuid: str,
        completed_parts: list[tuple[int, str]],
        current_user: dict,
    ) -> ModuleMaterial:
        self._ensure_multipart_storage_supported()
        course = self._get_manageable_course(course_uuid=course_uuid, current_user=current_user)
        module = self._get_manageable_module(course=course, module_uuid=module_uuid)
        upload_session = self._get_manageable_upload_session(module=module, upload_session_uuid=upload_session_uuid)
        if self._expire_upload_session_if_stale(upload_session):
            self.session.commit()
            raise invalid_request_error("Upload session expired. Please start the upload again.")
        self._ensure_upload_session_open(upload_session)
        self._ensure_sort_order_available(
            module.module_id,
            upload_session.sort_order,
            exclude_session_uuid=upload_session.session_uuid,
        )
        self._validate_completed_parts(completed_parts)

        try:
            stored_file = self.storage.complete_multipart_material_upload(
                bucket=upload_session.bucket,
                object_key=upload_session.object_key,
                upload_id=upload_session.multipart_upload_id,
                parts=completed_parts,
                content_type=upload_session.content_type,
                size_bytes=upload_session.size_bytes,
            )
            material = self.materials.create(
                module_id=module.module_id,
                title=upload_session.title,
                material_type=upload_session.material_type,
                resource_url=stored_file.public_url,
                sort_order=upload_session.sort_order,
                metadata_json=self._build_material_metadata_from_session(upload_session, stored_file),
            )
            self._register_ai_index_job(
                course=course,
                module=module,
                material=material,
                stored_file=stored_file,
            )
            self.upload_sessions.update(
                upload_session,
                status=MaterialUploadSessionStatus.COMPLETED,
                material_id=material.material_id,
                metadata_json={
                    **(upload_session.metadata_json or {}),
                    "completedParts": [part_number for part_number, _ in completed_parts],
                    "resourceUrl": material.resource_url,
                },
            )
            self.courses.touch(course)
            self.session.commit()
            self.session.refresh(material)
            return material
        except Exception as exc:
            self.session.rollback()
            stored_session = self.upload_sessions.get_by_session_uuid(upload_session_uuid)
            if stored_session is not None:
                self.upload_sessions.update(
                    stored_session,
                    status=MaterialUploadSessionStatus.FAILED,
                    metadata_json={
                        **(stored_session.metadata_json or {}),
                        "lastError": str(exc),
                    },
                )
                self.session.commit()
            raise

    def abort_multipart_upload(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        upload_session_uuid: str,
        current_user: dict,
    ) -> ModuleMaterialUploadSession:
        self._ensure_multipart_storage_supported()
        course = self._get_manageable_course(course_uuid=course_uuid, current_user=current_user)
        module = self._get_manageable_module(course=course, module_uuid=module_uuid)
        upload_session = self._get_manageable_upload_session(module=module, upload_session_uuid=upload_session_uuid)

        if upload_session.status == MaterialUploadSessionStatus.COMPLETED:
            raise invalid_request_error("Completed upload sessions cannot be aborted")
        if upload_session.status == MaterialUploadSessionStatus.ABORTED:
            return upload_session

        self.storage.abort_multipart_material_upload(
            bucket=upload_session.bucket,
            object_key=upload_session.object_key,
            upload_id=upload_session.multipart_upload_id,
        )
        self.upload_sessions.update(upload_session, status=MaterialUploadSessionStatus.ABORTED)
        self.session.commit()
        self.session.refresh(upload_session)
        return upload_session

    def _get_manageable_course(self, *, course_uuid: str, current_user: dict) -> Course:
        actor_id = self._get_actor_id(current_user)
        course_id = decode_course_uuid(course_uuid)
        course = self.courses.get_by_id(course_id)
        if course is None:
            raise http_error(status_code=status.HTTP_404_NOT_FOUND, code="COURSE_NOT_FOUND", message="Course not found")

        if current_user.get("identity") == "Admin":
            return course

        if course.educator_id != actor_id:
            raise http_error(
                status_code=status.HTTP_403_FORBIDDEN,
                code="COURSE_OWNERSHIP_REQUIRED",
                message="You can only manage materials for your own courses",
            )
        return course

    def _get_manageable_module(self, *, course: Course, module_uuid: str) -> Module:
        learning_path = self.learning_paths.get_by_course_id(course.course_id)
        if learning_path is None:
            raise http_error(
                status_code=status.HTTP_404_NOT_FOUND,
                code="LEARNING_PATH_NOT_FOUND",
                message="Learning path not found",
            )

        module_id = decode_module_uuid(module_uuid)
        module = self.modules.get_by_id(module_id)
        if module is None or module.learning_path_id != learning_path.learning_path_id:
            raise http_error(status_code=status.HTTP_404_NOT_FOUND, code="MODULE_NOT_FOUND", message="Module not found")
        return module

    def _get_manageable_upload_session(
        self,
        *,
        module: Module,
        upload_session_uuid: str,
    ) -> ModuleMaterialUploadSession:
        upload_session = self.upload_sessions.get_by_session_uuid(upload_session_uuid)
        if upload_session is None or upload_session.module_id != module.module_id:
            raise http_error(
                status_code=status.HTTP_404_NOT_FOUND,
                code="UPLOAD_SESSION_NOT_FOUND",
                message="Upload session not found",
            )
        return upload_session

    def _normalize_title(self, *, title: str | None, upload: UploadFile) -> str:
        normalized = (title or "").strip()
        if normalized:
            return normalized
        fallback = Path(upload.filename or "").name.strip()
        if fallback:
            return fallback
        raise invalid_request_error("Material title is required")

    def _normalize_title_from_filename(self, *, title: str | None, filename: str) -> str:
        normalized = (title or "").strip()
        if normalized:
            return normalized
        fallback = Path(filename or "").name.strip()
        if fallback:
            return fallback
        raise invalid_request_error("Material title is required")

    def _parse_material_type(self, *, material_type: str | None, upload: UploadFile) -> MaterialType:
        normalized = (material_type or "").strip().lower()
        if normalized:
            try:
                return MaterialType(normalized)
            except ValueError as exc:
                raise invalid_request_error("materialType must be one of pdf, video, file, link, text") from exc

        content_type = (upload.content_type or "").strip().lower()
        if content_type in _MATERIAL_TYPE_BY_CONTENT_TYPE:
            return _MATERIAL_TYPE_BY_CONTENT_TYPE[content_type]
        if content_type.startswith(_VIDEO_PREFIX):
            return MaterialType.VIDEO
        return MaterialType.FILE

    def _parse_material_type_from_name(
        self,
        *,
        material_type: str | None,
        filename: str,
        content_type: str | None,
    ) -> MaterialType:
        normalized = (material_type or "").strip().lower()
        if normalized:
            try:
                return MaterialType(normalized)
            except ValueError as exc:
                raise invalid_request_error("materialType must be one of pdf, video, file, link, text") from exc

        normalized_content_type = (content_type or "").strip().lower()
        if normalized_content_type in _MATERIAL_TYPE_BY_CONTENT_TYPE:
            return _MATERIAL_TYPE_BY_CONTENT_TYPE[normalized_content_type]
        if normalized_content_type.startswith(_VIDEO_PREFIX):
            return MaterialType.VIDEO
        if Path(filename or "").suffix.lower() == ".pdf":
            return MaterialType.PDF
        return MaterialType.FILE

    def _resolve_target_sort_order(self, module_id: int, *, requested_sort_order: int | None) -> int:
        if requested_sort_order is not None:
            self._cleanup_stale_upload_sessions(module_id, requested_sort_order)
            self._ensure_sort_order_available(module_id, requested_sort_order)
            return requested_sort_order

        candidate_sort_order = self.materials.get_max_sort_order(module_id) + 1
        while True:
            self._cleanup_stale_upload_sessions(module_id, candidate_sort_order)
            if not self._has_conflicting_sort_order(module_id, candidate_sort_order):
                return candidate_sort_order
            candidate_sort_order += 1

    def _has_conflicting_sort_order(
        self,
        module_id: int,
        sort_order: int,
        *,
        exclude_session_uuid: str | None = None,
    ) -> bool:
        if self.materials.get_by_module_and_sort_order(module_id, sort_order) is not None:
            return True
        return (
            self.upload_sessions.get_active_by_module_and_sort_order(
                module_id,
                sort_order,
                exclude_session_uuid=exclude_session_uuid,
            )
            is not None
        )

    def _ensure_sort_order_available(
        self,
        module_id: int,
        sort_order: int,
        *,
        exclude_session_uuid: str | None = None,
    ) -> None:
        existing_material = self.materials.get_by_module_and_sort_order(module_id, sort_order)
        if existing_material is not None:
            raise invalid_request_error("A material with this sortOrder already exists in the module")

        active_session = self.upload_sessions.get_active_by_module_and_sort_order(
            module_id,
            sort_order,
            exclude_session_uuid=exclude_session_uuid,
        )
        if active_session is not None:
            raise invalid_request_error("A pending upload session already exists for this sortOrder")

    def _ensure_upload_session_open(self, upload_session: ModuleMaterialUploadSession) -> None:
        if upload_session.status == MaterialUploadSessionStatus.COMPLETED:
            raise invalid_request_error("Upload session has already been completed")
        if upload_session.status == MaterialUploadSessionStatus.ABORTED:
            raise invalid_request_error("Upload session has already been aborted")
        if upload_session.status == MaterialUploadSessionStatus.FAILED:
            raise invalid_request_error("Upload session has failed and cannot be reused")

    def _cleanup_stale_upload_sessions(self, module_id: int, sort_order: int) -> None:
        active_sessions = self.upload_sessions.list_active_by_module_and_sort_order(module_id, sort_order)
        did_change = False

        for active_session in active_sessions:
            if self._expire_upload_session_if_stale(active_session):
                did_change = True

        if did_change:
            self.session.commit()

    def _expire_upload_session_if_stale(self, upload_session: ModuleMaterialUploadSession) -> bool:
        if upload_session.status not in {
            MaterialUploadSessionStatus.INITIATED,
            MaterialUploadSessionStatus.UPLOADING,
        }:
            return False

        if not self._is_upload_session_stale(upload_session):
            return False

        cleanup_metadata = {
            **(upload_session.metadata_json or {}),
            "expiredAt": self._utcnow().isoformat(),
            "expiredReason": "interrupted-upload-session-timeout",
        }

        try:
            self.storage.abort_multipart_material_upload(
                bucket=upload_session.bucket,
                object_key=upload_session.object_key,
                upload_id=upload_session.multipart_upload_id,
            )
        except Exception as exc:
            cleanup_metadata["storageAbortError"] = str(exc)

        self.upload_sessions.update(
            upload_session,
            status=MaterialUploadSessionStatus.FAILED,
            metadata_json=cleanup_metadata,
        )
        return True

    def _is_upload_session_stale(self, upload_session: ModuleMaterialUploadSession) -> bool:
        reference_time = upload_session.updated_at or upload_session.created_at
        return reference_time <= self._utcnow() - timedelta(seconds=settings.multipart_upload_session_ttl_seconds)

    def _utcnow(self) -> datetime:
        return datetime.utcnow()

    def _validate_completed_parts(self, completed_parts: list[tuple[int, str]]) -> None:
        if not completed_parts:
            raise invalid_request_error("At least one uploaded part is required")

        seen_part_numbers: set[int] = set()
        for part_number, etag in completed_parts:
            if part_number < 1 or part_number > 10000:
                raise invalid_request_error("partNumber must be between 1 and 10000")
            if part_number in seen_part_numbers:
                raise invalid_request_error("Duplicate partNumber values are not allowed")
            seen_part_numbers.add(part_number)
            if not etag.strip():
                raise invalid_request_error("etag is required for every completed part")

    def _build_material_metadata_from_session(
        self,
        upload_session: ModuleMaterialUploadSession,
        stored_file: StoredFile,
    ) -> dict:
        return {
            "storageProvider": stored_file.provider,
            "bucket": stored_file.bucket,
            "objectKey": stored_file.object_key,
            "originalFilename": upload_session.original_filename,
            "storedRelativePath": stored_file.object_key,
            "contentType": stored_file.content_type,
            "sizeBytes": stored_file.size_bytes,
            "uploadSessionUuid": upload_session.session_uuid,
            "multipartUploadId": upload_session.multipart_upload_id,
        }

    def _read_material_storage_provider(self, *, metadata: dict[str, object]) -> str | None:
        raw_provider = metadata.get("storageProvider")
        if isinstance(raw_provider, str):
            normalized = raw_provider.strip()
            if normalized:
                return normalized
        return None

    def cleanup_material_dependencies(self, *, material: ModuleMaterial) -> None:
        metadata = material.metadata_json if isinstance(material.metadata_json, dict) else {}
        storage_provider = self._read_material_storage_provider(metadata=metadata)
        bucket = self._read_material_bucket(metadata=metadata)
        object_key = self._read_material_object_key(metadata=metadata)

        self.ai_index_jobs.delete_material_index(material_id=material.material_id)
        self.storage.delete_module_material(
            storage_provider=storage_provider,
            bucket=bucket,
            object_key=object_key,
        )

    def _read_material_bucket(self, *, metadata: dict[str, object]) -> str | None:
        raw_bucket = metadata.get("bucket")
        if isinstance(raw_bucket, str):
            normalized = raw_bucket.strip()
            if normalized:
                return normalized
        return None

    def _read_material_object_key(self, *, metadata: dict[str, object]) -> str | None:
        for key in ("objectKey", "storedRelativePath"):
            raw_value = metadata.get(key)
            if isinstance(raw_value, str):
                normalized = raw_value.strip()
                if normalized:
                    return normalized
        return None

    def _get_actor_id(self, current_user: dict) -> int:
        actor_id = current_user.get("id")
        if not isinstance(actor_id, int):
            raise invalid_identity_response_error()
        return actor_id

    def _ensure_multipart_storage_supported(self) -> None:
        if self.storage.provider != "minio":
            raise invalid_request_error("Multipart direct uploads require OBJECT_STORAGE_PROVIDER=minio")

    def _register_ai_index_job(
        self,
        *,
        course: Course,
        module: Module,
        material: ModuleMaterial,
        stored_file: StoredFile,
    ) -> None:
        self.ai_index_jobs.register_material_job(
            course_id=course.course_id,
            module_id=module.module_id,
            material_id=material.material_id,
            educator_id=course.educator_id,
            title=material.title,
            material_type=material.material_type.value,
            resource_url=material.resource_url,
            storage_path=stored_file.object_key,
            absolute_path=str(stored_file.absolute_path) if stored_file.absolute_path is not None else None,
            content_type=stored_file.content_type,
            size_bytes=stored_file.size_bytes,
            module_status=module.status.value,
            storage_provider=stored_file.provider,
            storage_bucket=stored_file.bucket,
            object_key=stored_file.object_key,
        )

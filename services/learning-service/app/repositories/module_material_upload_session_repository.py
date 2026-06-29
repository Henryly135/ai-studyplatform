from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.module_material_upload_sessions import MaterialUploadSessionStatus, ModuleMaterialUploadSession
from app.models.module_materials import MaterialType

_UNSET = object()
_ACTIVE_UPLOAD_STATUSES = (
    MaterialUploadSessionStatus.INITIATED,
    MaterialUploadSessionStatus.UPLOADING,
)


class ModuleMaterialUploadSessionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_session_uuid(self, session_uuid: str) -> ModuleMaterialUploadSession | None:
        stmt = select(ModuleMaterialUploadSession).where(ModuleMaterialUploadSession.session_uuid == session_uuid)
        return self.session.scalar(stmt)

    def list_active_by_module_and_sort_order(
        self,
        module_id: int,
        sort_order: int,
        *,
        exclude_session_uuid: str | None = None,
    ) -> list[ModuleMaterialUploadSession]:
        stmt = select(ModuleMaterialUploadSession).where(
            ModuleMaterialUploadSession.module_id == module_id,
            ModuleMaterialUploadSession.sort_order == sort_order,
            ModuleMaterialUploadSession.status.in_(_ACTIVE_UPLOAD_STATUSES),
        )
        if exclude_session_uuid:
            stmt = stmt.where(ModuleMaterialUploadSession.session_uuid != exclude_session_uuid)
        stmt = stmt.order_by(ModuleMaterialUploadSession.updated_at.desc(), ModuleMaterialUploadSession.upload_session_id.desc())
        return list(self.session.scalars(stmt))

    def get_active_by_module_and_sort_order(
        self,
        module_id: int,
        sort_order: int,
        *,
        exclude_session_uuid: str | None = None,
    ) -> ModuleMaterialUploadSession | None:
        active_sessions = self.list_active_by_module_and_sort_order(
            module_id,
            sort_order,
            exclude_session_uuid=exclude_session_uuid,
        )
        return active_sessions[0] if active_sessions else None

    def create(
        self,
        *,
        session_uuid: str,
        module_id: int,
        created_by_user_id: int,
        title: str,
        material_type: MaterialType,
        sort_order: int,
        original_filename: str,
        content_type: str | None,
        size_bytes: int | None,
        storage_provider: str,
        bucket: str | None,
        object_key: str,
        multipart_upload_id: str,
        status: MaterialUploadSessionStatus = MaterialUploadSessionStatus.INITIATED,
        metadata_json: dict[str, Any] | None = None,
    ) -> ModuleMaterialUploadSession:
        upload_session = ModuleMaterialUploadSession(
            session_uuid=session_uuid,
            module_id=module_id,
            created_by_user_id=created_by_user_id,
            title=title,
            material_type=material_type,
            sort_order=sort_order,
            original_filename=original_filename,
            content_type=content_type,
            size_bytes=size_bytes,
            storage_provider=storage_provider,
            bucket=bucket,
            object_key=object_key,
            multipart_upload_id=multipart_upload_id,
            status=status,
            metadata_json=metadata_json,
        )
        self.session.add(upload_session)
        self.session.flush()
        return upload_session

    def update(
        self,
        upload_session: ModuleMaterialUploadSession,
        *,
        status: MaterialUploadSessionStatus | object = _UNSET,
        material_id: int | None | object = _UNSET,
        metadata_json: dict[str, Any] | None | object = _UNSET,
    ) -> ModuleMaterialUploadSession:
        if status is not _UNSET:
            upload_session.status = status
        if material_id is not _UNSET:
            upload_session.material_id = material_id
        if metadata_json is not _UNSET:
            upload_session.metadata_json = metadata_json
        self.session.flush()
        return upload_session

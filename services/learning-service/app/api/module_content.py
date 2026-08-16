from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import require_identity_permission, require_identity_user
from app.db.session import get_db_session
from app.schemas.course import MaterialResponse, ModuleResponse
from app.schemas.material_upload import (
    MultipartMaterialUploadCompleteRequest,
    MultipartMaterialUploadInitRequest,
    MultipartMaterialUploadInitResponse,
    MultipartMaterialUploadPartUrlResponse,
    MultipartMaterialUploadSessionResponse,
)
from app.schemas.module import ModuleProgressUpdateRequest
from app.services.course_catalog_service import CourseCatalogService
from app.services.module_material_service import ModuleMaterialService
from app.services.module_progress_service import ModuleProgressService
from platform_common.permissions.codes import RESOURCE_UPLOAD


router = APIRouter(tags=["module-content"])


@router.post(
    "/courses/{course_uuid}/modules/{module_uuid}/progress",
    summary="Update Module Progress [Learner]",
    description="Updates the current learner's progress for a module.",
    response_model=ModuleResponse,
    response_model_exclude_none=True,
)
def update_module_progress(
    course_uuid: str,
    module_uuid: str,
    payload: ModuleProgressUpdateRequest,
    current_user: dict = Depends(require_identity_user),
    session: Session = Depends(get_db_session),
) -> ModuleResponse:
    return ModuleProgressService(session).update_progress(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        payload=payload,
        current_user=current_user,
    )


@router.post(
    "/courses/{course_uuid}/modules/{module_uuid}/materials/upload",
    summary="Upload Module Material [Educator Owner/Admin]",
    description="Uploads a material file for a module and registers the related AI indexing job.",
    response_model=MaterialResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def upload_module_material(
    course_uuid: str,
    module_uuid: str,
    title: str | None = Form(default=None),
    material_type: str | None = Form(default=None, alias="materialType"),
    sort_order: int | None = Form(default=None, alias="sortOrder"),
    file: UploadFile = File(...),
    current_user: dict = Depends(require_identity_permission(RESOURCE_UPLOAD)),
    session: Session = Depends(get_db_session),
) -> MaterialResponse:
    material = ModuleMaterialService(session).upload_material(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        title=title,
        material_type=material_type,
        sort_order=sort_order,
        file=file,
        current_user=current_user,
    )
    return CourseCatalogService(session).to_material_response(material, current_user=current_user)


@router.post(
    "/courses/{course_uuid}/modules/{module_uuid}/materials/uploads/init",
    summary="Init Multipart Material Upload [Educator Owner/Admin]",
    description="Creates a multipart upload session for a large module material and reserves its final storage location.",
    response_model=MultipartMaterialUploadInitResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def init_multipart_module_material_upload(
    course_uuid: str,
    module_uuid: str,
    payload: MultipartMaterialUploadInitRequest,
    current_user: dict = Depends(require_identity_permission(RESOURCE_UPLOAD)),
    session: Session = Depends(get_db_session),
) -> MultipartMaterialUploadInitResponse:
    upload_session = ModuleMaterialService(session).initiate_multipart_upload(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        title=payload.title,
        material_type=payload.materialType,
        sort_order=payload.sortOrder,
        file_name=payload.fileName,
        content_type=payload.contentType,
        size_bytes=payload.sizeBytes,
        current_user=current_user,
    )
    return MultipartMaterialUploadInitResponse(
        uploadSessionUuid=upload_session.session_uuid,
        uploadId=upload_session.multipart_upload_id,
        bucket=upload_session.bucket,
        objectKey=upload_session.object_key,
        storageProvider=upload_session.storage_provider,
        partUrlExpiresSeconds=settings.minio_multipart_part_url_expires_seconds,
    )


@router.get(
    "/courses/{course_uuid}/modules/{module_uuid}/materials/uploads/{upload_session_uuid}/parts/{part_number}",
    summary="Get Multipart Part Upload URL [Educator Owner/Admin]",
    description="Returns a short-lived signed URL for uploading one multipart chunk directly to object storage.",
    response_model=MultipartMaterialUploadPartUrlResponse,
    response_model_exclude_none=True,
)
def get_multipart_module_material_part_upload_url(
    course_uuid: str,
    module_uuid: str,
    upload_session_uuid: str,
    part_number: int,
    current_user: dict = Depends(require_identity_permission(RESOURCE_UPLOAD)),
    session: Session = Depends(get_db_session),
) -> MultipartMaterialUploadPartUrlResponse:
    upload_url = ModuleMaterialService(session).get_multipart_upload_part_url(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        upload_session_uuid=upload_session_uuid,
        part_number=part_number,
        current_user=current_user,
    )
    return MultipartMaterialUploadPartUrlResponse(
        uploadSessionUuid=upload_session_uuid,
        partNumber=part_number,
        method="PUT",
        uploadUrl=upload_url,
        expiresSeconds=settings.minio_multipart_part_url_expires_seconds,
    )


@router.post(
    "/courses/{course_uuid}/modules/{module_uuid}/materials/uploads/{upload_session_uuid}/complete",
    summary="Complete Multipart Material Upload [Educator Owner/Admin]",
    description="Finalizes a multipart upload session, creates the module material record, and triggers downstream indexing.",
    response_model=MaterialResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def complete_multipart_module_material_upload(
    course_uuid: str,
    module_uuid: str,
    upload_session_uuid: str,
    payload: MultipartMaterialUploadCompleteRequest,
    current_user: dict = Depends(require_identity_permission(RESOURCE_UPLOAD)),
    session: Session = Depends(get_db_session),
) -> MaterialResponse:
    material = ModuleMaterialService(session).complete_multipart_upload(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        upload_session_uuid=upload_session_uuid,
        completed_parts=[(part.partNumber, part.etag) for part in payload.parts],
        current_user=current_user,
    )
    return CourseCatalogService(session).to_material_response(material, current_user=current_user)


@router.delete(
    "/courses/{course_uuid}/modules/{module_uuid}/materials/uploads/{upload_session_uuid}",
    summary="Abort Multipart Material Upload [Educator Owner/Admin]",
    description="Aborts a multipart upload session and releases the reserved upload state.",
    response_model=MultipartMaterialUploadSessionResponse,
    response_model_exclude_none=True,
)
def abort_multipart_module_material_upload(
    course_uuid: str,
    module_uuid: str,
    upload_session_uuid: str,
    current_user: dict = Depends(require_identity_permission(RESOURCE_UPLOAD)),
    session: Session = Depends(get_db_session),
) -> MultipartMaterialUploadSessionResponse:
    upload_session = ModuleMaterialService(session).abort_multipart_upload(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        upload_session_uuid=upload_session_uuid,
        current_user=current_user,
    )
    return MultipartMaterialUploadSessionResponse(
        uploadSessionId=upload_session.upload_session_id,
        uploadSessionUuid=upload_session.session_uuid,
        moduleId=upload_session.module_id,
        title=upload_session.title,
        materialType=upload_session.material_type.value,
        sortOrder=upload_session.sort_order,
        originalFilename=upload_session.original_filename,
        contentType=upload_session.content_type,
        sizeBytes=upload_session.size_bytes,
        storageProvider=upload_session.storage_provider,
        bucket=upload_session.bucket,
        objectKey=upload_session.object_key,
        status=upload_session.status.value,
        materialId=upload_session.material_id,
        createdAt=upload_session.created_at,
        updatedAt=upload_session.updated_at,
    )


@router.delete(
    "/courses/{course_uuid}/modules/{module_uuid}/materials/{material_uuid}",
    summary="Delete Module Material [Educator Owner/Admin]",
    description="Deletes a module material record and synchronously cleans up its stored file and AI index.",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_module_material(
    course_uuid: str,
    module_uuid: str,
    material_uuid: str,
    current_user: dict = Depends(require_identity_permission(RESOURCE_UPLOAD)),
    session: Session = Depends(get_db_session),
) -> Response:
    ModuleMaterialService(session).delete_material(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        material_uuid=material_uuid,
        current_user=current_user,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)

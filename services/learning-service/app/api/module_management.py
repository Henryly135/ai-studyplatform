from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.deps import require_identity_permission
from app.db.session import get_db_session
from app.schemas.module import (
    ModuleAuthoringResponse,
    ModuleCreateRequest,
    ModulePrerequisiteRequest,
    ModulePublishRequest,
    ModuleReorderRequest,
    ModuleUpdateRequest,
)
from app.services.module_management_service import ModuleManagementService
from platform_common.permissions.codes import MODULE_CREATE, MODULE_DELETE, MODULE_PUBLISH, MODULE_UPDATE


router = APIRouter(prefix="/courses/{course_uuid}/modules", tags=["module-management"])


@router.post(
    "",
    summary="Create Module [Educator Owner/Admin]",
    description="Creates a new draft module under the selected course.",
    response_model=ModuleAuthoringResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def create_module(
    course_uuid: str,
    payload: ModuleCreateRequest,
    current_user: dict = Depends(require_identity_permission(MODULE_CREATE)),
    session: Session = Depends(get_db_session),
) -> ModuleAuthoringResponse:
    return ModuleManagementService(session).create_module(
        course_uuid=course_uuid,
        payload=payload,
        current_user=current_user,
    )


@router.patch(
    "/reorder",
    summary="Reorder Modules [Educator Owner/Admin]",
    description="Reorders modules within the course learning path.",
    response_model=list[ModuleAuthoringResponse],
    response_model_exclude_none=True,
)
def reorder_modules(
    course_uuid: str,
    payload: ModuleReorderRequest,
    current_user: dict = Depends(require_identity_permission(MODULE_UPDATE)),
    session: Session = Depends(get_db_session),
) -> list[ModuleAuthoringResponse]:
    return ModuleManagementService(session).reorder_modules(
        course_uuid=course_uuid,
        payload=payload,
        current_user=current_user,
    )


@router.patch(
    "/{module_uuid}",
    summary="Update Module [Educator Owner/Admin]",
    description="Updates module content and authoring metadata.",
    response_model=ModuleAuthoringResponse,
    response_model_exclude_none=True,
)
def update_module(
    course_uuid: str,
    module_uuid: str,
    payload: ModuleUpdateRequest,
    current_user: dict = Depends(require_identity_permission(MODULE_UPDATE)),
    session: Session = Depends(get_db_session),
) -> ModuleAuthoringResponse:
    return ModuleManagementService(session).update_module(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        payload=payload,
        current_user=current_user,
    )


@router.post(
    "/{module_uuid}/publish",
    summary="Publish Module [Educator Owner/Admin]",
    description="Changes module status and releases blocked indexing jobs when the module becomes published.",
    response_model=ModuleAuthoringResponse,
    response_model_exclude_none=True,
)
def publish_module(
    course_uuid: str,
    module_uuid: str,
    payload: ModulePublishRequest,
    current_user: dict = Depends(require_identity_permission(MODULE_PUBLISH)),
    session: Session = Depends(get_db_session),
) -> ModuleAuthoringResponse:
    return ModuleManagementService(session).publish_module(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        payload=payload,
        current_user=current_user,
    )


@router.put(
    "/{module_uuid}/prerequisite",
    summary="Set Module Prerequisite [Educator Owner/Admin]",
    description="Sets the prerequisite module within the same course learning path.",
    response_model=ModuleAuthoringResponse,
    response_model_exclude_none=True,
)
def set_module_prerequisite(
    course_uuid: str,
    module_uuid: str,
    payload: ModulePrerequisiteRequest,
    current_user: dict = Depends(require_identity_permission(MODULE_UPDATE)),
    session: Session = Depends(get_db_session),
) -> ModuleAuthoringResponse:
    return ModuleManagementService(session).set_module_prerequisite(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        payload=payload,
        current_user=current_user,
    )


@router.delete(
    "/{module_uuid}/prerequisite",
    summary="Remove Module Prerequisite [Educator Owner/Admin]",
    description="Removes the prerequisite rule for a module.",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_module_prerequisite(
    course_uuid: str,
    module_uuid: str,
    current_user: dict = Depends(require_identity_permission(MODULE_UPDATE)),
    session: Session = Depends(get_db_session),
) -> Response:
    ModuleManagementService(session).remove_module_prerequisite(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        current_user=current_user,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{module_uuid}",
    summary="Delete Module [Educator Owner/Admin]",
    description="Deletes a module, its dependent materials, and reorders the remaining modules in the learning path.",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_module(
    course_uuid: str,
    module_uuid: str,
    current_user: dict = Depends(require_identity_permission(MODULE_DELETE)),
    session: Session = Depends(get_db_session),
) -> Response:
    ModuleManagementService(session).delete_module(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        current_user=current_user,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)

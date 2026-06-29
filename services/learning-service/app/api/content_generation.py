from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import require_identity_permission
from app.db.session import get_db_session
from app.schemas.content_generation import ContentDraftGenerateRequest, ContentDraftResponse, ContentDraftUpdateRequest
from app.services.content_generation_service import EducatorContentDraftService
from platform_common.permissions.codes import MODULE_UPDATE


router = APIRouter(prefix="/courses/{course_uuid}/modules/{module_uuid}/content-drafts", tags=["content-generation"])


@router.post(
    "/management/generate",
    summary="Generate Educator Content Draft [Educator Owner/Admin]",
    response_model=ContentDraftResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def generate_content_draft(
    course_uuid: str,
    module_uuid: str,
    payload: ContentDraftGenerateRequest,
    current_user: dict = Depends(require_identity_permission(MODULE_UPDATE)),
    session: Session = Depends(get_db_session),
) -> ContentDraftResponse:
    return EducatorContentDraftService(session).generate_draft(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        payload=payload,
        current_user=current_user,
    )


@router.get(
    "/management",
    summary="List Educator Content Drafts [Educator Owner/Admin]",
    response_model=list[ContentDraftResponse],
    response_model_exclude_none=True,
)
def list_content_drafts(
    course_uuid: str,
    module_uuid: str,
    current_user: dict = Depends(require_identity_permission(MODULE_UPDATE)),
    session: Session = Depends(get_db_session),
) -> list[ContentDraftResponse]:
    return EducatorContentDraftService(session).list_drafts(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        current_user=current_user,
    )


@router.get(
    "/management/{draft_uuid}",
    summary="Get Educator Content Draft [Educator Owner/Admin]",
    response_model=ContentDraftResponse,
    response_model_exclude_none=True,
)
def get_content_draft(
    course_uuid: str,
    module_uuid: str,
    draft_uuid: str,
    current_user: dict = Depends(require_identity_permission(MODULE_UPDATE)),
    session: Session = Depends(get_db_session),
) -> ContentDraftResponse:
    return EducatorContentDraftService(session).get_draft(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        draft_uuid=draft_uuid,
        current_user=current_user,
    )


@router.patch(
    "/management/{draft_uuid}",
    summary="Update Educator Content Draft [Educator Owner/Admin]",
    response_model=ContentDraftResponse,
    response_model_exclude_none=True,
)
def update_content_draft(
    course_uuid: str,
    module_uuid: str,
    draft_uuid: str,
    payload: ContentDraftUpdateRequest,
    current_user: dict = Depends(require_identity_permission(MODULE_UPDATE)),
    session: Session = Depends(get_db_session),
) -> ContentDraftResponse:
    return EducatorContentDraftService(session).update_draft(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        draft_uuid=draft_uuid,
        payload=payload,
        current_user=current_user,
    )

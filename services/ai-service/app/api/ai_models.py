from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_identity_permission
from app.db.session import get_db_session
from app.schemas.ai_models import AIModelCatalogResponse
from app.core.uuid_codec import decode_course_uuid, decode_module_uuid
from app.services.chat.learning_context_access_client import (
    LearningContextAccessClient,
)
from app.services.providers.model_service import AIModelCatalogService
from platform_common.errors import invalid_request_error
from platform_common.permissions.codes import AI_CHAT_USE


router = APIRouter(tags=["ai-models"])


@router.get("/models", response_model=AIModelCatalogResponse)
def list_ai_models(
    courseUuid: str | None = Query(default=None),
    moduleUuid: str | None = Query(default=None),
    current_user: dict = Depends(require_identity_permission(AI_CHAT_USE)),
    db: Session = Depends(get_db_session),
) -> AIModelCatalogResponse:
    if moduleUuid and not courseUuid:
        raise invalid_request_error("moduleUuid requires courseUuid.")
    if courseUuid:
        LearningContextAccessClient().ensure_chat_context_access(
            course_uuid=courseUuid,
            module_uuid=moduleUuid,
            current_user=current_user,
        )

    payload = AIModelCatalogService(db).list_model_status(
        user_id=int(current_user["id"]),
        course_id=decode_course_uuid(courseUuid) if courseUuid else None,
        module_id=decode_module_uuid(moduleUuid) if moduleUuid else None,
    )
    return AIModelCatalogResponse.model_validate(payload)

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_identity_permission
from app.db.session import get_db_session
from app.schemas.ai_models import AIModelCatalogResponse
from app.services.providers.model_service import AIModelCatalogService
from platform_common.permissions.codes import AI_CHAT_USE


router = APIRouter(tags=["ai-models"])


@router.get("/models", response_model=AIModelCatalogResponse)
def list_ai_models(
    current_user: dict = Depends(require_identity_permission(AI_CHAT_USE)),
    db: Session = Depends(get_db_session),
) -> AIModelCatalogResponse:
    payload = AIModelCatalogService(db).list_model_status(user_id=int(current_user["id"]))
    return AIModelCatalogResponse.model_validate(payload)

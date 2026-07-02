from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_internal_request
from app.db.session import get_db_session
from app.schemas.ai_context import AIChatContextAccessRequest, AIChatContextAccessResponse
from app.services.ai_context_access_service import AIContextAccessService


router = APIRouter(prefix="/internal/ai-context", tags=["internal-ai-context"])


@router.post("/chat-access", response_model=AIChatContextAccessResponse)
def check_ai_chat_context_access(
    payload: AIChatContextAccessRequest,
    _: None = Depends(require_internal_request),
    session: Session = Depends(get_db_session),
) -> AIChatContextAccessResponse:
    AIContextAccessService(session).ensure_chat_context_access(
        course_uuid=payload.courseUuid,
        module_uuid=payload.moduleUuid,
        user_id=payload.userId,
        identity=payload.identity,
    )
    return AIChatContextAccessResponse(allowed=True)

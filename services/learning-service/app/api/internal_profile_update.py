from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_internal_request
from app.db.session import get_db_session
from app.schemas.profile_update import QuizSignalSummaryRequest, QuizSignalSummaryResponse
from app.services.quiz_signal_service import QuizSignalService


router = APIRouter(prefix="/internal/profile-update", tags=["internal-profile-update"])


@router.post("/quiz-signal-summary", response_model=QuizSignalSummaryResponse)
def get_quiz_signal_summary(
    payload: QuizSignalSummaryRequest,
    _: None = Depends(require_internal_request),
    session: Session = Depends(get_db_session),
) -> QuizSignalSummaryResponse:
    return QuizSignalService(session).build_summary(payload=payload)

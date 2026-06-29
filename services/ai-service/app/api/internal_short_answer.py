from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import require_internal_request
from app.schemas.short_answer import ShortAnswerEvaluationRequest, ShortAnswerEvaluationResponse
from app.services.short_answer_evaluation_service import ShortAnswerEvaluationService


router = APIRouter(prefix="/internal/short-answer", tags=["internal-short-answer"])


@router.post("/evaluate", response_model=ShortAnswerEvaluationResponse)
def evaluate_short_answer(
    payload: ShortAnswerEvaluationRequest,
    _: None = Depends(require_internal_request),
) -> ShortAnswerEvaluationResponse:
    return ShortAnswerEvaluationService().evaluate(payload)

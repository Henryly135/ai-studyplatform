from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import require_internal_request
from app.services.study_planner.generation_service import StudyPlanGenerationService
from app.services.study_planner.schemas import StudyPlanGenerationRequest, StudyPlanGenerationResponse


router = APIRouter(prefix="/internal/study-planner", tags=["internal-study-planner"])


@router.post("/generate", response_model=StudyPlanGenerationResponse)
def generate_study_plan(
    payload: StudyPlanGenerationRequest,
    _: None = Depends(require_internal_request),
) -> StudyPlanGenerationResponse:
    return StudyPlanGenerationService().generate(payload)

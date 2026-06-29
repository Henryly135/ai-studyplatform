from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import require_internal_request
from app.schemas.content_generation import ContentGenerationRequest, ContentGenerationResponse
from app.services.content_generation_service import EducatorContentGenerationService


router = APIRouter(prefix="/internal/content-generation", tags=["internal-content-generation"])


@router.post("/educator-draft", response_model=ContentGenerationResponse)
def generate_educator_content_draft(
    payload: ContentGenerationRequest,
    _: None = Depends(require_internal_request),
) -> ContentGenerationResponse:
    return EducatorContentGenerationService().generate(payload)

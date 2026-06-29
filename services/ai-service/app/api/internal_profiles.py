from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_internal_request
from app.db.session import get_db_session
from app.schemas.profiles import (
    GlobalProfileExistenceRead,
    ModuleProfileInitBatchRequest,
    ModuleProfileInitBatchResponse,
)
from app.services.profiles.global_profile_service import GlobalProfileService
from app.services.profiles.module_profile_service import ModuleProfileService


router = APIRouter(prefix="/internal/profiles", tags=["internal-profiles"])


@router.get("/global-exists/{learner_id}", response_model=GlobalProfileExistenceRead)
def get_global_profile_exists(
    learner_id: int,
    _: None = Depends(require_internal_request),
    db: Session = Depends(get_db_session),
) -> GlobalProfileExistenceRead:
    exists = GlobalProfileService(db).global_profile_exists(learner_id=learner_id)
    return GlobalProfileExistenceRead(learnerId=learner_id, exists=exists)


@router.post("/module/init-batch", response_model=ModuleProfileInitBatchResponse)
def initialize_module_profiles_batch(
    payload: ModuleProfileInitBatchRequest,
    _: None = Depends(require_internal_request),
    db: Session = Depends(get_db_session),
) -> ModuleProfileInitBatchResponse:
    return ModuleProfileService(db).initialize_batch_for_learner(payload=payload)

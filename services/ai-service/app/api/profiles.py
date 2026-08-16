from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_identity_permission
from app.db.session import get_db_session
from app.schemas.profiles import (
    GlobalProfileInitRequest,
    GlobalProfileRead,
    GlobalProfileUpdateRequest,
    ModuleProfileRead,
)
from app.services.profiles.global_profile_service import GlobalProfileService
from app.services.profiles.module_profile_service import ModuleProfileService
from platform_common.permissions.codes import LEARNER_PROFILE_MANAGE


router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.post("/global/init", response_model=GlobalProfileRead)
def initialize_global_profile(
    payload: GlobalProfileInitRequest,
    current_user: dict = Depends(require_identity_permission(LEARNER_PROFILE_MANAGE)),
    db: Session = Depends(get_db_session),
) -> GlobalProfileRead:
    learner_id = int(current_user["id"])
    return GlobalProfileService(db).initialize_for_learner(learner_id=learner_id, payload=payload)


@router.get("/global/me", response_model=GlobalProfileRead)
def get_my_global_profile(
    current_user: dict = Depends(require_identity_permission(LEARNER_PROFILE_MANAGE)),
    db: Session = Depends(get_db_session),
) -> GlobalProfileRead:
    learner_id = int(current_user["id"])
    return GlobalProfileService(db).get_for_learner(learner_id=learner_id)


@router.put("/global/me", response_model=GlobalProfileRead)
def update_my_global_profile(
    payload: GlobalProfileUpdateRequest,
    current_user: dict = Depends(require_identity_permission(LEARNER_PROFILE_MANAGE)),
    db: Session = Depends(get_db_session),
) -> GlobalProfileRead:
    learner_id = int(current_user["id"])
    return GlobalProfileService(db).update_for_learner(learner_id=learner_id, payload=payload)


@router.delete("/global/me", response_model=GlobalProfileRead)
def reset_my_global_profile(
    current_user: dict = Depends(require_identity_permission(LEARNER_PROFILE_MANAGE)),
    db: Session = Depends(get_db_session),
) -> GlobalProfileRead:
    learner_id = int(current_user["id"])
    return GlobalProfileService(db).reset_for_learner(learner_id=learner_id)


@router.post("/module/{course_uuid}/{module_uuid}/init", response_model=ModuleProfileRead)
def initialize_module_profile(
    course_uuid: str,
    module_uuid: str,
    current_user: dict = Depends(require_identity_permission(LEARNER_PROFILE_MANAGE)),
    db: Session = Depends(get_db_session),
) -> ModuleProfileRead:
    learner_id = int(current_user["id"])
    return ModuleProfileService(db).initialize_for_learner(
        learner_id=learner_id,
        course_uuid=course_uuid,
        module_uuid=module_uuid,
    )


@router.get("/module/{course_uuid}/{module_uuid}", response_model=ModuleProfileRead)
def get_my_module_profile(
    course_uuid: str,
    module_uuid: str,
    current_user: dict = Depends(require_identity_permission(LEARNER_PROFILE_MANAGE)),
    db: Session = Depends(get_db_session),
) -> ModuleProfileRead:
    learner_id = int(current_user["id"])
    return ModuleProfileService(db).get_for_learner(
        learner_id=learner_id,
        course_uuid=course_uuid,
        module_uuid=module_uuid,
    )

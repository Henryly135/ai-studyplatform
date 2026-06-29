from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_internal_request
from app.db.session import get_db_session
from app.schemas.profile_update import (
    ModuleProfileCandidateUpdateRequest,
    ModuleProfileCandidateUpdateResponse,
    ModuleProfileUpdateCheckRequest,
    ModuleProfileUpdateCheckResponse,
    ModuleUpdateContextRequest,
    ModuleUpdateContextResponse,
)
from app.services.orchestration.langgraph.checkpointer import build_graph_config, get_langgraph_checkpointer
from app.services.orchestration.langgraph.profile_update_graph import ModuleProfileUpdateGraphRunner
from app.services.workflows.profile_update.services.candidate_service import ModuleProfileCandidateService
from app.services.workflows.profile_update.services.context_service import ModuleUpdateContextService


router = APIRouter(prefix="/internal/profile-update", tags=["internal-profile-update"])


@router.post("/context", response_model=ModuleUpdateContextResponse)
def get_module_update_context(
    payload: ModuleUpdateContextRequest,
    _: None = Depends(require_internal_request),
    session: Session = Depends(get_db_session),
) -> ModuleUpdateContextResponse:
    return ModuleUpdateContextService(session).build_context(payload=payload)


@router.post("/candidate", response_model=ModuleProfileCandidateUpdateResponse)
def submit_module_profile_candidate_update(
    payload: ModuleProfileCandidateUpdateRequest,
    _: None = Depends(require_internal_request),
    session: Session = Depends(get_db_session),
) -> ModuleProfileCandidateUpdateResponse:
    return ModuleProfileCandidateService(session).submit_candidate_patch(payload=payload)


@router.post("/run-check", response_model=ModuleProfileUpdateCheckResponse)
def run_module_profile_update_check(
    payload: ModuleProfileUpdateCheckRequest,
    _: None = Depends(require_internal_request),
    session: Session = Depends(get_db_session),
) -> ModuleProfileUpdateCheckResponse:
    thread_id = f"profile-update:{payload.learnerId}:{payload.courseUuid}:{payload.moduleUuid}"
    config = build_graph_config(thread_id=thread_id, checkpoint_ns="profile_update")
    return ModuleProfileUpdateGraphRunner(
        session,
        checkpointer=get_langgraph_checkpointer(),
    ).run(payload=payload, config=config)

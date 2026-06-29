from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_internal_request
from app.db.session import get_db_session
from app.schemas.user_directory import UserDirectoryLookupRequest, UserDirectoryLookupResponse
from app.services.user_directory_service import UserDirectoryService


router = APIRouter(prefix="/internal", tags=["internal"])


@router.post("/users/lookup", response_model=UserDirectoryLookupResponse)
def lookup_users(
    payload: UserDirectoryLookupRequest,
    _: None = Depends(require_internal_request),
    session: Session = Depends(get_db_session),
) -> UserDirectoryLookupResponse:
    return UserDirectoryService(session).lookup_users_by_ids(user_ids=payload.userIds)

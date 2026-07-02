from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_internal_request
from app.db.session import get_db_session
from app.schemas.course_access import ForumCourseAccessRequest, ForumCourseAccessResponse
from app.services.course_space_access_service import CourseSpaceAccessService


router = APIRouter(prefix="/internal/course-access", tags=["internal-course-access"])


@router.post("/forum", response_model=ForumCourseAccessResponse)
def check_course_forum_access(
    payload: ForumCourseAccessRequest,
    _: None = Depends(require_internal_request),
    session: Session = Depends(get_db_session),
) -> ForumCourseAccessResponse:
    CourseSpaceAccessService(session).ensure_forum_access(
        course_uuid=payload.courseUuid,
        user_id=payload.userId,
        identity=payload.identity,
    )
    return ForumCourseAccessResponse(allowed=True)

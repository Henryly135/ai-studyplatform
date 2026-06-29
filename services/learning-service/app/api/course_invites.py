from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.public_url import resolve_public_frontend_base_url
from app.core.deps import require_identity_permission, require_identity_user
from app.db.session import get_db_session
from app.services.course_invite_service import CourseInviteService, CourseInviteServiceError
from platform_common.permissions.codes import COURSE_ENROLLMENT_MANAGE, COURSE_ENROL


router = APIRouter(tags=["course-invites"])


@router.post(
    "/courses/{course_uuid}/invite-links",
    summary="Generate Course Invite Link [Educator]",
    description="Generates a reusable invite link for learners to self-enrol into the course.",
)
def generate_course_invite_link(
    course_uuid: str,
    request: Request,
    current_user: dict = Depends(require_identity_permission(COURSE_ENROLLMENT_MANAGE)),
    session: Session = Depends(get_db_session),
):
    try:
        return CourseInviteService(session).generate_invite_link(
            course_uuid=course_uuid,
            current_user=current_user,
            public_frontend_base_url=resolve_public_frontend_base_url(request),
        )
    except CourseInviteServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get(
    "/courses/{course_uuid}/invite-links",
    summary="List Course Invite Links [Educator]",
    description="Lists all invite links for a course.",
)
def list_course_invite_links(
    course_uuid: str,
    request: Request,
    current_user: dict = Depends(require_identity_permission(COURSE_ENROLLMENT_MANAGE)),
    session: Session = Depends(get_db_session),
):
    try:
        return CourseInviteService(session).list_invite_links(
            course_uuid=course_uuid,
            current_user=current_user,
            public_frontend_base_url=resolve_public_frontend_base_url(request),
        )
    except CourseInviteServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.delete(
    "/courses/invite-links/{invite_uuid}",
    summary="Deactivate Course Invite Link [Educator]",
    description="Deactivates an invite link so it can no longer be used.",
)
def deactivate_course_invite_link(
    invite_uuid: str,
    current_user: dict = Depends(require_identity_permission(COURSE_ENROLLMENT_MANAGE)),
    session: Session = Depends(get_db_session),
):
    try:
        return CourseInviteService(session).deactivate_invite_link(
            invite_uuid=invite_uuid,
            current_user=current_user,
        )
    except CourseInviteServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get(
    "/invite/course/validate",
    summary="Validate Course Invite Token [Public]",
    description="Validates a course invite token and returns course information.",
)
def validate_course_invite_token(
    token: str | None = None,
    session: Session = Depends(get_db_session),
):
    return CourseInviteService(session).validate_invite_token(token=token or "")


@router.post(
    "/invite/course/enrol",
    summary="Enrol via Course Invite Link [Learner]",
    description="Enrols the authenticated learner into the course associated with the invite token.",
)
def enrol_via_course_invite(
    token: str,
    current_user: dict = Depends(require_identity_permission(COURSE_ENROL)),
    session: Session = Depends(get_db_session),
):
    return CourseInviteService(session).enrol_via_invite(
        token=token,
        current_user=current_user,
    )

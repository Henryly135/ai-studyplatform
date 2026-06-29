from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.orm import Session

from app.core.deps import require_identity_permission
from app.core.time import now_local
from app.core.uuid_codec import decode_comment_uuid, decode_course_uuid, decode_forum_post_uuid
from app.db.session import get_db_session
from app.schemas.forum import (
    CourseForumCommentCreateRequest,
    CourseForumCommentRead,
    CourseForumCommentUpdateRequest,
    CourseForumPostCreateRequest,
    CourseForumPostRead,
    CourseForumPostUpdateRequest,
    PaginatedCourseForumCommentResponse,
    PaginatedCourseForumPostResponse,
)
from app.services.forum_comment_service import ForumCommentService
from app.services.forum_service import ForumService
from platform_common.auth import parse_bearer_token
from platform_common.permissions.codes import FORUM_PIN, FORUM_READ, FORUM_WRITE


router = APIRouter(tags=["forum"])


@router.post(
    "/courses/{course_uuid}/forum-posts",
    response_model=CourseForumPostRead,
    status_code=status.HTTP_201_CREATED,
)
def create_forum_post(
    course_uuid: str,
    payload: CourseForumPostCreateRequest,
    current_user: dict = Depends(require_identity_permission(FORUM_WRITE)),
    session: Session = Depends(get_db_session),
) -> CourseForumPostRead:
    return ForumService(session).create_post(
        course_id=decode_course_uuid(course_uuid),
        payload=payload,
        current_user=current_user,
    )


@router.get(
    "/courses/{course_uuid}/forum-posts",
    response_model=PaginatedCourseForumPostResponse,
)
def list_forum_posts(
    course_uuid: str,
    query: str | None = Query(default=None, alias="query"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=100),
    current_user: dict = Depends(require_identity_permission(FORUM_READ)),
    session: Session = Depends(get_db_session),
) -> PaginatedCourseForumPostResponse:
    _ = current_user
    return ForumService(session).list_posts(
        course_id=decode_course_uuid(course_uuid),
        query=query,
        page=page,
        page_size=page_size,
    )


@router.get("/forum-posts/{post_uuid}", response_model=CourseForumPostRead)
def get_forum_post(
    post_uuid: str,
    current_user: dict = Depends(require_identity_permission(FORUM_READ)),
    session: Session = Depends(get_db_session),
) -> CourseForumPostRead:
    _ = current_user
    return ForumService(session).get_post(post_id=decode_forum_post_uuid(post_uuid))


@router.patch("/forum-posts/{post_uuid}", response_model=CourseForumPostRead)
def update_forum_post(
    post_uuid: str,
    payload: CourseForumPostUpdateRequest,
    current_user: dict = Depends(require_identity_permission(FORUM_WRITE)),
    session: Session = Depends(get_db_session),
) -> CourseForumPostRead:
    return ForumService(session).update_post(
        post_id=decode_forum_post_uuid(post_uuid),
        payload=payload,
        current_user=current_user,
    )


@router.delete("/forum-posts/{post_uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_forum_post(
    post_uuid: str,
    current_user: dict = Depends(require_identity_permission(FORUM_WRITE)),
    session: Session = Depends(get_db_session),
) -> Response:
    ForumService(session).delete_post(post_id=decode_forum_post_uuid(post_uuid), current_user=current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/forum-posts/{post_uuid}/pin", response_model=CourseForumPostRead)
def pin_forum_post(
    post_uuid: str,
    authorization: str | None = Header(None),
    current_user: dict = Depends(require_identity_permission(FORUM_PIN)),
    session: Session = Depends(get_db_session),
) -> CourseForumPostRead:
    return ForumService(session).pin_post(
        post_id=decode_forum_post_uuid(post_uuid),
        current_user=current_user,
        token=parse_bearer_token(authorization),
    )


@router.delete("/forum-posts/{post_uuid}/pin", response_model=CourseForumPostRead)
def unpin_forum_post(
    post_uuid: str,
    authorization: str | None = Header(None),
    current_user: dict = Depends(require_identity_permission(FORUM_PIN)),
    session: Session = Depends(get_db_session),
) -> CourseForumPostRead:
    return ForumService(session).unpin_post(
        post_id=decode_forum_post_uuid(post_uuid),
        current_user=current_user,
        token=parse_bearer_token(authorization),
    )


@router.post(
    "/forum-posts/{post_uuid}/comments",
    response_model=CourseForumCommentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_forum_comment(
    post_uuid: str,
    payload: CourseForumCommentCreateRequest,
    current_user: dict = Depends(require_identity_permission(FORUM_WRITE)),
    session: Session = Depends(get_db_session),
) -> CourseForumCommentRead:
    return ForumCommentService(session).create_comment(
        post_id=decode_forum_post_uuid(post_uuid),
        payload=payload,
        current_user=current_user,
    )


@router.get(
    "/forum-posts/{post_uuid}/comments",
    response_model=PaginatedCourseForumCommentResponse,
)
def list_forum_comments(
    post_uuid: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=5, alias="pageSize", ge=1, le=100),
    current_user: dict = Depends(require_identity_permission(FORUM_READ)),
    session: Session = Depends(get_db_session),
) -> PaginatedCourseForumCommentResponse:
    _ = current_user
    return ForumCommentService(session).list_post_comments(
        post_id=decode_forum_post_uuid(post_uuid),
        page=page,
        page_size=page_size,
    )


@router.get("/forum-comments/{comment_uuid}", response_model=CourseForumCommentRead)
def get_forum_comment(
    comment_uuid: str,
    current_user: dict = Depends(require_identity_permission(FORUM_READ)),
    session: Session = Depends(get_db_session),
) -> CourseForumCommentRead:
    _ = current_user
    return ForumCommentService(session).get_comment(comment_id=decode_comment_uuid(comment_uuid))


@router.get(
    "/forum-comments/{comment_uuid}/replies",
    response_model=PaginatedCourseForumCommentResponse,
)
def list_forum_comment_replies(
    comment_uuid: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=5, alias="pageSize", ge=1, le=100),
    current_user: dict = Depends(require_identity_permission(FORUM_READ)),
    session: Session = Depends(get_db_session),
) -> PaginatedCourseForumCommentResponse:
    _ = current_user
    return ForumCommentService(session).list_comment_replies(
        comment_id=decode_comment_uuid(comment_uuid),
        page=page,
        page_size=page_size,
    )


@router.patch("/forum-comments/{comment_uuid}", response_model=CourseForumCommentRead)
def update_forum_comment(
    comment_uuid: str,
    payload: CourseForumCommentUpdateRequest,
    current_user: dict = Depends(require_identity_permission(FORUM_WRITE)),
    session: Session = Depends(get_db_session),
) -> CourseForumCommentRead:
    return ForumCommentService(session).update_comment(
        comment_id=decode_comment_uuid(comment_uuid),
        payload=payload,
        current_user=current_user,
    )


@router.delete("/forum-comments/{comment_uuid}", response_model=CourseForumCommentRead)
def delete_forum_comment(
    comment_uuid: str,
    current_user: dict = Depends(require_identity_permission(FORUM_WRITE)),
    session: Session = Depends(get_db_session),
) -> CourseForumCommentRead:
    return ForumCommentService(session).delete_comment(
        comment_id=decode_comment_uuid(comment_uuid),
        deleted_at=now_local(),
        current_user=current_user,
    )

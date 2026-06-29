from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import require_identity_user
from app.db.session import get_db_session
from app.schemas.course import CourseDetailResponse, CourseSummaryResponse, ModuleResponse, PaginatedCourseSummaryResponse
from app.services.course_catalog_service import CourseCatalogService


router = APIRouter(prefix="/courses", tags=["course-catalog"])


@router.get(
    "/search",
    summary="Search Courses [Any Authenticated User]",
    description="Searches published courses by title or subtitle for the course-center experience.",
    response_model=list[CourseSummaryResponse],
    response_model_exclude_none=True,
)
def search_courses(
    q: str = Query(..., min_length=1),
    current_user: dict = Depends(require_identity_user),
    session: Session = Depends(get_db_session),
):
    return CourseCatalogService(session).search_courses(current_user=current_user, query=q)


@router.get(
    "",
    summary="List Courses [Any Authenticated User]",
    description="Public course-center endpoint that returns published courses only.",
    response_model=PaginatedCourseSummaryResponse,
    response_model_exclude_none=True,
)
def list_courses(
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, alias="pageSize", ge=1, le=100),
    current_user: dict = Depends(require_identity_user),
    session: Session = Depends(get_db_session),
):
    return CourseCatalogService(session).list_published_courses(
        current_user=current_user,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{course_uuid}/modules/{module_uuid}",
    summary="Get Course Module [Any Authenticated User]",
    description="Returns a single module using course-center access rules for the current identity.",
    response_model=ModuleResponse,
    response_model_exclude_none=True,
)
def get_course_module(
    course_uuid: str,
    module_uuid: str,
    class_id: str | None = Query(default=None, alias="classId"),
    current_user: dict = Depends(require_identity_user),
    session: Session = Depends(get_db_session),
):
    return CourseCatalogService(session).get_course_module_by_uuid(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        current_user=current_user,
        class_id=class_id,
    )


@router.get(
    "/{course_uuid}",
    summary="Get Course By Uuid [Any Authenticated User]",
    description="Returns course-center course detail using published visibility rules.",
    response_model=CourseDetailResponse,
    response_model_exclude_none=True,
)
def get_course_by_uuid(
    course_uuid: str,
    class_id: str | None = Query(default=None, alias="classId"),
    current_user: dict = Depends(require_identity_user),
    session: Session = Depends(get_db_session),
):
    return CourseCatalogService(session).get_course_by_uuid(
        course_uuid=course_uuid,
        current_user=current_user,
        class_id=class_id,
    )

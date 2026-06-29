from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import require_identity_permission, require_identity_user
from app.db.session import get_db_session
from app.schemas.course import (
    CourseCreateRequest,
    CourseDetailResponse,
    CourseSummaryResponse,
    CoursePublishRequest,
    CourseUpdateRequest,
    EducatorAnalyticsResponse,
    EducatorQuizAnalyticsResponse,
    PaginatedCourseSummaryResponse,
)
from app.services.course_catalog_service import CourseCatalogService
from app.services.course_management_service import CourseManagementService
from platform_common.permissions.codes import COURSE_CREATE, COURSE_PUBLISH, COURSE_UPDATE


router = APIRouter(prefix="/courses", tags=["course-management"])


@router.post(
    "",
    summary="Create Course [Educator]",
    description="Creates a new draft course and its default learning path. Accepts multipart/form-data and optionally stores coverImage under the courseUuid folder.",
    response_model=CourseDetailResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def create_course(
    title: str = Form(..., min_length=1, max_length=200),
    subtitle: str | None = Form(default=None, max_length=255),
    description: str | None = Form(default=None),
    difficulty_level: str | None = Form(default=None, alias="difficultyLevel"),
    estimated_minutes: int | None = Form(default=None, alias="estimatedMinutes", ge=1),
    category: str | None = Form(default=None, max_length=100),
    language_code: str | None = Form(default=None, alias="languageCode", max_length=20),
    is_public: bool = Form(default=False, alias="isPublic"),
    learning_path_title: str | None = Form(default=None, alias="learningPathTitle", max_length=200),
    learning_path_description: str | None = Form(default=None, alias="learningPathDescription"),
    cover_image: UploadFile | None = File(default=None, alias="coverImage"),
    current_user: dict = Depends(require_identity_permission(COURSE_CREATE)),
    session: Session = Depends(get_db_session),
) -> CourseDetailResponse:
    payload = CourseCreateRequest(
        title=title,
        subtitle=subtitle,
        description=description,
        difficultyLevel=difficulty_level,
        estimatedMinutes=estimated_minutes,
        category=category,
        languageCode=language_code,
        isPublic=is_public,
        learningPathTitle=learning_path_title,
        learningPathDescription=learning_path_description,
    )
    return CourseManagementService(session).create_course(
        payload=payload,
        current_user=current_user,
        cover_image=cover_image,
    )


@router.patch(
    "/{course_uuid}",
    summary="Update Course [Educator Owner/Admin]",
    description="Updates course-level metadata such as title, description, cover, and learning path title/description.",
    response_model=CourseDetailResponse,
    response_model_exclude_none=True,
)
def update_course(
    course_uuid: str,
    payload: CourseUpdateRequest,
    current_user: dict = Depends(require_identity_permission(COURSE_UPDATE)),
    session: Session = Depends(get_db_session),
) -> CourseDetailResponse:
    return CourseManagementService(session).update_course(
        course_uuid=course_uuid,
        payload=payload,
        current_user=current_user,
    )


@router.delete(
    "/{course_uuid}",
    summary="Delete Course [Educator Owner/Admin]",
    description="Deletes a course and synchronously cleans up its cover image and material dependencies.",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_course(
    course_uuid: str,
    current_user: dict = Depends(require_identity_permission(COURSE_UPDATE)),
    session: Session = Depends(get_db_session),
) -> Response:
    CourseManagementService(session).delete_course(
        course_uuid=course_uuid,
        current_user=current_user,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{course_uuid}/cover",
    summary="Upload Course Cover [Educator Owner/Admin]",
    description="Uploads and stores a replacement course cover image without changing the original JSON course update contract.",
    response_model=CourseDetailResponse,
    response_model_exclude_none=True,
)
def upload_course_cover(
    course_uuid: str,
    cover_image: UploadFile = File(..., alias="coverImage"),
    current_user: dict = Depends(require_identity_permission(COURSE_UPDATE)),
    session: Session = Depends(get_db_session),
) -> CourseDetailResponse:
    return CourseManagementService(session).update_course_cover(
        course_uuid=course_uuid,
        cover_image=cover_image,
        current_user=current_user,
    )


@router.post(
    "/{course_uuid}/publish",
    summary="Publish Course [Educator Owner/Admin]",
    description="Publishes the course and the selected modules after validating they are publish-ready.",
    response_model=CourseDetailResponse,
    response_model_exclude_none=True,
)
def publish_course(
    course_uuid: str,
    payload: CoursePublishRequest,
    current_user: dict = Depends(require_identity_permission(COURSE_PUBLISH)),
    session: Session = Depends(get_db_session),
) -> CourseDetailResponse:
    return CourseManagementService(session).publish_course(
        course_uuid=course_uuid,
        payload=payload,
        current_user=current_user,
    )


@router.get(
    "/me/analytics",
    summary="Get My Course Analytics [Educator]",
    description="Returns per-course enrollment stats and aggregate totals for all courses owned by the current educator.",
    response_model=EducatorAnalyticsResponse,
    response_model_exclude_none=True,
)
def get_my_analytics(
    current_user: dict = Depends(require_identity_permission(COURSE_CREATE)),
    session: Session = Depends(get_db_session),
) -> EducatorAnalyticsResponse:
    return CourseManagementService(session).get_educator_analytics(current_user=current_user)


@router.get(
    "/me/analytics/quiz",
    summary="Get My Quiz Analytics [Educator]",
    description="Returns per-module quiz stats across all courses owned by the current educator.",
    response_model=EducatorQuizAnalyticsResponse,
    response_model_exclude_none=True,
)
def get_my_quiz_analytics(
    current_user: dict = Depends(require_identity_permission(COURSE_CREATE)),
    session: Session = Depends(get_db_session),
) -> EducatorQuizAnalyticsResponse:
    return CourseManagementService(session).get_educator_quiz_analytics(current_user=current_user)


@router.get(
    "/me/managed",
    summary="List My Managed Courses [Educator/Admin]",
    description="Educator sees only their own courses across all statuses; Admin sees all courses across all statuses.",
    response_model=PaginatedCourseSummaryResponse,
    response_model_exclude_none=True,
)
def list_my_managed_courses(
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    offset: int | None = Query(default=None, ge=0),
    page_size: int = Query(default=23, alias="pageSize", ge=1, le=100),
    current_user: dict = Depends(require_identity_user),
    session: Session = Depends(get_db_session),
):
    return CourseCatalogService(session).list_managed_courses(
        current_user=current_user,
        search=search,
        page=page,
        page_size=page_size,
        offset=offset,
    )


@router.get(
    "/{course_uuid}/management",
    summary="Get Course Management Detail [Educator Owner/Admin]",
    description="Returns all modules and materials for management, without course-center visibility filtering.",
    response_model=CourseDetailResponse,
    response_model_exclude_none=True,
)
def get_course_management_by_uuid(
    course_uuid: str,
    current_user: dict = Depends(require_identity_user),
    session: Session = Depends(get_db_session),
):
    return CourseCatalogService(session).get_course_management_by_uuid(
        course_uuid=course_uuid,
        current_user=current_user,
    )

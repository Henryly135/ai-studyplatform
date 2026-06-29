import re
from urllib.parse import urlparse

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.uuid_codec import (
    decode_course_uuid,
    decode_module_uuid,
    encode_course_uuid,
    encode_material_uuid,
    encode_module_uuid,
    encode_user_uuid,
)
from app.models.courses import Course
from app.models.module_materials import ModuleMaterial
from app.models.module_progress import ProgressStatus
from app.models.modules import Module
from app.repositories.learning_path_repository import LearningPathRepository
from app.repositories.module_material_repository import ModuleMaterialRepository
from app.repositories.module_prerequisite_repository import ModulePrerequisiteRepository
from app.repositories.module_progress_repository import ModuleProgressRepository
from app.repositories.module_repository import ModuleRepository
from app.repositories.course_enrollment_repository import CourseEnrollmentRepository
from app.repositories.course_repository import CourseRepository
from app.repositories.quiz_repository import QuizRepository
from app.schemas.course import (
    CourseDetailResponse,
    CourseSummaryResponse,
    MaterialResponse,
    ModuleResponse,
    PaginatedCourseSummaryResponse,
)
from app.models.courses import CourseStatus
from app.services.identity_user_client import IdentityUserClient
from app.services.module_unlocking_service import ModuleUnlockingService


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "module"


class CourseCatalogService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.courses = CourseRepository(session)
        self.learning_paths = LearningPathRepository(session)
        self.modules = ModuleRepository(session)
        self.materials = ModuleMaterialRepository(session)
        self.module_prerequisites = ModulePrerequisiteRepository(session)
        self.module_progress = ModuleProgressRepository(session)
        self.enrollments = CourseEnrollmentRepository(session)
        self.quizzes = QuizRepository(session)
        self.identity_users = IdentityUserClient()
        self.unlocking = ModuleUnlockingService(session)

    def list_courses(self, *, current_user: dict, search: str | None = None) -> list[CourseSummaryResponse]:
        courses = self.courses.list_all()
        if search:
            normalized_search = search.strip().lower()
            courses = [
                course
                for course in courses
                if normalized_search
                in " ".join(
                    filter(
                        None,
                        [
                            course.title,
                            course.subtitle,
                            course.description,
                            course.category,
                        ],
                    )
                ).lower()
            ]

        educator_profiles_by_id = self._lookup_educator_profiles(courses)
        return [
            self._to_course_summary(
                course,
                current_user=current_user,
                educator_profiles_by_id=educator_profiles_by_id,
            )
            for course in courses
        ]

    def list_published_courses(
        self,
        *,
        current_user: dict,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedCourseSummaryResponse:
        courses, total, safe_page, total_pages = self.courses.list_by_status_paginated(
            CourseStatus.PUBLISHED,
            search=search,
            page=page,
            page_size=page_size,
        )
        educator_profiles_by_id = self._lookup_educator_profiles(courses)
        return PaginatedCourseSummaryResponse(
            items=[
                self._to_course_summary(
                    course,
                    current_user=current_user,
                    educator_profiles_by_id=educator_profiles_by_id,
                )
                for course in courses
            ],
            page=safe_page,
            pageSize=page_size,
            total=total,
            totalPages=total_pages,
        )

    def list_enrolled_courses(
        self,
        *,
        current_user: dict,
        search: str | None = None,
    ) -> list[CourseSummaryResponse]:
        learner_id = current_user.get("id")
        if not isinstance(learner_id, int):
            raise HTTPException(status_code=401, detail="Unable to resolve current user")
        if current_user.get("identity") != "Learner":
            raise HTTPException(status_code=403, detail="Only learners can view enrolled courses")

        enrollments = self.enrollments.list_active_by_learner(learner_id)
        courses = self.courses.list_by_ids([enrollment.course_id for enrollment in enrollments])
        courses = [course for course in courses if course.status == CourseStatus.PUBLISHED]
        courses = self._filter_courses_by_search(courses, search=search)
        educator_profiles_by_id = self._lookup_educator_profiles(courses)
        return [
            self._to_course_summary(
                course,
                current_user=current_user,
                educator_profiles_by_id=educator_profiles_by_id,
            )
            for course in courses
        ]

    def list_managed_courses(
        self,
        *,
        current_user: dict,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
        offset: int | None = None,
    ) -> PaginatedCourseSummaryResponse:
        actor_id = current_user.get("id")
        if not isinstance(actor_id, int):
            raise HTTPException(status_code=401, detail="Unable to resolve current user")

        identity = current_user.get("identity")
        if identity == "Admin":
            courses, total, safe_page, total_pages = self.courses.list_all_paginated(
                search=search,
                page=page,
                page_size=page_size,
                offset=offset,
            )
        elif identity == "Educator":
            courses, total, safe_page, total_pages = self.courses.list_by_educator_paginated(
                actor_id,
                search=search,
                page=page,
                page_size=page_size,
                offset=offset,
            )
        else:
            raise HTTPException(status_code=403, detail="Only educators and admins can view managed courses")

        educator_profiles_by_id = self._lookup_educator_profiles(courses)
        return PaginatedCourseSummaryResponse(
            items=[
                self._to_course_summary(
                    course,
                    current_user=current_user,
                    educator_profiles_by_id=educator_profiles_by_id,
                )
                for course in courses
            ],
            page=safe_page,
            pageSize=page_size,
            total=total,
            totalPages=total_pages,
        )

    def search_courses(self, *, current_user: dict, query: str) -> list[CourseSummaryResponse]:
        normalized_query = query.strip()
        if not normalized_query:
            return []

        courses = self.courses.search_by_title_or_subtitle(normalized_query)
        educator_profiles_by_id = self._lookup_educator_profiles(courses)
        return [
            self._to_course_summary(
                course,
                current_user=current_user,
                educator_profiles_by_id=educator_profiles_by_id,
            )
            for course in courses
        ]

    def _filter_courses_by_search(self, courses: list[Course], *, search: str | None) -> list[Course]:
        if not search:
            return courses

        normalized_search = search.strip().lower()
        if not normalized_search:
            return courses

        return [
            course
            for course in courses
            if normalized_search
            in " ".join(
                filter(
                    None,
                    [
                        course.title,
                        course.subtitle,
                        course.description,
                        course.category,
                    ],
                )
            ).lower()
        ]

    def get_course_by_id(
        self,
        *,
        course_id: int,
        current_user: dict,
        class_id: str | None = None,
    ) -> CourseDetailResponse:
        course = self.courses.get_by_id(course_id)
        if course is None:
            raise HTTPException(status_code=404, detail="Course not found")

        return self._to_course_detail(course, current_user=current_user, class_id=class_id)

    def get_course_by_uuid(
        self,
        *,
        course_uuid: str,
        current_user: dict,
        class_id: str | None = None,
    ) -> CourseDetailResponse:
        return self.get_course_by_id(
            course_id=decode_course_uuid(course_uuid),
            current_user=current_user,
            class_id=class_id,
        )

    def get_course_management_by_uuid(
        self,
        *,
        course_uuid: str,
        current_user: dict,
    ) -> CourseDetailResponse:
        actor_id = current_user.get("id")
        if not isinstance(actor_id, int):
            raise HTTPException(status_code=401, detail="Unable to resolve current user")

        course = self.courses.get_by_id(decode_course_uuid(course_uuid))
        if course is None:
            raise HTTPException(status_code=404, detail="Course not found")

        identity = current_user.get("identity")
        if identity == "Admin":
            return self._to_course_management_detail(course, current_user=current_user)
        if identity == "Educator" and actor_id == course.educator_id:
            return self._to_course_management_detail(course, current_user=current_user)
        raise HTTPException(status_code=403, detail="Course management access is not allowed for the current user")

    def get_course_module_by_id(
        self,
        *,
        course_id: int,
        module_id: int,
        current_user: dict,
        class_id: str | None = None,
    ) -> ModuleResponse:
        course = self.courses.get_by_id(course_id)
        if course is None:
            raise HTTPException(status_code=404, detail="Course not found")

        learning_path = self.learning_paths.get_by_course_id(course.course_id)
        if learning_path is None:
            raise HTTPException(status_code=404, detail="Learning path not found")

        module = self.modules.get_by_id(module_id)
        if module is None or module.learning_path_id != learning_path.learning_path_id:
            raise HTTPException(status_code=404, detail="Module not found")

        if not self._can_user_access_module(
            course=course,
            module=module,
            current_user=current_user,
            class_id=class_id,
        ):
            raise HTTPException(status_code=403, detail="Module is not accessible for the current user")

        return self._to_module_response(module, current_user=current_user)

    def get_course_module_by_uuid(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        current_user: dict,
        class_id: str | None = None,
    ) -> ModuleResponse:
        return self.get_course_module_by_id(
            course_id=decode_course_uuid(course_uuid),
            module_id=decode_module_uuid(module_uuid),
            current_user=current_user,
            class_id=class_id,
        )

    def to_material_response(self, material: ModuleMaterial) -> MaterialResponse:
        return MaterialResponse(
            materialId=material.material_id,
            materialUuid=encode_material_uuid(material.material_id),
            moduleId=material.module_id,
            title=material.title,
            materialType=material.material_type.value,
            resourceUrl=self._resolve_material_url(material.resource_url),
            sortOrder=material.sort_order,
            metadataJson=material.metadata_json,
        )

    def _lookup_educator_profiles(self, courses: list[Course]) -> dict[int, dict[str, str]]:
        educator_ids = sorted({course.educator_id for course in courses})
        if not educator_ids:
            return {}

        profiles_by_id = self.identity_users.lookup_users_by_ids(user_ids=educator_ids)
        educator_profiles_by_id: dict[int, dict[str, str]] = {}
        for educator_id, profile in profiles_by_id.items():
            user_name = profile.get("userName")
            email = profile.get("email")

            normalized_user_name = user_name.strip() if isinstance(user_name, str) and user_name.strip() else ""
            normalized_email = email.strip() if isinstance(email, str) and email.strip() else ""

            if normalized_user_name or normalized_email:
                educator_profiles_by_id[educator_id] = {
                    "userName": normalized_user_name,
                    "email": normalized_email,
                }

        return educator_profiles_by_id

    def _to_course_summary(
        self,
        course: Course,
        *,
        current_user: dict,
        educator_profiles_by_id: dict[int, dict[str, str]] | None = None,
    ) -> CourseSummaryResponse:
        learning_path = self.learning_paths.get_by_course_id(course.course_id)
        module_count = 0
        if learning_path is not None:
            if current_user.get("identity") == "Educator" and current_user.get("id") == course.educator_id:
                module_count = len(self.modules.list_by_learning_path(learning_path.learning_path_id))
            else:
                module_count = len(self.modules.list_published_by_learning_path(learning_path.learning_path_id))

        educator_profile = (educator_profiles_by_id or {}).get(course.educator_id, {})

        return CourseSummaryResponse(
            courseId=course.course_id,
            courseUuid=encode_course_uuid(course.course_id),
            educatorId=course.educator_id,
            educatorUuid=encode_user_uuid(course.educator_id),
            educatorName=educator_profile.get("userName") or None,
            educatorEmail=educator_profile.get("email") or None,
            educatorUserName=educator_profile.get("userName") or None,
            title=course.title,
            subtitle=course.subtitle,
            description=course.description,
            coverImageUrl=self._resolve_cover_image_url(course.cover_image_url),
            status=course.status.value,
            difficultyLevel=course.difficulty_level.value if course.difficulty_level else None,
            estimatedMinutes=course.estimated_minutes,
            category=course.category,
            languageCode=course.language_code,
            isPublic=bool(course.is_public),
            publishedAt=course.published_at,
            termLabel=None,
            courseCode=None,
            schoolName=None,
            moduleCount=module_count,
        )

    def _to_course_detail(
        self,
        course: Course,
        *,
        current_user: dict,
        class_id: str | None,
    ) -> CourseDetailResponse:
        learning_path = self.learning_paths.get_by_course_id(course.course_id)
        all_modules = self.modules.list_by_learning_path(learning_path.learning_path_id) if learning_path is not None else []
        modules = [
            module
            for module in all_modules
            if self._can_user_access_module(
                course=course,
                module=module,
                current_user=current_user,
                class_id=class_id,
            )
        ]
        summary = self._to_course_summary(
            course,
            current_user=current_user,
            educator_profiles_by_id=self._lookup_educator_profiles([course]),
        )

        return CourseDetailResponse(
            **summary.dict(),
            learningPathId=learning_path.learning_path_id if learning_path else None,
            learningPathTitle=learning_path.title if learning_path else None,
            learningPathDescription=learning_path.description if learning_path else None,
            modules=[self._to_module_response(module, current_user=current_user) for module in modules],
        )

    def _to_module_response(self, module: Module, *, current_user: dict) -> ModuleResponse:
        prerequisite_rule = self.module_prerequisites.get_by_module_id(module.module_id)
        prerequisite_module = (
            self.modules.get_by_id(prerequisite_rule.prerequisite_module_id)
            if prerequisite_rule is not None
            else None
        )
        is_locked, lock_message = self._get_lock_state(
            module=module,
            prerequisite_module=prerequisite_module,
            current_user=current_user,
        )

        quiz = self.quizzes.get_by_module_id(module.module_id)
        from app.models.quizzes import QuizStatus
        has_published_quiz = quiz is not None and quiz.status == QuizStatus.PUBLISHED
        learner_id = current_user.get("id")
        is_learner = current_user.get("identity") == "Learner" and isinstance(learner_id, int)
        progress = (
            self.module_progress.get_by_module_and_learner(module.module_id, learner_id)
            if is_learner
            else None
        )
        progress_status = progress.progress_status.value if progress is not None else None
        is_completed = progress.progress_status == ProgressStatus.COMPLETED if progress is not None else False
        completed_at = progress.completed_at if progress is not None else None

        return ModuleResponse(
            moduleId=module.module_id,
            moduleUuid=encode_module_uuid(module.module_id),
            title=module.title,
            description=module.description,
            content=module.content,
            sortOrder=module.sort_order,
            estimatedMinutes=module.estimated_minutes,
            status=module.status.value,
            classId=module.visible_to_class_id,
            prerequisiteModuleUuid=(
                encode_module_uuid(prerequisite_module.module_id)
                if prerequisite_module is not None
                else None
            ),
            prerequisiteModuleTitle=prerequisite_module.title if prerequisite_module is not None else None,
            isLocked=is_locked,
            lockMessage=lock_message,
            slug=_slugify(module.title),
            materials=[
                self.to_material_response(material)
                for material in self.materials.list_by_module(module.module_id)
            ],
            hasPublishedQuiz=has_published_quiz,
            quizTitle=quiz.title if has_published_quiz else None,
            quizTimeLimitSeconds=quiz.time_limit_seconds if has_published_quiz else None,
            progressStatus=progress_status,
            isCompleted=is_completed,
            completedAt=completed_at,
        )

    def _to_course_management_detail(
        self,
        course: Course,
        *,
        current_user: dict,
    ) -> CourseDetailResponse:
        learning_path = self.learning_paths.get_by_course_id(course.course_id)
        modules = self.modules.list_by_learning_path(learning_path.learning_path_id) if learning_path is not None else []
        summary = self._to_course_summary(
            course,
            current_user=current_user,
            educator_profiles_by_id=self._lookup_educator_profiles([course]),
        )

        return CourseDetailResponse(
            **summary.dict(),
            learningPathId=learning_path.learning_path_id if learning_path else None,
            learningPathTitle=learning_path.title if learning_path else None,
            learningPathDescription=learning_path.description if learning_path else None,
            modules=[self._to_module_response(module, current_user=current_user) for module in modules],
        )

    def _resolve_cover_image_url(self, cover_image_url: str | None) -> str | None:
        resolved_url = self._resolve_storage_url(cover_image_url)
        return resolved_url or None

    def _resolve_material_url(self, resource_url: str | None) -> str:
        return self._resolve_storage_url(resource_url) or ""

    def _resolve_storage_url(self, resource_url: str | None) -> str:
        if not resource_url:
            return ""
        normalized_url = resource_url.strip()
        parsed_path = urlparse(normalized_url).path or normalized_url

        if (
            settings.object_storage_provider.strip().lower() == "minio"
            and settings.minio_public_base_url.strip()
        ):
            bucket_marker = f"/{settings.minio_bucket.strip('/')}/"
            if bucket_marker in parsed_path:
                _, suffix = parsed_path.split(bucket_marker, 1)
                base = settings.minio_public_base_url.rstrip("/")
                return f"{base}/{suffix.lstrip('/')}"

            public_base_path = urlparse(settings.minio_public_base_url).path.rstrip("/")
            if public_base_path and parsed_path.startswith(f"{public_base_path}/"):
                suffix = parsed_path.removeprefix(public_base_path).lstrip("/")
                base = settings.minio_public_base_url.rstrip("/")
                return f"{base}/{suffix}"

        material_base_path = urlparse(settings.learning_material_public_base_url).path.rstrip("/")
        if material_base_path and parsed_path.startswith(f"{material_base_path}/"):
            suffix = parsed_path.removeprefix(material_base_path).lstrip("/")
            base = settings.learning_material_public_base_url.rstrip("/")
            return f"{base}/{suffix}"

        if normalized_url.startswith(("http://", "https://", "/")):
            return normalized_url
        return f"{settings.learning_material_public_base_url.rstrip('/')}/{normalized_url.lstrip('/')}"

    def _can_user_access_module(
        self,
        *,
        course: Course,
        module: Module,
        current_user: dict,
        class_id: str | None,
    ) -> bool:
        identity = current_user.get("identity")
        user_id = current_user.get("id")

        # Published course detail follows the public course-center view:
        # only published modules are visible, regardless of elevated identity.
        if course.status == CourseStatus.PUBLISHED:
            if module.status.value == "draft":
                return False
            if module.status.value == "published":
                return True
            return bool(class_id and module.visible_to_class_id == class_id)

        if identity == "Admin":
            return True
        if identity == "Educator" and user_id == course.educator_id:
            return True
        if identity != "Learner":
            return False
        if module.status.value == "draft":
            return False
        if module.status.value == "published":
            return True
        return bool(class_id and module.visible_to_class_id == class_id)

    def _get_lock_state(
        self,
        *,
        module: Module,
        prerequisite_module: Module | None,
        current_user: dict,
    ) -> tuple[bool, str | None]:
        if prerequisite_module is None:
            return False, None
        if current_user.get("identity") != "Learner":
            return False, None

        learner_id = current_user.get("id")
        if not isinstance(learner_id, int):
            return True, "Unable to resolve learner identity for progression checks"

        if self.unlocking.is_module_unlocked(module_id=module.module_id, learner_id=learner_id):
            return False, None

        return True, f"Complete {prerequisite_module.title} before accessing this module"

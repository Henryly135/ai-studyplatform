from fastapi import status
from sqlalchemy.orm import Session

from app.core.uuid_codec import decode_course_uuid, decode_module_uuid, encode_course_uuid, encode_module_uuid
from app.models.courses import Course
from app.models.learning_paths import LearningPath
from app.models.modules import Module, ModuleStatus
from app.repositories.course_repository import CourseRepository
from app.repositories.learning_path_repository import LearningPathRepository
from app.repositories.module_prerequisite_repository import ModulePrerequisiteRepository
from app.repositories.module_repository import ModuleRepository, _UNSET
from app.schemas.module import (
    ModuleAuthoringResponse,
    ModuleCreateRequest,
    ModulePrerequisiteRequest,
    ModulePublishRequest,
    ModuleReorderRequest,
    ModuleUpdateRequest,
)
from app.services.ai_index_job_client import AIIndexJobClient
from app.services.course_enrollment_aggregate_service import CourseEnrollmentAggregateService
from app.services.module_material_service import ModuleMaterialService
from platform_common.errors import http_error, invalid_identity_response_error, invalid_request_error


class ModuleManagementService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.courses = CourseRepository(session)
        self.learning_paths = LearningPathRepository(session)
        self.modules = ModuleRepository(session)
        self.module_prerequisites = ModulePrerequisiteRepository(session)
        self.ai_index_jobs = AIIndexJobClient()
        self.enrollment_aggregates = CourseEnrollmentAggregateService(session)
        self.material_service = ModuleMaterialService(session)

    def create_module(self, *, course_uuid: str, payload: ModuleCreateRequest, current_user: dict) -> ModuleAuthoringResponse:
        course = self._get_manageable_course(course_uuid=course_uuid, current_user=current_user)
        learning_path = self._get_learning_path(course.course_id)
        sort_order = payload.sortOrder or (self.modules.get_max_sort_order(learning_path.learning_path_id) + 1)

        if self.modules.get_by_learning_path_and_sort_order(learning_path.learning_path_id, sort_order):
            raise invalid_request_error("A module with this sortOrder already exists in the learning path")

        module = self.modules.create(
            learning_path_id=learning_path.learning_path_id,
            title=self._normalize_required_text(payload.title, field_name="title"),
            description=self._normalize_optional_text(payload.description),
            content=self._normalize_required_text(payload.content, field_name="content"),
            sort_order=sort_order,
            estimated_minutes=payload.estimatedMinutes,
            status=ModuleStatus.DRAFT,
            visible_to_class_id=None,
        )
        self.courses.touch(course)
        self.session.commit()
        self.session.refresh(module)
        return self._to_authoring_response(module=module, course=course)

    def update_module(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        payload: ModuleUpdateRequest,
        current_user: dict,
    ) -> ModuleAuthoringResponse:
        course = self._get_manageable_course(course_uuid=course_uuid, current_user=current_user)
        learning_path = self._get_learning_path(course.course_id)
        module = self._get_learning_path_module(
            learning_path_id=learning_path.learning_path_id,
            module_uuid=module_uuid,
        )

        normalized_title = (
            self._normalize_required_text(payload.title, field_name="title")
            if payload.title is not None
            else _UNSET
        )
        normalized_description = (
            self._normalize_optional_text(payload.description)
            if payload.description is not None
            else _UNSET
        )
        normalized_content = (
            self._normalize_required_text(payload.content, field_name="content")
            if payload.content is not None
            else _UNSET
        )

        sort_order = payload.sortOrder if payload.sortOrder is not None else _UNSET
        if payload.sortOrder is not None:
            existing = self.modules.get_by_learning_path_and_sort_order(learning_path.learning_path_id, payload.sortOrder)
            if existing is not None and existing.module_id != module.module_id:
                raise invalid_request_error("A module with this sortOrder already exists in the learning path")

        estimated_minutes = payload.estimatedMinutes if payload.estimatedMinutes is not None else _UNSET

        updated_module = self.modules.update(
            module,
            title=normalized_title,
            description=normalized_description,
            content=normalized_content,
            sort_order=sort_order,
            estimated_minutes=estimated_minutes,
        )
        self.courses.touch(course)
        self.session.commit()
        self.session.refresh(updated_module)
        return self._to_authoring_response(module=updated_module, course=course)

    def publish_module(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        payload: ModulePublishRequest,
        current_user: dict,
    ) -> ModuleAuthoringResponse:
        course = self._get_manageable_course(course_uuid=course_uuid, current_user=current_user)
        learning_path = self._get_learning_path(course.course_id)
        module = self._get_learning_path_module(
            learning_path_id=learning_path.learning_path_id,
            module_uuid=module_uuid,
        )

        if not module.content or not module.content.strip():
            raise invalid_request_error("Module content is required before publishing")

        status = self._parse_status(payload.status)
        visible_to_class_id = self._normalize_optional_text(payload.classId)
        if status == ModuleStatus.ARCHIVED and not visible_to_class_id:
            raise invalid_request_error("classId is required when status is archived")

        published_module = self.modules.update(
            module,
            status=status,
            visible_to_class_id=visible_to_class_id if status == ModuleStatus.ARCHIVED else None,
        )

        if status == ModuleStatus.PUBLISHED:
            self.enrollment_aggregates.sync_total_module_count_for_course(course_id=course.course_id)
        self.courses.touch(course)
        self.session.commit()
        if status == ModuleStatus.PUBLISHED:
            self.ai_index_jobs.release_blocked_jobs(
                course_id=course.course_id,
                module_ids=[module.module_id],
            )
        self.session.refresh(published_module)
        return self._to_authoring_response(module=published_module, course=course)

    def reorder_modules(
        self,
        *,
        course_uuid: str,
        payload: ModuleReorderRequest,
        current_user: dict,
    ) -> list[ModuleAuthoringResponse]:
        course = self._get_manageable_course(course_uuid=course_uuid, current_user=current_user)
        learning_path = self._get_learning_path(course.course_id)

        module_ids = [decode_module_uuid(item.moduleUuid) for item in payload.modules]
        modules = self.modules.list_by_ids(module_ids)
        if len(modules) != len(payload.modules):
            raise http_error(status_code=status.HTTP_404_NOT_FOUND, code="MODULE_NOT_FOUND", message="Module not found")

        module_by_id = {module.module_id: module for module in modules}
        used_sort_orders: set[int] = set()

        for item in payload.modules:
            module_id = decode_module_uuid(item.moduleUuid)
            module = module_by_id.get(module_id)
            if module is None or module.learning_path_id != learning_path.learning_path_id:
                raise http_error(status_code=status.HTTP_404_NOT_FOUND, code="MODULE_NOT_FOUND", message="Module not found")
            if item.sortOrder in used_sort_orders:
                raise invalid_request_error("sortOrder values must be unique when reordering modules")
            used_sort_orders.add(item.sortOrder)

        # Move selected modules to a temporary non-conflicting range first so swaps
        # do not violate the unique (learning_path_id, sort_order) constraint mid-update.
        temp_sort_order_base = self.modules.get_max_sort_order(learning_path.learning_path_id) + len(payload.modules) + 1
        for index, item in enumerate(payload.modules):
            module = module_by_id[decode_module_uuid(item.moduleUuid)]
            self.modules.update(module, sort_order=temp_sort_order_base + index)

        for item in payload.modules:
            module = module_by_id[decode_module_uuid(item.moduleUuid)]
            self.modules.update(module, sort_order=item.sortOrder)

        self.courses.touch(course)
        self.session.commit()
        ordered_modules = self.modules.list_by_learning_path(learning_path.learning_path_id)
        return [self._to_authoring_response(module=module, course=course) for module in ordered_modules]

    def delete_module(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        current_user: dict,
    ) -> None:
        course = self._get_manageable_course(course_uuid=course_uuid, current_user=current_user)
        learning_path = self._get_learning_path(course.course_id)
        module = self._get_learning_path_module(
            learning_path_id=learning_path.learning_path_id,
            module_uuid=module_uuid,
        )

        deleted_sort_order = module.sort_order
        materials = self.material_service.materials.list_by_module(module.module_id)
        for material in materials:
            self.material_service.delete_material_record(material=material, course=course)

        self.modules.delete(module)

        remaining_modules = self.modules.list_by_learning_path(learning_path.learning_path_id)
        for index, sibling_module in enumerate(
            [item for item in remaining_modules if item.sort_order > deleted_sort_order],
            start=deleted_sort_order,
        ):
            self.modules.update(sibling_module, sort_order=index)

        self.enrollment_aggregates.sync_all_learners_progress_for_course(course_id=course.course_id)
        self.courses.touch(course)
        self.session.commit()

    def set_module_prerequisite(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        payload: ModulePrerequisiteRequest,
        current_user: dict,
    ) -> ModuleAuthoringResponse:
        course = self._get_manageable_course(course_uuid=course_uuid, current_user=current_user)
        learning_path = self._get_learning_path(course.course_id)
        module = self._get_learning_path_module(
            learning_path_id=learning_path.learning_path_id,
            module_uuid=module_uuid,
        )

        prerequisite_module = self._get_learning_path_module(
            learning_path_id=learning_path.learning_path_id,
            module_uuid=payload.prerequisiteModuleUuid,
        )
        if prerequisite_module.module_id == module.module_id:
            raise invalid_request_error("A module cannot depend on itself")
        if prerequisite_module.sort_order >= module.sort_order:
            raise invalid_request_error("A prerequisite module must come before the dependent module")

        self.module_prerequisites.upsert(
            module_id=module.module_id,
            prerequisite_module_id=prerequisite_module.module_id,
        )
        self.courses.touch(course)
        self.session.commit()
        self.session.refresh(module)
        return self._to_authoring_response(module=module, course=course)

    def remove_module_prerequisite(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        current_user: dict,
    ) -> None:
        course = self._get_manageable_course(course_uuid=course_uuid, current_user=current_user)
        learning_path = self._get_learning_path(course.course_id)
        module = self._get_learning_path_module(
            learning_path_id=learning_path.learning_path_id,
            module_uuid=module_uuid,
        )
        existing = self.module_prerequisites.get_by_module_id(module.module_id)
        if existing is not None:
            self.module_prerequisites.delete(existing)
            self.courses.touch(course)
            self.session.commit()

    def _get_manageable_course(self, *, course_uuid: str, current_user: dict) -> Course:
        actor_id = current_user.get("id")
        if not isinstance(actor_id, int):
            raise invalid_identity_response_error()

        course_id = decode_course_uuid(course_uuid)
        course = self.courses.get_by_id(course_id)
        if course is None:
            raise http_error(status_code=status.HTTP_404_NOT_FOUND, code="COURSE_NOT_FOUND", message="Course not found")

        if current_user.get("identity") == "Admin":
            return course

        if course.educator_id != actor_id:
            raise http_error(
                status_code=status.HTTP_403_FORBIDDEN,
                code="COURSE_OWNERSHIP_REQUIRED",
                message="You can only manage modules for your own courses",
            )
        return course

    def _get_learning_path(self, course_id: int) -> LearningPath:
        learning_path = self.learning_paths.get_by_course_id(course_id)
        if learning_path is None:
            raise http_error(
                status_code=status.HTTP_404_NOT_FOUND,
                code="LEARNING_PATH_NOT_FOUND",
                message="Learning path not found",
            )
        return learning_path

    def _get_learning_path_module(self, *, learning_path_id: int, module_uuid: str) -> Module:
        module_id = decode_module_uuid(module_uuid)
        module = self.modules.get_by_id(module_id)
        if module is None or module.learning_path_id != learning_path_id:
            raise http_error(status_code=status.HTTP_404_NOT_FOUND, code="MODULE_NOT_FOUND", message="Module not found")
        return module

    def _parse_status(self, status: str) -> ModuleStatus:
        normalized = status.strip().lower()
        try:
            return ModuleStatus(normalized)
        except ValueError as exc:
            raise invalid_request_error("status must be one of draft, published, archived") from exc

    def _normalize_required_text(self, value: str | None, *, field_name: str) -> str:
        normalized = self._normalize_optional_text(value)
        if not normalized:
            raise invalid_request_error(f"Module {field_name} is required")
        return normalized

    def _normalize_optional_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    def _to_authoring_response(self, *, module: Module, course: Course) -> ModuleAuthoringResponse:
        prerequisite_rule = self.module_prerequisites.get_by_module_id(module.module_id)
        return ModuleAuthoringResponse(
            moduleId=module.module_id,
            moduleUuid=encode_module_uuid(module.module_id),
            courseId=course.course_id,
            courseUuid=encode_course_uuid(course.course_id),
            learningPathId=module.learning_path_id,
            title=module.title,
            description=module.description,
            content=module.content,
            sortOrder=module.sort_order,
            estimatedMinutes=module.estimated_minutes,
            status=module.status.value,
            classId=module.visible_to_class_id,
            prerequisiteModuleUuid=(
                encode_module_uuid(prerequisite_rule.prerequisite_module_id)
                if prerequisite_rule is not None
                else None
            ),
            createdAt=module.created_at,
            updatedAt=module.updated_at,
        )

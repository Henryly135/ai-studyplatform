from types import SimpleNamespace

from app.models.course_enrollments import EnrollmentStatus
from app.models.courses import CourseStatus
from app.models.modules import ModuleStatus
from app.services.course_catalog_service import CourseCatalogService


class FakeMaterials:
    def __init__(self, rows) -> None:
        self.rows = rows
        self.list_calls = 0

    def list_by_module(self, module_id: int):
        self.list_calls += 1
        return [row for row in self.rows if row.module_id == module_id]


def _course(status: CourseStatus = CourseStatus.PUBLISHED):
    return SimpleNamespace(
        course_id=1,
        educator_id=5,
        title="Course",
        subtitle=None,
        description=None,
        cover_image_url=None,
        status=status,
        difficulty_level=None,
        estimated_minutes=None,
        category=None,
        language_code="en",
        is_public=True,
        published_at=None,
    )


def _module(*, status: ModuleStatus = ModuleStatus.PUBLISHED, class_id: str | None = None):
    return SimpleNamespace(
        module_id=2,
        learning_path_id=10,
        title="Module",
        description=None,
        content=None,
        sort_order=1,
        estimated_minutes=None,
        status=status,
        visible_to_class_id=class_id,
    )


def _material():
    return SimpleNamespace(
        material_id=3,
        module_id=2,
        title="Notes",
        material_type=SimpleNamespace(value="pdf"),
        resource_url="/learning-materials/notes.pdf",
        sort_order=1,
        metadata_json={"objectKey": "notes.pdf"},
    )


def _service(monkeypatch, *, course=None, module=None, enrollment=None, unlocked: bool = True):
    monkeypatch.setattr("app.services.course_catalog_service.encode_course_uuid", lambda value: f"course-{value}")
    monkeypatch.setattr("app.services.course_catalog_service.encode_module_uuid", lambda value: f"module-{value}")
    monkeypatch.setattr("app.services.course_catalog_service.encode_material_uuid", lambda value: f"material-{value}")
    monkeypatch.setattr("app.services.course_catalog_service.encode_user_uuid", lambda value: f"user-{value}")

    course = course or _course()
    module = module or _module()
    materials = FakeMaterials([_material()])

    service = CourseCatalogService(SimpleNamespace())
    service.courses = SimpleNamespace(get_by_id=lambda _course_id: course)
    service.learning_paths = SimpleNamespace(
        get_by_course_id=lambda _course_id: SimpleNamespace(
            learning_path_id=10,
            title="Path",
            description=None,
        )
    )
    service.modules = SimpleNamespace(
        get_by_id=lambda _module_id: module,
        list_by_learning_path=lambda _path_id: [module],
        list_published_by_learning_path=lambda _path_id: [module] if module.status == ModuleStatus.PUBLISHED else [],
    )
    service.materials = materials
    service.module_prerequisites = SimpleNamespace(get_by_module_id=lambda _module_id: None)
    service.module_progress = SimpleNamespace(get_by_module_and_learner=lambda *_args: None)
    service.enrollments = SimpleNamespace(get_by_course_and_learner=lambda **_kwargs: enrollment)
    service.quizzes = SimpleNamespace(get_by_module_id=lambda _module_id: None)
    service.identity_users = SimpleNamespace(lookup_users_by_ids=lambda **_kwargs: {})
    service.unlocking = SimpleNamespace(is_module_unlocked=lambda **_kwargs: unlocked)
    service.storage = SimpleNamespace(get_material_access_url=lambda **_kwargs: "signed://material")
    return service, materials


def test_course_detail_hides_material_urls_from_unenrolled_learners(monkeypatch) -> None:
    # Tests public course outline does not leak signed material URLs before enrollment.
    service, materials = _service(monkeypatch, enrollment=None)

    detail = service.get_course_by_id(
        course_id=1,
        current_user={"id": 7, "identity": "Learner"},
    )

    assert len(detail.modules) == 1
    assert detail.modules[0].materials == []
    assert materials.list_calls == 0


def test_course_detail_returns_material_urls_for_enrolled_unlocked_learners(monkeypatch) -> None:
    # Tests enrolled learners can still open material resources for unlocked modules.
    enrollment = SimpleNamespace(enrollment_status=EnrollmentStatus.ACTIVE)
    service, materials = _service(monkeypatch, enrollment=enrollment, unlocked=True)

    detail = service.get_course_by_id(
        course_id=1,
        current_user={"id": 7, "identity": "Learner"},
    )

    assert detail.modules[0].materials[0].resourceUrl == "signed://material"
    assert materials.list_calls == 1


def test_course_detail_hides_material_urls_for_locked_learner_modules(monkeypatch) -> None:
    # Tests prerequisite locks also prevent signed material URL issuance.
    enrollment = SimpleNamespace(enrollment_status=EnrollmentStatus.ACTIVE)
    service, materials = _service(monkeypatch, enrollment=enrollment, unlocked=False)

    detail = service.get_course_by_id(
        course_id=1,
        current_user={"id": 7, "identity": "Learner"},
    )

    assert detail.modules[0].materials == []
    assert materials.list_calls == 0


def test_course_detail_returns_material_urls_for_owner_educator(monkeypatch) -> None:
    # Tests the owning educator keeps material visibility for course authoring workflows.
    service, materials = _service(monkeypatch, course=_course(status=CourseStatus.DRAFT), module=_module(status=ModuleStatus.DRAFT))

    detail = service.get_course_by_id(
        course_id=1,
        current_user={"id": 5, "identity": "Educator"},
    )

    assert detail.modules[0].materials[0].resourceUrl == "signed://material"
    assert materials.list_calls == 1

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.api import course_management as course_management_api
from app.schemas.course import EducatorMaterialBriefsResponse, EducatorTeachingInsightsResponse
from app.services import course_management_service as management_module
from app.services.course_management_service import CourseManagementService


def test_teaching_insights_prioritize_course_and_quiz_actions(monkeypatch) -> None:
    # Tests educator teaching insights convert aggregate progress/quiz stats into actionable recommendations.
    monkeypatch.setattr(management_module, "encode_course_uuid", lambda course_id: f"course-{course_id}")
    monkeypatch.setattr(management_module, "encode_module_uuid", lambda module_id: f"module-{module_id}")
    service = CourseManagementService(SimpleNamespace())
    service.enrollments = SimpleNamespace(
        aggregate_stats_by_educator=lambda *, educator_id: [
            {
                "course_id": 1,
                "course_title": "Algebra",
                "status": "published",
                "total_enrollments": 6,
                "active_enrollments": 5,
                "completed_enrollments": 0,
                "avg_progress_percent": 24.2,
            },
            {
                "course_id": 2,
                "course_title": "Geometry",
                "status": "published",
                "total_enrollments": 0,
                "active_enrollments": 0,
                "completed_enrollments": 0,
                "avg_progress_percent": None,
            },
        ]
    )
    service.quiz_attempts = SimpleNamespace(
        aggregate_stats_by_educator=lambda *, educator_id: [
            {
                "course_id": 1,
                "course_title": "Algebra",
                "module_id": 10,
                "module_title": "Linear equations",
                "quiz_title": "Linear Quiz",
                "total_attempts": 4,
                "unique_learners": 4,
                "avg_score_percent": 52.0,
                "pass_rate": 0.25,
                "avg_duration_seconds": 600,
            },
            {
                "course_id": 2,
                "course_title": "Geometry",
                "module_id": 20,
                "module_title": "Triangles",
                "quiz_title": "Triangle Quiz",
                "total_attempts": 0,
                "unique_learners": 0,
                "avg_score_percent": None,
                "pass_rate": None,
                "avg_duration_seconds": None,
            },
        ]
    )

    response = service.get_educator_teaching_insights(current_user={"id": 7, "identity": "Educator"})

    assert response.totalInsights == 4
    assert response.highPriorityCount == 2
    assert response.items[0].priority == "high"
    assert response.items[0].courseUuid == "course-1"
    assert response.items[0].metricValue in {"24%", "25%"}
    assert any(item.category == "course_launch" for item in response.items)
    assert any(item.category == "quiz_engagement" for item in response.items)
    assert not any(hasattr(item, "learnerEmail") for item in response.items)


def test_teaching_insights_api_uses_current_user(monkeypatch) -> None:
    # Tests the API handler delegates to the teaching insight aggregate service.
    calls = []

    class FakeCourseManagementService:
        def __init__(self, session) -> None:
            self.session = session

        def get_educator_teaching_insights(self, *, current_user):
            calls.append(current_user)
            return EducatorTeachingInsightsResponse(
                generatedAt=management_module.now_local(),
                totalInsights=0,
                highPriorityCount=0,
                items=[],
            )

    monkeypatch.setattr(course_management_api, "CourseManagementService", FakeCourseManagementService)

    response = course_management_api.get_my_teaching_insights(
        current_user={"id": 7, "identity": "Educator"},
        session=object(),
    )

    assert calls == [{"id": 7, "identity": "Educator"}]
    assert response.totalInsights == 0


def test_material_briefs_summarize_material_coverage_without_urls(monkeypatch) -> None:
    # Tests educator material briefs summarize module coverage and quiz difficulty without exposing material URLs.
    monkeypatch.setattr(management_module, "encode_course_uuid", lambda course_id: f"course-{course_id}")
    monkeypatch.setattr(management_module, "encode_module_uuid", lambda module_id: f"module-{module_id}")
    service = CourseManagementService(SimpleNamespace())
    course = SimpleNamespace(
        course_id=1,
        title="Algebra",
        learning_path=SimpleNamespace(learning_path_id=11),
    )
    modules = [
        SimpleNamespace(module_id=10, title="Linear equations", status=SimpleNamespace(value="published")),
        SimpleNamespace(module_id=20, title="Quadratics", status=SimpleNamespace(value="draft")),
    ]
    materials_by_module = {
        10: [
            SimpleNamespace(
                material_id=100,
                title="Linear notes",
                material_type=SimpleNamespace(value="pdf"),
                resource_url="https://example.test/private-linear-notes.pdf",
                metadata_json={"objectKey": "secret/private-linear-notes.pdf"},
            ),
            SimpleNamespace(
                material_id=101,
                title="Walkthrough",
                material_type=SimpleNamespace(value="video"),
                resource_url="https://example.test/private-video.mp4",
                metadata_json={"objectKey": "secret/private-video.mp4"},
            ),
        ],
        20: [],
    }
    service.courses = SimpleNamespace(list_by_educator=lambda educator_id: [course])
    service.modules = SimpleNamespace(list_by_learning_path=lambda learning_path_id: modules)
    service.materials = SimpleNamespace(list_by_module=lambda module_id: materials_by_module[module_id])
    service.quiz_attempts = SimpleNamespace(
        aggregate_stats_by_educator=lambda *, educator_id: [
            {
                "course_id": 1,
                "course_title": "Algebra",
                "module_id": 10,
                "module_title": "Linear equations",
                "quiz_title": "Linear Quiz",
                "total_attempts": 4,
                "unique_learners": 4,
                "avg_score_percent": 55.0,
                "pass_rate": 0.25,
                "avg_duration_seconds": 500,
            }
        ]
    )

    response = service.get_educator_material_briefs(current_user={"id": 7, "identity": "Educator"})
    serialized = response.model_dump_json()

    assert response.totalBriefs == 2
    assert response.highPriorityCount == 2
    assert response.items[0].priority == "high"
    assert response.items[0].moduleUuid in {"module-10", "module-20"}
    assert any(item.materialTypes == ["pdf", "video"] for item in response.items)
    assert "private-linear-notes" not in serialized
    assert "objectKey" not in serialized
    assert "resourceUrl" not in serialized


def test_material_briefs_scan_local_text_material_body_without_leaking_source(monkeypatch, tmp_path: Path) -> None:
    # Tests educator material briefs use local text-body signals while avoiding raw source text or object paths.
    monkeypatch.setattr(management_module, "encode_course_uuid", lambda course_id: f"course-{course_id}")
    monkeypatch.setattr(management_module, "encode_module_uuid", lambda module_id: f"module-{module_id}")
    material_root = tmp_path / "materials"
    object_key = "course-a/module-a/private_notes.txt"
    target_path = material_root / object_key
    target_path.parent.mkdir(parents=True)
    target_path.write_text(
        "Advanced theorem proof and optimization notes. VeryPrivateCapstonePhrase.",
        encoding="utf-8",
    )
    monkeypatch.setattr(management_module, "settings", SimpleNamespace(material_root_path=material_root))

    service = CourseManagementService(SimpleNamespace())
    course = SimpleNamespace(
        course_id=1,
        title="Algebra",
        learning_path=SimpleNamespace(learning_path_id=11),
    )
    module = SimpleNamespace(module_id=10, title="Linear equations", status=SimpleNamespace(value="published"))
    service.courses = SimpleNamespace(list_by_educator=lambda educator_id: [course])
    service.modules = SimpleNamespace(list_by_learning_path=lambda learning_path_id: [module])
    service.materials = SimpleNamespace(
        list_by_module=lambda module_id: [
            SimpleNamespace(
                material_id=100,
                title="Private notes",
                material_type=SimpleNamespace(value="text"),
                resource_url="/api/learning/materials/course-a/module-a/private_notes.txt",
                metadata_json={
                    "storageProvider": "local",
                    "objectKey": object_key,
                    "contentType": "text/plain",
                },
            )
        ]
    )
    service.quiz_attempts = SimpleNamespace(aggregate_stats_by_educator=lambda *, educator_id: [])

    response = service.get_educator_material_briefs(current_user={"id": 7, "identity": "Educator"})
    item = response.items[0]
    serialized = response.model_dump_json()

    assert "Text scan found 1 text-backed material" in item.summary
    assert "advanced concept cues" in item.summary
    assert "advanced or technical cues" in item.difficultySignal
    assert "private_notes" not in serialized
    assert "objectKey" not in serialized
    assert "VeryPrivateCapstonePhrase" not in serialized


def test_material_briefs_ignore_invalid_local_text_object_key(monkeypatch, tmp_path: Path) -> None:
    # Tests broken local text metadata is treated as unavailable signal instead of breaking the educator dashboard.
    monkeypatch.setattr(management_module, "encode_course_uuid", lambda course_id: f"course-{course_id}")
    monkeypatch.setattr(management_module, "encode_module_uuid", lambda module_id: f"module-{module_id}")
    monkeypatch.setattr(management_module, "settings", SimpleNamespace(material_root_path=tmp_path))

    service = CourseManagementService(SimpleNamespace())
    course = SimpleNamespace(
        course_id=1,
        title="Algebra",
        learning_path=SimpleNamespace(learning_path_id=11),
    )
    module = SimpleNamespace(module_id=10, title="Linear equations", status=SimpleNamespace(value="published"))
    service.courses = SimpleNamespace(list_by_educator=lambda educator_id: [course])
    service.modules = SimpleNamespace(list_by_learning_path=lambda learning_path_id: [module])
    service.materials = SimpleNamespace(
        list_by_module=lambda module_id: [
            SimpleNamespace(
                material_id=100,
                title="Broken notes",
                material_type=SimpleNamespace(value="text"),
                resource_url="/api/learning/materials/../secret.txt",
                metadata_json={
                    "storageProvider": "local",
                    "objectKey": "../secret.txt",
                    "contentType": "text/plain",
                },
            )
        ]
    )
    service.quiz_attempts = SimpleNamespace(aggregate_stats_by_educator=lambda *, educator_id: [])

    response = service.get_educator_material_briefs(current_user={"id": 7, "identity": "Educator"})

    assert response.items[0].moduleUuid == "module-10"
    assert "Text scan found" not in response.items[0].summary


def test_material_briefs_scan_minio_text_material_body_without_leaking_source(monkeypatch) -> None:
    # Tests production-style MinIO text-backed materials can inform briefs without exposing raw source data.
    monkeypatch.setattr(management_module, "encode_course_uuid", lambda course_id: f"course-{course_id}")
    monkeypatch.setattr(management_module, "encode_module_uuid", lambda module_id: f"module-{module_id}")
    monkeypatch.setattr(management_module, "settings", SimpleNamespace(minio_bucket="learning-materials"))
    response_state = {"closed": False, "released": False}
    calls = []

    class FakeMinioResponse:
        def read(self, size: int = -1) -> bytes:
            text = (
                "By the end you will learn the method. "
                "Worked example with practice checkpoint. "
                "VeryPrivateMinioPhrase."
            )
            payload = text.encode("utf-8")
            return payload if size < 0 else payload[:size]

        def close(self) -> None:
            response_state["closed"] = True

        def release_conn(self) -> None:
            response_state["released"] = True

    class FakeMinioClient:
        def get_object(self, bucket: str, object_key: str):
            calls.append((bucket, object_key))
            return FakeMinioResponse()

    monkeypatch.setattr(management_module.StorageService, "_build_minio_client", lambda self: FakeMinioClient())
    service = CourseManagementService(SimpleNamespace())
    course = SimpleNamespace(
        course_id=1,
        title="Algebra",
        learning_path=SimpleNamespace(learning_path_id=11),
    )
    module = SimpleNamespace(module_id=10, title="Linear equations", status=SimpleNamespace(value="published"))
    service.courses = SimpleNamespace(list_by_educator=lambda educator_id: [course])
    service.modules = SimpleNamespace(list_by_learning_path=lambda learning_path_id: [module])
    service.materials = SimpleNamespace(
        list_by_module=lambda module_id: [
            SimpleNamespace(
                material_id=100,
                title="MinIO notes",
                material_type=SimpleNamespace(value="text"),
                resource_url="/learning-materials/course-a/module-a/private_minio_notes.txt",
                metadata_json={
                    "storageProvider": "minio",
                    "bucket": "learning-materials",
                    "objectKey": "course-a/module-a/private_minio_notes.txt",
                    "contentType": "text/plain",
                },
            )
        ]
    )
    service.quiz_attempts = SimpleNamespace(aggregate_stats_by_educator=lambda *, educator_id: [])

    response = service.get_educator_material_briefs(current_user={"id": 7, "identity": "Educator"})
    item = response.items[0]
    serialized = response.model_dump_json()

    assert calls == [("learning-materials", "course-a/module-a/private_minio_notes.txt")]
    assert response_state == {"closed": True, "released": True}
    assert "Text scan found 1 text-backed material" in item.summary
    assert "learning objectives" in item.summary
    assert "worked examples" in item.summary
    assert "practice checkpoints" in item.summary
    assert "private_minio_notes" not in serialized
    assert "objectKey" not in serialized
    assert "VeryPrivateMinioPhrase" not in serialized


def test_material_briefs_api_uses_current_user(monkeypatch) -> None:
    # Tests the API handler delegates to the current educator material brief service.
    calls = []

    class FakeCourseManagementService:
        def __init__(self, session) -> None:
            self.session = session

        def get_educator_material_briefs(self, *, current_user):
            calls.append(current_user)
            return EducatorMaterialBriefsResponse(
                generatedAt=management_module.now_local(),
                totalBriefs=0,
                highPriorityCount=0,
                items=[],
            )

    monkeypatch.setattr(course_management_api, "CourseManagementService", FakeCourseManagementService)

    response = course_management_api.get_my_material_briefs(
        current_user={"id": 7, "identity": "Educator"},
        session=object(),
    )

    assert calls == [{"id": 7, "identity": "Educator"}]
    assert response.totalBriefs == 0

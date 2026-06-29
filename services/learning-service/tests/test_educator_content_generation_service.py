from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.educator_content_drafts import EducatorContentDraftType
from app.models.module_materials import MaterialType
from app.models.modules import ModuleStatus
from app.schemas.content_generation import ContentDraftGenerateRequest, ContentDraftUpdateRequest
from app.services.content_generation_service import EducatorContentDraftService


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.refreshed = []

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, obj):
        self.refreshed.append(obj)


class FakeCourses:
    def __init__(self, course):
        self.course = course

    def get_by_id(self, course_id: int):
        return self.course if self.course and self.course.course_id == course_id else None


class FakeLearningPaths:
    def __init__(self, path):
        self.path = path

    def get_by_course_id(self, course_id: int):
        return self.path if self.path and self.path.course_id == course_id else None


class FakeModules:
    def __init__(self, module):
        self.module = module

    def get_by_id(self, module_id: int):
        return self.module if self.module and self.module.module_id == module_id else None


class FakeMaterials:
    def __init__(self, materials):
        self.materials = list(materials)

    def list_by_module(self, module_id: int):
        return [material for material in self.materials if material.module_id == module_id]


class FakeDrafts:
    def __init__(self) -> None:
        self.rows = []
        self.created_payloads = []
        self.updated_payloads = []

    def create(self, **kwargs):
        self.created_payloads.append(kwargs)
        draft = SimpleNamespace(
            content_draft_id=len(self.rows) + 1,
            module_id=kwargs["module_id"],
            content_type=kwargs["content_type"],
            title=kwargs["title"],
            teacher_prompt=kwargs["teacher_prompt"],
            material_scope=kwargs["material_scope"],
            structured_content_json=kwargs["structured_content_json"],
            grounding_json=kwargs["grounding_json"],
            confidence_score=kwargs["confidence_score"],
            is_fallback=kwargs["is_fallback"],
            fallback_reason=kwargs["fallback_reason"],
            provider_name=kwargs["provider_name"],
            provider_model=kwargs["provider_model"],
            created_by=kwargs["created_by"],
            updated_by=kwargs["updated_by"],
            created_at=datetime(2026, 6, 30, 10, 0, 0),
            updated_at=datetime(2026, 6, 30, 10, 0, 0),
        )
        self.rows.append(draft)
        return draft

    def list_by_module(self, module_id: int):
        return [draft for draft in self.rows if draft.module_id == module_id]

    def get_by_id(self, draft_id: int):
        for draft in self.rows:
            if draft.content_draft_id == draft_id:
                return draft
        return None

    def update(self, draft, **kwargs):
        self.updated_payloads.append(kwargs)
        for key, value in kwargs.items():
            if key == "structured_content_json":
                draft.structured_content_json = value
            elif key == "grounding_json":
                draft.grounding_json = value
            elif key == "updated_by":
                draft.updated_by = value
            elif key == "title":
                draft.title = value
        draft.updated_at = datetime(2026, 6, 30, 11, 0, 0)
        return draft


class FakeAIClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def generate_draft(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def _course(educator_id=7):
    return SimpleNamespace(course_id=1, educator_id=educator_id, title="Algorithms")


def _path():
    return SimpleNamespace(learning_path_id=10, course_id=1)


def _module():
    return SimpleNamespace(
        module_id=20,
        learning_path_id=10,
        title="Graph Traversal",
        description="BFS and DFS traversal.",
        content="BFS uses a queue. DFS explores paths deeply.",
        status=ModuleStatus.DRAFT,
    )


def _material():
    return SimpleNamespace(
        material_id=30,
        module_id=20,
        title="Graph Notes",
        material_type=MaterialType.PDF,
        resource_url="/materials/graphs.pdf",
        metadata_json={"summary": "BFS, DFS, queues, stacks, and visited sets."},
    )


def _ai_response(content_type="summary"):
    return {
        "contentType": content_type,
        "title": "Graph Traversal Summary",
        "structuredContent": {"summary": "BFS and DFS visit graph nodes in different orders."},
        "grounding": [
            {
                "sourceTitle": "Graph Notes",
                "sourceType": "pdf",
                "reference": "Traversal section",
                "rationale": "Supports the generated summary.",
            }
        ],
        "confidenceScore": "0.8300",
        "isFallback": False,
        "provider": "fake",
        "model": "fake-model",
    }


def _service(ai_response=None):
    session = FakeSession()
    service = EducatorContentDraftService.__new__(EducatorContentDraftService)
    service.session = session
    service.courses = FakeCourses(_course())
    service.learning_paths = FakeLearningPaths(_path())
    service.modules = FakeModules(_module())
    service.materials = FakeMaterials([_material()])
    service.drafts = FakeDrafts()
    service.ai_client = FakeAIClient(ai_response or _ai_response())
    return service


def _patch_codecs(monkeypatch):
    monkeypatch.setattr("app.services.content_generation_service.decode_course_uuid", lambda value: 1)
    monkeypatch.setattr("app.services.content_generation_service.decode_module_uuid", lambda value: 20)
    monkeypatch.setattr("app.services.content_generation_service.decode_content_draft_uuid", lambda value: 1)
    monkeypatch.setattr("app.services.content_generation_service.encode_content_draft_uuid", lambda value: f"draft-{value}")
    monkeypatch.setattr("app.services.content_generation_service.encode_module_uuid", lambda value: f"module-{value}")


def test_generate_content_draft_persists_owner_scoped_ai_response(monkeypatch):
    _patch_codecs(monkeypatch)
    service = _service()
    original_module_content = service.modules.module.content
    original_module_status = service.modules.module.status

    result = service.generate_draft(
        course_uuid="course-1",
        module_uuid="module-20",
        payload=ContentDraftGenerateRequest(
            contentType="summary",
            teacherPrompt="Create a concise teaching summary.",
            materialScope="Graph notes",
        ),
        current_user={"id": 7, "identity": "Educator"},
    )

    assert result.draftUuid == "draft-1"
    assert result.moduleUuid == "module-20"
    assert result.contentType == "summary"
    assert result.structuredContent["summary"].startswith("BFS")
    assert result.grounding[0].sourceTitle == "Graph Notes"
    assert result.provider == "fake"
    assert service.session.commits == 1
    assert service.drafts.created_payloads[0]["content_type"] == EducatorContentDraftType.SUMMARY
    assert service.drafts.created_payloads[0]["confidence_score"] == Decimal("0.8300")
    assert service.ai_client.calls[0]["materials"][0]["summary"].startswith("BFS")
    assert service.modules.module.content == original_module_content
    assert service.modules.module.status == original_module_status


def test_generate_content_draft_rejects_non_owner(monkeypatch):
    _patch_codecs(monkeypatch)
    service = _service()

    with pytest.raises(HTTPException) as exc_info:
        service.generate_draft(
            course_uuid="course-1",
            module_uuid="module-20",
            payload=ContentDraftGenerateRequest(contentType="summary", teacherPrompt="Help"),
            current_user={"id": 8, "identity": "Educator"},
        )

    assert exc_info.value.status_code == 403
    assert service.session.commits == 0
    assert service.ai_client.calls == []


def test_generate_content_draft_rejects_invalid_ai_shape(monkeypatch):
    _patch_codecs(monkeypatch)
    service = _service(ai_response={"contentType": "summary", "title": "Broken"})

    with pytest.raises(HTTPException) as exc_info:
        service.generate_draft(
            course_uuid="course-1",
            module_uuid="module-20",
            payload=ContentDraftGenerateRequest(contentType="summary", teacherPrompt="Help"),
            current_user={"id": 7, "identity": "Educator"},
        )

    assert exc_info.value.status_code == 502
    assert service.session.commits == 0
    assert service.drafts.rows == []


def test_generate_content_draft_rejects_unmatched_ai_grounding(monkeypatch):
    _patch_codecs(monkeypatch)
    bad_response = _ai_response()
    bad_response["grounding"] = [
        {
            "sourceTitle": "Other Course Notes",
            "sourceType": "pdf",
            "reference": "Unrelated section",
            "rationale": "This source does not belong to the current module.",
        }
    ]
    service = _service(ai_response=bad_response)

    with pytest.raises(HTTPException) as exc_info:
        service.generate_draft(
            course_uuid="course-1",
            module_uuid="module-20",
            payload=ContentDraftGenerateRequest(contentType="summary", teacherPrompt="Help"),
            current_user={"id": 7, "identity": "Educator"},
        )

    assert exc_info.value.status_code == 502
    assert service.session.commits == 0
    assert service.drafts.rows == []


def test_update_content_draft_saves_edited_structured_content(monkeypatch):
    _patch_codecs(monkeypatch)
    service = _service()
    created = service.generate_draft(
        course_uuid="course-1",
        module_uuid="module-20",
        payload=ContentDraftGenerateRequest(contentType="summary", teacherPrompt="Help"),
        current_user={"id": 7, "identity": "Educator"},
    )

    updated = service.update_draft(
        course_uuid="course-1",
        module_uuid="module-20",
        draft_uuid=created.draftUuid,
        payload=ContentDraftUpdateRequest(
            title="Edited summary",
            structuredContent={"summary": "Edited text."},
            grounding=[
                {
                    "sourceTitle": "Graph Notes",
                    "sourceType": "pdf",
                    "reference": "Edited reference",
                    "rationale": "Educator verified this source.",
                }
            ],
        ),
        current_user={"id": 7, "identity": "Educator"},
    )

    assert updated.title == "Edited summary"
    assert updated.structuredContent == {"summary": "Edited text."}
    assert updated.grounding[0].reference == "Edited reference"
    assert updated.updatedBy == 7
    assert service.session.commits == 2

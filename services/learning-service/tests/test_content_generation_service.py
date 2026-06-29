from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.educator_content_drafts import EducatorContentDraftType
from app.schemas.content_generation import ContentDraftGenerateRequest, ContentDraftUpdateRequest
from app.services.content_generation_service import EducatorContentDraftService


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.refreshed = []

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def refresh(self, obj) -> None:
        self.refreshed.append(obj)


class FakeCourses:
    def __init__(self, course) -> None:
        self.course = course

    def get_by_id(self, course_id: int):
        return self.course if self.course and self.course.course_id == course_id else None


class FakeLearningPaths:
    def __init__(self, path) -> None:
        self.path = path

    def get_by_course_id(self, course_id: int):
        return self.path if self.path and self.path.course_id == course_id else None


class FakeModules:
    def __init__(self, module) -> None:
        self.module = module

    def get_by_id(self, module_id: int):
        return self.module if self.module and self.module.module_id == module_id else None


class FakeMaterials:
    def __init__(self, materials=None) -> None:
        self.materials = list(materials or [])

    def list_by_module(self, module_id: int):
        return [material for material in self.materials if material.module_id == module_id]


class FakeDrafts:
    def __init__(self, drafts=None) -> None:
        self.drafts = list(drafts or [])
        self.created = []

    def get_by_id(self, draft_id: int):
        return next((draft for draft in self.drafts if draft.content_draft_id == draft_id), None)

    def list_by_module(self, module_id: int):
        return [draft for draft in self.drafts if draft.module_id == module_id]

    def create(self, **kwargs):
        draft = SimpleNamespace(
            content_draft_id=len(self.drafts) + 100,
            created_at=datetime(2026, 6, 30, 12, 0, 0),
            updated_at=datetime(2026, 6, 30, 12, 0, 0),
            **kwargs,
        )
        self.drafts.append(draft)
        self.created.append(draft)
        return draft

    def update(self, draft, **kwargs):
        for key, value in kwargs.items():
            setattr(draft, key, value)
        draft.updated_at = datetime(2026, 6, 30, 13, 0, 0)
        return draft


class FakeAIClient:
    def __init__(self, response=None) -> None:
        self.response = response or {
            "contentType": "summary",
            "title": "Graph Traversal Summary",
            "structuredContent": {
                "summary": "BFS and DFS traverse graphs in different orders.",
                "keyPoints": ["BFS uses a queue.", "DFS uses recursion or a stack."],
            },
            "grounding": [
                {
                    "sourceTitle": "Graph Notes",
                    "sourceType": "pdf",
                    "reference": "BFS and DFS sections",
                    "rationale": "Supports the generated summary.",
                }
            ],
            "confidenceScore": "0.8200",
            "isFallback": False,
            "provider": "test",
            "model": "stub",
        }
        self.calls = []

    def generate_draft(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def _course(educator_id=7):
    return SimpleNamespace(course_id=1, educator_id=educator_id, title="Algorithms")


def _path():
    return SimpleNamespace(learning_path_id=10, course_id=1)


def _module(content="BFS uses a queue. DFS explores deeply."):
    return SimpleNamespace(
        module_id=20,
        learning_path_id=10,
        title="Graph Traversal",
        description="BFS and DFS traversal",
        content=content,
    )


def _material():
    return SimpleNamespace(
        material_id=30,
        module_id=20,
        title="Graph Notes",
        material_type=SimpleNamespace(value="pdf"),
        resource_url="/materials/graphs.pdf",
        metadata_json={"summary": "BFS queues and DFS stacks."},
    )


def _draft():
    return SimpleNamespace(
        content_draft_id=100,
        module_id=20,
        content_type=EducatorContentDraftType.SUMMARY,
        title="Old title",
        teacher_prompt="Old prompt",
        material_scope=None,
        structured_content_json={"summary": "Old"},
        grounding_json=[
            {
                "sourceTitle": "Graph Notes",
                "sourceType": "pdf",
                "reference": "Old section",
                "rationale": "Old rationale",
            }
        ],
        confidence_score=Decimal("0.8200"),
        is_fallback=False,
        fallback_reason=None,
        provider_name="test",
        provider_model="stub",
        created_by=7,
        updated_by=7,
        created_at=datetime(2026, 6, 30, 12, 0, 0),
        updated_at=datetime(2026, 6, 30, 12, 0, 0),
    )


def _service(monkeypatch, *, course=None, module=None, materials=None, drafts=None, ai_response=None):
    session = FakeSession()
    service = EducatorContentDraftService(session, ai_client=FakeAIClient(ai_response))
    service.courses = FakeCourses(course or _course())
    service.learning_paths = FakeLearningPaths(_path())
    service.modules = FakeModules(module or _module())
    service.materials = FakeMaterials(materials if materials is not None else [_material()])
    service.drafts = FakeDrafts(drafts)
    monkeypatch.setattr("app.services.content_generation_service.decode_course_uuid", lambda _: 1)
    monkeypatch.setattr("app.services.content_generation_service.decode_module_uuid", lambda _: 20)
    monkeypatch.setattr("app.services.content_generation_service.decode_content_draft_uuid", lambda _: 100)
    monkeypatch.setattr("app.services.content_generation_service.encode_module_uuid", lambda value: f"module-{value}")
    monkeypatch.setattr("app.services.content_generation_service.encode_content_draft_uuid", lambda value: f"draft-{value}")
    return service, session


def test_generate_draft_persists_grounded_ai_response(monkeypatch):
    service, session = _service(monkeypatch)

    result = service.generate_draft(
        course_uuid="course-uuid",
        module_uuid="module-uuid",
        payload=ContentDraftGenerateRequest(contentType="summary", teacherPrompt="Create a concise overview."),
        current_user={"id": 7, "identity": "Educator"},
    )

    assert result.draftUuid == "draft-100"
    assert result.contentType == "summary"
    assert result.structuredContent["summary"].startswith("BFS")
    assert result.grounding[0].sourceTitle == "Graph Notes"
    assert result.confidenceScore == Decimal("0.8200")
    assert service.drafts.created[0].created_by == 7
    assert service.ai_client.calls[0]["materials"][0]["summary"] == "BFS queues and DFS stacks."
    assert session.commits == 1


def test_generate_draft_rejects_invalid_ai_response_without_partial_write(monkeypatch):
    service, session = _service(monkeypatch, ai_response={"contentType": "summary", "title": "Broken"})

    with pytest.raises(HTTPException) as exc_info:
        service.generate_draft(
            course_uuid="course-uuid",
            module_uuid="module-uuid",
            payload=ContentDraftGenerateRequest(contentType="summary", teacherPrompt="Create a concise overview."),
            current_user={"id": 7, "identity": "Educator"},
        )

    assert exc_info.value.status_code == 502
    assert service.drafts.created == []
    assert session.commits == 0


def test_generate_draft_requires_owned_course(monkeypatch):
    service, _ = _service(monkeypatch, course=_course(educator_id=99))

    with pytest.raises(HTTPException) as exc_info:
        service.generate_draft(
            course_uuid="course-uuid",
            module_uuid="module-uuid",
            payload=ContentDraftGenerateRequest(contentType="summary", teacherPrompt="Create a concise overview."),
            current_user={"id": 7, "identity": "Educator"},
        )

    assert exc_info.value.status_code == 403


def test_generate_draft_requires_context(monkeypatch):
    service, _ = _service(monkeypatch, module=_module(content=None), materials=[])

    with pytest.raises(HTTPException) as exc_info:
        service.generate_draft(
            course_uuid="course-uuid",
            module_uuid="module-uuid",
            payload=ContentDraftGenerateRequest(contentType="summary"),
            current_user={"id": 7, "identity": "Educator"},
        )

    assert exc_info.value.status_code == 400


def test_update_draft_saves_teacher_edits(monkeypatch):
    existing = _draft()
    service, session = _service(monkeypatch, drafts=[existing])

    result = service.update_draft(
        course_uuid="course-uuid",
        module_uuid="module-uuid",
        draft_uuid="draft-uuid",
        payload=ContentDraftUpdateRequest(
            title="Edited title",
            structuredContent={"summary": "Edited summary."},
            grounding=[
                {
                    "sourceTitle": "Edited source",
                    "sourceType": "teacher_note",
                    "reference": "Manual edit",
                    "rationale": "Teacher refined the draft.",
                }
            ],
        ),
        current_user={"id": 8, "identity": "Admin"},
    )

    assert result.title == "Edited title"
    assert result.structuredContent["summary"] == "Edited summary."
    assert result.grounding[0].sourceTitle == "Edited source"
    assert existing.updated_by == 8
    assert session.commits == 1

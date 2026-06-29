from __future__ import annotations

import json

from app.schemas.content_generation import ContentGenerationRequest, ContentGenerationResponse
from app.services.providers.types import AIProviderError, ChatGenerationResult
from app.services.content_generation_service import EducatorContentGenerationService


class FakeProvider:
    provider_name = "fake-provider"

    def __init__(self, *, text: str | None = None, error: Exception | None = None) -> None:
        self.text = text
        self.error = error

    def generate(self, request):
        if self.error:
            raise self.error
        assert request.response_mime_type == "application/json"
        return ChatGenerationResult(text=self.text, usage_metadata={"total_tokens": 20}, raw_response={"ok": True})


def _payload() -> dict:
    return {
        "courseUuid": "course-uuid",
        "moduleUuid": "module-uuid",
        "educatorId": 7,
        "courseTitle": "Algorithms",
        "moduleTitle": "Graph Traversal",
        "moduleDescription": "Breadth-first and depth-first traversal for graphs.",
        "moduleContent": "BFS uses a queue to visit nodes by level. DFS explores paths deeply before backtracking.",
        "contentType": "slide_outline",
        "teacherPrompt": "Prepare slides for a 20 minute lesson.",
        "materials": [
            {
                "materialId": 11,
                "title": "Graph Traversal Notes",
                "materialType": "pdf",
                "resourceUrl": "/materials/graphs.pdf",
                "summary": "Notes covering BFS, DFS, queues, stacks, and visited sets.",
            }
        ],
    }


def test_content_generation_service_uses_provider_json(monkeypatch) -> None:
    provider_json = {
        "contentType": "slide_outline",
        "title": "Graph Traversal Lesson",
        "structuredContent": {
            "slides": [
                {
                    "title": "BFS and DFS",
                    "bullets": ["BFS uses a queue.", "DFS uses a stack or recursion."],
                    "speakerNotes": "Connect traversal order to graph examples.",
                }
            ],
        },
        "grounding": [
            {
                "sourceTitle": "Graph Traversal Notes",
                "sourceType": "pdf",
                "reference": "BFS and DFS sections",
                "rationale": "Supports the traversal comparison.",
            }
        ],
        "confidenceScore": 0.86,
    }
    monkeypatch.setattr(
        "app.services.content_generation_service.get_chat_provider",
        lambda: FakeProvider(text=json.dumps(provider_json)),
    )

    response = EducatorContentGenerationService().generate(ContentGenerationRequest(**_payload()))

    assert response.contentType == "slide_outline"
    assert response.structuredContent["slides"]
    assert response.grounding[0].sourceTitle == "Graph Traversal Notes"
    assert response.confidenceScore >= 0.8
    assert response.isFallback is False
    assert response.provider == "fake-provider"


def test_content_generation_service_falls_back_when_provider_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.content_generation_service.get_chat_provider",
        lambda: FakeProvider(error=AIProviderError("quota", error_type="quota", status_code=429)),
    )
    payload = {
        **_payload(),
        "moduleDescription": None,
        "moduleContent": None,
        "teacherPrompt": "Help.",
        "materials": [],
        "contentType": "summary",
    }

    response = EducatorContentGenerationService().generate(ContentGenerationRequest(**payload))

    assert response.isFallback is True
    assert response.confidenceScore < 0.5
    assert response.fallbackReason == "quota"
    assert response.grounding[0].sourceType == "module"


def test_content_generation_service_falls_back_on_low_provider_confidence(monkeypatch) -> None:
    provider_json = {
        "contentType": "summary",
        "title": "Weak draft",
        "structuredContent": {"summary": "Too little context."},
        "grounding": [
            {
                "sourceTitle": "Graph Traversal Notes",
                "sourceType": "pdf",
                "reference": "Unknown",
                "rationale": "Weak support.",
            }
        ],
        "confidenceScore": 0.3,
    }
    monkeypatch.setattr(
        "app.services.content_generation_service.get_chat_provider",
        lambda: FakeProvider(text=json.dumps(provider_json)),
    )

    response = EducatorContentGenerationService().generate(ContentGenerationRequest(**{**_payload(), "contentType": "summary"}))

    assert response.isFallback is True
    assert response.fallbackReason == "low_confidence"
    assert response.provider == "fallback"


def test_content_generation_service_falls_back_on_empty_provider_content(monkeypatch) -> None:
    provider_json = {
        "contentType": "summary",
        "title": "Empty draft",
        "structuredContent": {},
        "grounding": [
            {
                "sourceTitle": "Graph Traversal Notes",
                "sourceType": "pdf",
                "reference": "BFS section",
                "rationale": "Supports the summary.",
            }
        ],
        "confidenceScore": 0.9,
    }
    monkeypatch.setattr(
        "app.services.content_generation_service.get_chat_provider",
        lambda: FakeProvider(text=json.dumps(provider_json)),
    )

    response = EducatorContentGenerationService().generate(ContentGenerationRequest(**{**_payload(), "contentType": "summary"}))

    assert response.isFallback is True
    assert response.fallbackReason == "invalid_provider_response"
    assert response.structuredContent


def test_content_generation_service_falls_back_on_unmatched_grounding(monkeypatch) -> None:
    provider_json = {
        "contentType": "summary",
        "title": "Ungrounded draft",
        "structuredContent": {"summary": "A summary from the wrong source."},
        "grounding": [
            {
                "sourceTitle": "Other Course Notes",
                "sourceType": "pdf",
                "reference": "Unrelated section",
                "rationale": "This does not belong to the module.",
            }
        ],
        "confidenceScore": 0.9,
    }
    monkeypatch.setattr(
        "app.services.content_generation_service.get_chat_provider",
        lambda: FakeProvider(text=json.dumps(provider_json)),
    )

    response = EducatorContentGenerationService().generate(ContentGenerationRequest(**{**_payload(), "contentType": "summary"}))

    assert response.isFallback is True
    assert response.fallbackReason == "unmatched_grounding"
    assert response.grounding[0].sourceTitle == "Graph Traversal Notes"


def test_internal_content_generation_endpoint_success(client, monkeypatch) -> None:
    monkeypatch.setattr(
        EducatorContentGenerationService,
        "generate",
        lambda self, payload: ContentGenerationResponse(
            contentType=payload.contentType,
            title="Generated",
            structuredContent={"summary": "Generated summary.", "keyPoints": ["One"]},
            grounding=[
                {
                    "sourceTitle": "Graph Notes",
                    "sourceType": "pdf",
                    "reference": "BFS section",
                    "rationale": "Supports the summary.",
                }
            ],
            confidenceScore=0.82,
            isFallback=False,
            provider="test",
            model="stub",
        ),
    )

    response = client.post("/internal/content-generation/educator-draft", json={**_payload(), "contentType": "summary"})

    assert response.status_code == 200
    body = response.json()
    assert body["structuredContent"]["summary"] == "Generated summary."
    assert body["grounding"][0]["sourceTitle"] == "Graph Notes"


def test_internal_content_generation_endpoint_rejects_empty_context(client) -> None:
    payload = {
        **_payload(),
        "moduleDescription": None,
        "moduleContent": None,
        "teacherPrompt": None,
        "materials": [],
    }

    response = client.post("/internal/content-generation/educator-draft", json=payload)

    assert response.status_code == 422

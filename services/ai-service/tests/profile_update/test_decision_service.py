from __future__ import annotations

from types import SimpleNamespace

from app.services.workflows.profile_update.services.decision_service import ModuleProfileUpdateDecisionService


def test_generate_decision_uses_chat_provider_adapter(monkeypatch) -> None:
    # Tests module profile update decisions call the provider adapter with JSON response mode.
    captured: dict[str, object] = {}

    class FakeProvider:
        def generate(self, request):
            captured["request"] = request
            return SimpleNamespace(text='{"should_update": false, "reason": "No update needed", "patch": {}}')

    monkeypatch.setattr(
        "app.services.workflows.profile_update.services.decision_service.get_chat_provider",
        lambda: FakeProvider(),
    )

    result = ModuleProfileUpdateDecisionService().generate_decision(
        context={"scope": {"learnerId": 7}},
        validation_feedback=[],
    )

    assert result.should_update is False
    assert result.patch == {}
    assert captured["request"].response_mime_type == "application/json"
    assert captured["request"].contents.startswith("Module update context JSON")

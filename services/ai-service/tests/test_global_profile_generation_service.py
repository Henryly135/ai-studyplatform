from __future__ import annotations

import pytest

from app.services.profiles.global_profile_generation_service import (
    GlobalProfileGenerationService,
    GlobalProfilePreferences,
)


def _preferences() -> GlobalProfilePreferences:
    return GlobalProfilePreferences(
        support_role="Coach",
        help_style="Step by step",
        learning_focus="Conceptual clarity",
        response_tone="Encouraging",
    )


def test_validate_generated_profile_accepts_complete_profile() -> None:
    # Tests validation accepts a complete, concise global profile.
    content = (
        "# Global Skills Profile\n\n"
        "Support role:\nCoach\n\n"
        "Help style:\nStep by step examples and direct checks for understanding.\n\n"
        "Learning focus:\nConceptual clarity, practice transfer, and steady revision across topics.\n\n"
        "Response tone:\nEncouraging, concise, and calm.\n\n"
        "Platform instruction:\nUse this profile as the learner's stable preference layer across modules."
    )

    assert GlobalProfileGenerationService().validate_generated_profile(content) == []


def test_validate_generated_profile_reports_missing_blocked_and_length_issues() -> None:
    # Tests validation reports missing sections, blocked terms, and too-short output.
    issues = GlobalProfileGenerationService().validate_generated_profile("quiz score")

    assert "Missing required section: # Global Skills Profile" in issues
    assert "Contains disallowed content: quiz score" in issues
    assert "Profile is too short" in issues


def test_render_template_fallback_uses_preferences() -> None:
    # Tests fallback profile rendering embeds learner preferences in the default structure.
    rendered = GlobalProfileGenerationService().render_template_fallback(
        preferences=_preferences(),
        default_template="ignored",
    )

    assert "# Global Skills Profile" in rendered
    assert "Coach" in rendered
    assert "Step by step" in rendered
    assert "Conceptual clarity" in rendered
    assert "Encouraging" in rendered


def test_build_user_prompt_includes_validation_issues() -> None:
    # Tests retry prompt includes previous validation issues for regeneration.
    prompt = GlobalProfileGenerationService()._build_user_prompt(
        preferences=_preferences(),
        default_template="# Template",
        validation_issues=["Missing section"],
    )

    assert "Default profile template" in prompt
    assert "Learner preferences" in prompt
    assert "- Missing section" in prompt
    assert "previous output did not pass validation" in prompt


@pytest.mark.parametrize(
    "preferences",
    [
        GlobalProfilePreferences("", "style", "focus", "tone"),
        GlobalProfilePreferences("x" * 201, "style", "focus", "tone"),
    ],
)
def test_validate_preferences_rejects_blank_or_too_long_fields(preferences) -> None:
    # Tests preference validation rejects empty and overlong fields.
    with pytest.raises(Exception):
        GlobalProfileGenerationService()._validate_preferences(preferences)


def test_generate_profile_falls_back_after_generation_failures(monkeypatch) -> None:
    # Tests profile generation falls back to template rendering after repeated provider failures.
    service = GlobalProfileGenerationService()
    monkeypatch.setattr(service, "load_default_template", lambda: "# Template")
    monkeypatch.setattr(service, "_generate_once", lambda **_: (_ for _ in ()).throw(RuntimeError("provider down")))

    rendered = service.generate_profile(preferences=_preferences())

    assert "Coach" in rendered
    assert "Platform instruction:" in rendered

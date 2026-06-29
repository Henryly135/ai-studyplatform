from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.core.prompts import get_prompt_template
from app.services.providers import AIProviderConfigurationError, AIProviderError, ChatGenerationRequest, get_chat_provider
from platform_common.errors import invalid_request_error

_REQUIRED_SECTIONS = (
    "# Global Skills Profile",
    "Support role:",
    "Help style:",
    "Learning focus:",
    "Response tone:",
    "Platform instruction:",
)
_BLOCKED_TERMS = (
    "module-specific",
    "quiz score",
    "performance",
    "mastery",
    "correct count",
    "wrong answer",
)


@dataclass(frozen=True)
class GlobalProfilePreferences:
    support_role: str
    help_style: str
    learning_focus: str
    response_tone: str


class GlobalProfileGenerationService:
    MAX_ATTEMPTS = 3
    PROMPT_TEMPLATE_NAME = "global_profile_init_v1"

    def load_default_template(self) -> str:
        template_path = Path(__file__).resolve().parents[2] / "assets" / "templates" / "default_global_profile_v1.md"
        return template_path.read_text(encoding="utf-8").strip()

    def generate_profile(self, *, preferences: GlobalProfilePreferences) -> str:
        self._validate_preferences(preferences)
        default_template = self.load_default_template()
        last_issues: list[str] = []

        for _ in range(self.MAX_ATTEMPTS):
            try:
                generated = self._generate_once(
                    preferences=preferences,
                    default_template=default_template,
                    validation_issues=last_issues,
                )
            except Exception as exc:
                last_issues = [f"Generation error: {exc}"]
                continue
            issues = self.validate_generated_profile(generated)
            if not issues:
                return generated.strip()
            last_issues = issues

        return self.render_template_fallback(preferences=preferences, default_template=default_template)

    def validate_generated_profile(self, content: str) -> list[str]:
        normalized = content.strip()
        issues: list[str] = []
        for marker in _REQUIRED_SECTIONS:
            if marker not in normalized:
                issues.append(f"Missing required section: {marker}")

        lowered = normalized.lower()
        for blocked in _BLOCKED_TERMS:
            if blocked in lowered:
                issues.append(f"Contains disallowed content: {blocked}")

        word_count = len(normalized.split())
        if word_count < 30:
            issues.append("Profile is too short")
        if word_count > 220:
            issues.append("Profile is too long")
        return issues

    def render_template_fallback(self, *, preferences: GlobalProfilePreferences, default_template: str) -> str:
        _ = default_template
        return (
            "# Global Skills Profile\n\n"
            "Support role:\n"
            f"{preferences.support_role}\n\n"
            "Help style:\n"
            f"{preferences.help_style}\n\n"
            "Learning focus:\n"
            f"{preferences.learning_focus}\n\n"
            "Response tone:\n"
            f"{preferences.response_tone}\n\n"
            "Platform instruction:\n"
            "Use this profile as the learner's stable global preference layer.\n"
            "Provide help in a way that matches the learner's selected preferences.\n"
            "Keep this profile general across modules.\n"
            "If module-level evidence suggests a more specific need, the module profile may refine the support style."
        )

    def _generate_once(
        self,
        *,
        preferences: GlobalProfilePreferences,
        default_template: str,
        validation_issues: list[str],
    ) -> str:
        prompt = self._build_user_prompt(
            preferences=preferences,
            default_template=default_template,
            validation_issues=validation_issues,
        )
        try:
            prompt_template = get_prompt_template(self.PROMPT_TEMPLATE_NAME)
            response = get_chat_provider().generate(
                ChatGenerationRequest(
                    model=settings.ai_chat_model,
                    contents=prompt,
                    system_instruction=prompt_template.system_instruction,
                    temperature=0.2,
                    max_output_tokens=800,
                )
            )
        except (AIProviderConfigurationError, AIProviderError) as exc:
            raise invalid_request_error(f"Global profile generation failed: {exc}") from exc

        content = (response.text or "").strip()
        if not content:
            raise invalid_request_error("Global profile generation returned empty content")
        return content

    def _build_user_prompt(
        self,
        *,
        preferences: GlobalProfilePreferences,
        default_template: str,
        validation_issues: list[str],
    ) -> str:
        base_prompt = (
            "Default profile template:\n\n"
            f"{default_template}\n\n"
            "Learner preferences:\n\n"
            f"Support role: {preferences.support_role}\n"
            f"Help style: {preferences.help_style}\n"
            f"Learning focus: {preferences.learning_focus}\n"
            f"Response tone: {preferences.response_tone}\n\n"
            "Generate a learner-specific global skills profile based on the template and these preferences."
        )
        if not validation_issues:
            return base_prompt

        issue_lines = "\n".join(f"- {issue}" for issue in validation_issues)
        return (
            f"{base_prompt}\n\n"
            "Your previous output did not pass validation.\n\n"
            "Validation issues:\n"
            f"{issue_lines}\n\n"
            "Please regenerate the profile and fix these issues.\n"
            "Remember:\n"
            "- keep the markdown structure\n"
            "- do not include module-specific or performance-based information\n"
            "- keep the profile concise and clear"
        )

    def _validate_preferences(self, preferences: GlobalProfilePreferences) -> None:
        for field_name, value in (
            ("support_role", preferences.support_role),
            ("help_style", preferences.help_style),
            ("learning_focus", preferences.learning_focus),
            ("response_tone", preferences.response_tone),
        ):
            normalized = value.strip()
            if not normalized:
                raise invalid_request_error(f"{field_name} is required")
            if len(normalized) > 200:
                raise invalid_request_error(f"{field_name} must be at most 200 characters")

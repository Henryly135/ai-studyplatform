from __future__ import annotations

import json
from typing import Any

from google import genai
from google.genai import errors as genai_errors, types

from app.core.config import settings
from app.core.prompts import get_prompt_template
from app.services.provider_error_messages import MODULE_PROFILE_UPDATE_UNAVAILABLE
from app.services.workflows.profile_update.schemas import ModuleProfileUpdateCheckDecision
from platform_common.errors import invalid_request_error


class ModuleProfileUpdateDecisionService:
    PROMPT_TEMPLATE_NAME = "module_profile_update_check_v1"

    def generate_decision(
        self,
        *,
        context: dict[str, Any],
        validation_feedback: list[str],
    ) -> ModuleProfileUpdateCheckDecision:
        if not settings.gemini_api_key:
            raise invalid_request_error(MODULE_PROFILE_UPDATE_UNAVAILABLE)

        prompt_template = get_prompt_template(self.PROMPT_TEMPLATE_NAME)
        prompt = self._build_prompt(context=context, validation_feedback=validation_feedback)
        client = genai.Client(api_key=settings.gemini_api_key)
        try:
            response = client.models.generate_content(
                model=settings.ai_demo_model_name,
                config=types.GenerateContentConfig(
                    system_instruction=prompt_template.system_instruction,
                    temperature=0.2,
                    max_output_tokens=1200,
                    response_mime_type="application/json",
                ),
                contents=prompt,
            )
        except genai_errors.ClientError as exc:
            raise invalid_request_error(MODULE_PROFILE_UPDATE_UNAVAILABLE) from exc

        content = (response.text or "").strip()
        if not content:
            raise invalid_request_error("Module profile update check returned empty content")

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise invalid_request_error("Module profile update check returned invalid JSON") from exc

        if not isinstance(parsed, dict):
            raise invalid_request_error("Module profile update check returned an unexpected payload")

        decision = ModuleProfileUpdateCheckDecision.model_validate(parsed)
        if not decision.should_update:
            return ModuleProfileUpdateCheckDecision(
                should_update=False,
                update_mode=None,
                reason=decision.reason,
                patch={},
            )
        if decision.update_mode is None:
            raise invalid_request_error("update_mode is required when should_update is true")
        if not decision.patch:
            raise invalid_request_error("patch is required when should_update is true")
        return decision

    def _build_prompt(
        self,
        *,
        context: dict[str, Any],
        validation_feedback: list[str],
    ) -> str:
        output_shape = {
            "should_update": True,
            "update_mode": "light_update",
            "reason": "Short evidence-based reason.",
            "patch": {
                "weak_points": ["example weakness"],
                "recommended_focus": ["example focus"],
                "confidence_estimate": 0.42,
            },
        }
        prompt = (
            "Module update context JSON:\n"
            f"{json.dumps(context, ensure_ascii=True, indent=2)}\n\n"
            "Required output JSON shape:\n"
            f"{json.dumps(output_shape, ensure_ascii=True, indent=2)}\n\n"
            "If no update is needed, return:\n"
            '{"should_update": false, "update_mode": null, "reason": "short reason", "patch": {}}\n'
        )
        if not validation_feedback:
            return prompt

        issues = "\n".join(f"- {issue}" for issue in validation_feedback)
        return (
            f"{prompt}\n\n"
            "The previous candidate patch was rejected.\n"
            "Validation feedback:\n"
            f"{issues}\n\n"
            "Regenerate a corrected JSON response.\n"
        )

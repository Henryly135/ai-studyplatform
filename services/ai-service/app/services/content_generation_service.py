from __future__ import annotations

import json
import re
from typing import Any

from app.core.config import settings
from app.schemas.content_generation import (
    ContentGenerationGroundingItem,
    ContentGenerationMaterialInput,
    ContentGenerationRequest,
    ContentGenerationResponse,
)
from app.services.providers.factory import get_chat_provider
from app.services.providers.types import (
    AIProviderConfigurationError,
    AIProviderError,
    ChatGenerationRequest,
)


class EducatorContentGenerationService:
    def generate(self, payload: ContentGenerationRequest) -> ContentGenerationResponse:
        try:
            provider = get_chat_provider()
            result = provider.generate(
                ChatGenerationRequest(
                    model=settings.ai_chat_model,
                    system_instruction=self._system_instruction(),
                    contents=self._prompt(payload),
                    temperature=0.25,
                    max_output_tokens=max(settings.ai_chat_max_output_tokens, 1400),
                    response_mime_type="application/json",
                )
            )
            response = self._parse_provider_response(result.text)
            if response.contentType != payload.contentType:
                raise ValueError("Provider returned a content type mismatch")
            if not self._grounding_matches_payload(response, payload):
                return self._fallback_response(payload, fallback_reason="unmatched_grounding")
            if response.confidenceScore < 0.5:
                return self._fallback_response(payload, fallback_reason="low_confidence")
            return response.model_copy(
                update={
                    "provider": response.provider or provider.provider_name,
                    "model": response.model or settings.ai_chat_model,
                    "isFallback": False,
                    "fallbackReason": None,
                }
            )
        except (AIProviderConfigurationError, AIProviderError, ValueError, TypeError, json.JSONDecodeError) as exc:
            return self._fallback_response(payload, fallback_reason=self._fallback_reason(exc))

    def _system_instruction(self) -> str:
        return (
            "You generate editable teaching content drafts for educators. Return only valid JSON. "
            "The JSON must include contentType, title, structuredContent, grounding, and confidenceScore. "
            "Each grounding item must name a module material or module context with sourceTitle, sourceType, "
            "reference, and rationale. Do not include markdown outside JSON."
        )

    def _prompt(self, payload: ContentGenerationRequest) -> str:
        return json.dumps(
            {
                "task": "Generate an educator-editable teaching content draft from the module context.",
                "course": {"uuid": payload.courseUuid, "title": payload.courseTitle},
                "module": {
                    "uuid": payload.moduleUuid,
                    "title": payload.moduleTitle,
                    "description": payload.moduleDescription,
                    "content": payload.moduleContent,
                },
                "contentType": payload.contentType,
                "materialScope": payload.materialScope,
                "teacherPrompt": payload.teacherPrompt,
                "materials": [material.model_dump() for material in payload.materials],
                "responseShape": {
                    "contentType": payload.contentType,
                    "title": "string",
                    "structuredContent": {
                        "summary": "string for summary drafts",
                        "keyPoints": ["string"],
                        "objectives": ["string for learning_objectives drafts"],
                        "activities": [{"title": "string", "durationMinutes": "integer", "description": "string"}],
                        "explanations": [{"level": "support|core|extension", "title": "string", "body": "string"}],
                        "slides": [{"title": "string", "bullets": ["string"], "speakerNotes": "string"}],
                        "editableMarkdown": "optional educator-editable markdown string",
                    },
                    "grounding": [
                        {
                            "sourceTitle": "string",
                            "sourceType": "pdf|video|file|link|text|module",
                            "reference": "material title, heading, or module section",
                            "rationale": "why this source supports the draft",
                        }
                    ],
                    "confidenceScore": "number between 0 and 1",
                },
            },
            ensure_ascii=True,
        )

    def _parse_provider_response(self, text: str | None) -> ContentGenerationResponse:
        if not text or not text.strip():
            raise ValueError("Provider returned an empty content draft")
        parsed: Any = json.loads(text)
        if isinstance(parsed, dict) and "draft" in parsed:
            parsed = parsed["draft"]
        if not isinstance(parsed, dict):
            raise ValueError("Provider returned an unexpected content draft shape")
        return ContentGenerationResponse.model_validate(parsed)

    def _grounding_matches_payload(self, response: ContentGenerationResponse, payload: ContentGenerationRequest) -> bool:
        allowed_titles = [payload.moduleTitle, *(material.title for material in payload.materials)]
        return all(self._source_title_matches(item.sourceTitle, allowed_titles) for item in response.grounding)

    def _source_title_matches(self, source_title: str, allowed_titles: list[str]) -> bool:
        normalized_source = self._normalize_match_text(source_title)
        if not normalized_source:
            return False
        for title in allowed_titles:
            normalized_title = self._normalize_match_text(title)
            if normalized_title and (
                normalized_source == normalized_title
                or normalized_title in normalized_source
                or normalized_source in normalized_title
            ):
                return True
        return False

    def _fallback_response(self, payload: ContentGenerationRequest, *, fallback_reason: str) -> ContentGenerationResponse:
        grounding = self._grounding(payload)
        structured_content = self._structured_content(payload, is_fallback=True)
        return ContentGenerationResponse(
            contentType=payload.contentType,
            title=self._title(payload),
            structuredContent=structured_content,
            grounding=grounding,
            confidenceScore=0.48,
            isFallback=True,
            fallbackReason=fallback_reason,
            provider="fallback",
            model="educator-content-heuristic-v1",
        )

    def _structured_content(self, payload: ContentGenerationRequest, *, is_fallback: bool) -> dict[str, Any]:
        key_terms = self._key_terms(payload)
        if payload.contentType == "summary":
            return {
                "summary": self._summary_text(payload, key_terms, is_fallback=is_fallback),
                "keyPoints": self._key_points(payload, key_terms),
                "teacherNotes": self._teacher_notes(payload),
            }
        if payload.contentType == "learning_objectives":
            return {
                "objectives": [
                    f"Explain {term} in the context of {payload.moduleTitle}."
                    for term in key_terms[:4]
                ]
                or [f"Describe the core ideas from {payload.moduleTitle}."],
                "successCriteria": [
                    "Students can use precise terminology.",
                    "Students can connect examples back to the module materials.",
                ],
            }
        if payload.contentType == "activity_suggestions":
            return {
                "activities": [
                    {
                        "title": f"{payload.moduleTitle} concept sort",
                        "durationMinutes": 15,
                        "description": f"Students sort examples and non-examples for {', '.join(key_terms[:3]) or payload.moduleTitle}.",
                        "materialsNeeded": [material.title for material in payload.materials[:3]] or ["Module notes"],
                    },
                    {
                        "title": "Peer explanation check",
                        "durationMinutes": 10,
                        "description": "Pairs explain the concept, then annotate one missing detail using the source material.",
                        "materialsNeeded": ["Timer", "Shared notes"],
                    },
                ],
                "teacherNotes": self._teacher_notes(payload),
            }
        if payload.contentType == "differentiated_explanation":
            return {
                "explanations": [
                    {
                        "level": "support",
                        "title": "Plain-language explanation",
                        "body": f"Start with the main idea of {payload.moduleTitle}: {self._first_sentence(payload)}",
                    },
                    {
                        "level": "core",
                        "title": "Core class explanation",
                        "body": f"Connect {', '.join(key_terms[:3]) or 'the core terms'} to the examples in the module materials.",
                    },
                    {
                        "level": "extension",
                        "title": "Extension prompt",
                        "body": "Ask students to compare this idea with a prior module and justify the difference.",
                    },
                ]
            }
        return {
            "slides": [
                {
                    "title": payload.moduleTitle,
                    "bullets": self._key_points(payload, key_terms)[:3],
                    "speakerNotes": self._summary_text(payload, key_terms, is_fallback=is_fallback),
                },
                {
                    "title": "Guided practice",
                    "bullets": [
                        "Review one source example.",
                        "Identify the key terms.",
                        "Apply the idea to a new case.",
                    ],
                    "speakerNotes": "Use the activity as a quick formative check.",
                },
                {
                    "title": "Exit check",
                    "bullets": [
                        "One sentence summary.",
                        "One question still unresolved.",
                    ],
                    "speakerNotes": "Collect responses to plan follow-up support.",
                },
            ]
        }

    def _grounding(self, payload: ContentGenerationRequest) -> list[ContentGenerationGroundingItem]:
        materials = payload.materials[:4]
        if materials:
            return [
                ContentGenerationGroundingItem(
                    sourceTitle=material.title,
                    sourceType=material.materialType,
                    reference=material.summary or material.resourceUrl or f"Module material {index + 1}",
                    rationale=f"Used as source context for {payload.contentType.replace('_', ' ')}.",
                )
                for index, material in enumerate(materials)
            ]
        return [
            ContentGenerationGroundingItem(
                sourceTitle=payload.moduleTitle,
                sourceType="module",
                reference=payload.moduleDescription or payload.moduleContent or payload.teacherPrompt or "Teacher prompt",
                rationale="Used module metadata and teacher prompt because no material records were available.",
            )
        ]

    def _title(self, payload: ContentGenerationRequest) -> str:
        label = payload.contentType.replace("_", " ").title()
        return f"{payload.moduleTitle} {label}"

    def _summary_text(self, payload: ContentGenerationRequest, key_terms: list[str], *, is_fallback: bool) -> str:
        base = self._first_sentence(payload)
        terms = ", ".join(key_terms[:4])
        if terms:
            base = f"{base} Key emphasis: {terms}."
        if is_fallback:
            base = f"{base} This is a low-confidence starting point because limited source context was available."
        return base

    def _key_points(self, payload: ContentGenerationRequest, key_terms: list[str]) -> list[str]:
        if key_terms:
            return [f"Clarify how {term} applies in {payload.moduleTitle}." for term in key_terms[:5]]
        return [
            f"Introduce the main idea of {payload.moduleTitle}.",
            "Connect the idea to one concrete example.",
            "Check understanding with a short student response.",
        ]

    def _teacher_notes(self, payload: ContentGenerationRequest) -> str:
        if payload.teacherPrompt:
            return f"Teacher prompt incorporated: {payload.teacherPrompt}"
        if payload.materialScope:
            return f"Material scope: {payload.materialScope}"
        return "Review the draft and tailor examples for the class."

    def _first_sentence(self, payload: ContentGenerationRequest) -> str:
        text = payload.moduleContent or payload.moduleDescription or payload.teacherPrompt or ""
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        first = next((sentence for sentence in sentences if sentence.strip()), "")
        if first:
            return first[:500]
        if payload.materials:
            return f"This draft is grounded in {payload.materials[0].title}."
        return f"This draft introduces {payload.moduleTitle}."

    def _key_terms(self, payload: ContentGenerationRequest) -> list[str]:
        source = " ".join(
            [
                payload.moduleTitle,
                payload.moduleDescription or "",
                payload.moduleContent or "",
                payload.teacherPrompt or "",
                " ".join(material.title for material in payload.materials),
                " ".join(material.summary or "" for material in payload.materials),
            ]
        )
        words = [word.lower() for word in re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", source)]
        stop_words = {
            "this",
            "that",
            "with",
            "from",
            "module",
            "course",
            "students",
            "student",
            "teacher",
            "prompt",
            "material",
            "materials",
            "explain",
            "summary",
            "learning",
        }
        seen: set[str] = set()
        terms: list[str] = []
        for word in words:
            if word in stop_words or word in seen:
                continue
            seen.add(word)
            terms.append(word)
        return terms[:8]

    def _is_low_context(self, payload: ContentGenerationRequest) -> bool:
        material_words = sum(len(self._words(material.title + " " + (material.summary or ""))) for material in payload.materials)
        module_words = len(self._words((payload.moduleContent or "") + " " + (payload.moduleDescription or "")))
        prompt_words = len(self._words(payload.teacherPrompt or ""))
        return material_words + module_words + prompt_words < 18

    def _words(self, text: str) -> list[str]:
        return re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text)

    def _fallback_reason(self, exc: Exception) -> str:
        if isinstance(exc, AIProviderError):
            return exc.error_type
        if isinstance(exc, AIProviderConfigurationError):
            return "provider_not_configured"
        return "invalid_provider_response"

    def _normalize_match_text(self, value: str) -> str:
        return re.sub(r"\s+", " ", value.strip().lower())

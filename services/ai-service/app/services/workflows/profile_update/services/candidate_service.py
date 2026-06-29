from __future__ import annotations

import copy
import logging

from app.core.time import now_local
from app.services.workflows.profile_update.schemas import (
    ModuleProfileCandidateUpdateRequest,
    ModuleProfileCandidateUpdateResponse,
)
from app.services.workflows.profile_update.services.persistence_service import ModuleProfilePersistenceService


logger = logging.getLogger(__name__)

PATCH_LIST_FIELDS = {
    "common_error_patterns",
    "weak_points",
    "strong_points",
    "recent_confusions",
    "recommended_focus",
}
MAX_LIST_ITEM_LENGTH = 300
LIGHT_UPDATE_MAX_FIELDS = 6
ALLOWED_RESPONSE_PREFERENCES = {
    "adaptive",
    "more_guided",
    "more_concise",
    "step_by_step",
    "worked_examples",
    "simpler_language",
}
ALLOWED_KNOWLEDGE_STABILITY = {
    "unknown",
    "unstable",
    "mixed",
    "stable",
}
ALLOWED_ENGAGEMENT_PATTERNS = {
    "unknown",
    "engaged",
    "high_engagement",
    "persistent_but_struggling",
    "low_engagement",
}
ALLOWED_SUPPORT_NEED_LEVELS = {
    "low",
    "medium",
    "high",
}


class ModuleProfileCandidateService:
    def __init__(self, session) -> None:
        self.session = session
        self.persistence = ModuleProfilePersistenceService(session)

    def submit_candidate_patch(
        self,
        *,
        payload: ModuleProfileCandidateUpdateRequest,
    ) -> ModuleProfileCandidateUpdateResponse:
        changed_fields = list(payload.patch.model_dump(exclude_none=True).keys())
        logger.info(
            "Submitting module profile candidate patch",
            extra={
                "learnerId": payload.learnerId,
                "courseUuid": payload.courseUuid,
                "moduleUuid": payload.moduleUuid,
                "source": payload.source,
                "updateMode": payload.updateMode,
                "changedFields": changed_fields,
            },
        )
        try:
            base = self.persistence.load_active_or_default(
                learner_id=payload.learnerId,
                course_uuid=payload.courseUuid,
                module_uuid=payload.moduleUuid,
            )
            candidate = self._merge_patch(
                base_profile=base.base_profile,
                patch=payload.patch.model_dump(exclude_none=True),
            )
            self._validate_candidate(
                candidate=candidate,
                update_mode=payload.updateMode,
                changed_fields=changed_fields,
            )
            profile = self.persistence.persist_candidate(
                learner_id=payload.learnerId,
                course_id=base.course_id,
                module_id=base.module_id,
                active_asset=base.active_asset,
                candidate=candidate,
            )
            response = ModuleProfileCandidateUpdateResponse(
                accepted=True,
                retryable=False,
                code="PROFILE_UPDATED",
                message="Candidate patch accepted and persisted",
                changedFields=changed_fields,
                profile=profile,
            )
            logger.info(
                "Accepted module profile candidate patch",
                extra={
                    "learnerId": payload.learnerId,
                    "courseUuid": payload.courseUuid,
                    "moduleUuid": payload.moduleUuid,
                    "updateMode": payload.updateMode,
                    "changedFields": changed_fields,
                    "newVersion": profile.version if profile is not None else None,
                    "objectKey": profile.objectKey if profile is not None else None,
                },
            )
            return response
        except ValueError as exc:
            self.session.rollback()
            logger.warning(
                "Rejected module profile candidate patch",
                extra={
                    "learnerId": payload.learnerId,
                    "courseUuid": payload.courseUuid,
                    "moduleUuid": payload.moduleUuid,
                    "updateMode": payload.updateMode,
                    "changedFields": changed_fields,
                    "retryable": True,
                    "validationMessage": str(exc),
                },
            )
            return ModuleProfileCandidateUpdateResponse(
                accepted=False,
                retryable=True,
                code="INVALID_CANDIDATE_PATCH",
                message=str(exc),
                changedFields=changed_fields,
                profile=None,
            )
        except Exception as exc:
            self.session.rollback()
            logger.exception(
                "Module profile update failed unexpectedly",
                extra={
                    "learnerId": payload.learnerId,
                    "courseUuid": payload.courseUuid,
                    "moduleUuid": payload.moduleUuid,
                    "updateMode": payload.updateMode,
                    "changedFields": changed_fields,
                },
            )
            return ModuleProfileCandidateUpdateResponse(
                accepted=False,
                retryable=False,
                code="PROFILE_UPDATE_FAILED",
                message=str(exc),
                changedFields=changed_fields,
                profile=None,
            )

    def build_candidate_request(
        self,
        *,
        learner_id: int,
        course_uuid: str,
        module_uuid: str,
        source: str,
        update_mode: str,
        reason: str,
        patch: dict,
    ) -> ModuleProfileCandidateUpdateRequest:
        return ModuleProfileCandidateUpdateRequest.model_validate(
            {
                "learnerId": learner_id,
                "courseUuid": course_uuid,
                "moduleUuid": module_uuid,
                "source": source,
                "updateMode": update_mode,
                "reason": reason,
                "patch": patch,
            }
        )

    def _merge_patch(self, *, base_profile: dict, patch: dict) -> dict:
        candidate = copy.deepcopy(base_profile)
        for field, value in patch.items():
            if field in PATCH_LIST_FIELDS and isinstance(value, list):
                candidate[field] = self._normalize_string_list(value)
            else:
                candidate[field] = value.strip() if isinstance(value, str) else value
        candidate["profile_type"] = "module_profile"
        candidate["profile_status"] = "updated"
        candidate["last_updated_at"] = now_local().isoformat()
        return candidate

    def _validate_candidate(
        self,
        *,
        candidate: dict,
        update_mode: str,
        changed_fields: list[str],
    ) -> None:
        if update_mode == "light_update" and len(changed_fields) > LIGHT_UPDATE_MAX_FIELDS:
            raise ValueError("light_update patch changes too many fields")

        response_preference = candidate.get("response_preference")
        if response_preference is not None and response_preference not in ALLOWED_RESPONSE_PREFERENCES:
            raise ValueError("response_preference is not allowed")

        knowledge_stability = candidate.get("knowledge_stability")
        if knowledge_stability is not None and knowledge_stability not in ALLOWED_KNOWLEDGE_STABILITY:
            raise ValueError("knowledge_stability is not allowed")

        engagement_pattern = candidate.get("engagement_pattern")
        if engagement_pattern is not None and engagement_pattern not in ALLOWED_ENGAGEMENT_PATTERNS:
            raise ValueError("engagement_pattern is not allowed")

        support_need_level = candidate.get("support_need_level")
        if support_need_level is not None and support_need_level not in ALLOWED_SUPPORT_NEED_LEVELS:
            raise ValueError("support_need_level is not allowed")

        confidence_estimate = candidate.get("confidence_estimate")
        if confidence_estimate is None or not (0.0 <= float(confidence_estimate) <= 1.0):
            raise ValueError("confidence_estimate must be between 0 and 1")

        for field in PATCH_LIST_FIELDS:
            value = candidate.get(field)
            if value is None:
                raise ValueError(f"{field} must not be null")
            if not isinstance(value, list):
                raise ValueError(f"{field} must be a list")
            if len(value) > 10:
                raise ValueError(f"{field} exceeds maximum item count")
            for item in value:
                if not isinstance(item, str):
                    raise ValueError(f"{field} items must be strings")
                if len(item.strip()) == 0:
                    raise ValueError(f"{field} items must not be empty")
                if len(item.strip()) > MAX_LIST_ITEM_LENGTH:
                    raise ValueError(f"{field} items exceed maximum length")

    def _normalize_string_list(self, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            item = value.strip()
            if item and item not in normalized:
                normalized.append(item)
        return normalized

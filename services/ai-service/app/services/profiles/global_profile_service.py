from __future__ import annotations

import logging
import re

from app.models.learner_global_profile_asset import LearnerGlobalProfileAsset
from app.repositories.learner_global_profile_assets_repository import LearnerGlobalProfileAssetsRepository
from app.schemas.profiles import GlobalProfileInitRequest, GlobalProfileRead, GlobalProfileUpdateRequest
from app.services.profiles.global_profile_asset_service import GlobalProfileAssetService
from app.services.profiles.global_profile_generation_service import (
    GlobalProfileGenerationService,
    GlobalProfilePreferences,
)
from platform_common.errors import invalid_request_error


logger = logging.getLogger(__name__)

_PREFERENCE_FIELDS = (
    ("supportRole", "Support role:"),
    ("helpStyle", "Help style:"),
    ("learningFocus", "Learning focus:"),
    ("responseTone", "Response tone:"),
)


class GlobalProfileService:
    def __init__(self, session) -> None:
        self.session = session
        self.assets = LearnerGlobalProfileAssetsRepository(session)
        self.asset_storage = GlobalProfileAssetService()
        self.generator = GlobalProfileGenerationService()

    def initialize_for_learner(self, *, learner_id: int, payload: GlobalProfileInitRequest) -> GlobalProfileRead:
        existing = self.assets.get_active_by_learner(learner_id)
        if existing is not None:
            try:
                self.asset_storage.load_profile(object_key=existing.object_key)
            except Exception:
                logger.exception(
                    "Failed to load existing learner global profile during initialization; deleting broken mapping",
                    extra={
                        "learnerId": learner_id,
                        "profileAssetId": existing.profile_asset_id,
                        "objectKey": existing.object_key,
                    },
                )
                self.assets.delete(existing)
                self.session.commit()
                existing = None

        if existing is not None:
            raise invalid_request_error("Global profile already exists for this learner")

        default_template = self.generator.load_default_template()
        self.asset_storage.ensure_default_template_asset(content=default_template)

        preferences = GlobalProfilePreferences(
            support_role=payload.supportRole.strip(),
            help_style=payload.helpStyle.strip(),
            learning_focus=payload.learningFocus.strip(),
            response_tone=payload.responseTone.strip(),
        )
        content = self.generator.generate_profile(preferences=preferences)

        version = self.assets.get_next_version(learner_id)
        object_key = self.asset_storage.get_profile_object_key(learner_id=learner_id, version=version)
        self.asset_storage.save_profile(object_key=object_key, content=content)
        asset = self.assets.create(
            learner_id=learner_id,
            object_key=object_key,
            version=version,
            preferences=self._preferences_to_dict(preferences),
        )
        self.session.commit()
        self.session.refresh(asset)
        return self._to_read(asset=asset, content=content, is_default_profile=False)

    def update_for_learner(
        self,
        *,
        learner_id: int,
        payload: GlobalProfileUpdateRequest,
    ) -> GlobalProfileRead:
        """Regenerate the active profile while retaining the previous version."""
        existing = self.assets.get_active_by_learner(learner_id)
        if existing is None:
            raise invalid_request_error("Global profile does not exist for this learner")

        default_template = self.generator.load_default_template()
        self.asset_storage.ensure_default_template_asset(content=default_template)
        preferences = self._preferences_from_payload(payload)
        content = self.generator.generate_profile(preferences=preferences)

        version = self.assets.get_next_version(learner_id)
        object_key = self.asset_storage.get_profile_object_key(learner_id=learner_id, version=version)
        # Generate and persist the replacement before archiving the current asset. If generation
        # or storage fails, the learner can continue using the existing active profile.
        self.asset_storage.save_profile(object_key=object_key, content=content)
        self.assets.archive_active_for_learner(learner_id)
        asset = self.assets.create(
            learner_id=learner_id,
            object_key=object_key,
            version=version,
            preferences=self._preferences_to_dict(preferences),
        )
        self.session.commit()
        self.session.refresh(asset)
        return self._to_read(asset=asset, content=content, is_default_profile=False)

    def reset_for_learner(self, *, learner_id: int) -> GlobalProfileRead:
        """Deactivate the learner profile and return the default template.

        Archived rows and their stored objects are deliberately retained so a reset is
        reversible for operators and does not destroy profile history.
        """
        default_template = self.generator.load_default_template()
        self.asset_storage.ensure_default_template_asset(content=default_template)
        self.assets.archive_active_for_learner(learner_id)
        self.session.commit()
        return self._build_default_response(learner_id=learner_id, content=default_template)

    def get_for_learner(self, *, learner_id: int) -> GlobalProfileRead:
        default_template = self.generator.load_default_template()
        self.asset_storage.ensure_default_template_asset(content=default_template)
        asset = self.assets.get_active_by_learner(learner_id)
        if asset is None:
            return self._build_default_response(learner_id=learner_id, content=default_template)

        try:
            content = self.asset_storage.load_profile(object_key=asset.object_key)
            return self._to_read(asset=asset, content=content, is_default_profile=False)
        except Exception:
            logger.exception(
                "Failed to load learner global profile asset; deleting broken mapping and falling back to default",
                extra={
                    "learnerId": learner_id,
                    "profileAssetId": asset.profile_asset_id,
                    "objectKey": asset.object_key,
                },
            )
            self.assets.delete(asset)
            self.session.commit()
            return self._build_default_response(learner_id=learner_id, content=default_template)

    def global_profile_exists(self, *, learner_id: int) -> bool:
        return self.assets.get_active_by_learner(learner_id) is not None

    def _build_default_response(self, *, learner_id: int, content: str) -> GlobalProfileRead:
        return GlobalProfileRead(
            learnerId=learner_id,
            version=None,
            objectKey=None,
            content=content,
            preferences={},
            isDefaultProfile=True,
            createdAt=None,
            updatedAt=None,
        )

    def _to_read(
        self,
        *,
        asset: LearnerGlobalProfileAsset,
        content: str,
        is_default_profile: bool,
    ) -> GlobalProfileRead:
        return GlobalProfileRead(
            learnerId=asset.learner_id,
            version=asset.version,
            objectKey=asset.object_key,
            content=content,
            preferences=self._preferences_from_asset(asset=asset, content=content),
            isDefaultProfile=is_default_profile,
            createdAt=asset.created_at,
            updatedAt=asset.updated_at,
        )

    @staticmethod
    def _preferences_from_payload(
        payload: GlobalProfileInitRequest | GlobalProfileUpdateRequest,
    ) -> GlobalProfilePreferences:
        return GlobalProfilePreferences(
            support_role=payload.supportRole.strip(),
            help_style=payload.helpStyle.strip(),
            learning_focus=payload.learningFocus.strip(),
            response_tone=payload.responseTone.strip(),
        )

    @staticmethod
    def _preferences_to_dict(preferences: GlobalProfilePreferences) -> dict[str, str]:
        return {
            "supportRole": preferences.support_role,
            "helpStyle": preferences.help_style,
            "learningFocus": preferences.learning_focus,
            "responseTone": preferences.response_tone,
        }

    @classmethod
    def _preferences_from_asset(cls, *, asset: LearnerGlobalProfileAsset, content: str) -> dict[str, str]:
        stored = getattr(asset, "preferences", None)
        if isinstance(stored, dict):
            normalized = {
                key: str(stored[key]).strip()
                for key, _ in _PREFERENCE_FIELDS
                if stored.get(key) is not None and str(stored[key]).strip()
            }
            if len(normalized) == len(_PREFERENCE_FIELDS):
                return normalized
        return cls._extract_preferences_from_content(content)

    @staticmethod
    def _extract_preferences_from_content(content: str) -> dict[str, str]:
        """Backfill preferences for assets created before structured preferences were stored."""
        preferences: dict[str, str] = {}
        for key, marker in _PREFERENCE_FIELDS:
            match = re.search(
                rf"(?im)^\s*{re.escape(marker)}[ \t]*(?:\r?\n[ \t]*)?([^\r\n]+)",
                content,
            )
            if match:
                value = match.group(1).strip()
                if value:
                    preferences[key] = value
        return preferences

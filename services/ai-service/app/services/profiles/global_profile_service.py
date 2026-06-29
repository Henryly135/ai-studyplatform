from __future__ import annotations

import logging

from app.models.learner_global_profile_asset import LearnerGlobalProfileAsset
from app.repositories.learner_global_profile_assets_repository import LearnerGlobalProfileAssetsRepository
from app.schemas.profiles import GlobalProfileInitRequest, GlobalProfileRead
from app.services.profiles.global_profile_asset_service import GlobalProfileAssetService
from app.services.profiles.global_profile_generation_service import (
    GlobalProfileGenerationService,
    GlobalProfilePreferences,
)
from platform_common.errors import invalid_request_error


logger = logging.getLogger(__name__)


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
        )
        self.session.commit()
        self.session.refresh(asset)
        return self._to_read(asset=asset, content=content, is_default_profile=False)

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
            isDefaultProfile=is_default_profile,
            createdAt=asset.created_at,
            updatedAt=asset.updated_at,
        )

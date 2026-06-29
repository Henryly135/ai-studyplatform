from __future__ import annotations

import logging
from dataclasses import dataclass

from app.core.uuid_codec import decode_course_uuid, decode_module_uuid
from app.repositories.learner_module_profile_assets_repository import LearnerModuleProfileAssetsRepository
from app.schemas.profiles import ModuleProfileRead
from app.services.profiles.module_profile_asset_service import ModuleProfileAssetService
from app.services.profiles.module_profile_service import ModuleProfileService


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LoadedModuleProfileBase:
    course_id: int
    module_id: int
    active_asset: object | None
    base_profile: dict


class ModuleProfilePersistenceService:
    def __init__(self, session) -> None:
        self.session = session
        self.profile_service = ModuleProfileService(session)
        self.assets = LearnerModuleProfileAssetsRepository(session)
        self.asset_storage = ModuleProfileAssetService()

    def load_active_or_default(
        self,
        *,
        learner_id: int,
        course_uuid: str,
        module_uuid: str,
    ) -> LoadedModuleProfileBase:
        course_id = decode_course_uuid(course_uuid)
        module_id = decode_module_uuid(module_uuid)
        active_asset = self.assets.get_active_by_scope(
            learner_id=learner_id,
            course_id=course_id,
            module_id=module_id,
        )
        if active_asset is not None:
            try:
                return LoadedModuleProfileBase(
                    course_id=course_id,
                    module_id=module_id,
                    active_asset=active_asset,
                    base_profile=self.asset_storage.load_profile(object_key=active_asset.object_key),
                )
            except Exception:
                logger.warning(
                    "Failed to load active module profile; falling back to default base",
                    extra={
                        "learnerId": learner_id,
                        "courseId": course_id,
                        "moduleId": module_id,
                        "profileAssetId": active_asset.profile_asset_id,
                        "objectKey": active_asset.object_key,
                    },
                )
                self.assets.delete(active_asset)
                self.session.commit()

        default_template = self.profile_service.load_default_template()
        self.asset_storage.ensure_default_template_asset(content=default_template)
        return LoadedModuleProfileBase(
            course_id=course_id,
            module_id=module_id,
            active_asset=None,
            base_profile=self.profile_service.build_default_module_profile(template=default_template),
        )

    def persist_candidate(
        self,
        *,
        learner_id: int,
        course_id: int,
        module_id: int,
        active_asset,
        candidate: dict,
    ) -> ModuleProfileRead:
        version = self.assets.get_next_version(
            learner_id=learner_id,
            course_id=course_id,
            module_id=module_id,
        )
        object_key = self.asset_storage.get_profile_object_key(
            learner_id=learner_id,
            course_id=course_id,
            module_id=module_id,
            version=version,
        )
        self.asset_storage.save_profile(object_key=object_key, content=candidate)
        if active_asset is not None:
            self.assets.archive_active_by_scope(
                learner_id=learner_id,
                course_id=course_id,
                module_id=module_id,
            )
        asset = self.assets.create(
            learner_id=learner_id,
            course_id=course_id,
            module_id=module_id,
            object_key=object_key,
            version=version,
        )
        self.session.commit()
        self.session.refresh(asset)
        logger.info(
            "Persisted new module profile version",
            extra={
                "learnerId": learner_id,
                "courseId": course_id,
                "moduleId": module_id,
                "newVersion": version,
                "objectKey": object_key,
                "archivedPreviousActive": active_asset is not None,
            },
        )
        return self.profile_service._to_read(asset=asset, content=candidate)

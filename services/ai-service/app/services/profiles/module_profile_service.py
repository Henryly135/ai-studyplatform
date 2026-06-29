from __future__ import annotations

import copy
import json
import logging
from pathlib import Path

from app.core.uuid_codec import decode_course_uuid, decode_module_uuid, encode_course_uuid, encode_module_uuid
from app.models.learner_module_profile_asset import LearnerModuleProfileAsset
from app.repositories.learner_module_profile_assets_repository import LearnerModuleProfileAssetsRepository
from app.schemas.profiles import (
    ModuleProfileInitBatchFailedItem,
    ModuleProfileInitBatchRequest,
    ModuleProfileInitBatchResponse,
    ModuleProfileRead,
)
from app.services.profiles.module_profile_asset_service import ModuleProfileAssetService


logger = logging.getLogger(__name__)


class ModuleProfileService:
    def __init__(self, session) -> None:
        self.session = session
        self.assets = LearnerModuleProfileAssetsRepository(session)
        self.asset_storage = ModuleProfileAssetService()

    def initialize_for_learner(self, *, learner_id: int, course_uuid: str, module_uuid: str) -> ModuleProfileRead:
        course_id = decode_course_uuid(course_uuid)
        module_id = decode_module_uuid(module_uuid)

        existing = self.assets.get_active_by_scope(
            learner_id=learner_id,
            course_id=course_id,
            module_id=module_id,
        )
        if existing is not None:
            try:
                content = self.asset_storage.load_profile(object_key=existing.object_key)
                return self._to_read(asset=existing, content=content)
            except Exception:
                logger.exception(
                    "Failed to load existing learner module profile during initialization; deleting broken mapping",
                    extra={
                        "learnerId": learner_id,
                        "courseId": course_id,
                        "moduleId": module_id,
                        "profileAssetId": existing.profile_asset_id,
                        "objectKey": existing.object_key,
                    },
                )
                self.assets.delete(existing)
                self.session.commit()

        default_template = self.load_default_template()
        self.asset_storage.ensure_default_template_asset(content=default_template)
        content = self.build_default_module_profile(template=default_template)

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
        self.asset_storage.save_profile(object_key=object_key, content=content)
        asset = self.assets.create(
            learner_id=learner_id,
            course_id=course_id,
            module_id=module_id,
            object_key=object_key,
            version=version,
        )
        self.session.commit()
        self.session.refresh(asset)
        return self._to_read(asset=asset, content=content)

    def initialize_batch_for_learner(
        self,
        *,
        payload: ModuleProfileInitBatchRequest,
    ) -> ModuleProfileInitBatchResponse:
        initialized_count = 0
        skipped_count = 0
        failed_items: list[ModuleProfileInitBatchFailedItem] = []
        course_id = decode_course_uuid(payload.courseUuid)

        for module_uuid in payload.moduleUuids:
            try:
                module_id = decode_module_uuid(module_uuid)
                existing = self.assets.get_active_by_scope(
                    learner_id=payload.learnerId,
                    course_id=course_id,
                    module_id=module_id,
                )
                profile = self.initialize_for_learner(
                    learner_id=payload.learnerId,
                    course_uuid=payload.courseUuid,
                    module_uuid=module_uuid,
                )
                if existing is not None and profile.objectKey == existing.object_key:
                    skipped_count += 1
                else:
                    initialized_count += 1
            except Exception as exc:
                self.session.rollback()
                logger.exception(
                    "Failed to initialize learner module profile in batch",
                    extra={
                        "learnerId": payload.learnerId,
                        "courseUuid": payload.courseUuid,
                        "moduleUuid": module_uuid,
                        "triggerSource": payload.triggerSource,
                    },
                )
                failed_items.append(
                    ModuleProfileInitBatchFailedItem(
                        moduleUuid=module_uuid,
                        message=str(exc) or "Failed to initialize module profile",
                    )
                )

        return ModuleProfileInitBatchResponse(
            learnerId=payload.learnerId,
            courseUuid=payload.courseUuid,
            triggerSource=payload.triggerSource,
            requestedCount=len(payload.moduleUuids),
            initializedCount=initialized_count,
            skippedCount=skipped_count,
            failedCount=len(failed_items),
            failedItems=failed_items,
        )

    def get_for_learner(self, *, learner_id: int, course_uuid: str, module_uuid: str) -> ModuleProfileRead:
        course_id = decode_course_uuid(course_uuid)
        module_id = decode_module_uuid(module_uuid)

        default_template = self.load_default_template()
        self.asset_storage.ensure_default_template_asset(content=default_template)
        asset = self.assets.get_active_by_scope(
            learner_id=learner_id,
            course_id=course_id,
            module_id=module_id,
        )
        if asset is None:
            return self._build_default_response(
                learner_id=learner_id,
                course_id=course_id,
                module_id=module_id,
                content=self.build_default_module_profile(template=default_template),
            )

        try:
            content = self.asset_storage.load_profile(object_key=asset.object_key)
            return self._to_read(asset=asset, content=content)
        except Exception:
            logger.exception(
                "Failed to load learner module profile asset; deleting broken mapping and falling back to default",
                extra={
                    "learnerId": learner_id,
                    "courseId": course_id,
                    "moduleId": module_id,
                    "profileAssetId": asset.profile_asset_id,
                    "objectKey": asset.object_key,
                },
            )
            self.assets.delete(asset)
            self.session.commit()
            return self._build_default_response(
                learner_id=learner_id,
                course_id=course_id,
                module_id=module_id,
                content=self.build_default_module_profile(template=default_template),
            )

    def load_default_template(self) -> dict:
        template_path = Path(__file__).resolve().parents[2] / "assets" / "templates" / "default_module_profile_v1.json"
        return json.loads(template_path.read_text(encoding="utf-8"))

    def build_default_module_profile(self, *, template: dict) -> dict:
        return copy.deepcopy(template)

    def _build_default_response(
        self,
        *,
        learner_id: int,
        course_id: int,
        module_id: int,
        content: dict,
    ) -> ModuleProfileRead:
        return ModuleProfileRead(
            learnerId=learner_id,
            courseUuid=encode_course_uuid(course_id),
            moduleUuid=encode_module_uuid(module_id),
            version=None,
            objectKey=None,
            content=content,
            isDefaultProfile=True,
            createdAt=None,
            updatedAt=None,
        )

    def _to_read(self, *, asset: LearnerModuleProfileAsset, content: dict) -> ModuleProfileRead:
        return ModuleProfileRead(
            learnerId=asset.learner_id,
            courseUuid=encode_course_uuid(asset.course_id),
            moduleUuid=encode_module_uuid(asset.module_id),
            version=asset.version,
            objectKey=asset.object_key,
            content=content,
            isDefaultProfile=False,
            createdAt=asset.created_at,
            updatedAt=asset.updated_at,
        )

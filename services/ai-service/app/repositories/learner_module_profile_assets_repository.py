from sqlalchemy import desc, func, select, update
from sqlalchemy.orm import Session

from app.models.learner_global_profile_asset import AIProfileAssetStatus
from app.models.learner_module_profile_asset import LearnerModuleProfileAsset


class LearnerModuleProfileAssetsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_active_by_scope(
        self,
        *,
        learner_id: int,
        course_id: int,
        module_id: int,
    ) -> LearnerModuleProfileAsset | None:
        stmt = (
            select(LearnerModuleProfileAsset)
            .where(
                LearnerModuleProfileAsset.learner_id == learner_id,
                LearnerModuleProfileAsset.course_id == course_id,
                LearnerModuleProfileAsset.module_id == module_id,
                LearnerModuleProfileAsset.status == AIProfileAssetStatus.ACTIVE,
            )
            .order_by(
                desc(LearnerModuleProfileAsset.version),
                desc(LearnerModuleProfileAsset.updated_at),
                desc(LearnerModuleProfileAsset.created_at),
            )
            .limit(1)
        )
        return self.session.scalar(stmt)

    def get_next_version(self, *, learner_id: int, course_id: int, module_id: int) -> int:
        stmt = (
            select(func.max(LearnerModuleProfileAsset.version))
            .where(
                LearnerModuleProfileAsset.learner_id == learner_id,
                LearnerModuleProfileAsset.course_id == course_id,
                LearnerModuleProfileAsset.module_id == module_id,
            )
        )
        max_version = self.session.scalar(stmt)
        return int(max_version or 0) + 1

    def archive_active_by_scope(self, *, learner_id: int, course_id: int, module_id: int) -> None:
        stmt = (
            update(LearnerModuleProfileAsset)
            .where(
                LearnerModuleProfileAsset.learner_id == learner_id,
                LearnerModuleProfileAsset.course_id == course_id,
                LearnerModuleProfileAsset.module_id == module_id,
                LearnerModuleProfileAsset.status == AIProfileAssetStatus.ACTIVE,
            )
            .values(status=AIProfileAssetStatus.ARCHIVED)
        )
        self.session.execute(stmt)
        self.session.flush()

    def create(
        self,
        *,
        learner_id: int,
        course_id: int,
        module_id: int,
        object_key: str,
        version: int,
        status: AIProfileAssetStatus = AIProfileAssetStatus.ACTIVE,
    ) -> LearnerModuleProfileAsset:
        profile_asset = LearnerModuleProfileAsset(
            learner_id=learner_id,
            course_id=course_id,
            module_id=module_id,
            object_key=object_key,
            version=version,
            status=status,
        )
        self.session.add(profile_asset)
        self.session.flush()
        return profile_asset

    def delete(self, profile_asset: LearnerModuleProfileAsset) -> None:
        self.session.delete(profile_asset)
        self.session.flush()

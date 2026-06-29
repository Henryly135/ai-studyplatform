from sqlalchemy import desc, func, select, update
from sqlalchemy.orm import Session

from app.models.learner_global_profile_asset import AIProfileAssetStatus, LearnerGlobalProfileAsset


class LearnerGlobalProfileAssetsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, profile_asset_id: int) -> LearnerGlobalProfileAsset | None:
        return self.session.get(LearnerGlobalProfileAsset, profile_asset_id)

    def get_active_by_learner(self, learner_id: int) -> LearnerGlobalProfileAsset | None:
        stmt = (
            select(LearnerGlobalProfileAsset)
            .where(
                LearnerGlobalProfileAsset.learner_id == learner_id,
                LearnerGlobalProfileAsset.status == AIProfileAssetStatus.ACTIVE,
            )
            .order_by(
                desc(LearnerGlobalProfileAsset.version),
                desc(LearnerGlobalProfileAsset.updated_at),
                desc(LearnerGlobalProfileAsset.created_at),
            )
            .limit(1)
        )
        return self.session.scalar(stmt)

    def list_by_learner(self, learner_id: int) -> list[LearnerGlobalProfileAsset]:
        stmt = (
            select(LearnerGlobalProfileAsset)
            .where(LearnerGlobalProfileAsset.learner_id == learner_id)
            .order_by(
                desc(LearnerGlobalProfileAsset.version),
                desc(LearnerGlobalProfileAsset.updated_at),
                desc(LearnerGlobalProfileAsset.created_at),
            )
        )
        return list(self.session.scalars(stmt))

    def get_next_version(self, learner_id: int) -> int:
        stmt = select(func.max(LearnerGlobalProfileAsset.version)).where(
            LearnerGlobalProfileAsset.learner_id == learner_id
        )
        max_version = self.session.scalar(stmt)
        return int(max_version or 0) + 1

    def archive_active_for_learner(self, learner_id: int) -> None:
        stmt = (
            update(LearnerGlobalProfileAsset)
            .where(
                LearnerGlobalProfileAsset.learner_id == learner_id,
                LearnerGlobalProfileAsset.status == AIProfileAssetStatus.ACTIVE,
            )
            .values(status=AIProfileAssetStatus.ARCHIVED)
        )
        self.session.execute(stmt)
        self.session.flush()

    def create(
        self,
        *,
        learner_id: int,
        object_key: str,
        version: int,
        status: AIProfileAssetStatus = AIProfileAssetStatus.ACTIVE,
    ) -> LearnerGlobalProfileAsset:
        profile_asset = LearnerGlobalProfileAsset(
            learner_id=learner_id,
            object_key=object_key,
            version=version,
            status=status,
        )
        self.session.add(profile_asset)
        self.session.flush()
        return profile_asset

    def delete(self, profile_asset: LearnerGlobalProfileAsset) -> None:
        self.session.delete(profile_asset)
        self.session.flush()

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.module_progress import ModuleProgress, ProgressStatus

_UNSET = object()


class ModuleProgressRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, module_progress_id: int) -> ModuleProgress | None:
        """Used by progress-detail services to load a module progress record by primary key."""
        return self.session.get(ModuleProgress, module_progress_id)

    def get_by_module_and_learner(
        self,
        module_id: int,
        learner_id: int,
    ) -> ModuleProgress | None:
        """Used by progress-tracking services to resolve a learner's progress for a module."""
        stmt = select(ModuleProgress).where(
            ModuleProgress.module_id == module_id,
            ModuleProgress.learner_id == learner_id,
        )
        return self.session.scalar(stmt)

    def list_by_module(self, module_id: int) -> list[ModuleProgress]:
        """Used by educator analytics services to list learner progress records for a module."""
        stmt = (
            select(ModuleProgress)
            .where(ModuleProgress.module_id == module_id)
            .order_by(ModuleProgress.updated_at.desc(), ModuleProgress.module_progress_id.desc())
        )
        return list(self.session.scalars(stmt))

    def list_by_learner(self, learner_id: int) -> list[ModuleProgress]:
        """Used by learner progress services to list all module progress records for a learner."""
        stmt = (
            select(ModuleProgress)
            .where(ModuleProgress.learner_id == learner_id)
            .order_by(ModuleProgress.updated_at.desc(), ModuleProgress.module_progress_id.desc())
        )
        return list(self.session.scalars(stmt))

    def list_completed_by_learner(self, learner_id: int) -> list[ModuleProgress]:
        """Used by achievement and progress-summary services to list completed modules for a learner."""
        stmt = (
            select(ModuleProgress)
            .where(
                ModuleProgress.learner_id == learner_id,
                ModuleProgress.progress_status == ProgressStatus.COMPLETED,
            )
            .order_by(ModuleProgress.completed_at.desc(), ModuleProgress.module_progress_id.desc())
        )
        return list(self.session.scalars(stmt))

    def create(
        self,
        *,
        module_id: int,
        learner_id: int,
        progress_status: ProgressStatus = ProgressStatus.NOT_STARTED,
        progress_percent: Decimal = Decimal("0.00"),
        time_spent_seconds: int = 0,
        started_at: datetime | None = None,
        last_accessed_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> ModuleProgress:
        """Used by progress-tracking services to create a learner's module progress record."""
        progress = ModuleProgress(
            module_id=module_id,
            learner_id=learner_id,
            progress_status=progress_status,
            progress_percent=progress_percent,
            time_spent_seconds=time_spent_seconds,
            started_at=started_at,
            last_accessed_at=last_accessed_at,
            completed_at=completed_at,
        )
        self.session.add(progress)
        self.session.flush()
        return progress

    def update_progress(
        self,
        progress: ModuleProgress,
        *,
        progress_status: ProgressStatus,
        progress_percent: Decimal,
        time_spent_seconds: int,
        started_at: datetime | None | object = _UNSET,
        last_accessed_at: datetime | None | object = _UNSET,
        completed_at: datetime | None | object = _UNSET,
    ) -> ModuleProgress:
        """Used by progress-sync services to update module completion and time-tracking fields."""
        progress.progress_status = progress_status
        progress.progress_percent = progress_percent
        progress.time_spent_seconds = time_spent_seconds
        if started_at is not _UNSET:
            progress.started_at = started_at
        if last_accessed_at is not _UNSET:
            progress.last_accessed_at = last_accessed_at
        if completed_at is not _UNSET:
            progress.completed_at = completed_at
        self.session.flush()
        return progress

    def touch_last_accessed(
        self,
        progress: ModuleProgress,
        accessed_at: datetime,
    ) -> ModuleProgress:
        """Used by learner activity services to store the latest module access timestamp."""
        progress.last_accessed_at = accessed_at
        self.session.flush()
        return progress

    def delete(self, progress: ModuleProgress) -> None:
        """Used by progress-management services to remove a module progress record."""
        self.session.delete(progress)
        self.session.flush()

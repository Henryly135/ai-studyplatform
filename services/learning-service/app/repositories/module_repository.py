from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.modules import Module, ModuleStatus

_UNSET = object()


class ModuleRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, module_id: int) -> Module | None:
        """Used by module-detail services to load a module by primary key."""
        return self.session.get(Module, module_id)

    def list_by_learning_path(self, learning_path_id: int) -> list[Module]:
        """Used by educator and course-detail services to list all modules in a learning path."""
        stmt = (
            select(Module)
            .where(Module.learning_path_id == learning_path_id)
            .order_by(Module.sort_order.asc(), Module.module_id.asc())
        )
        return list(self.session.scalars(stmt))

    def list_by_ids(self, module_ids: list[int]) -> list[Module]:
        if not module_ids:
            return []
        stmt = select(Module).where(Module.module_id.in_(module_ids))
        return list(self.session.scalars(stmt))

    def list_published_by_learning_path(self, learning_path_id: int) -> list[Module]:
        """Used by learner-facing services to list published modules in a learning path."""
        stmt = (
            select(Module)
            .where(
                Module.learning_path_id == learning_path_id,
                Module.status == ModuleStatus.PUBLISHED,
            )
            .order_by(Module.sort_order.asc(), Module.module_id.asc())
        )
        return list(self.session.scalars(stmt))

    def get_by_learning_path_and_sort_order(
        self,
        learning_path_id: int,
        sort_order: int,
    ) -> Module | None:
        """Used by module-ordering services to load a module by path and display position."""
        stmt = select(Module).where(
            Module.learning_path_id == learning_path_id,
            Module.sort_order == sort_order,
        )
        return self.session.scalar(stmt)

    def get_max_sort_order(self, learning_path_id: int) -> int:
        modules = self.list_by_learning_path(learning_path_id)
        if not modules:
            return 0
        return max(module.sort_order for module in modules)

    def create(
        self,
        *,
        learning_path_id: int,
        title: str,
        description: str | None = None,
        content: str | None = None,
        sort_order: int,
        estimated_minutes: int | None = None,
        status: ModuleStatus = ModuleStatus.DRAFT,
        visible_to_class_id: str | None = None,
    ) -> Module:
        """Used by curriculum authoring services to create a module record."""
        module = Module(
            learning_path_id=learning_path_id,
            title=title,
            description=description,
            content=content,
            sort_order=sort_order,
            estimated_minutes=estimated_minutes,
            status=status,
            visible_to_class_id=visible_to_class_id,
        )
        self.session.add(module)
        self.session.flush()
        return module

    def update(
        self,
        module: Module,
        *,
        title: str | object = _UNSET,
        description: str | None | object = _UNSET,
        content: str | None | object = _UNSET,
        sort_order: int | object = _UNSET,
        estimated_minutes: int | None | object = _UNSET,
        status: ModuleStatus | object = _UNSET,
        visible_to_class_id: str | None | object = _UNSET,
    ) -> Module:
        """Used by module-management services to apply partial updates to a module."""
        if title is not _UNSET:
            module.title = title
        if description is not _UNSET:
            module.description = description
        if content is not _UNSET:
            module.content = content
        if sort_order is not _UNSET:
            module.sort_order = sort_order
        if estimated_minutes is not _UNSET:
            module.estimated_minutes = estimated_minutes
        if status is not _UNSET:
            module.status = status
        if visible_to_class_id is not _UNSET:
            module.visible_to_class_id = visible_to_class_id
        self.session.flush()
        return module

    def delete(self, module: Module) -> None:
        """Used by curriculum management services to remove a module record."""
        self.session.delete(module)
        self.session.flush()

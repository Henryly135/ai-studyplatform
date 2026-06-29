from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.module_prerequisites import ModulePrerequisite


class ModulePrerequisiteRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_module_id(self, module_id: int) -> ModulePrerequisite | None:
        stmt = select(ModulePrerequisite).where(ModulePrerequisite.module_id == module_id)
        return self.session.scalar(stmt)

    def create(self, *, module_id: int, prerequisite_module_id: int) -> ModulePrerequisite:
        rule = ModulePrerequisite(
            module_id=module_id,
            prerequisite_module_id=prerequisite_module_id,
        )
        self.session.add(rule)
        self.session.flush()
        return rule

    def update(
        self,
        rule: ModulePrerequisite,
        *,
        prerequisite_module_id: int,
    ) -> ModulePrerequisite:
        rule.prerequisite_module_id = prerequisite_module_id
        self.session.flush()
        return rule

    def upsert(self, *, module_id: int, prerequisite_module_id: int) -> ModulePrerequisite:
        existing = self.get_by_module_id(module_id)
        if existing is None:
            return self.create(module_id=module_id, prerequisite_module_id=prerequisite_module_id)
        return self.update(existing, prerequisite_module_id=prerequisite_module_id)

    def delete(self, rule: ModulePrerequisite) -> None:
        self.session.delete(rule)
        self.session.flush()

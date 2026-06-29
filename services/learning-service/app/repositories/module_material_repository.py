from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.module_materials import MaterialType, ModuleMaterial

_UNSET = object()


class ModuleMaterialRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, material_id: int) -> ModuleMaterial | None:
        """Used by content-delivery services to load a module material by primary key."""
        return self.session.get(ModuleMaterial, material_id)

    def list_by_module(self, module_id: int) -> list[ModuleMaterial]:
        """Used by module-detail services to list all materials belonging to a module."""
        stmt = (
            select(ModuleMaterial)
            .where(ModuleMaterial.module_id == module_id)
            .order_by(ModuleMaterial.sort_order.asc(), ModuleMaterial.material_id.asc())
        )
        return list(self.session.scalars(stmt))

    def get_by_module_and_sort_order(
        self,
        module_id: int,
        sort_order: int,
    ) -> ModuleMaterial | None:
        """Used by material-ordering services to load a material by module and sort order."""
        stmt = select(ModuleMaterial).where(
            ModuleMaterial.module_id == module_id,
            ModuleMaterial.sort_order == sort_order,
        )
        return self.session.scalar(stmt)

    def get_max_sort_order(self, module_id: int) -> int:
        materials = self.list_by_module(module_id)
        if not materials:
            return 0
        return max(material.sort_order for material in materials)

    def list_by_type(self, module_id: int, material_type: MaterialType) -> list[ModuleMaterial]:
        """Used by content-delivery services to filter a module's materials by type."""
        stmt = (
            select(ModuleMaterial)
            .where(
                ModuleMaterial.module_id == module_id,
                ModuleMaterial.material_type == material_type,
            )
            .order_by(ModuleMaterial.sort_order.asc(), ModuleMaterial.material_id.asc())
        )
        return list(self.session.scalars(stmt))

    def create(
        self,
        *,
        module_id: int,
        title: str,
        material_type: MaterialType,
        resource_url: str,
        sort_order: int,
        metadata_json: dict[str, Any] | None = None,
    ) -> ModuleMaterial:
        """Used by authoring services to create a learning material for a module."""
        material = ModuleMaterial(
            module_id=module_id,
            title=title,
            material_type=material_type,
            resource_url=resource_url,
            sort_order=sort_order,
            metadata_json=metadata_json,
        )
        self.session.add(material)
        self.session.flush()
        return material

    def update(
        self,
        material: ModuleMaterial,
        *,
        title: str | object = _UNSET,
        material_type: MaterialType | object = _UNSET,
        resource_url: str | object = _UNSET,
        sort_order: int | object = _UNSET,
        metadata_json: dict[str, Any] | None | object = _UNSET,
    ) -> ModuleMaterial:
        """Used by material-management services to apply partial updates to a module material."""
        if title is not _UNSET:
            material.title = title
        if material_type is not _UNSET:
            material.material_type = material_type
        if resource_url is not _UNSET:
            material.resource_url = resource_url
        if sort_order is not _UNSET:
            material.sort_order = sort_order
        if metadata_json is not _UNSET:
            material.metadata_json = metadata_json
        self.session.flush()
        return material

    def delete(self, material: ModuleMaterial) -> None:
        """Used by content-management services to remove a module material record."""
        self.session.delete(material)
        self.session.flush()

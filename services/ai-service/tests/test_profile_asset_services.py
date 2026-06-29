from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.profiles.global_profile_asset_service import GlobalProfileAssetService
from app.services.profiles.module_profile_asset_service import ModuleProfileAssetService


def test_global_profile_asset_service_saves_and_loads_local_markdown(monkeypatch, tmp_path) -> None:
    # Tests local storage for learner global profile markdown assets.
    monkeypatch.setattr(
        "app.services.profiles.global_profile_asset_service.settings",
        SimpleNamespace(object_storage_provider="local", ai_profile_root_path=str(tmp_path)),
    )
    service = GlobalProfileAssetService()
    object_key = service.get_profile_object_key(learner_id=7, version=2)

    stored = service.save_profile(object_key=object_key, content="# Profile")

    assert stored.object_key == "global/7/skill_v2.md"
    assert service.load_profile(object_key=object_key) == "# Profile"


def test_global_profile_asset_service_ensures_default_template_once(monkeypatch, tmp_path) -> None:
    # Tests that the local default template is created once and not overwritten.
    monkeypatch.setattr(
        "app.services.profiles.global_profile_asset_service.settings",
        SimpleNamespace(object_storage_provider="local", ai_profile_root_path=str(tmp_path)),
    )
    service = GlobalProfileAssetService()

    object_key = service.ensure_default_template_asset(content="first")
    service.ensure_default_template_asset(content="second")

    assert object_key == service.DEFAULT_TEMPLATE_OBJECT_KEY
    assert (tmp_path / object_key).read_text(encoding="utf-8") == "first"


def test_module_profile_asset_service_saves_and_loads_local_json(monkeypatch, tmp_path) -> None:
    # Tests local storage for learner module profile JSON assets.
    monkeypatch.setattr(
        "app.services.profiles.module_profile_asset_service.settings",
        SimpleNamespace(object_storage_provider="local", ai_profile_root_path=str(tmp_path)),
    )
    service = ModuleProfileAssetService()
    object_key = service.get_profile_object_key(learner_id=7, course_id=11, module_id=22, version=3)

    stored = service.save_profile(object_key=object_key, content={"confidence_estimate": 0.5})

    assert stored.object_key == "module/7/11/22/profile_v3.json"
    assert service.load_profile(object_key=object_key) == {"confidence_estimate": 0.5}


def test_module_profile_asset_service_serializes_ascii_json(monkeypatch, tmp_path) -> None:
    # Tests deterministic indented JSON serialization for local module profiles.
    monkeypatch.setattr(
        "app.services.profiles.module_profile_asset_service.settings",
        SimpleNamespace(object_storage_provider="local", ai_profile_root_path=str(tmp_path)),
    )
    service = ModuleProfileAssetService()

    serialized = service._serialize({"topic": "指针"})

    assert "\\u6307\\u9488" in serialized
    assert "\n  " in serialized


@pytest.mark.parametrize(
    ("module_path", "service_class"),
    [
        ("app.services.profiles.global_profile_asset_service.settings", GlobalProfileAssetService),
        ("app.services.profiles.module_profile_asset_service.settings", ModuleProfileAssetService),
    ],
)
def test_profile_asset_services_reject_unknown_provider(monkeypatch, tmp_path, module_path, service_class) -> None:
    # Tests provider validation for both profile asset services.
    monkeypatch.setattr(
        module_path,
        SimpleNamespace(object_storage_provider="s3", ai_profile_root_path=str(tmp_path)),
    )

    with pytest.raises(ValueError):
        service_class()

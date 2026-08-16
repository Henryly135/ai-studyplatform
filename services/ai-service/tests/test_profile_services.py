from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.schemas.profiles import GlobalProfileInitRequest, GlobalProfileUpdateRequest, ModuleProfileInitBatchRequest
from app.services.profiles.global_profile_service import GlobalProfileService
from app.services.profiles.module_profile_service import ModuleProfileService


class FakeSession:
    def __init__(self) -> None:
        self.commit_calls = 0
        self.rollback_calls = 0
        self.refreshed = []

    def commit(self) -> None:
        self.commit_calls += 1

    def rollback(self) -> None:
        self.rollback_calls += 1

    def refresh(self, obj) -> None:
        self.refreshed.append(obj)


def test_global_profile_initialize_creates_new_profile(monkeypatch) -> None:
    # Tests global profile initialization creates asset storage and repository mapping.
    session = FakeSession()
    service = GlobalProfileService(session)
    asset = SimpleNamespace(
        learner_id=7,
        version=1,
        object_key="global/7/skill_v1.md",
        preferences={"supportRole": "coach", "helpStyle": "steps", "learningFocus": "concepts", "responseTone": "calm"},
        created_at=None,
        updated_at=None,
    )
    service.assets = SimpleNamespace(
        get_active_by_learner=lambda learner_id: None,
        get_next_version=lambda learner_id: 1,
        create=lambda **kwargs: asset,
    )
    service.asset_storage = SimpleNamespace(
        ensure_default_template_asset=lambda content: "template-key",
        get_profile_object_key=lambda learner_id, version: "global/7/skill_v1.md",
        save_profile=lambda object_key, content: None,
    )
    service.generator = SimpleNamespace(
        load_default_template=lambda: "# Default",
        generate_profile=lambda preferences: "# Generated",
    )

    result = service.initialize_for_learner(
        learner_id=7,
        payload=GlobalProfileInitRequest(
            supportRole="coach",
            helpStyle="steps",
            learningFocus="concepts",
            responseTone="calm",
        ),
    )

    assert result.content == "# Generated"
    assert result.isDefaultProfile is False
    assert session.commit_calls == 1
    assert session.refreshed == [asset]


def test_global_profile_update_archives_existing_and_creates_next_version() -> None:
    session = FakeSession()
    service = GlobalProfileService(session)
    existing = SimpleNamespace(learner_id=7, version=1, object_key="global/7/skill_v1.md")
    replacement = SimpleNamespace(
        learner_id=7,
        version=2,
        object_key="global/7/skill_v2.md",
        preferences={"supportRole": "mentor", "helpStyle": "concise", "learningFocus": "projects", "responseTone": "direct"},
        created_at=None,
        updated_at=None,
    )
    archived = []
    service.assets = SimpleNamespace(
        get_active_by_learner=lambda learner_id: existing,
        get_next_version=lambda learner_id: 2,
        archive_active_for_learner=lambda learner_id: archived.append(learner_id),
        create=lambda **kwargs: replacement,
    )
    saved = []
    service.asset_storage = SimpleNamespace(
        ensure_default_template_asset=lambda content: None,
        get_profile_object_key=lambda learner_id, version: "global/7/skill_v2.md",
        save_profile=lambda **kwargs: saved.append(kwargs),
    )
    service.generator = SimpleNamespace(
        load_default_template=lambda: "# Default",
        generate_profile=lambda preferences: "# Generated v2",
    )

    result = service.update_for_learner(
        learner_id=7,
        payload=GlobalProfileUpdateRequest(
            supportRole="mentor",
            helpStyle="concise",
            learningFocus="projects",
            responseTone="direct",
        ),
    )

    assert result.version == 2
    assert result.preferences["supportRole"] == "mentor"
    assert archived == [7]
    assert saved == [{"object_key": "global/7/skill_v2.md", "content": "# Generated v2"}]
    assert session.commit_calls == 1
    assert session.refreshed == [replacement]


def test_global_profile_reset_archives_active_and_returns_default() -> None:
    session = FakeSession()
    service = GlobalProfileService(session)
    archived = []
    service.assets = SimpleNamespace(archive_active_for_learner=lambda learner_id: archived.append(learner_id))
    service.generator = SimpleNamespace(load_default_template=lambda: "# Default")
    service.asset_storage = SimpleNamespace(ensure_default_template_asset=lambda content: None)

    result = service.reset_for_learner(learner_id=7)

    assert result.isDefaultProfile is True
    assert result.preferences == {}
    assert archived == [7]
    assert session.commit_calls == 1


def test_global_profile_initialize_rejects_existing_valid_profile() -> None:
    # Tests global profile initialization rejects learners with an existing readable profile.
    service = GlobalProfileService(FakeSession())
    service.assets = SimpleNamespace(get_active_by_learner=lambda learner_id: SimpleNamespace(object_key="key"))
    service.asset_storage = SimpleNamespace(load_profile=lambda object_key: "# Existing")

    with pytest.raises(Exception) as exc_info:
        service.initialize_for_learner(
            learner_id=7,
            payload=GlobalProfileInitRequest(
                supportRole="coach",
                helpStyle="steps",
                learningFocus="concepts",
                responseTone="calm",
            ),
        )

    assert "Global profile already exists" in str(exc_info.value)


def test_global_profile_get_returns_default_or_existing_and_deletes_broken_asset() -> None:
    # Tests global profile reads default, existing, and broken-asset fallback paths.
    session = FakeSession()
    service = GlobalProfileService(session)
    service.generator = SimpleNamespace(load_default_template=lambda: "# Default")
    service.asset_storage = SimpleNamespace(
        ensure_default_template_asset=lambda content: None,
        load_profile=lambda object_key: "# Existing",
    )
    service.assets = SimpleNamespace(get_active_by_learner=lambda learner_id: None)
    assert service.get_for_learner(learner_id=7).isDefaultProfile is True

    asset = SimpleNamespace(profile_asset_id=1, learner_id=7, version=2, object_key="key", preferences={}, created_at=None, updated_at=None)
    service.assets = SimpleNamespace(get_active_by_learner=lambda learner_id: asset)
    assert service.get_for_learner(learner_id=7).content == "# Existing"

    deleted = []
    service.asset_storage = SimpleNamespace(ensure_default_template_asset=lambda content: None, load_profile=lambda object_key: (_ for _ in ()).throw(RuntimeError("bad")))
    service.assets = SimpleNamespace(get_active_by_learner=lambda learner_id: asset, delete=lambda profile_asset: deleted.append(profile_asset))
    assert service.get_for_learner(learner_id=7).isDefaultProfile is True
    assert deleted == [asset]


def test_module_profile_initialize_creates_or_returns_existing_profile(monkeypatch) -> None:
    # Tests module profile initialization returns existing readable profile or creates a new one.
    monkeypatch.setattr("app.services.profiles.module_profile_service.decode_course_uuid", lambda value: 11)
    monkeypatch.setattr("app.services.profiles.module_profile_service.decode_module_uuid", lambda value: 22)
    monkeypatch.setattr("app.services.profiles.module_profile_service.encode_course_uuid", lambda value: f"course-{value}")
    monkeypatch.setattr("app.services.profiles.module_profile_service.encode_module_uuid", lambda value: f"module-{value}")
    session = FakeSession()
    service = ModuleProfileService(session)
    existing = SimpleNamespace(
        learner_id=7,
        course_id=11,
        module_id=22,
        version=1,
        object_key="existing",
        created_at=None,
        updated_at=None,
    )
    service.assets = SimpleNamespace(get_active_by_scope=lambda **_: existing)
    service.asset_storage = SimpleNamespace(load_profile=lambda object_key: {"existing": True})
    assert service.initialize_for_learner(learner_id=7, course_uuid="c", module_uuid="m").content == {"existing": True}

    created = SimpleNamespace(
        learner_id=7,
        course_id=11,
        module_id=22,
        version=2,
        object_key="created",
        created_at=None,
        updated_at=None,
    )
    service.assets = SimpleNamespace(
        get_active_by_scope=lambda **_: None,
        get_next_version=lambda **_: 2,
        create=lambda **_: created,
    )
    service.asset_storage = SimpleNamespace(
        ensure_default_template_asset=lambda content: None,
        get_profile_object_key=lambda **_: "created",
        save_profile=lambda **_: None,
    )
    monkeypatch.setattr(service, "load_default_template", lambda: {"template": True})

    result = service.initialize_for_learner(learner_id=7, course_uuid="c", module_uuid="m")

    assert result.objectKey == "created"
    assert result.isDefaultProfile is False
    assert session.commit_calls == 1


def test_module_profile_get_returns_default_existing_or_broken_fallback(monkeypatch) -> None:
    # Tests module profile get handles default, existing, and broken asset fallback paths.
    monkeypatch.setattr("app.services.profiles.module_profile_service.decode_course_uuid", lambda value: 11)
    monkeypatch.setattr("app.services.profiles.module_profile_service.decode_module_uuid", lambda value: 22)
    monkeypatch.setattr("app.services.profiles.module_profile_service.encode_course_uuid", lambda value: f"course-{value}")
    monkeypatch.setattr("app.services.profiles.module_profile_service.encode_module_uuid", lambda value: f"module-{value}")
    session = FakeSession()
    service = ModuleProfileService(session)
    monkeypatch.setattr(service, "load_default_template", lambda: {"template": True})
    service.asset_storage = SimpleNamespace(ensure_default_template_asset=lambda content: None, load_profile=lambda object_key: {"existing": True})
    service.assets = SimpleNamespace(get_active_by_scope=lambda **_: None)
    assert service.get_for_learner(learner_id=7, course_uuid="c", module_uuid="m").isDefaultProfile is True

    asset = SimpleNamespace(profile_asset_id=1, learner_id=7, course_id=11, module_id=22, version=1, object_key="key", created_at=None, updated_at=None)
    service.assets = SimpleNamespace(get_active_by_scope=lambda **_: asset)
    assert service.get_for_learner(learner_id=7, course_uuid="c", module_uuid="m").content == {"existing": True}

    deleted = []
    service.asset_storage = SimpleNamespace(ensure_default_template_asset=lambda content: None, load_profile=lambda object_key: (_ for _ in ()).throw(RuntimeError("bad")))
    service.assets = SimpleNamespace(get_active_by_scope=lambda **_: asset, delete=lambda profile_asset: deleted.append(profile_asset))
    assert service.get_for_learner(learner_id=7, course_uuid="c", module_uuid="m").isDefaultProfile is True
    assert deleted == [asset]


def test_module_profile_initialize_batch_counts_initialized_skipped_and_failed(monkeypatch) -> None:
    # Tests module profile batch initialization counts initialized, skipped, and failed modules.
    monkeypatch.setattr("app.services.profiles.module_profile_service.decode_course_uuid", lambda value: 11)
    monkeypatch.setattr("app.services.profiles.module_profile_service.decode_module_uuid", lambda value: {"skip": 1, "new": 2, "bad": 3}[value])
    service = ModuleProfileService(FakeSession())
    existing = SimpleNamespace(object_key="existing")
    service.assets = SimpleNamespace(
        get_active_by_scope=lambda learner_id, course_id, module_id: existing if module_id == 1 else None
    )

    def _initialize(**kwargs):
        if kwargs["module_uuid"] == "bad":
            raise RuntimeError("bad module")
        object_key = "existing" if kwargs["module_uuid"] == "skip" else "created"
        return SimpleNamespace(objectKey=object_key)

    service.initialize_for_learner = _initialize

    result = service.initialize_batch_for_learner(
        payload=ModuleProfileInitBatchRequest(
            learnerId=7,
            courseUuid="course",
            moduleUuids=["skip", "new", "bad"],
            triggerSource="enrollment",
        )
    )

    assert result.skippedCount == 1
    assert result.initializedCount == 1
    assert result.failedCount == 1

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from app.models.ai_chat_messages import AIMessageRole
from app.models.ai_index_jobs import AIJobStatus
from app.models.ai_knowledge_sources import AIKnowledgeSourceType, AIPublishStatus, AIVisibilityScope
from app.models.learner_global_profile_asset import AIProfileAssetStatus
from app.repositories.ai_chat_messages_repository import AIChatMessagesRepository
from app.repositories.ai_chat_sessions_repository import AIChatSessionsRepository
from app.repositories.ai_index_jobs_repository import AIIndexJobsRepository
from app.repositories.ai_knowledge_sources_repository import AIKnowledgeSourcesRepository
from app.repositories.learner_global_profile_assets_repository import LearnerGlobalProfileAssetsRepository
from app.repositories.learner_module_profile_assets_repository import LearnerModuleProfileAssetsRepository


class FakeResult:
    def __init__(self, rowcount: int = 3) -> None:
        self.rowcount = rowcount

    def all(self):
        return []


class FakeSession:
    def __init__(self, scalar_value=None, scalars_value=None, rowcount: int = 3) -> None:
        self.scalar_value = scalar_value
        self.scalars_value = scalars_value or []
        self.added = []
        self.deleted = []
        self.executed = []
        self.flush_calls = 0
        self.rowcount = rowcount

    def get(self, model, obj_id):
        return SimpleNamespace(model=model, obj_id=obj_id)

    def scalar(self, stmt):
        return self.scalar_value

    def scalars(self, stmt):
        return self.scalars_value

    def execute(self, stmt):
        self.executed.append(stmt)
        return FakeResult(self.rowcount)

    def add(self, obj) -> None:
        self.added.append(obj)

    def delete(self, obj) -> None:
        self.deleted.append(obj)

    def flush(self) -> None:
        self.flush_calls += 1


def test_chat_message_repository_create_and_list_visible() -> None:
    # Tests chat message repository creates messages and builds visible history query.
    session = FakeSession(scalars_value=[SimpleNamespace(message_id=1)])
    repo = AIChatMessagesRepository(session)

    created = repo.create(session_id=1, role=AIMessageRole.USER, content_text="hello")
    visible = repo.list_visible_by_session(1)

    assert created in session.added
    assert visible[0].message_id == 1
    assert session.flush_calls == 1


def test_chat_session_repository_create_update_record_and_list() -> None:
    # Tests chat session repository create/list/update activity methods.
    now = datetime(2026, 4, 29, tzinfo=timezone.utc)
    session = FakeSession(scalars_value=[SimpleNamespace(session_id=1)])
    repo = AIChatSessionsRepository(session)

    created = repo.create(user_id=7, course_id=1, module_id=2, session_type="demo", title="Title")
    created.message_count = 0
    repo.record_user_message(created, timestamp=now)
    repo.update_activity(
        created,
        last_message_at=now,
        last_user_message_at=now,
        last_assistant_message_at=now,
        message_increment=1,
        summary_text="summary",
    )

    assert repo.get_by_id(1).obj_id == 1
    assert repo.list_by_user(7)[0].session_id == 1
    assert repo.list_by_user_and_module(user_id=7, module_id=2)[0].session_id == 1
    assert (created.course_id, created.module_id) == (1, 2)
    assert created.message_count == 2
    assert created.summary_text == "summary"


def test_index_jobs_repository_create_update_list_delete_and_supersede() -> None:
    # Tests index job repository query builders and state mutation helpers.
    now = datetime(2026, 4, 29, tzinfo=timezone.utc)
    session = FakeSession(scalars_value=[SimpleNamespace(job_id=1)])
    repo = AIIndexJobsRepository(session)
    repo.lock_material_job_scope(material_id=4)

    job = repo.create_material_job(
        source_ref_id="1",
        course_id=2,
        module_id=3,
        material_id=4,
        source_version="v1",
        content_hash=None,
        metadata_json={},
        status=AIJobStatus.QUEUED,
        priority=100,
        trigger_event_id="event",
    )
    repo.update_status(job, status=AIJobStatus.RUNNING, worker_id="worker", attempt_count=2)
    repo.mark_superseded([job])

    assert repo.get_by_id(1).obj_id == 1
    assert repo.list_replaceable_material_jobs(material_id=4)[0].job_id == 1
    assert repo.list_backfill_candidate_material_jobs()[0].job_id == 1
    assert repo.list_blocked_jobs_for_modules(course_id=2, module_ids=[] ) == []
    assert repo.list_blocked_jobs_for_modules(course_id=2, module_ids=[3])[0].job_id == 1
    assert repo.list_running_material_jobs(material_id=4)[0].job_id == 1
    assert repo.list_stale_running_jobs(locked_before=now)[0].job_id == 1
    assert repo.delete_by_material_id(material_id=4) == 3
    assert job.status == AIJobStatus.SUPERSEDED

    claim_session = FakeSession(rowcount=1, scalar_value=9)
    claim_repo = AIIndexJobsRepository(claim_session)
    assert claim_repo.claim_queued_job(
        job_id=9,
        worker_id="worker",
        claimed_at=now,
    ) is True
    assert claim_repo.has_newer_material_job(material_id=4, job_id=8) is True


def test_knowledge_sources_repository_create_update_list_and_delete() -> None:
    # Tests knowledge source repository query builders and source mutation helpers.
    session = FakeSession(scalars_value=[SimpleNamespace(source_id=1)], scalar_value=SimpleNamespace(source_id=2))
    repo = AIKnowledgeSourcesRepository(session)

    source = repo.create(
        source_type=AIKnowledgeSourceType.MATERIAL,
        source_ref_id="1",
        course_id=2,
        module_id=3,
        material_id=4,
        title="Lesson",
        content_text="content",
        content_markdown=None,
        language_code=None,
        visibility_scope=AIVisibilityScope.COURSE_ONLY,
        publish_status=AIPublishStatus.DRAFT,
        content_hash="hash",
        embedding_model="embedding",
        embedding_version="v1",
        source_version="object",
        metadata_json={},
        created_by=None,
        updated_by=None,
        origin_event_id=None,
    )
    repo.update(
        source,
        title="Updated",
        content_text="new",
        content_markdown="# new",
        language_code="en",
        visibility_scope=AIVisibilityScope.COURSE_ONLY,
        publish_status=AIPublishStatus.PUBLISHED,
        content_hash="hash2",
        embedding_model="embedding",
        embedding_version="v2",
        source_version="object2",
        metadata_json={"x": 1},
        updated_by=7,
        origin_event_id="event",
    )
    repo.delete(source)

    assert repo.get_by_id(1).obj_id == 1
    assert repo.get_by_type_and_ref(source_type=AIKnowledgeSourceType.MATERIAL, source_ref_id="1").source_id == 2
    assert repo.list_by_course_id(2)[0].source_id == 1
    assert repo.list_by_module_id(3)[0].source_id == 1
    assert repo.list_by_material_id(4)[0].source_id == 1
    assert repo.list_material_sources()[0].source_id == 1
    assert repo.delete_by_type_and_ref(source_type=AIKnowledgeSourceType.MATERIAL, source_ref_id="1") == 3
    assert source.title == "Updated"
    assert source in session.deleted


def test_profile_asset_repositories_create_archive_version_and_delete() -> None:
    # Tests global and module profile asset repositories create, archive, version, and delete mappings.
    session = FakeSession(scalar_value=2)
    global_repo = LearnerGlobalProfileAssetsRepository(session)
    module_repo = LearnerModuleProfileAssetsRepository(session)

    global_asset = global_repo.create(learner_id=7, object_key="global/key", version=3)
    module_asset = module_repo.create(learner_id=7, course_id=1, module_id=2, object_key="module/key", version=4)
    global_repo.archive_active_for_learner(7)
    module_repo.archive_active_by_scope(learner_id=7, course_id=1, module_id=2)
    global_repo.delete(global_asset)
    module_repo.delete(module_asset)

    assert global_repo.get_by_id(1).obj_id == 1
    assert global_repo.get_next_version(7) == 3
    assert module_repo.get_next_version(learner_id=7, course_id=1, module_id=2) == 3
    assert global_asset.status == AIProfileAssetStatus.ACTIVE
    assert module_asset.status == AIProfileAssetStatus.ACTIVE
    assert len(session.executed) == 2
    assert global_asset in session.deleted
    assert module_asset in session.deleted

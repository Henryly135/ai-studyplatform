from __future__ import annotations

import json
from types import SimpleNamespace

from app.services.workflows.quiz_generation.services.generation_run_store import QuizGenerationRunStore


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.deleted: list[str] = []

    def get(self, key: str):
        return self.values.get(key)

    def setex(self, key: str, ttl: int, value: str) -> None:
        self.values[key] = value

    def delete(self, key: str) -> None:
        self.deleted.append(key)
        self.values.pop(key, None)


def _store(client: FakeRedis) -> QuizGenerationRunStore:
    store = QuizGenerationRunStore(client=client)
    store.prefix = "test.qgen"
    store.ttl = 60
    return store


def test_create_or_get_active_run_creates_run_and_active_pointer(monkeypatch) -> None:
    # Tests that a new queued run is saved and linked as the active run.
    client = FakeRedis()
    store = _store(client)
    monkeypatch.setattr(
        "app.services.workflows.quiz_generation.services.generation_run_store.uuid4",
        lambda: SimpleNamespace(hex="abc123"),
    )
    monkeypatch.setattr(store, "_now", lambda: "2026-04-29T00:00:00Z")

    run, created = store.create_or_get_active_run(
        course_uuid="course-1",
        module_uuid="module-1",
        actor_id=7,
        additional_instructions="focus",
    )

    assert created is True
    assert run["runId"] == "qgen_abc123"
    assert run["status"] == "queued"
    assert client.get("test.qgen:active:7:course-1:module-1") == "qgen_abc123"
    saved_run = json.loads(client.get("test.qgen:run:qgen_abc123"))
    assert saved_run["events"][0]["event"] == "queued"


def test_create_or_get_active_run_reuses_non_terminal_active_run() -> None:
    # Tests that an existing running run is reused instead of creating a duplicate.
    client = FakeRedis()
    store = _store(client)
    run = {"runId": "run-1", "status": "running", "events": []}
    client.setex("test.qgen:run:run-1", 60, json.dumps(run))
    client.setex("test.qgen:active:7:course-1:module-1", 60, "run-1")

    active_run, created = store.create_or_get_active_run(
        course_uuid="course-1",
        module_uuid="module-1",
        actor_id=7,
        additional_instructions=None,
    )

    assert active_run == run
    assert created is False


def test_get_active_run_clears_terminal_or_missing_run() -> None:
    # Tests that completed active runs are hidden and their active key is removed.
    client = FakeRedis()
    store = _store(client)
    client.setex("test.qgen:run:run-1", 60, json.dumps({"runId": "run-1", "status": "completed"}))
    client.setex("test.qgen:active:7:course-1:module-1", 60, "run-1")

    assert store.get_active_run(actor_id=7, course_uuid="course-1", module_uuid="module-1") is None
    assert "test.qgen:active:7:course-1:module-1" in client.deleted


def test_run_status_transitions_append_events_and_clear_active(monkeypatch) -> None:
    # Tests running, step completion, final completion, and active-key cleanup.
    client = FakeRedis()
    store = _store(client)
    monkeypatch.setattr(store, "_now", lambda: "2026-04-29T00:00:00Z")
    run = {
        "runId": "run-1",
        "courseUuid": "course-1",
        "moduleUuid": "module-1",
        "actorId": 7,
        "status": "queued",
        "events": [],
    }
    store._save_run(run)
    client.setex("test.qgen:active:7:course-1:module-1", 60, "run-1")

    store.mark_running("run-1", step="load", message="Loading")
    store.mark_step_completed("run-1", step="load", message="Loaded", data={"count": 1})
    store.complete_run("run-1", attempt_start_response={"token": "abc"})

    saved_run = store.get_run("run-1")
    assert saved_run["status"] == "completed"
    assert saved_run["attemptStartResponse"] == {"token": "abc"}
    assert [event["event"] for event in saved_run["events"]] == ["step_started", "step_completed", "result"]
    assert "test.qgen:active:7:course-1:module-1" in client.deleted


def test_fail_run_marks_error_and_clear_active(monkeypatch) -> None:
    # Tests that failed runs store the error message and clear the active pointer.
    client = FakeRedis()
    store = _store(client)
    monkeypatch.setattr(store, "_now", lambda: "2026-04-29T00:00:00Z")
    store._save_run(
        {
            "runId": "run-1",
            "courseUuid": "course-1",
            "moduleUuid": "module-1",
            "actorId": 7,
            "status": "running",
            "events": [],
        }
    )
    client.setex("test.qgen:active:7:course-1:module-1", 60, "run-1")

    store.fail_run("run-1", message="boom")

    saved_run = store.get_run("run-1")
    assert saved_run["status"] == "failed"
    assert saved_run["error"] == "boom"
    assert saved_run["events"][-1]["event"] == "error"
    assert "test.qgen:active:7:course-1:module-1" in client.deleted


def test_get_run_returns_none_for_missing_or_invalid_json() -> None:
    # Tests defensive parsing when Redis has no value or corrupt JSON.
    client = FakeRedis()
    store = _store(client)
    client.setex("test.qgen:run:broken", 60, "{")

    assert store.get_run("missing") is None
    assert store.get_run("broken") is None


def test_append_event_keeps_only_latest_100_events(monkeypatch) -> None:
    # Tests event history trimming to the latest one hundred entries.
    client = FakeRedis()
    store = _store(client)
    monkeypatch.setattr(store, "_now", lambda: "2026-04-29T00:00:00Z")
    store._save_run({"runId": "run-1", "status": "running", "events": []})

    for index in range(105):
        store.append_event("run-1", event=f"event-{index}", step="graph", message="tick")

    saved_run = store.get_run("run-1")
    assert len(saved_run["events"]) == 100
    assert saved_run["events"][0]["event"] == "event-5"

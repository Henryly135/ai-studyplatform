from __future__ import annotations

from datetime import datetime, timezone
import json
from uuid import uuid4

from redis import Redis

from app.core.config import settings


RUN_TERMINAL_STATUSES = {"completed", "failed"}


class QuizGenerationRunStore:
    _client: Redis | None = None

    def __init__(self, client: Redis | None = None) -> None:
        self.client = client or self._get_client()
        self.prefix = settings.quiz_generation_run_key_prefix
        self.ttl = settings.quiz_generation_run_ttl_seconds

    @classmethod
    def _get_client(cls) -> Redis:
        if cls._client is None:
            cls._client = Redis.from_url(settings.quiz_generation_run_redis_url, decode_responses=True)
        return cls._client

    def create_or_get_active_run(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        actor_id: int,
        additional_instructions: str | None,
    ) -> tuple[dict, bool]:
        active_key = self._active_key(actor_id=actor_id, course_uuid=course_uuid, module_uuid=module_uuid)
        active_run_id = self.client.get(active_key)
        if active_run_id:
            active_run = self.get_run(active_run_id)
            if active_run and active_run.get("status") not in RUN_TERMINAL_STATUSES:
                return active_run, False

        now = self._now()
        run = {
            "runId": f"qgen_{uuid4().hex}",
            "courseUuid": course_uuid,
            "moduleUuid": module_uuid,
            "actorId": actor_id,
            "additionalInstructions": additional_instructions,
            "status": "queued",
            "currentStep": None,
            "message": "Queued quiz generation.",
            "startedAt": now,
            "updatedAt": now,
            "error": None,
            "attemptStartResponse": None,
            "events": [],
        }
        self._save_run(run)
        self.client.setex(active_key, self.ttl, run["runId"])
        self.append_event(run["runId"], event="queued", step="graph", message="Queued quiz generation.")
        return run, True

    def get_run(self, run_id: str) -> dict | None:
        raw = self.client.get(self._run_key(run_id))
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def get_active_run(self, *, actor_id: int, course_uuid: str, module_uuid: str) -> dict | None:
        run_id = self.client.get(
            self._active_key(actor_id=actor_id, course_uuid=course_uuid, module_uuid=module_uuid)
        )
        if not run_id:
            return None
        run = self.get_run(run_id)
        if not run or run.get("status") in RUN_TERMINAL_STATUSES:
            self.client.delete(self._active_key(actor_id=actor_id, course_uuid=course_uuid, module_uuid=module_uuid))
            return None
        return run

    def mark_running(self, run_id: str, *, step: str, message: str) -> None:
        self.update_run(run_id, status="running", currentStep=step, message=message)
        self.append_event(run_id, event="step_started", step=step, message=message)

    def mark_step_completed(self, run_id: str, *, step: str, message: str, data: dict | None = None) -> None:
        self.update_run(run_id, status="running", currentStep=step, message=message)
        self.append_event(run_id, event="step_completed", step=step, message=message, data=data)

    def complete_run(self, run_id: str, *, attempt_start_response: dict) -> None:
        self.update_run(
            run_id,
            status="completed",
            currentStep="graph",
            message="Generated quiz session is ready.",
            attemptStartResponse=attempt_start_response,
            error=None,
        )
        self.append_event(
            run_id,
            event="result",
            step="graph",
            message="Generated quiz attempt graph completed.",
            data={"attemptStartResponse": attempt_start_response},
        )
        run = self.get_run(run_id)
        if run:
            self._clear_active_key(run)

    def fail_run(self, run_id: str, *, message: str) -> None:
        self.update_run(run_id, status="failed", currentStep="graph", message=message, error=message)
        self.append_event(run_id, event="error", step="graph", message=message)
        run = self.get_run(run_id)
        if run:
            self._clear_active_key(run)

    def update_run(self, run_id: str, **fields) -> None:
        run = self.get_run(run_id)
        if not run:
            return
        run.update(fields)
        run["updatedAt"] = self._now()
        self._save_run(run)

    def append_event(
        self,
        run_id: str,
        *,
        event: str,
        step: str | None,
        message: str,
        data: dict | None = None,
    ) -> None:
        run = self.get_run(run_id)
        if not run:
            return
        events = list(run.get("events") or [])
        events.append(
            {
                "event": event,
                "step": step,
                "message": message,
                "timestamp": self._now(),
                "data": data or {},
            }
        )
        run["events"] = events[-100:]
        run["updatedAt"] = self._now()
        self._save_run(run)

    def _save_run(self, run: dict) -> None:
        run_id = str(run["runId"])
        self.client.setex(self._run_key(run_id), self.ttl, json.dumps(run, ensure_ascii=True))

    def _run_key(self, run_id: str) -> str:
        return f"{self.prefix}:run:{run_id}"

    def _active_key(self, *, actor_id: int, course_uuid: str, module_uuid: str) -> str:
        return f"{self.prefix}:active:{actor_id}:{course_uuid}:{module_uuid}"

    def _clear_active_key(self, run: dict) -> None:
        try:
            self.client.delete(
                self._active_key(
                    actor_id=int(run["actorId"]),
                    course_uuid=str(run["courseUuid"]),
                    module_uuid=str(run["moduleUuid"]),
                )
            )
        except Exception:
            return

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

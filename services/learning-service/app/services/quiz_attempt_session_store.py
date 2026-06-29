import json
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from redis import Redis

from app.core.config import settings


@dataclass(frozen=True)
class QuizAttemptSessionData:
    session_token: str
    quiz_id: int
    module_id: int
    course_id: int
    learner_id: int
    attempt_number: int
    question_count: int
    time_limit_seconds: int | None
    started_at: datetime
    expires_at: datetime | None
    questions: list[dict[str, Any]]

    def to_json(self) -> str:
        payload = asdict(self)
        payload["started_at"] = self.started_at.isoformat()
        payload["expires_at"] = self.expires_at.isoformat() if self.expires_at is not None else None
        return json.dumps(payload, separators=(",", ":"))

    @classmethod
    def from_json(cls, raw: str) -> "QuizAttemptSessionData":
        payload = json.loads(raw)
        return cls(
            session_token=str(payload["session_token"]),
            quiz_id=int(payload["quiz_id"]),
            module_id=int(payload["module_id"]),
            course_id=int(payload["course_id"]),
            learner_id=int(payload["learner_id"]),
            attempt_number=int(payload["attempt_number"]),
            question_count=int(payload["question_count"]),
            time_limit_seconds=(
                int(payload["time_limit_seconds"]) if payload.get("time_limit_seconds") is not None else None
            ),
            started_at=datetime.fromisoformat(payload["started_at"]),
            expires_at=datetime.fromisoformat(payload["expires_at"]) if payload.get("expires_at") else None,
            questions=list(payload["questions"]),
        )


class QuizAttemptSessionStore:
    _client: Redis | None = None

    def __init__(self) -> None:
        if QuizAttemptSessionStore._client is None:
            QuizAttemptSessionStore._client = Redis.from_url(settings.quiz_redis_url, decode_responses=True)
        self.client = QuizAttemptSessionStore._client

    def create_session(self, session: QuizAttemptSessionData) -> None:
        ttl_seconds = self._compute_session_ttl_seconds(session.time_limit_seconds)
        previous_session_token = self.client.get(self._active_session_key(session.quiz_id, session.learner_id))
        if previous_session_token:
            self.client.delete(self._session_key(previous_session_token))
        self.client.set(self._session_key(session.session_token), session.to_json(), ex=ttl_seconds)
        self.client.set(self._active_session_key(session.quiz_id, session.learner_id), session.session_token, ex=ttl_seconds)

    def get_active_session(self, quiz_id: int, learner_id: int) -> QuizAttemptSessionData | None:
        active_token = self.client.get(self._active_session_key(quiz_id, learner_id))
        if active_token is None:
            return None
        return self.get_session(active_token)

    def get_session(self, session_token: str) -> QuizAttemptSessionData | None:
        payload = self.client.get(self._session_key(session_token))
        if payload is None:
            return None
        return QuizAttemptSessionData.from_json(payload)

    def delete_session(self, session_token: str) -> None:
        session = self.get_session(session_token)
        self.client.delete(self._session_key(session_token))
        if session is not None:
            active_key = self._active_session_key(session.quiz_id, session.learner_id)
            if self.client.get(active_key) == session_token:
                self.client.delete(active_key)

    def issue_attempt_number(self, *, quiz_id: int, learner_id: int, base_attempt_number: int) -> int:
        counter_key = self._counter_key(quiz_id, learner_id)
        self.client.set(counter_key, base_attempt_number, nx=True, ex=settings.quiz_attempt_counter_ttl_seconds)
        next_attempt_number = int(self.client.incr(counter_key))
        self.client.expire(counter_key, settings.quiz_attempt_counter_ttl_seconds)
        return next_attempt_number

    def acquire_submit_lock(self, session_token: str) -> str | None:
        lock_value = secrets.token_urlsafe(16)
        acquired = self.client.set(
            self._submit_lock_key(session_token),
            lock_value,
            nx=True,
            ex=settings.quiz_attempt_submit_lock_seconds,
        )
        return lock_value if acquired else None

    def release_submit_lock(self, session_token: str, lock_value: str) -> None:
        lock_key = self._submit_lock_key(session_token)
        current_value = self.client.get(lock_key)
        if current_value == lock_value:
            self.client.delete(lock_key)

    def _compute_session_ttl_seconds(self, time_limit_seconds: int | None) -> int:
        if time_limit_seconds is None:
            return settings.quiz_attempt_session_fallback_ttl_seconds
        return time_limit_seconds + settings.quiz_attempt_session_grace_seconds

    def _session_key(self, session_token: str) -> str:
        return f"quiz:attempt_session:{session_token}"

    def _submit_lock_key(self, session_token: str) -> str:
        return f"quiz:attempt_submit_lock:{session_token}"

    def _counter_key(self, quiz_id: int, learner_id: int) -> str:
        return f"quiz:attempt_counter:{quiz_id}:{learner_id}"

    def _active_session_key(self, quiz_id: int, learner_id: int) -> str:
        return f"quiz:active_session:{quiz_id}:{learner_id}"

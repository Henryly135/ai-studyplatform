from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from app.schemas.profiles import ModuleProfileRead
from app.services.workflows.profile_update.schemas import QuizSignalSummaryRead
from app.services.workflows.profile_update.services.context_service import ModuleUpdateContextService


def test_build_context_uses_default_base_when_no_active_profile(monkeypatch):
    # Tests profile update context falls back to default profile when no active asset exists.
    service = ModuleUpdateContextService(session=object())
    monkeypatch.setattr("app.services.workflows.profile_update.services.context_service.decode_course_uuid", lambda _: 101)
    monkeypatch.setattr("app.services.workflows.profile_update.services.context_service.decode_module_uuid", lambda _: 202)
    service.profile_service.get_for_learner = lambda **_: ModuleProfileRead(
        learnerId=7,
        courseUuid="course-uuid",
        moduleUuid="module-uuid",
        content={"confidence_estimate": 0.5, "weak_points": [], "strong_points": [], "common_error_patterns": [], "recent_confusions": [], "recommended_focus": []},
        isDefaultProfile=True,
    )
    service.profile_assets.get_active_by_scope = lambda **_: None
    service.quiz_signals.fetch_summary = lambda **_: QuizSignalSummaryRead(
        available=False,
        unavailableReason="learning_service_unavailable",
        signalStrength="none",
        evidenceCount=0,
        timeWindow=None,
        summary=None,
    )
    service.chat_sessions.list_by_user_and_module = lambda **_: []

    payload = SimpleNamespace(
        learnerId=7,
        courseUuid="course-uuid",
        moduleUuid="module-uuid",
        triggerSource="quiz",
    )

    result = service.build_context(payload=payload)

    assert result.baseProfile.profileExists is False
    assert result.baseProfile.baseProfileSource == "default"
    assert result.quizSignalSummary.available is False
    assert result.chatSignalSummary.available is False
    assert result.recentHistorySummary.hasPriorActiveProfile is False


def test_build_chat_signal_summary_marks_threshold_and_topics():
    # Tests chat signals detect threshold, topics, and preferred response style.
    service = ModuleUpdateContextService(session=object())
    now = datetime.now(timezone.utc)
    service.chat_sessions.list_by_user_and_module = lambda **_: [
        SimpleNamespace(
            session_id=1,
            title="pointer arithmetic",
            summary_text="learner asks for examples",
            message_count=9,
        )
    ]
    service.chat_messages.list_visible_by_session = lambda _session_id: [
        SimpleNamespace(role="user", content_text="Please explain pointer arithmetic step by step", created_at=now),
        SimpleNamespace(role="assistant", content_text="Sure", created_at=now),
        SimpleNamespace(role="user", content_text="I still don't get ownership", created_at=now),
        SimpleNamespace(role="user", content_text="Show me an example", created_at=now),
        SimpleNamespace(role="user", content_text="I am confused", created_at=now),
        SimpleNamespace(role="user", content_text="step by step please", created_at=now),
        SimpleNamespace(role="user", content_text="show me an example", created_at=now),
        SimpleNamespace(role="user", content_text="still don't understand", created_at=now),
        SimpleNamespace(role="user", content_text="break it down", created_at=now),
    ]

    result = service._build_chat_signal_summary(
        learner_id=9,
        module_id=88,
        trigger_source="chat",
    )

    assert result.available is True
    assert result.summary is not None
    assert result.summary.thresholdReached is True
    assert result.summary.userMessageCount == 8
    assert "pointer arithmetic" in result.summary.dominantTopics
    assert "step_by_step" in result.summary.preferredResponseStyleSignals
    assert result.signalStrength in {"medium", "high"}

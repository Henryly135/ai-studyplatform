from __future__ import annotations

import logging
from collections import Counter

from app.core.uuid_codec import decode_course_uuid, decode_module_uuid
from app.repositories.ai_chat_messages_repository import AIChatMessagesRepository
from app.repositories.ai_chat_sessions_repository import AIChatSessionsRepository
from app.repositories.learner_module_profile_assets_repository import LearnerModuleProfileAssetsRepository
from app.services.profiles.module_profile_service import ModuleProfileService
from app.services.workflows.profile_update.schemas import (
    BaseProfileContextRead,
    ChatSignalSummaryDetailRead,
    ChatSignalSummaryRead,
    ExpectedActionRead,
    ListConstraintRead,
    ModuleUpdateContextRequest,
    ModuleUpdateContextResponse,
    ModuleUpdateContextScopeRead,
    ModuleUpdateTriggerRead,
    NumericConstraintRead,
    QuizSignalSummaryRead,
    RecentHistorySummaryRead,
    SignalTimeWindowRead,
    UpdateConstraintsRead,
    UpdateModeDefinitionRead,
)
from app.services.workflows.profile_update.services.quiz_signal_client import LearningQuizSignalClient


logger = logging.getLogger(__name__)

CHAT_THRESHOLD_RULE = "8_user_messages_in_module"
CHAT_THRESHOLD_COUNT = 8
MAX_CHAT_SESSIONS = 3
MAX_CHAT_SUMMARIES = 3


class ModuleUpdateContextService:
    def __init__(self, session) -> None:
        self.session = session
        self.profile_service = ModuleProfileService(session)
        self.profile_assets = LearnerModuleProfileAssetsRepository(session)
        self.chat_sessions = AIChatSessionsRepository(session)
        self.chat_messages = AIChatMessagesRepository(session)
        self.quiz_signals = LearningQuizSignalClient()

    def build_context(self, *, payload: ModuleUpdateContextRequest) -> ModuleUpdateContextResponse:
        logger.info(
            "Building module update context",
            extra={
                "learnerId": payload.learnerId,
                "courseUuid": payload.courseUuid,
                "moduleUuid": payload.moduleUuid,
                "triggerSource": payload.triggerSource,
            },
        )
        course_id = decode_course_uuid(payload.courseUuid)
        module_id = decode_module_uuid(payload.moduleUuid)

        base_profile = self.profile_service.get_for_learner(
            learner_id=payload.learnerId,
            course_uuid=payload.courseUuid,
            module_uuid=payload.moduleUuid,
        )
        active_asset = self.profile_assets.get_active_by_scope(
            learner_id=payload.learnerId,
            course_id=course_id,
            module_id=module_id,
        )
        quiz_signal = self.quiz_signals.fetch_summary(
            course_id=course_id,
            module_id=module_id,
            learner_id=payload.learnerId,
        )
        chat_signal = self._build_chat_signal_summary(
            learner_id=payload.learnerId,
            module_id=module_id,
            trigger_source=payload.triggerSource,
        )

        response = ModuleUpdateContextResponse(
            scope=ModuleUpdateContextScopeRead(
                learnerId=payload.learnerId,
                courseUuid=payload.courseUuid,
                moduleUuid=payload.moduleUuid,
            ),
            trigger=ModuleUpdateTriggerRead(
                source=payload.triggerSource,
                reason=self._derive_trigger_reason(payload.triggerSource),
            ),
            baseProfile=BaseProfileContextRead(
                profileExists=not base_profile.isDefaultProfile,
                baseProfileSource="default" if base_profile.isDefaultProfile else "active",
                version=base_profile.version,
                objectKey=base_profile.objectKey,
                currentProfile=base_profile.content,
                createdAt=base_profile.createdAt,
                updatedAt=base_profile.updatedAt,
            ),
            quizSignalSummary=quiz_signal,
            chatSignalSummary=chat_signal,
            recentHistorySummary=RecentHistorySummaryRead(
                hasPriorActiveProfile=active_asset is not None,
                latestVersion=active_asset.version if active_asset is not None else None,
                latestUpdatedAt=active_asset.updated_at if active_asset is not None else None,
                latestProfileStatus="active" if active_asset is not None else "default_only",
            ),
            updateConstraints=self._build_update_constraints(),
            expectedAction=self._build_expected_action(),
        )
        logger.info(
            "Built module update context",
            extra={
                "learnerId": payload.learnerId,
                "courseUuid": payload.courseUuid,
                "moduleUuid": payload.moduleUuid,
                "triggerSource": payload.triggerSource,
                "baseProfileSource": response.baseProfile.baseProfileSource,
                "quizSignalAvailable": response.quizSignalSummary.available,
                "chatSignalAvailable": response.chatSignalSummary.available,
                "hasPriorActiveProfile": response.recentHistorySummary.hasPriorActiveProfile,
            },
        )
        return response

    def _build_chat_signal_summary(
        self,
        *,
        learner_id: int,
        module_id: int,
        trigger_source: str,
    ) -> ChatSignalSummaryRead:
        sessions = self.chat_sessions.list_by_user_and_module(user_id=learner_id, module_id=module_id)[:MAX_CHAT_SESSIONS]
        if not sessions:
            logger.info(
                "No chat sessions found for module update context",
                extra={
                    "learnerId": learner_id,
                    "moduleId": module_id,
                    "triggerSource": trigger_source,
                },
            )
            return ChatSignalSummaryRead(
                available=False,
                unavailableReason="no_chat_sessions",
                signalStrength="none",
                evidenceCount=0,
                timeWindow=None,
                summary=None,
            )

        message_count = sum(session.message_count for session in sessions)
        all_messages = []
        for session in sessions:
            all_messages.extend(self.chat_messages.list_visible_by_session(session.session_id))

        user_messages = [message for message in all_messages if str(getattr(message.role, "value", message.role)) == "user"]
        user_message_texts = [message.content_text.strip() for message in user_messages if message.content_text.strip()]
        style_signals = self._extract_style_signals(user_message_texts)
        frustration_signals = self._extract_frustration_signals(user_message_texts)
        repeated_confusions = self._extract_repeated_confusions(user_message_texts)
        latest_summaries = [
            session.summary_text.strip()
            for session in sessions
            if session.summary_text and session.summary_text.strip()
        ][:MAX_CHAT_SUMMARIES]
        dominant_topics = self._derive_dominant_topics(sessions=sessions, repeated_confusions=repeated_confusions)
        threshold_reached = len(user_messages) >= CHAT_THRESHOLD_COUNT

        timestamps = [message.created_at for message in all_messages]
        time_window = (
            SignalTimeWindowRead(startAt=min(timestamps), endAt=max(timestamps))
            if timestamps
            else None
        )
        summary = ChatSignalSummaryDetailRead(
            sessionCount=len(sessions),
            messageCount=message_count,
            userMessageCount=len(user_messages),
            thresholdRule=CHAT_THRESHOLD_RULE,
            thresholdReached=threshold_reached,
            latestSessionSummaries=latest_summaries,
            dominantTopics=dominant_topics,
            repeatedConfusions=repeated_confusions,
            preferredResponseStyleSignals=style_signals,
            frustrationSignals=frustration_signals,
            engagementPatternHint=self._derive_engagement_pattern(
                user_message_count=len(user_messages),
                frustration_count=len(frustration_signals),
            ),
            responsePreferenceShiftHint=self._derive_response_preference_shift(style_signals),
            supportNeedShiftHint=self._derive_support_need_shift(
                threshold_reached=threshold_reached,
                frustration_count=len(frustration_signals),
            ),
            changeSignificance=self._derive_chat_change_significance(
                threshold_reached=threshold_reached,
                frustration_count=len(frustration_signals),
                style_signal_count=len(style_signals),
            ),
            reasonForTrigger=self._derive_trigger_reason(trigger_source),
        )
        response = ChatSignalSummaryRead(
            signalStrength=self._derive_chat_signal_strength(
                threshold_reached=threshold_reached,
                frustration_count=len(frustration_signals),
                repeated_confusion_count=len(repeated_confusions),
            ),
            evidenceCount=len(user_messages),
            timeWindow=time_window,
            summary=summary,
        )
        logger.info(
            "Built chat signal summary",
            extra={
                "learnerId": learner_id,
                "moduleId": module_id,
                "triggerSource": trigger_source,
                "sessionCount": len(sessions),
                "userMessageCount": len(user_messages),
                "thresholdReached": threshold_reached,
                "signalStrength": response.signalStrength,
            },
        )
        return response

    def _build_update_constraints(self) -> UpdateConstraintsRead:
        return UpdateConstraintsRead(
            allowedPatchFields=[
                "learning_style",
                "response_preference",
                "knowledge_stability",
                "engagement_pattern",
                "common_error_patterns",
                "support_need_level",
                "confidence_estimate",
                "weak_points",
                "strong_points",
                "recent_confusions",
                "recommended_focus",
            ],
            disallowedFields=[
                "profile_type",
                "profile_status",
                "last_updated_at",
                "learnerId",
                "courseUuid",
                "moduleUuid",
                "version",
                "objectKey",
                "createdAt",
                "updatedAt",
                "isDefaultProfile",
            ],
            updateModes=[
                UpdateModeDefinitionRead(mode="no_update", description="Keep the current active profile unchanged."),
                UpdateModeDefinitionRead(mode="light_update", description="Apply a minimal, evidence-backed patch to the current profile."),
                UpdateModeDefinitionRead(mode="full_rewrite", description="Submit a broader patch because the current profile is materially outdated."),
            ],
            patchGuidance=[
                "Submit a patch, not a full profile document.",
                "Change only fields supported by quiz or chat evidence.",
                "Do not include metadata or system-controlled fields.",
                "Use light_update by default unless broader coordinated change is clearly justified.",
            ],
            numericConstraints=[
                NumericConstraintRead(field="confidence_estimate", minValue=0.0, maxValue=1.0),
            ],
            listConstraints=[
                ListConstraintRead(field="common_error_patterns", maxItems=10, maxItemLength=300),
                ListConstraintRead(field="weak_points", maxItems=10, maxItemLength=300),
                ListConstraintRead(field="strong_points", maxItems=10, maxItemLength=300),
                ListConstraintRead(field="recent_confusions", maxItems=10, maxItemLength=300),
                ListConstraintRead(field="recommended_focus", maxItems=10, maxItemLength=300),
            ],
        )

    def _build_expected_action(self) -> ExpectedActionRead:
        return ExpectedActionRead(
            steps=[
                "Review base profile and current signals.",
                "Decide whether the profile should update.",
                "If update is needed, choose light_update or full_rewrite.",
                "Produce a candidate patch using allowed fields only.",
                "Submit the candidate patch through the candidate update API/tool.",
            ],
            outputShape={
                "should_update": True,
                "update_mode": "light_update",
                "reason": "string",
                "patch": {
                    "weak_points": ["string"],
                    "recommended_focus": ["string"],
                    "confidence_estimate": 0.42,
                },
            },
        )

    def _derive_trigger_reason(self, trigger_source: str) -> str:
        return {
            "quiz": "quiz_submitted",
            "chat": "chat_threshold_reached",
            "progress": "progress_signal_detected",
            "manual": "manual_update_check_requested",
            "system": "system_update_check_requested",
        }.get(trigger_source, "system_update_check_requested")

    def _extract_style_signals(self, user_messages: list[str]) -> list[str]:
        signal_keywords = {
            "step_by_step": ["step by step", "slowly", "break it down"],
            "worked_examples": ["example", "show me", "walk through"],
            "simpler_language": ["simpler", "simple words", "easier words"],
            "concise_answers": ["brief", "short answer", "quickly"],
        }
        detected: list[str] = []
        normalized_messages = [message.lower() for message in user_messages]
        for signal, keywords in signal_keywords.items():
            if any(keyword in message for message in normalized_messages for keyword in keywords):
                detected.append(signal)
        return detected

    def _extract_frustration_signals(self, user_messages: list[str]) -> list[str]:
        keywords = ["i don't get", "still don't", "confused", "stuck", "not sure", "lost"]
        detected: list[str] = []
        for message in user_messages:
            lowered = message.lower()
            if any(keyword in lowered for keyword in keywords):
                detected.append(message[:160])
        return detected[:3]

    def _extract_repeated_confusions(self, user_messages: list[str]) -> list[str]:
        normalized = [" ".join(message.lower().split()) for message in user_messages if message.strip()]
        counts = Counter(normalized)
        repeated = [message for message, count in counts.items() if count > 1]
        if repeated:
            return repeated[:3]
        return normalized[-3:]

    def _derive_dominant_topics(self, *, sessions, repeated_confusions: list[str]) -> list[str]:
        topics: list[str] = []
        for session in sessions:
            if session.title and session.title.strip():
                topics.append(session.title.strip())
        for confusion in repeated_confusions:
            if confusion not in topics:
                topics.append(confusion)
        return topics[:3]

    def _derive_engagement_pattern(self, *, user_message_count: int, frustration_count: int) -> str:
        if user_message_count >= CHAT_THRESHOLD_COUNT and frustration_count > 0:
            return "persistent_but_struggling"
        if user_message_count >= CHAT_THRESHOLD_COUNT:
            return "high_engagement"
        if user_message_count > 0:
            return "engaged"
        return "unknown"

    def _derive_response_preference_shift(self, style_signals: list[str]) -> str:
        if "step_by_step" in style_signals or "worked_examples" in style_signals:
            return "more_guided"
        if "concise_answers" in style_signals:
            return "more_concise"
        return "stable"

    def _derive_support_need_shift(self, *, threshold_reached: bool, frustration_count: int) -> str:
        if frustration_count > 0:
            return "up"
        if threshold_reached:
            return "slightly_up"
        return "stable"

    def _derive_chat_change_significance(
        self,
        *,
        threshold_reached: bool,
        frustration_count: int,
        style_signal_count: int,
    ) -> str:
        if frustration_count >= 2:
            return "major"
        if threshold_reached or style_signal_count > 0:
            return "moderate"
        return "minor"

    def _derive_chat_signal_strength(
        self,
        *,
        threshold_reached: bool,
        frustration_count: int,
        repeated_confusion_count: int,
    ) -> str:
        if frustration_count >= 2 or repeated_confusion_count >= 2:
            return "high"
        if threshold_reached:
            return "medium"
        return "low"

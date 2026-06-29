from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph

from app.services.workflows.profile_update.nodes.decide_update import decide_update_node
from app.services.workflows.profile_update.nodes.finalize_result import finalize_result_node
from app.services.workflows.profile_update.nodes.load_context import load_context_node
from app.services.workflows.profile_update.nodes.submit_candidate import submit_candidate_node
from app.services.workflows.profile_update.schemas import (
    ModuleProfileUpdateCheckRequest,
    ModuleProfileUpdateCheckResponse,
    ProfileUpdateWorkflowState,
)
from platform_common.errors import invalid_request_error


logger = logging.getLogger(__name__)


class ModuleProfileUpdateGraphRunner:
    MAX_ATTEMPTS = 2

    def __init__(self, session, checkpointer=None) -> None:
        self.session = session
        self.checkpointer = checkpointer
        self.graph = self._build_graph()

    def run(self, *, payload: ModuleProfileUpdateCheckRequest, config: dict | None = None) -> ModuleProfileUpdateCheckResponse:
        logger.info(
            "Starting module profile update graph runner",
            extra={
                "learnerId": payload.learnerId,
                "courseUuid": payload.courseUuid,
                "moduleUuid": payload.moduleUuid,
                "triggerSource": payload.triggerSource,
            },
        )
        state: ProfileUpdateWorkflowState = {
            "request": payload,
            "validationFeedback": [],
            "attemptCount": 0,
        }
        final_state = self.graph.invoke(state, config=config)
        result = final_state.get("result")
        if result is None:
            raise invalid_request_error("Profile update graph did not produce a final result")
        return result

    def _build_graph(self):
        graph = StateGraph(ProfileUpdateWorkflowState)
        graph.add_node("load_context", self._load_context)
        graph.add_node("decide_update", self._decide_update)
        graph.add_node("submit_candidate", self._submit_candidate)
        graph.add_node("finalize_result", self._finalize_result)

        graph.add_edge(START, "load_context")
        graph.add_edge("load_context", "decide_update")
        graph.add_conditional_edges(
            "decide_update",
            self._route_after_decision,
            {
                "submit_candidate": "submit_candidate",
                "finalize_result": "finalize_result",
            },
        )
        graph.add_conditional_edges(
            "submit_candidate",
            self._route_after_candidate,
            {
                "decide_update": "decide_update",
                "finalize_result": "finalize_result",
            },
        )
        graph.add_edge("finalize_result", END)
        return graph.compile(checkpointer=self.checkpointer)

    def _load_context(self, state: ProfileUpdateWorkflowState) -> ProfileUpdateWorkflowState:
        return load_context_node(state=state, session=self.session)

    def _decide_update(self, state: ProfileUpdateWorkflowState) -> ProfileUpdateWorkflowState:
        next_state = decide_update_node(state=state)
        decision = next_state["decision"]
        request = next_state["request"]
        logger.info(
            "Generated module profile update decision",
            extra={
                "learnerId": request.learnerId,
                "courseUuid": request.courseUuid,
                "moduleUuid": request.moduleUuid,
                "triggerSource": request.triggerSource,
                "shouldUpdate": decision.should_update,
                "updateMode": decision.update_mode,
                "changedFields": list(decision.patch.keys()),
            },
        )
        return next_state

    def _submit_candidate(self, state: ProfileUpdateWorkflowState) -> ProfileUpdateWorkflowState:
        next_state = submit_candidate_node(state=state, session=self.session)
        request = next_state["request"]
        candidate_result = next_state.get("candidateResult")
        if candidate_result is None:
            raise invalid_request_error("Profile update graph did not produce a candidate result")

        if candidate_result.accepted:
            logger.info(
                "Module profile update graph completed successfully",
                extra={
                    "learnerId": request.learnerId,
                    "courseUuid": request.courseUuid,
                    "moduleUuid": request.moduleUuid,
                    "triggerSource": request.triggerSource,
                    "newVersion": candidate_result.profile.version if candidate_result.profile is not None else None,
                },
            )
        elif candidate_result.retryable:
            next_state["validationFeedback"] = [candidate_result.message]
            logger.warning(
                "Retrying module profile update graph after retryable validation failure",
                extra={
                    "learnerId": request.learnerId,
                    "courseUuid": request.courseUuid,
                    "moduleUuid": request.moduleUuid,
                    "triggerSource": request.triggerSource,
                    "validationMessage": candidate_result.message,
                    "attemptCount": next_state.get("attemptCount"),
                },
            )
        else:
            logger.warning(
                "Module profile update graph failed with non-retryable rejection",
                extra={
                    "learnerId": request.learnerId,
                    "courseUuid": request.courseUuid,
                    "moduleUuid": request.moduleUuid,
                    "triggerSource": request.triggerSource,
                    "validationMessage": candidate_result.message,
                },
            )
        return next_state

    def _finalize_result(self, state: ProfileUpdateWorkflowState) -> ProfileUpdateWorkflowState:
        return {
            **state,
            "result": finalize_result_node(state=state),
        }

    def _route_after_decision(self, state: ProfileUpdateWorkflowState) -> str:
        request = state["request"]
        decision = state["decision"]
        if not decision.should_update:
            logger.info(
                "Module profile update graph decided no update",
                extra={
                    "learnerId": request.learnerId,
                    "courseUuid": request.courseUuid,
                    "moduleUuid": request.moduleUuid,
                    "triggerSource": request.triggerSource,
                },
            )
            return "finalize_result"
        return "submit_candidate"

    def _route_after_candidate(self, state: ProfileUpdateWorkflowState) -> str:
        request = state["request"]
        candidate_result = state.get("candidateResult")
        if candidate_result is None:
            raise invalid_request_error("Profile update graph did not produce a candidate result")
        if candidate_result.accepted or not candidate_result.retryable:
            return "finalize_result"
        if state.get("attemptCount", 0) >= self.MAX_ATTEMPTS:
            logger.warning(
                "Module profile update graph exhausted retries",
                extra={
                    "learnerId": request.learnerId,
                    "courseUuid": request.courseUuid,
                    "moduleUuid": request.moduleUuid,
                    "triggerSource": request.triggerSource,
                },
            )
            return "finalize_result"
        return "decide_update"

from sqlalchemy.orm import Session

from app.models.ai_prompt_logs import AIPromptCallType, AIPromptLog, AIPromptStatus


class AIPromptLogsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        session_id: int | None,
        message_id: int | None,
        user_id: int,
        call_type: AIPromptCallType,
        model_name: str,
        input_text: str,
        status: AIPromptStatus,
        prompt_template_name: str | None = None,
        output_text: str | None = None,
        request_json: dict | list | None = None,
        response_json: dict | list | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
        latency_ms: int | None = None,
        error_message: str | None = None,
        trace_id: str | None = None,
    ) -> AIPromptLog:
        prompt_log = AIPromptLog(
            session_id=session_id,
            message_id=message_id,
            user_id=user_id,
            call_type=call_type,
            prompt_template_name=prompt_template_name,
            model_name=model_name,
            input_text=input_text,
            output_text=output_text,
            request_json=request_json,
            response_json=response_json,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            status=status,
            error_message=error_message,
            trace_id=trace_id,
        )
        self.session.add(prompt_log)
        self.session.flush()
        return prompt_log

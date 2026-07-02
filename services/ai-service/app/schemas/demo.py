from pydantic import BaseModel, Field


class ChatServiceRequest(BaseModel):
    session_id: int | None = None
    user_id: int = Field(..., ge=1)
    course_id: int | None = Field(default=None, ge=1)
    module_id: int | None = Field(default=None, ge=1)
    message: str = Field(..., min_length=1, max_length=4000)
    model_id: str | None = Field(default=None, max_length=120)


class ChatRequest(BaseModel):
    session_uuid: str | None = None
    course_uuid: str | None = None
    module_uuid: str | None = None
    message: str = Field(..., min_length=1, max_length=4000)
    model_id: str | None = Field(default=None, max_length=120)


class ChatResponse(BaseModel):
    session_uuid: str
    user_message_id: int
    assistant_message_id: int
    reply: str
    sources: list[dict[str, object]] = Field(default_factory=list)
    model_id: str | None = None
    model_name: str | None = None
    provider: str | None = None


class APIErrorDetail(BaseModel):
    code: str
    message: str


class APIErrorResponse(BaseModel):
    success: bool = False
    error: APIErrorDetail


class ChatSuccessResponse(BaseModel):
    success: bool = True
    data: ChatResponse


class ChatSessionSummary(BaseModel):
    session_uuid: str
    user_id: int
    course_uuid: str | None = None
    module_uuid: str | None = None
    session_type: str
    title: str | None = None
    status: str
    message_count: int
    summary_text: str | None = None
    last_message_at: str | None = None
    created_at: str
    updated_at: str


class ChatMessageItem(BaseModel):
    message_id: int
    session_uuid: str
    role: str
    message_type: str
    parent_message_id: int | None = None
    content_text: str
    created_at: str


class ChatSessionDetail(BaseModel):
    session: ChatSessionSummary
    messages: list[ChatMessageItem]


class AIHealthResponse(BaseModel):
    status: str
    module: str
    provider: str
    model: str
    configured: bool

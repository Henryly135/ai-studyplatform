export type ChatSessionSummary = {
  session_uuid: string;
  user_id: number;
  course_uuid: string | null;
  module_uuid: string | null;
  session_type: string;
  title: string | null;
  status: string;
  message_count: number;
  summary_text: string | null;
  last_message_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ChatSessionMessage = {
  message_id: number;
  session_uuid: string;
  role: "user" | "assistant" | "system" | "tool";
  message_type: string;
  parent_message_id: number | null;
  content_text: string;
  created_at: string;
};

export type ChatSessionDetail = {
  session: ChatSessionSummary;
  messages: ChatSessionMessage[];
};

export type ChatResponse = {
  session_uuid: string;
  user_message_id: number;
  assistant_message_id: number;
  reply: string;
};

export type ChatSuccessResponse = {
  success: true;
  data: ChatResponse;
};

export type APIErrorResponse = {
  success?: false;
  error?: {
    code: string;
    message: string;
  };
  detail?: string;
};

export type CourseChatMessage = {
  id: number;
  role: "user" | "assistant";
  text: string;
};

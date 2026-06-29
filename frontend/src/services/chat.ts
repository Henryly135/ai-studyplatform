import type {
  APIErrorResponse,
  ChatSessionDetail,
  ChatSessionSummary,
  ChatSuccessResponse,
} from "../types/chat";
import {
  buildAuthHeaders,
  getStoredAccessToken,
  handleAuthenticationFailureFromResponse,
  parseJsonText,
} from "./api";

const CHAT_API_URL = "/api/ai/chat";
const CHAT_SESSIONS_API_URL = "/api/ai/chat/sessions";

function getAccessToken() {
  return getStoredAccessToken();
}

async function parseResponse<T>(response: Response): Promise<T> {
  const responseText = await response.text();
  const data: unknown = parseJsonText(responseText);
  handleAuthenticationFailureFromResponse(response.status, data);

  if (data === null) {
    if (!response.ok) {
      if (response.status >= 500) {
        throw new Error("The AI service is temporarily unavailable. Please try again shortly.");
      }
      throw new Error("Request failed.");
    }

    throw new Error("The server returned an unexpected response.");
  }

  if (!response.ok) {
    const errorPayload = data as APIErrorResponse;
    const detailPayload =
      errorPayload.detail && typeof errorPayload.detail === "object"
        ? (errorPayload.detail as { code?: string; message?: string })
        : null;
    throw new Error(
      errorPayload.error?.message
        ? errorPayload.error.message
        : detailPayload?.message
          ? detailPayload.message
          : typeof errorPayload.detail === "string"
          ? errorPayload.detail
          : "Request failed."
    );
  }

  return data as T;
}

export async function listModuleChatSessions(moduleUuid: string): Promise<ChatSessionSummary[]> {
  const response = await fetch(`/api/ai/chat/modules/${moduleUuid}/sessions`, {
    headers: buildAuthHeaders(),
  });

  return parseResponse<ChatSessionSummary[]>(response);
}

export async function listChatSessions(): Promise<ChatSessionSummary[]> {
  const response = await fetch(CHAT_SESSIONS_API_URL, {
    headers: buildAuthHeaders(),
  });

  return parseResponse<ChatSessionSummary[]>(response);
}

export async function getChatSessionDetail(sessionUuid: string): Promise<ChatSessionDetail> {
  const response = await fetch(`${CHAT_SESSIONS_API_URL}/${sessionUuid}`, {
    headers: buildAuthHeaders(),
  });

  return parseResponse<ChatSessionDetail>(response);
}

export async function sendChatMessage(payload: {
  courseUuid: string | null;
  moduleUuid: string;
  message: string;
  sessionUuid?: string | null;
}) {
  getAccessToken();
  const response = await fetch(CHAT_API_URL, {
    method: "POST",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify({
      session_uuid: payload.sessionUuid ?? null,
      course_uuid: payload.courseUuid,
      module_uuid: payload.moduleUuid,
      message: payload.message,
    }),
  });

  const data = await parseResponse<ChatSuccessResponse>(response);
  return data.data;
}

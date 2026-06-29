import type { GlobalProfileInitRequest, GlobalProfileRead } from "../types/profile";
import {
  buildAuthHeaders,
  handleAuthenticationFailureFromResponse,
  parseJsonText,
} from "./api";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";
const AI_API_BASE_URL = API_BASE_URL.startsWith("/api")
  ? `${API_BASE_URL}/ai`
  : `${API_BASE_URL.replace(/\/$/, "")}/ai`;

function getErrorMessage(data: unknown, fallback: string) {
  if (!data || typeof data !== "object") {
    return fallback;
  }

  const detail = (data as { detail?: unknown }).detail;
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }

  const error = (data as { error?: { message?: unknown } }).error;
  if (error && typeof error.message === "string" && error.message.trim()) {
    return error.message;
  }

  return fallback;
}

export async function initializeGlobalProfile(
  payload: GlobalProfileInitRequest
): Promise<GlobalProfileRead> {
  const response = await fetch(`${AI_API_BASE_URL}/profiles/global/init`, {
    method: "POST",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify(payload),
  });

  const text = await response.text();
  const data = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, data);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "Failed to initialize learning profile."));
  }

  return data as GlobalProfileRead;
}

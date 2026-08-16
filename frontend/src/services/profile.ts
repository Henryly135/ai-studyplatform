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

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function getField(data: Record<string, unknown>, camelKey: string, snakeKey?: string) {
  return data[camelKey] ?? (snakeKey ? data[snakeKey] : undefined);
}

function toNonNegativeNumber(value: unknown) {
  const parsed =
    typeof value === "number"
      ? value
      : typeof value === "string" && value.trim()
        ? Number(value)
        : 0;

  return Number.isFinite(parsed) ? Math.max(0, parsed) : 0;
}

function toNullableNonNegativeNumber(value: unknown) {
  if (value === null || value === undefined) {
    return null;
  }

  const parsed =
    typeof value === "number"
      ? value
      : typeof value === "string" && value.trim()
        ? Number(value)
        : Number.NaN;

  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
}

function toNullableString(value: unknown) {
  return value === null || value === undefined ? null : String(value);
}

function toBoolean(value: unknown) {
  if (typeof value === "boolean") {
    return value;
  }

  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (["true", "1", "yes"].includes(normalized)) {
      return true;
    }
    if (["false", "0", "no"].includes(normalized)) {
      return false;
    }
  }

  return false;
}

const PROFILE_PREFERENCE_KEYS = [
  "supportRole",
  "helpStyle",
  "learningFocus",
  "responseTone",
] as const;

function normalizePreferences(value: unknown): Partial<GlobalProfileInitRequest> {
  const data = asRecord(value);
  return PROFILE_PREFERENCE_KEYS.reduce<Partial<GlobalProfileInitRequest>>((preferences, key) => {
    const rawValue = data[key];
    if (rawValue !== null && rawValue !== undefined && String(rawValue).trim()) {
      preferences[key] = String(rawValue);
    }
    return preferences;
  }, {});
}

function normalizeGlobalProfile(payload: unknown): GlobalProfileRead {
  const data = asRecord(payload);

  return {
    learnerId: toNonNegativeNumber(getField(data, "learnerId", "learner_id")),
    profileType: String(getField(data, "profileType", "profile_type") ?? "global"),
    version: toNullableNonNegativeNumber(data.version),
    objectKey: toNullableString(getField(data, "objectKey", "object_key")),
    content: String(data.content ?? ""),
    preferences: normalizePreferences(getField(data, "preferences")),
    isDefaultProfile: toBoolean(getField(data, "isDefaultProfile", "is_default_profile")),
    createdAt: toNullableString(getField(data, "createdAt", "created_at")),
    updatedAt: toNullableString(getField(data, "updatedAt", "updated_at")),
  };
}

async function requestGlobalProfile(
  path: string,
  init: RequestInit,
  fallbackErrorMessage: string
): Promise<GlobalProfileRead> {
  const response = await fetch(`${AI_API_BASE_URL}${path}`, {
    ...init,
    headers: buildAuthHeaders(init.body ? { "Content-Type": "application/json" } : undefined),
  });

  const text = await response.text();
  const data = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, data);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, fallbackErrorMessage));
  }

  return normalizeGlobalProfile(data);
}

export async function initializeGlobalProfile(
  payload: GlobalProfileInitRequest
): Promise<GlobalProfileRead> {
  return requestGlobalProfile("/profiles/global/init", {
    method: "POST",
    body: JSON.stringify(payload),
  }, "初始化学习画像失败。");
}

export async function getMyGlobalProfile(): Promise<GlobalProfileRead> {
  return requestGlobalProfile(
    "/profiles/global/me",
    { method: "GET" },
    "读取学习画像失败。"
  );
}

export async function updateGlobalProfile(
  payload: GlobalProfileInitRequest
): Promise<GlobalProfileRead> {
  return requestGlobalProfile("/profiles/global/me", {
    method: "PUT",
    body: JSON.stringify(payload),
  }, "更新学习画像失败。");
}

export async function resetGlobalProfile(): Promise<GlobalProfileRead> {
  return requestGlobalProfile(
    "/profiles/global/me",
    { method: "DELETE" },
    "重置学习画像失败。"
  );
}

import { isUsableAccessToken } from "../utils/accessToken";
import type { CurrentUserResponse, Identity } from "../types/auth";

const AUTHENTICATION_ERROR_MESSAGES = new Set([
  "Invalid credentials",
  "Unable to resolve current user",
  "无法解析当前用户",
]);

const AUTHENTICATION_ERROR_CODES = new Set([
  "INVALID_CREDENTIALS",
  "UNAUTHORIZED",
]);

const VALID_IDENTITIES = new Set<Identity>(["Learner", "Educator", "Admin"]);

export function clearStoredSession() {
  localStorage.removeItem("accessToken");
  localStorage.removeItem("tokenType");
  localStorage.removeItem("currentUser");
}

export function redirectToLogin() {
  if (window.location.pathname !== "/login") {
    window.location.assign("/login");
  }
}

export function handleAuthenticationFailure() {
  clearStoredSession();
  redirectToLogin();
}

export function getStoredAccessToken(): string {
  const accessToken = localStorage.getItem("accessToken");
  if (!accessToken || !isUsableAccessToken(accessToken)) {
    handleAuthenticationFailure();
    throw new Error("Invalid credentials");
  }

  return accessToken;
}

function readRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function pickField(data: Record<string, unknown>, camelKey: string, snakeKey?: string) {
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

function normalizeStoredCurrentUser(payload: unknown): CurrentUserResponse | null {
  const data = readRecord(payload);
  if (!data || !VALID_IDENTITIES.has(data.identity as Identity)) {
    return null;
  }

  const accountStatus = pickField(data, "accountStatus", "account_status");

  return {
    id: toNonNegativeNumber(data.id),
    userUuid: String(pickField(data, "userUuid", "user_uuid") ?? ""),
    email: String(data.email ?? ""),
    userName: String(pickField(data, "userName", "user_name") ?? ""),
    identity: data.identity as Identity,
    emailVerified: toBoolean(pickField(data, "emailVerified", "email_verified")),
    ...(accountStatus === null || accountStatus === undefined ? {} : { accountStatus: String(accountStatus) }),
  };
}

export function getStoredCurrentUser(): CurrentUserResponse | null {
  const raw = localStorage.getItem("currentUser");
  if (!raw) {
    return null;
  }

  try {
    const user = normalizeStoredCurrentUser(JSON.parse(raw));
    if (user) {
      return user;
    }
  } catch {
    // Fall through to remove the corrupt cache entry.
  }

  localStorage.removeItem("currentUser");
  return null;
}

export function buildAuthHeaders(headers: HeadersInit = {}): HeadersInit {
  return {
    ...headers,
    Authorization: `Bearer ${getStoredAccessToken()}`,
  };
}

export function parseJsonText(text: string) {
  try {
    return text ? JSON.parse(text) : null;
  } catch {
    return null;
  }
}

export function isAuthenticationFailure(status: number, payload: unknown): boolean {
  if (status === 401) {
    return true;
  }

  if (!payload || typeof payload !== "object") {
    return false;
  }

  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === "string" && AUTHENTICATION_ERROR_MESSAGES.has(detail)) {
    return true;
  }

  if (detail && typeof detail === "object") {
    const detailCode = (detail as { code?: unknown }).code;
    const detailMessage = (detail as { message?: unknown }).message;
    if (typeof detailCode === "string" && AUTHENTICATION_ERROR_CODES.has(detailCode)) {
      return true;
    }
    if (typeof detailMessage === "string" && AUTHENTICATION_ERROR_MESSAGES.has(detailMessage)) {
      return true;
    }
  }

  const error = (payload as { error?: unknown }).error;
  if (error && typeof error === "object") {
    const errorCode = (error as { code?: unknown }).code;
    const errorMessage = (error as { message?: unknown }).message;
    if (typeof errorCode === "string" && AUTHENTICATION_ERROR_CODES.has(errorCode)) {
      return true;
    }
    if (typeof errorMessage === "string" && AUTHENTICATION_ERROR_MESSAGES.has(errorMessage)) {
      return true;
    }
  }

  return false;
}

export function handleAuthenticationFailureFromResponse(status: number, payload: unknown) {
  if (isAuthenticationFailure(status, payload)) {
    handleAuthenticationFailure();
    throw new Error("Invalid credentials");
  }
}

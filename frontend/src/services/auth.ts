import type {
  ApiErrorResponse,
  ChangePasswordRequest,
  CurrentUserResponse,
  CurrentUserPermissionsResponse,
  Identity,
  EducatorInviteRegisterRequest,
  LoginRequest,
  LoginSuccessResponse,
  PermissionItem,
  RegisterRequest,
  RegisterSuccessResponse,
  ResetPasswordRequest,
} from "../types/auth";
import {
  buildAuthHeaders,
  handleAuthenticationFailureFromResponse,
} from "./api";
import { isUsableAccessToken } from "../utils/accessToken";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

async function parseJsonSafe(response: Response) {
  const text = await response.text();

  try {
    return text ? JSON.parse(text) : null;
  } catch {
    return text ? { detail: text } : null;
  }
}

function getErrorMessage(data: ApiErrorResponse | null, fallback: string) {
  if (!data) return fallback;

  if (data.errors && data.errors.length > 0) {
    return data.errors.map((item) => `${item.field}: ${item.reason}`).join(", ");
  }

  return data.detail || fallback;
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function getField(data: Record<string, unknown>, camelKey: string, snakeKey?: string) {
  return data[camelKey] ?? (snakeKey ? data[snakeKey] : undefined);
}

function toNonNegativeNumber(value: unknown, fallback = 0) {
  const parsed =
    typeof value === "number"
      ? value
      : typeof value === "string" && value.trim()
        ? Number(value)
        : fallback;

  return Number.isFinite(parsed) ? Math.max(0, parsed) : fallback;
}

function toBoolean(value: unknown, fallback = false) {
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

  return fallback;
}

function toNullableString(value: unknown) {
  return value === null || value === undefined ? null : String(value);
}

function normalizeIdentity(value: unknown): Identity {
  return value === "Admin" || value === "Educator" || value === "Learner" ? value : "Learner";
}

function isIdentity(value: unknown): value is Identity {
  return value === "Admin" || value === "Educator" || value === "Learner";
}

function normalizeAvailableIdentities(value: unknown, activeIdentity: Identity): Identity[] {
  const identities = Array.isArray(value)
    ? value
        .filter(isIdentity)
        .filter((identity, index, items) => items.indexOf(identity) === index)
    : [];

  if (!identities.includes(activeIdentity)) {
    identities.unshift(activeIdentity);
  }

  return identities;
}

function normalizeUser(payload: unknown): CurrentUserResponse {
  const data = asRecord(payload);
  const accountStatus = toNullableString(getField(data, "accountStatus", "account_status"));
  const identity = normalizeIdentity(data.identity);

  return {
    id: toNonNegativeNumber(data.id),
    userUuid: String(getField(data, "userUuid", "user_uuid") ?? ""),
    email: String(data.email ?? ""),
    userName: String(getField(data, "userName", "user_name") ?? ""),
    identity,
    availableIdentities: normalizeAvailableIdentities(
      getField(data, "availableIdentities", "available_identities"),
      identity
    ),
    emailVerified: toBoolean(getField(data, "emailVerified", "email_verified")),
    ...(accountStatus === null ? {} : { accountStatus }),
  };
}

function normalizeRegisterSuccess(payload: unknown): RegisterSuccessResponse {
  const data = asRecord(payload);
  const userPayload = getField(data, "user");

  return {
    detail: String(data.detail ?? ""),
    ...(userPayload && typeof userPayload === "object" && !Array.isArray(userPayload)
      ? { user: normalizeUser(userPayload) }
      : {}),
  };
}

function normalizeLoginSuccess(payload: unknown): LoginSuccessResponse {
  const data = asRecord(payload);
  const accessToken = String(getField(data, "accessToken", "access_token") ?? "");

  if (!isUsableAccessToken(accessToken)) {
    throw new Error("登录响应无效，请重试。");
  }

  return {
    accessToken,
    tokenType: "bearer",
    expiresIn: toNonNegativeNumber(getField(data, "expiresIn", "expires_in")),
    shouldShowGlobalProfileInitPrompt: toBoolean(
      getField(data, "shouldShowGlobalProfileInitPrompt", "should_show_global_profile_init_prompt")
    ),
    user: normalizeUser(data.user),
  };
}

function normalizeDetail(payload: unknown, fallback: string): { detail: string } {
  const data = asRecord(payload);
  return { detail: String(data.detail ?? fallback) };
}

function normalizeInviteValidation(payload: unknown): { valid: boolean; expiresAt: string } {
  const data = asRecord(payload);
  const result = {
    valid: toBoolean(data.valid),
    expiresAt: String(getField(data, "expiresAt", "expires_at") ?? ""),
  };

  if (!result.valid) {
    throw new Error("Invalid or expired invite link.");
  }

  return result;
}

function normalizePermission(payload: unknown): PermissionItem {
  const data = asRecord(payload);

  return {
    permissionId: toNonNegativeNumber(getField(data, "permissionId", "permission_id")),
    permissionCode: String(getField(data, "permissionCode", "permission_code") ?? ""),
    permissionName: String(getField(data, "permissionName", "permission_name") ?? ""),
    description: toNullableString(data.description),
  };
}

function normalizePermissions(payload: unknown): CurrentUserPermissionsResponse {
  const data = asRecord(payload);

  return {
    permissions: Array.isArray(data.permissions) ? data.permissions.map(normalizePermission) : [],
  };
}

export async function registerUser(
  payload: RegisterRequest
): Promise<RegisterSuccessResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/register`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  const data = await parseJsonSafe(response);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "注册失败。"));
  }

  return normalizeRegisterSuccess(data);
}

export async function loginUser(
  payload: LoginRequest
): Promise<LoginSuccessResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  const data = await parseJsonSafe(response);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "登录失败。"));
  }

  return normalizeLoginSuccess(data);
}

export async function switchCurrentRole(identity: Identity): Promise<LoginSuccessResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/switch-role`, {
    method: "POST",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify({ identity }),
  });

  const data = await parseJsonSafe(response);
  handleAuthenticationFailureFromResponse(response.status, data);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "切换身份失败。"));
  }

  return normalizeLoginSuccess(data);
}

export async function verifyEmail(token: string): Promise<{ detail: string }> {
  const response = await fetch(
    `${API_BASE_URL}/auth/verify-email?${new URLSearchParams({ token })}`,
    { method: "GET" }
  );

  const data = await parseJsonSafe(response);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "邮箱验证失败。"));
  }

  return normalizeDetail(data, "邮箱验证成功。");
}

export async function resendVerification(
  email: string
): Promise<{ detail: string }> {
  const response = await fetch(`${API_BASE_URL}/auth/resend-verification`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ email }),
  });

  const data = await parseJsonSafe(response);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "重新发送验证邮件失败。"));
  }

  return normalizeDetail(data, "Verification email resent.");
}

export async function changePassword(
  payload: ChangePasswordRequest,
  accessToken: string
): Promise<{ detail: string }> {
  void accessToken;
  const response = await fetch(`${API_BASE_URL}/auth/change-password`, {
    method: "POST",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify(payload),
  });

  const data = await parseJsonSafe(response);
  handleAuthenticationFailureFromResponse(response.status, data);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "修改密码失败。"));
  }

  return normalizeDetail(data, "Password changed.");
}

export async function forgotPassword(email: string): Promise<{ detail: string }> {
  const response = await fetch(`${API_BASE_URL}/auth/forgot-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });

  const data = await parseJsonSafe(response);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "发送重置邮件失败。"));
  }

  return normalizeDetail(data, "If the email exists, a reset link will be sent.");
}

export async function resetPassword(
  payload: ResetPasswordRequest
): Promise<{ detail: string }> {
  const response = await fetch(`${API_BASE_URL}/auth/reset-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const data = await parseJsonSafe(response);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "重置密码失败。"));
  }

  return normalizeDetail(data, "Password reset.");
}

export async function getCurrentUser(
  accessToken: string
): Promise<CurrentUserResponse> {
  void accessToken;
  const response = await fetch(`${API_BASE_URL}/auth/me`, {
    method: "GET",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
  });

  const data = await parseJsonSafe(response);
  handleAuthenticationFailureFromResponse(response.status, data);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "获取当前用户失败。"));
  }

  return normalizeUser(data);
}

export async function validateEducatorInviteToken(
  token: string
): Promise<{ valid: boolean; expiresAt: string }> {
  const response = await fetch(
    `${API_BASE_URL}/auth/invite/educator/validate?${new URLSearchParams({ token })}`,
    { method: "GET" }
  );

  const data = await parseJsonSafe(response);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "Invalid or expired invite link."));
  }

  return normalizeInviteValidation(data);
}

export async function registerEducatorViaInvite(
  payload: EducatorInviteRegisterRequest
): Promise<RegisterSuccessResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/register-educator-invite`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const data = await parseJsonSafe(response);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "注册失败。"));
  }

  return normalizeRegisterSuccess(data);
}

export async function getCurrentUserPermissions(
  accessToken: string
): Promise<CurrentUserPermissionsResponse> {
  void accessToken;
  const response = await fetch(`${API_BASE_URL}/auth/me/permissions`, {
    method: "GET",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
  });

  const data = await parseJsonSafe(response);
  handleAuthenticationFailureFromResponse(response.status, data);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "获取当前用户权限失败。"));
  }

  return normalizePermissions(data);
}

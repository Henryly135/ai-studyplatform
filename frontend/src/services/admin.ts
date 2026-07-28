import type { ApiErrorResponse, Identity } from "../types/auth";
import type {
  AdminAiDefaultModelResponse,
  AdminAiProviderCredential,
  AdminAiProviderCredentialHealthResponse,
  AdminAiProviderCredentialListResponse,
  AdminUpdateUserIdentityRequest,
  AdminUpdateUserStatusRequest,
  AdminUserListResponse,
  AdminUserResponse,
  EducatorApprovalHistoryStatus,
  EducatorApprovalListResponse,
  EducatorApprovalResponse,
  EducatorApprovalStatus,
  EducatorInviteTokenGenerateResponse,
  EducatorInviteTokenListResponse,
  EducatorInviteTokenResponse,
  ReviewEducatorApprovalRequest,
  SaveAdminAiProviderCredentialRequest,
  SendEducatorInviteEmailResponse,
  SendEducatorInviteEmailRequest,
  SetAdminAiDefaultModelRequest,
} from "../types/admin";
import {
  buildAuthHeaders,
  handleAuthenticationFailureFromResponse,
  parseJsonText,
} from "./api";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";
const AI_ADMIN_PROVIDERS_URL = `${API_BASE_URL}/ai/admin/ai/providers`;
const AI_ADMIN_DEFAULTS_URL = `${API_BASE_URL}/ai/admin/ai/defaults`;
const SUPPORTED_AI_PROVIDERS = new Set(["gemini", "glm", "openrouter"]);

async function parseJsonSafe(response: Response) {
  return parseJsonText(await response.text());
}

function getErrorMessage(data: ApiErrorResponse | null, fallback: string) {
  if (!data) return fallback;

  if (data.errors && data.errors.length > 0) {
    return data.errors.map((item) => `${item.field}: ${item.reason}`).join(", ");
  }

  return data.detail || fallback;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function asRecord(value: unknown): Record<string, unknown> {
  return isRecord(value) ? value : {};
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

function toStringList(value: unknown) {
  return Array.isArray(value) ? value.map((item) => String(item)) : [];
}

function normalizeIdentity(value: unknown): Identity {
  return value === "Admin" || value === "Educator" || value === "Learner" ? value : "Learner";
}

function normalizeApprovalStatus(value: unknown): EducatorApprovalStatus {
  return value === "approved" || value === "rejected" || value === "pending" ? value : "pending";
}

function normalizeAdminUser(payload: unknown): AdminUserResponse {
  const data = asRecord(payload);

  return {
    id: toNonNegativeNumber(data.id),
    userUuid: String(getField(data, "userUuid", "user_uuid") ?? ""),
    email: String(data.email ?? ""),
    userName: String(getField(data, "userName", "user_name") ?? ""),
    identity: normalizeIdentity(data.identity),
    roleCodes: toStringList(getField(data, "roleCodes", "role_codes")),
    emailVerified: toBoolean(getField(data, "emailVerified", "email_verified")),
    accountStatus: String(getField(data, "accountStatus", "account_status") ?? "deactivated"),
    createdAt: String(getField(data, "createdAt", "created_at") ?? ""),
    updatedAt: String(getField(data, "updatedAt", "updated_at") ?? ""),
    lastLoginAt: toNullableString(getField(data, "lastLoginAt", "last_login_at")),
  };
}

function normalizeAdminUserList(payload: unknown): AdminUserListResponse {
  const data = asRecord(payload);
  const users = Array.isArray(data.users) ? data.users.filter(isRecord).map(normalizeAdminUser) : [];

  return { users };
}

function normalizeEducatorApproval(payload: unknown): EducatorApprovalResponse {
  const data = asRecord(payload);

  return {
    requestUuid: String(getField(data, "requestUuid", "request_uuid") ?? ""),
    requestStatus: normalizeApprovalStatus(getField(data, "requestStatus", "request_status")),
    submittedAt: String(getField(data, "submittedAt", "submitted_at") ?? ""),
    updatedAt: String(getField(data, "updatedAt", "updated_at") ?? ""),
    reviewedAt: toNullableString(getField(data, "reviewedAt", "reviewed_at")),
    reviewComment: toNullableString(getField(data, "reviewComment", "review_comment")),
    supportingInfo: toNullableString(getField(data, "supportingInfo", "supporting_info")),
    supportingFileUrl: toNullableString(getField(data, "supportingFileUrl", "supporting_file_url")),
    userId: toNonNegativeNumber(getField(data, "userId", "user_id")),
    userUuid: String(getField(data, "userUuid", "user_uuid") ?? ""),
    email: String(data.email ?? ""),
    userName: String(getField(data, "userName", "user_name") ?? ""),
    identity: normalizeIdentity(data.identity),
    accountStatus: String(getField(data, "accountStatus", "account_status") ?? "deactivated"),
    emailVerified: toBoolean(getField(data, "emailVerified", "email_verified")),
    reviewerUserId: toNullableNonNegativeNumber(getField(data, "reviewerUserId", "reviewer_user_id")),
    reviewerUserUuid: toNullableString(getField(data, "reviewerUserUuid", "reviewer_user_uuid")),
    reviewerEmail: toNullableString(getField(data, "reviewerEmail", "reviewer_email")),
    reviewerName: toNullableString(getField(data, "reviewerName", "reviewer_name")),
  };
}

function normalizeEducatorApprovalList(payload: unknown): EducatorApprovalListResponse {
  const data = asRecord(payload);
  const requests = Array.isArray(data.requests)
    ? data.requests.filter(isRecord).map(normalizeEducatorApproval)
    : [];

  return { requests };
}

function normalizeInviteToken(payload: unknown): EducatorInviteTokenResponse {
  const data = asRecord(payload);

  return {
    inviteUuid: String(getField(data, "inviteUuid", "invite_uuid") ?? ""),
    createdAt: String(getField(data, "createdAt", "created_at") ?? ""),
    expiresAt: String(getField(data, "expiresAt", "expires_at") ?? ""),
    usedAt: toNullableString(getField(data, "usedAt", "used_at")),
    isUsed: toBoolean(getField(data, "isUsed", "is_used")),
  };
}

function normalizeGeneratedInviteToken(payload: unknown): EducatorInviteTokenGenerateResponse {
  const data = asRecord(payload);

  return {
    inviteUuid: String(getField(data, "inviteUuid", "invite_uuid") ?? ""),
    rawToken: String(getField(data, "rawToken", "raw_token") ?? ""),
    expiresAt: String(getField(data, "expiresAt", "expires_at") ?? ""),
    inviteUrl: String(getField(data, "inviteUrl", "invite_url") ?? ""),
  };
}

function normalizeInviteTokenList(payload: unknown): EducatorInviteTokenListResponse {
  const data = asRecord(payload);
  const tokens = Array.isArray(data.tokens) ? data.tokens.filter(isRecord).map(normalizeInviteToken) : [];

  return { tokens };
}

function normalizeSendInviteEmailResponse(payload: unknown): SendEducatorInviteEmailResponse {
  const data = asRecord(payload);
  const delivery = asRecord(getField(data, "emailDelivery", "email_delivery"));

  return {
    detail: String(data.detail ?? ""),
    emailDelivery: {
      attempted: toBoolean(data.attempted ?? delivery.attempted),
      delivered: toBoolean(data.delivered ?? delivery.delivered),
      reason: toNullableString(delivery.reason ?? data.reason),
    },
  };
}

function normalizeProviderCredential(payload: unknown): AdminAiProviderCredential {
  const data = asRecord(payload);

  return {
    provider: String(data.provider ?? ""),
    label: String(getField(data, "providerLabel", "provider_label") ?? data.label ?? data.provider ?? ""),
    backendSupported: toBoolean(getField(data, "backendSupported", "backend_supported"), true),
    configured: toBoolean(data.configured ?? getField(data, "hasCredential", "has_credential")),
    keyPreview: toNullableString(getField(data, "apiKeyHint", "api_key_hint") ?? getField(data, "keyPreview", "key_preview")),
    defaultModelId: toNullableString(getField(data, "defaultModelId", "default_model_id")),
    status: String(data.status ?? data.healthStatus ?? "unknown"),
    lastHealthCheckAt: toNullableString(getField(data, "lastCheckedAt", "last_checked_at") ?? getField(data, "lastHealthCheckAt", "last_health_check_at")),
    lastHealthStatus: toNullableString(getField(data, "healthStatus", "health_status") ?? getField(data, "lastHealthStatus", "last_health_status")),
    updatedAt: toNullableString(getField(data, "updatedAt", "updated_at")),
  };
}

function normalizeProviderCredentialList(payload: unknown): AdminAiProviderCredentialListResponse {
  const data = asRecord(payload);
  const rawCredentials = Array.isArray(data.providers)
    ? data.providers
    : Array.isArray(data.credentials)
      ? data.credentials
      : Array.isArray(data.items)
      ? data.items
      : [];

  return {
    credentials: rawCredentials
      .filter(isRecord)
      .map(normalizeProviderCredential)
      .filter((credential) =>
        SUPPORTED_AI_PROVIDERS.has(credential.provider.trim().toLowerCase())
      ),
  };
}

function normalizeProviderCredentialHealth(
  payload: unknown,
  fallbackProvider: string
): AdminAiProviderCredentialHealthResponse {
  const data = asRecord(payload);

  return {
    provider: String(data.provider ?? fallbackProvider),
    status: String(data.status ?? (toBoolean(data.ok) ? "ready" : "blocked")),
    ok: toBoolean(data.ok ?? data.healthy),
    checkedAt: String(getField(data, "checkedAt", "checked_at") ?? ""),
    message: toNullableString(data.message ?? data.detail),
  };
}

function normalizeDefaultModel(payload: unknown): AdminAiDefaultModelResponse {
  const data = asRecord(payload);

  return {
    modelId: String(getField(data, "defaultChatModelId", "default_chat_model_id") ?? getField(data, "modelId", "model_id") ?? ""),
    provider: toNullableString(data.provider),
  };
}

export async function getAdminUsers(
  accessToken: string
): Promise<AdminUserListResponse> {
  void accessToken;

  const response = await fetch(`${API_BASE_URL}/admin/users`, {
    method: "GET",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
  });

  const data = await parseJsonSafe(response);
  handleAuthenticationFailureFromResponse(response.status, data);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "获取用户失败。"));
  }

  return normalizeAdminUserList(data);
}

export async function listAdminAiProviderCredentials(
  accessToken: string
): Promise<AdminAiProviderCredentialListResponse> {
  void accessToken;

  const response = await fetch(AI_ADMIN_PROVIDERS_URL, {
    method: "GET",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
  });

  const data = await parseJsonSafe(response);
  handleAuthenticationFailureFromResponse(response.status, data);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "获取 AI provider key 配置失败。"));
  }

  return normalizeProviderCredentialList(data);
}

export async function saveAdminAiProviderCredential(
  accessToken: string,
  payload: SaveAdminAiProviderCredentialRequest
): Promise<AdminAiProviderCredential> {
  void accessToken;
  const { provider, ...requestBody } = payload;

  const response = await fetch(`${AI_ADMIN_PROVIDERS_URL}/${encodeURIComponent(provider)}/credential`, {
    method: "PUT",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify({
      apiKey: requestBody.apiKey,
      baseUrl: null,
      enabled: true,
    }),
  });

  const data = await parseJsonSafe(response);
  handleAuthenticationFailureFromResponse(response.status, data);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "保存 AI provider key 失败。"));
  }

  return normalizeProviderCredential(data);
}

export async function deleteAdminAiProviderCredential(
  accessToken: string,
  provider: string
): Promise<void> {
  void accessToken;

  const response = await fetch(`${AI_ADMIN_PROVIDERS_URL}/${encodeURIComponent(provider)}/credential`, {
    method: "DELETE",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
  });

  const data = await parseJsonSafe(response);
  handleAuthenticationFailureFromResponse(response.status, data);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "删除 AI provider key 失败。"));
  }
}

export async function checkAdminAiProviderCredentialHealth(
  accessToken: string,
  provider: string
): Promise<AdminAiProviderCredentialHealthResponse> {
  void accessToken;

  const response = await fetch(`${AI_ADMIN_PROVIDERS_URL}/${encodeURIComponent(provider)}/health-check`, {
    method: "POST",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
  });

  const data = await parseJsonSafe(response);
  handleAuthenticationFailureFromResponse(response.status, data);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "AI provider health check 失败。"));
  }

  return normalizeProviderCredentialHealth(data, provider);
}

export async function setAdminAiDefaultModel(
  accessToken: string,
  payload: SetAdminAiDefaultModelRequest
): Promise<AdminAiDefaultModelResponse> {
  void accessToken;

  const response = await fetch(AI_ADMIN_DEFAULTS_URL, {
    method: "PATCH",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify({ defaultChatModelId: payload.modelId }),
  });

  const data = await parseJsonSafe(response);
  handleAuthenticationFailureFromResponse(response.status, data);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "设置默认 AI 模型失败。"));
  }

  return normalizeDefaultModel(data);
}

export async function updateAdminUserIdentity(
  accessToken: string,
  userUuid: string,
  payload: AdminUpdateUserIdentityRequest
): Promise<AdminUserResponse> {
  void accessToken;

  const response = await fetch(`${API_BASE_URL}/admin/users/${userUuid}/identity`, {
    method: "PATCH",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify(payload),
  });

  const data = await parseJsonSafe(response);
  handleAuthenticationFailureFromResponse(response.status, data);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "更新用户身份失败。"));
  }

  return normalizeAdminUser(data);
}

export async function updateAdminUserStatus(
  accessToken: string,
  userUuid: string,
  payload: AdminUpdateUserStatusRequest
): Promise<AdminUserResponse> {
  void accessToken;

  const response = await fetch(`${API_BASE_URL}/admin/users/${userUuid}/status`, {
    method: "PATCH",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify(payload),
  });

  const data = await parseJsonSafe(response);
  handleAuthenticationFailureFromResponse(response.status, data);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "更新用户状态失败。"));
  }

  return normalizeAdminUser(data);
}

export async function getPendingEducatorApprovals(
  accessToken: string
): Promise<EducatorApprovalListResponse> {
  void accessToken;

  const response = await fetch(`${API_BASE_URL}/admin/educator-approvals`, {
    method: "GET",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
  });

  const data = await parseJsonSafe(response);
  handleAuthenticationFailureFromResponse(response.status, data);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "获取待处理教师申请失败。"));
  }

  return normalizeEducatorApprovalList(data);
}

export async function getReviewedEducatorApprovals(
  accessToken: string,
  status: EducatorApprovalHistoryStatus = "reviewed"
): Promise<EducatorApprovalListResponse> {
  void accessToken;

  const response = await fetch(
    `${API_BASE_URL}/admin/educator-approvals/history?status=${encodeURIComponent(status)}`,
    {
      method: "GET",
      headers: buildAuthHeaders({
        "Content-Type": "application/json",
      }),
    }
  );

  const data = await parseJsonSafe(response);
  handleAuthenticationFailureFromResponse(response.status, data);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "获取已审核教师申请失败。"));
  }

  return normalizeEducatorApprovalList(data);
}

export async function getEducatorApprovalDetail(
  accessToken: string,
  requestUuid: string
): Promise<EducatorApprovalResponse> {
  void accessToken;

  const response = await fetch(`${API_BASE_URL}/admin/educator-approvals/${requestUuid}`, {
    method: "GET",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
  });

  const data = await parseJsonSafe(response);
  handleAuthenticationFailureFromResponse(response.status, data);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "获取教师申请详情失败。"));
  }

  return normalizeEducatorApproval(data);
}

export async function reviewEducatorApproval(
  accessToken: string,
  requestUuid: string,
  payload: ReviewEducatorApprovalRequest
): Promise<EducatorApprovalResponse> {
  void accessToken;

  const response = await fetch(`${API_BASE_URL}/admin/educator-approvals/${requestUuid}`, {
    method: "PATCH",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify(payload),
  });

  const data = await parseJsonSafe(response);
  handleAuthenticationFailureFromResponse(response.status, data);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "审核教师申请失败。"));
  }

  return normalizeEducatorApproval(data);
}

export async function generateEducatorInviteToken(
  accessToken: string
): Promise<EducatorInviteTokenGenerateResponse> {
  void accessToken;

  const response = await fetch(`${API_BASE_URL}/admin/educator-invite-tokens`, {
    method: "POST",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
  });

  const data = await parseJsonSafe(response);
  handleAuthenticationFailureFromResponse(response.status, data);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "生成教师邀请链接失败。"));
  }

  return normalizeGeneratedInviteToken(data);
}

export async function sendEducatorInviteEmail(
  accessToken: string,
  inviteUuid: string,
  payload: SendEducatorInviteEmailRequest
): Promise<SendEducatorInviteEmailResponse> {
  void accessToken;

  const response = await fetch(`${API_BASE_URL}/admin/educator-invite-tokens/${inviteUuid}/send-email`, {
    method: "POST",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify(payload),
  });

  const data = await parseJsonSafe(response);
  handleAuthenticationFailureFromResponse(response.status, data);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "发送邀请邮件失败。"));
  }

  return normalizeSendInviteEmailResponse(data);
}

export async function listEducatorInviteTokens(
  accessToken: string
): Promise<EducatorInviteTokenListResponse> {
  void accessToken;

  const response = await fetch(`${API_BASE_URL}/admin/educator-invite-tokens`, {
    method: "GET",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
  });

  const data = await parseJsonSafe(response);
  handleAuthenticationFailureFromResponse(response.status, data);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "获取邀请令牌失败。"));
  }

  return normalizeInviteTokenList(data);
}

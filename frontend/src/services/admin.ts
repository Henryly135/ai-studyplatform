import type { ApiErrorResponse } from "../types/auth";
import type {
  AdminUpdateUserIdentityRequest,
  AdminUpdateUserStatusRequest,
  AdminUserListResponse,
  AdminUserResponse,
  EducatorApprovalHistoryStatus,
  EducatorApprovalListResponse,
  EducatorApprovalResponse,
  EducatorInviteTokenGenerateResponse,
  EducatorInviteTokenListResponse,
  ReviewEducatorApprovalRequest,
  SendEducatorInviteEmailRequest,
} from "../types/admin";
import {
  buildAuthHeaders,
  handleAuthenticationFailureFromResponse,
  parseJsonText,
} from "./api";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

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
    throw new Error(getErrorMessage(data, "Failed to fetch users."));
  }

  return data as AdminUserListResponse;
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
    throw new Error(getErrorMessage(data, "Failed to update user identity."));
  }

  return data as AdminUserResponse;
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
    throw new Error(getErrorMessage(data, "Failed to update user status."));
  }

  return data as AdminUserResponse;
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
    throw new Error(getErrorMessage(data, "Failed to fetch pending educator requests."));
  }

  return data as EducatorApprovalListResponse;
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
    throw new Error(getErrorMessage(data, "Failed to fetch reviewed educator requests."));
  }

  return data as EducatorApprovalListResponse;
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
    throw new Error(getErrorMessage(data, "Failed to fetch educator request details."));
  }

  return data as EducatorApprovalResponse;
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
    throw new Error(getErrorMessage(data, "Failed to review educator request."));
  }

  return data as EducatorApprovalResponse;
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
    throw new Error(getErrorMessage(data, "Failed to generate educator invite link."));
  }

  return data as EducatorInviteTokenGenerateResponse;
}

export async function sendEducatorInviteEmail(
  accessToken: string,
  inviteUuid: string,
  payload: SendEducatorInviteEmailRequest
): Promise<{ detail: string }> {
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
    throw new Error(getErrorMessage(data, "Failed to send invite email."));
  }

  return data as { detail: string };
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
    throw new Error(getErrorMessage(data, "Failed to fetch invite tokens."));
  }

  return data as EducatorInviteTokenListResponse;
}

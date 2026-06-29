import type {
  ApiErrorResponse,
  ChangePasswordRequest,
  CurrentUserResponse,
  CurrentUserPermissionsResponse,
  EducatorInviteRegisterRequest,
  LoginRequest,
  LoginSuccessResponse,
  RegisterRequest,
  RegisterSuccessResponse,
  ResetPasswordRequest,
} from "../types/auth";
import {
  buildAuthHeaders,
  handleAuthenticationFailureFromResponse,
} from "./api";

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

export async function registerUser(
  payload: RegisterRequest
): Promise<RegisterSuccessResponse> {
  console.log("[auth] register request", {
    url: `${API_BASE_URL}/auth/register`,
    payload,
  });

  const response = await fetch(`${API_BASE_URL}/auth/register`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  const data = await parseJsonSafe(response);

  console.log("[auth] register response", {
    status: response.status,
    ok: response.ok,
    data,
  });

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "Register failed."));
  }

  return data as RegisterSuccessResponse;
}

export async function loginUser(
  payload: LoginRequest
): Promise<LoginSuccessResponse> {
  console.log("[auth] login request", {
    url: `${API_BASE_URL}/auth/login`,
    payload,
  });

  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  const data = await parseJsonSafe(response);

  console.log("[auth] login response", {
    status: response.status,
    ok: response.ok,
    data,
  });

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "Login failed."));
  }

  return data as LoginSuccessResponse;
}

export async function verifyEmail(token: string): Promise<{ detail: string }> {
  const response = await fetch(
    `${API_BASE_URL}/auth/verify-email?${new URLSearchParams({ token })}`,
    { method: "GET" }
  );

  const data = await parseJsonSafe(response);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "Email verification failed."));
  }

  return data as { detail: string };
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
    throw new Error(getErrorMessage(data, "Failed to resend verification email."));
  }

  return data as { detail: string };
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
    throw new Error(getErrorMessage(data, "Failed to change password."));
  }

  return data as { detail: string };
}

export async function forgotPassword(email: string): Promise<{ detail: string }> {
  const response = await fetch(`${API_BASE_URL}/auth/forgot-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });

  const data = await parseJsonSafe(response);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "Failed to send reset email."));
  }

  return data as { detail: string };
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
    throw new Error(getErrorMessage(data, "Failed to reset password."));
  }

  return data as { detail: string };
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
    throw new Error(getErrorMessage(data, "Failed to fetch current user."));
  }

  return data as CurrentUserResponse;
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

  return data as { valid: boolean; expiresAt: string };
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
    throw new Error(getErrorMessage(data, "Registration failed."));
  }

  return data as RegisterSuccessResponse;
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
    throw new Error(getErrorMessage(data, "Failed to fetch current user permissions."));
  }

  return data as CurrentUserPermissionsResponse;
}

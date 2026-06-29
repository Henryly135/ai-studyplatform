const AUTHENTICATION_ERROR_MESSAGES = new Set([
  "Invalid credentials",
  "Unable to resolve current user",
]);

const AUTHENTICATION_ERROR_CODES = new Set([
  "INVALID_CREDENTIALS",
  "UNAUTHORIZED",
]);

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
  if (!accessToken) {
    handleAuthenticationFailure();
    throw new Error("Invalid credentials");
  }

  return accessToken;
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

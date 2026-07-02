type Base64Decoder = (value: string) => string;

type JwtPayload = {
  exp?: unknown;
};

function normalizeBase64Url(value: string) {
  const base64 = value.replace(/-/g, "+").replace(/_/g, "/");
  const remainder = base64.length % 4;
  return remainder === 0 ? base64 : `${base64}${"=".repeat(4 - remainder)}`;
}

function decodeJwtPayload(payloadSegment: string, decoder: Base64Decoder): JwtPayload {
  return JSON.parse(decoder(normalizeBase64Url(payloadSegment))) as JwtPayload;
}

export function isUsableAccessToken(
  token: string | null | undefined,
  nowMs = Date.now(),
  decoder: Base64Decoder = globalThis.atob
) {
  if (!token?.trim() || typeof decoder !== "function") {
    return false;
  }

  const parts = token.split(".");
  if (parts.length !== 3 || parts.some((part) => part.length === 0)) {
    return false;
  }

  try {
    const payload = decodeJwtPayload(parts[1], decoder);
    if (typeof payload.exp !== "number" || !Number.isFinite(payload.exp)) {
      return false;
    }

    return payload.exp * 1000 > nowMs;
  } catch {
    return false;
  }
}

DEFAULT_PUBLIC_ID_SECRET = "change-me-in-production-public-id-secret"


def get_public_id_secret(configured_secret: str | None) -> str:
    normalized = (configured_secret or "").strip()
    return normalized or DEFAULT_PUBLIC_ID_SECRET

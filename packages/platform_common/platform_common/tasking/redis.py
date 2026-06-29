def build_redis_url(*, host: str, port: int, db: int = 0, scheme: str = "redis") -> str:
    return f"{scheme}://{host}:{port}/{db}"

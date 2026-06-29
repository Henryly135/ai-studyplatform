from collections.abc import Generator

from sqlalchemy.orm import Session

from app.core.config import settings
from platform_common.db import build_engine, build_session_factory, get_session_dependency


engine = build_engine(database_url=settings.database_url, echo=settings.db_echo, pool_pre_ping=settings.db_pool_pre_ping)

SessionLocal = build_session_factory(engine)


def get_db_session() -> Generator[Session, None, None]:
    yield from get_session_dependency(SessionLocal)

from collections.abc import Callable, Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def build_engine(*, database_url: str, echo: bool, pool_pre_ping: bool) -> Engine:
    return create_engine(
        database_url,
        echo=echo,
        pool_pre_ping=pool_pre_ping,
    )


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def get_session_dependency(session_factory: Callable[[], Session]) -> Generator[Session, None, None]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()

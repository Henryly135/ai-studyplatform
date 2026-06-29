import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


SERVICE_ROOT = Path(__file__).resolve().parent.parent

if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))


@pytest.fixture()
def db_session():
    from app.db.base import Base
    from app.models import (  # noqa: F401
        audit,
        educator_approval_request,
        educator_invite_token,
        permission,
        role,
        role_permission,
        tokens,
        user,
        user_role,
    )

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)

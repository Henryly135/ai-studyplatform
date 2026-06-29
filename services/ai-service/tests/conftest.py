from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest


AI_SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = next(
    (
        parent
        for parent in AI_SERVICE_ROOT.parents
        if (parent / "packages" / "platform_common").exists()
    ),
    AI_SERVICE_ROOT,
)
PLATFORM_COMMON_ROOT = (
    REPO_ROOT / "packages" / "platform_common"
    if (REPO_ROOT / "packages" / "platform_common").exists()
    else Path("/packages/platform_common")
)

for path in (AI_SERVICE_ROOT, REPO_ROOT, PLATFORM_COMMON_ROOT):
    if path.exists() and str(path) not in sys.path:
        sys.path.insert(0, str(path))


try:
    import pgvector.sqlalchemy  # noqa: F401
except ModuleNotFoundError:
    from sqlalchemy.types import JSON, TypeDecorator

    pgvector_module = types.ModuleType("pgvector")
    pgvector_sqlalchemy_module = types.ModuleType("pgvector.sqlalchemy")

    class Vector(TypeDecorator):
        impl = JSON
        cache_ok = True

        def __init__(self, dimensions: int | None = None) -> None:
            super().__init__()
            self.dimensions = dimensions

    pgvector_sqlalchemy_module.Vector = Vector
    pgvector_module.sqlalchemy = pgvector_sqlalchemy_module
    sys.modules["pgvector"] = pgvector_module
    sys.modules["pgvector.sqlalchemy"] = pgvector_sqlalchemy_module


@pytest.fixture
def app():
    from app.main import app as fastapi_app

    return fastapi_app


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient

    from app.api.deps import require_internal_request
    from app.db.session import get_db_session

    def _fake_session():
        yield object()

    app.dependency_overrides[get_db_session] = _fake_session
    app.dependency_overrides[require_internal_request] = lambda: None
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()

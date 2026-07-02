from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.forum import router as forum_router
from app.api.internal_notifications import router as internal_notifications_router
from app.api.notifications import router as notifications_router
from app.core.config import settings
from app.db.session import engine


app = FastAPI(title="Communication Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(forum_router)
app.include_router(internal_notifications_router)
app.include_router(notifications_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Communication service running"}


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "communication-service",
        "database": "mysql",
        "port": str(settings.communication_port),
    }


@app.get("/ready")
def ready() -> dict[str, str]:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    return {"status": "ok", "database": "mysql"}

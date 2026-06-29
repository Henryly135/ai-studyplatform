"""API routers for the AI service."""

from app.api.chat import router as chat_router
from app.api.demo import router as demo_router
from app.api.tasks import router as tasks_router

__all__ = [
    "chat_router",
    "demo_router",
    "tasks_router",
]

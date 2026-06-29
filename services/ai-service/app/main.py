from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.chat import router as chat_router
from app.api.demo import router as demo_router
from app.api.internal_content_generation import router as internal_content_generation_router
from app.api.internal_index_jobs import router as internal_index_jobs_router
from app.api.internal_profiles import router as internal_profiles_router
from app.api.internal_profile_update import router as internal_profile_update_router
from app.api.internal_quiz_generation import router as internal_quiz_generation_router
from app.api.internal_short_answer import router as internal_short_answer_router
from app.api.internal_study_planner import router as internal_study_planner_router
from app.api.profiles import router as profiles_router
from app.api.quiz_generation import router as quiz_generation_router
from app.api.tasks import router as tasks_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.session import engine


configure_logging()


app = FastAPI(
    title="AI Service",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(demo_router)
app.include_router(chat_router)
app.include_router(profiles_router)
app.include_router(quiz_generation_router)
app.include_router(internal_content_generation_router)
app.include_router(internal_index_jobs_router)
app.include_router(internal_profiles_router)
app.include_router(internal_profile_update_router)
app.include_router(internal_quiz_generation_router)
app.include_router(internal_short_answer_router)
app.include_router(internal_study_planner_router)
app.include_router(tasks_router)


def _default_error_code(status_code: int) -> str:
    return {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        404: "NOT_FOUND",
        429: "TOO_MANY_REQUESTS",
        500: "INTERNAL_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
    }.get(status_code, "HTTP_ERROR")


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail and "message" in detail:
        error = detail
    else:
        error = {
            "code": _default_error_code(exc.status_code),
            "message": str(detail),
        }

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": error,
        },
    )


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "AI service running"}


@app.get("/health")
def health() -> dict[str, str]:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    return {
        "status": "ok",
        "database": "postgresql",
        "port": str(settings.ai_service_port),
    }

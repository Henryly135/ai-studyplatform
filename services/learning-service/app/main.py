from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api.admin import router as admin_router
from app.api.course_catalog import router as course_catalog_router
from app.api.course_enrollments import router as course_enrollments_router
from app.api.course_invites import router as course_invites_router
from app.api.course_management import router as course_management_router
from app.api.internal_quiz_generation import router as internal_quiz_generation_router
from app.api.internal_profile_update import router as internal_profile_update_router
from app.api.module_content import router as module_content_router
from app.api.module_management import router as module_management_router
from app.api.quiz import router as quiz_router
from app.api.short_answer import router as short_answer_router
from app.api.study_planner import router as study_planner_router
from app.core.config import settings
from app.db.session import engine


app = FastAPI(title="Learning Content Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

settings.material_root_path.mkdir(parents=True, exist_ok=True)
app.mount("/materials", StaticFiles(directory=settings.material_root_path), name="materials")

app.include_router(course_catalog_router)
app.include_router(course_enrollments_router)
app.include_router(course_invites_router)
app.include_router(course_management_router)
app.include_router(internal_quiz_generation_router)
app.include_router(internal_profile_update_router)
app.include_router(module_content_router)
app.include_router(module_management_router)
app.include_router(quiz_router)
app.include_router(short_answer_router)
app.include_router(study_planner_router)
app.include_router(admin_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Learning content service running"}


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "learning-service",
        "database": "mysql",
        "port": str(settings.learning_port),
    }


@app.get("/ready")
def ready() -> dict[str, str]:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    return {"status": "ok", "database": "mysql"}

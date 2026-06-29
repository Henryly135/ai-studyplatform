from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.quiz_service import QuizService


@celery_app.task(name="app.tasks.quiz_attempts.auto_submit_quiz_attempt_task")
def auto_submit_quiz_attempt_task(session_token: str) -> None:
    session = SessionLocal()
    try:
        QuizService(session).auto_submit_attempt(session_token=session_token)
    finally:
        session.close()

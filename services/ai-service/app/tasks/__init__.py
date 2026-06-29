from app.tasks.smoke import ping_task
from app.tasks.recover_stale_jobs import recover_stale_index_jobs_task
from app.tasks.quiz_generation import generate_quiz_attempt_run_task

__all__ = ["ping_task", "recover_stale_index_jobs_task", "generate_quiz_attempt_run_task"]

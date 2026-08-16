from __future__ import annotations

from app.core.celery_app import celery_app
from app.services.ai_index_job_client import AIIndexJobClient


@celery_app.task(
    bind=True,
    name="app.tasks.material_index_registration.register_material_index_job",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=900,
    max_retries=8,
)
def register_material_index_job(self, payload: dict[str, object]) -> dict[str, object]:
    """Retry AI index registration after the learning transaction is durable."""
    _ = self
    return AIIndexJobClient().register_material_job(**payload)

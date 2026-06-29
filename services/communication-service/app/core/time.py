from datetime import datetime

from platform_common.time import now_local as shared_now_local

from app.core.config import settings


def now_local() -> datetime:
    return shared_now_local(settings.app_timezone)

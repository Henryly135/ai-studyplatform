from datetime import datetime
from zoneinfo import ZoneInfo


def now_local(app_timezone: str) -> datetime:
    return datetime.now(ZoneInfo(app_timezone)).replace(tzinfo=None)

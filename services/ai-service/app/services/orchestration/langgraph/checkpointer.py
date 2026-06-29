from __future__ import annotations

import logging
from functools import lru_cache

from app.core.config import settings


logger = logging.getLogger(__name__)


def build_graph_config(*, thread_id: str, checkpoint_ns: str) -> dict:
    return {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": f"{settings.langgraph_checkpoint_key_prefix}:{checkpoint_ns}",
        }
    }


@lru_cache(maxsize=1)
def get_langgraph_checkpointer():
    if not settings.langgraph_checkpoint_enabled:
        return None

    try:
        try:
            from langgraph.checkpoint.memory import InMemorySaver as MemorySaver
        except Exception:
            from langgraph.checkpoint.memory import MemorySaver
    except Exception:
        logger.exception("Failed to import LangGraph in-memory checkpointer")
        return None

    # Prefer a dedicated Redis-backed saver when available; otherwise keep a
    # process-local saver so graph execution still works with the same API.
    try:
        from langgraph.checkpoint.redis import RedisSaver  # type: ignore

        saver = RedisSaver.from_conn_string(settings.langgraph_checkpoint_redis_url)
        setup = getattr(saver, "setup", None)
        if callable(setup):
            setup()
        logger.info(
            "Using Redis-backed LangGraph checkpointer",
            extra={"redisUrl": settings.langgraph_checkpoint_redis_url},
        )
        return saver
    except Exception:
        logger.warning(
            "Redis-backed LangGraph checkpointer unavailable; falling back to in-memory saver",
            extra={"redisUrl": settings.langgraph_checkpoint_redis_url},
        )
        return MemorySaver()

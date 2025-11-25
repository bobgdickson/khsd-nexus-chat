from __future__ import annotations

import logging
import os
from functools import lru_cache

from langfuse import get_client
from openinference.instrumentation.openai_agents import OpenAIAgentsInstrumentor

logger = logging.getLogger(__name__)

REQUIRED_ENV_VARS = ("LANGFUSE_SECRET_KEY", "LANGFUSE_PUBLIC_KEY")


@lru_cache(maxsize=1)
def configure_langfuse_tracing() -> bool:
    """Set up Langfuse + OpenInference instrumentation for OpenAI Agents."""

    missing = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
    if missing:
        logger.info(
            "Langfuse tracing disabled; missing environment variables: %s",
            ", ".join(missing),
        )
        return False

    try:
        get_client()
        OpenAIAgentsInstrumentor().instrument()
        logger.info("Langfuse OpenAI Agents instrumentation enabled.")
        return True
    except Exception:  # pragma: no cover - defensive
        logger.exception("Failed to configure Langfuse tracing.")
        return False

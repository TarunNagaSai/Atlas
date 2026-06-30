"""Logfire observability — wiring + the project logger.

Configures Pydantic Logfire for backend instrumentation:
- FastAPI: every HTTP request/response + Pydantic validation traces
- psycopg2: every DB query with duration and SQL text
- httpx: outbound HTTP calls (Gemini API, OpenAI, etc.)

It also routes Python's standard ``logging`` into Logfire, so log lines from our
own modules (via ``get_logger``) AND third-party libraries (uvicorn, google-genai,
psycopg, ...) land in the same trace stream as our spans instead of leaking to a
bare stdout. ``get_logger(__name__)`` is the one logging entry point for the app.

LOGFIRE_TOKEN in env sends traces to the Logfire platform.
If not set, traces are emitted to the local console (useful for dev).
"""

from __future__ import annotations

import logging
import os

import logfire

from app.schema.llm_settings import get_settings


def configure_logfire() -> None:
    token = os.getenv("LOGFIRE_TOKEN")
    logfire.configure(
        service_name="atlas-backend",
        send_to_logfire=bool(token),
    )
    logfire.instrument_psycopg()
    logfire.instrument_httpx()

    # Funnel the stdlib logging tree into Logfire. Must run after configure() so the
    # handler has a configured backend to emit to.
    logging.basicConfig(
        level=getattr(logging, get_settings().log_level, logging.INFO),
        handlers=[logfire.LogfireLoggingHandler()],
    )


def get_logger(name: str) -> logging.Logger:
    """Return a stdlib logger whose records flow into Logfire.

    Use this for plain log lines (``get_logger(__name__).info(...)``). Reach for
    ``logfire.span(...)`` / ``logfire.info(...)`` directly when you want a timed,
    nested span or structured event attached to the current trace.
    """
    return logging.getLogger(name)

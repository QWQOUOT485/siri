"""Safe local logging helpers."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


class SecretRedactionFilter(logging.Filter):
    _secret_names = ("api_key", "x-api-key", "authorization", "confirmation_token", "token")

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        lowered = message.casefold()
        if any(name in lowered for name in self._secret_names):
            record.msg = "[sensitive event redacted]"
            record.args = ()
        return True


def configure_logging(log_path: Path, level: str = "INFO") -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("siri_agent")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False
    if logger.handlers:
        return logger
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    file_handler = RotatingFileHandler(log_path, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.addFilter(SecretRedactionFilter())
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(SecretRedactionFilter())
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


def safe_log_fields(fields: dict[str, Any]) -> dict[str, Any]:
    hidden = {"api_key", "authorization", "x-api-key", "confirmation_token", "token"}
    return {key: "[redacted]" if key.casefold() in hidden else value for key, value in fields.items()}


def audit_event(logger: logging.Logger, *, client_ip: str | None, action: str, target: str | None, success: bool, duration_ms: float, error_code: str | None = None) -> None:
    """Write required audit fields without logging secrets or newlines."""

    def clean(value: Any) -> str:
        return str(value or "").replace("\r", " ").replace("\n", " ")[:200]

    logger.info(
        "audit client_ip=%s action=%s target=%s result=%s duration_ms=%.2f error_code=%s",
        clean(client_ip),
        clean(action),
        clean(target),
        "success" if success else "failure",
        duration_ms,
        clean(error_code),
    )

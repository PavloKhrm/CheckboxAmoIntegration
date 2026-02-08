import json
import logging
import sys
from typing import Any, Dict


_RESERVED_LOG_RECORD_KEYS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys())


class LessThanLevelFilter(logging.Filter):
    def __init__(self, exclusive_max_level: int) -> None:
        super().__init__()
        self.exclusive_max_level = exclusive_max_level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno < self.exclusive_max_level


class ExtraFieldsFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extras: Dict[str, Any] = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _RESERVED_LOG_RECORD_KEYS and not key.startswith("_")
        }
        if not extras:
            return base
        try:
            extras_json = json.dumps(extras, ensure_ascii=False, default=str, sort_keys=True)
        except Exception:
            extras_json = str(extras)
        return f"{base} {extras_json}"


def configure_logging(level_name: str) -> None:
    level = getattr(logging, level_name, logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    formatter = ExtraFieldsFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(level)
    stdout_handler.addFilter(LessThanLevelFilter(logging.ERROR))
    stdout_handler.setFormatter(formatter)

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(max(level, logging.ERROR))
    stderr_handler.setFormatter(formatter)

    root_logger.handlers = [stdout_handler, stderr_handler]

"""Logging estructurado JSON + rotación para Flor de Sal.

No añade dependencias externas: formateador JSON "hand-rolled" con stdlib.
Uso:
    from src.log_config import setup_logging, get_logger
    setup_logging(level="INFO", json=True, log_file="logs/app.log")
    log = get_logger(__name__)
    log.info("run_daily start", extra={"date": "2026-07-15", "n_iter": 1000})
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


# ----------------------------------------------------------------------
# Formateador JSON personalizado (sin dependencias externas)
# ----------------------------------------------------------------------
class JsonFormatter(logging.Formatter):
    """Formateador que emite una línea JSON por registro.

    Campos estándar:
        timestamp: ISO 8601 UTC (ej. "2026-07-15T06:12:34.123Z")
        level: nivel (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        logger: nombre del logger (ej. "src.pipeline")
        message: mensaje formateado
        module, funcName, lineno: origen de la llamada
        extra: cualquier clave extra pasada en `extra={...}`
    """

    def format(self, record: logging.LogRecord) -> str:
        # Timestamp en UTC ISO 8601 con milisegundos
        ts = datetime.fromtimestamp(record.created, tz=UTC).isoformat(
            timespec="milliseconds"
        ).replace("+00:00", "Z")

        # Mensaje formateado (con args si los hay)
        msg = record.getMessage()

        # Campos base
        log_dict: dict[str, Any] = {
            "timestamp": ts,
            "level": record.levelname,
            "logger": record.name,
            "message": msg,
            "module": record.module,
            "funcName": record.funcName,
            "lineno": record.lineno,
        }

        # Añade campos extra (todo lo que no sea atributo estándar de LogRecord)
        standard_attrs = {
            "name", "msg", "args", "created", "filename", "funcName", "levelname",
            "levelno", "lineno", "module", "msecs", "message", "pathname",
            "process", "processName", "relativeCreated", "thread", "threadName",
            "exc_info", "exc_text", "stack_info", "getMessage",
        }
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                log_dict[key] = value

        # Excepción si la hay
        if record.exc_info:
            log_dict["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_dict, ensure_ascii=False)


# ----------------------------------------------------------------------
# Formateador texto legible (para desarrollo / consola)
# ----------------------------------------------------------------------
class TextFormatter(logging.Formatter):
    """Formateador texto compacto: timestamp level logger message [extra]"""

    def __init__(self):
        super().__init__(
            fmt="%(asctime)s %(levelname)-8s %(name)s %(message)s",
            datefmt="%H:%M:%S",
        )

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        # Añade extra al final si existe
        standard_attrs = {
            "name", "msg", "args", "created", "filename", "funcName", "levelname",
            "levelno", "lineno", "module", "msecs", "message", "pathname",
            "process", "processName", "relativeCreated", "thread", "threadName",
            "exc_info", "exc_text", "stack_info", "getMessage",
        }
        extras = {
            k: v for k, v in record.__dict__.items()
            if k not in standard_attrs and not k.startswith("_")
        }
        if extras:
            base += f" {json.dumps(extras, ensure_ascii=False)}"
        return base


# ----------------------------------------------------------------------
# Configuración pública
# ----------------------------------------------------------------------
def setup_logging(
    level: str = "INFO",
    json: bool = True,
    log_file: str | None = None,
    max_bytes: int = 5 * 1024 * 1024,  # 5 MB
    backup_count: int = 3,
) -> None:
    """Configura el logging global.

    Args:
        level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        json: True → JSON lines en stdout; False → texto legible.
        log_file: Ruta opcional a fichero rotativo (RotatingFileHandler, 5 MB, 3 backups).
        max_bytes: Tamaño máximo del fichero antes de rotar.
        backup_count: Número de backups a conservar.
    """
    # Nivel
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Handler stdout
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(JsonFormatter() if json else TextFormatter())

    # Handlers
    handlers: list[logging.Handler] = [stdout_handler]

    # Handler fichero rotativo (opcional)
    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        file_handler.setFormatter(JsonFormatter())
        handlers.append(file_handler)

    # Configuración raíz
    logging.basicConfig(
        level=numeric_level,
        handlers=handlers,
        force=True,  # sobrescribe configuración previa (útil en tests / re-inicio)
    )

    # Silencia loggers ruidosos de terceros
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("streamlit").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Obtiene un logger configurado.

    Args:
        name: Normalmente `__name__` del módulo llamante.

    Returns:
        Logger listo para usar con `.info()`, `.debug()`, `.warning()`, etc.
    """
    return logging.getLogger(name)

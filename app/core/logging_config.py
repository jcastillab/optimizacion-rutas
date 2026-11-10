"""Logs JSON por línea (archivo rotativo + consola) y middleware de request."""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from starlette.datastructures import MutableHeaders

from app.core.errores import respuesta_500

log = logging.getLogger("transporte")
_CAMPOS = ("request_id", "usuario", "metodo", "ruta", "estado", "ms")


class FormatoJson(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        d = {
            "fecha": datetime.fromtimestamp(record.created, UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "nivel": record.levelname,
            "mensaje": record.getMessage(),
        }
        d.update({c: getattr(record, c, None) for c in _CAMPOS})
        if record.exc_info:
            d["traza"] = self.formatException(record.exc_info)
        return json.dumps(d, ensure_ascii=False)


def cerrar_logging() -> None:
    for h in list(log.handlers):
        log.removeHandler(h)
        h.close()


def configurar_logging(logs_dir: Path) -> None:
    """Idempotente: reemplaza los handlers (las pruebas cambian de carpeta)."""
    cerrar_logging()
    logs_dir.mkdir(parents=True, exist_ok=True)
    log.setLevel(logging.INFO)
    log.propagate = False
    fmt = FormatoJson()
    for h in (RotatingFileHandler(logs_dir / "app.log", maxBytes=2 * 1024 * 1024, backupCount=5, encoding="utf-8"),
              logging.StreamHandler()):
        h.setFormatter(fmt)
        log.addHandler(h)


class MiddlewareRequest:
    """ASGI puro: asigna request_id, añade X-Request-ID, registra y convierte
    las excepciones no controladas en un 500 genérico (la traza solo va al log)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        rid = uuid.uuid4().hex[:8]
        state = scope.setdefault("state", {})
        state.update(request_id=rid, usuario=None)
        inicio = time.perf_counter()
        estado = {"codigo": 500, "iniciada": False}

        async def enviar(msg):
            if msg["type"] == "http.response.start":
                estado.update(codigo=msg["status"], iniciada=True)
                MutableHeaders(scope=msg)["X-Request-ID"] = rid
            await send(msg)

        def extra():
            return {"request_id": rid, "usuario": state.get("usuario"), "metodo": scope["method"],
                    "ruta": scope["path"], "estado": estado["codigo"],
                    "ms": round((time.perf_counter() - inicio) * 1000, 1)}

        try:
            await self.app(scope, receive, enviar)
        except Exception:
            if not estado["iniciada"]:
                await respuesta_500(rid)(scope, receive, enviar)
            log.exception("Error no controlado", extra=extra())
        log.info("request", extra=extra())

"""Middleware ASGI: hosts permitidos (anti DNS rebinding) y cabeceras de seguridad."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
import uuid

from starlette.datastructures import MutableHeaders

log = logging.getLogger("transporte")
SIN_CSP = ("/api/docs",)  # Swagger UI carga scripts de un CDN


def hashes_scripts_inline(html: str) -> list[str]:
    """Fuentes CSP ``'sha256-...'`` de los ``<script>`` sin ``src`` del index (p. ej. el de Angular/beasties)."""
    return ["'sha256-" + base64.b64encode(hashlib.sha256(s.encode()).digest()).decode() + "'"
            for s in re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.DOTALL)]


def construir_csp(hashes: list[str]) -> str:
    return "; ".join([
        "default-src 'self'",
        "script-src 'self' " + " ".join(hashes) if hashes else "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",  # Angular inserta el CSS crítico en un <style>
        "img-src 'self' data:",
        "font-src 'self' data:",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ])


def _host_sin_puerto(host: str) -> str:
    if host.startswith("["):  # IPv6: [::1]:8000
        return host[: host.find("]") + 1]
    return host.split(":")[0]


class MiddlewareSeguridad:
    def __init__(self, app, hosts: list[str], csp: str):
        self.app, self.hosts, self.csp = app, {h.lower() for h in hosts}, csp

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope["headers"])
        host = _host_sin_puerto(headers.get(b"host", b"").decode("latin-1").lower())
        ruta = scope["path"]

        rid = uuid.uuid4().hex[:8]

        async def enviar(msg):
            if msg["type"] == "http.response.start":
                h = MutableHeaders(scope=msg)
                if "X-Request-ID" not in h:  # lo pone MiddlewareRequest; aquí solo en rechazos tempranos
                    h["X-Request-ID"] = rid
                h["X-Content-Type-Options"] = "nosniff"
                h["X-Frame-Options"] = "DENY"
                h["Referrer-Policy"] = "same-origin"
                if not ruta.startswith(SIN_CSP):
                    h["Content-Security-Policy"] = self.csp
            await send(msg)

        if host not in self.hosts:
            cuerpo = json.dumps({"error": {"codigo": "HOST_NO_PERMITIDO", "mensaje": "Host no permitido.",
                                           "detalle": None, "request_id": rid}}).encode()
            log.warning("host no permitido: %r", host, extra={"request_id": rid, "metodo": scope["method"],
                                                              "ruta": scope["path"], "estado": 400})
            await enviar({"type": "http.response.start", "status": 400,
                          "headers": [(b"content-type", b"application/json"),
                                      (b"content-length", str(len(cuerpo)).encode())]})
            await send({"type": "http.response.body", "body": cuerpo})
            return
        await self.app(scope, receive, enviar)

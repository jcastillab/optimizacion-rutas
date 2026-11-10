# ruff: noqa: B008  (idioma de FastAPI: Depends/Body en los valores por defecto)
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from app.api.deps import get_db
from app.core.config import settings
from app.db.modelos import Usuario

router = APIRouter(tags=["salud"])


@router.get("/salud")
def salud(db=Depends(get_db)):
    """Consulta real sobre ``usuarios``: una base de versión anterior o dañada responde 503, no "ok"."""
    try:
        db.scalar(select(func.count()).select_from(Usuario))
        bd = "ok"
    except Exception:  # noqa: BLE001  (la salud debe responder, sea cual sea el fallo)
        bd = "error"
    cuerpo = {"estado": "ok" if bd == "ok" else "error", "version": settings.version, "base_datos": bd}
    if bd != "ok":
        cuerpo["mensaje"] = "La base de datos no responde o no coincide con la versión de la aplicación."
    return JSONResponse(cuerpo, status_code=200 if bd == "ok" else 503)

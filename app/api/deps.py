"""Dependencias: sesión de base de datos, usuario actual, rol admin, origen."""
# ruff: noqa: B008  (idioma de FastAPI: Depends/Body en los valores por defecto)

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated
from urllib.parse import urlparse

from fastapi import Depends, Path, Query, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errores import NoAutenticado, SinPermiso
from app.core.seguridad import hash_token
from app.db.base import ahora
from app.db.modelos import Usuario
from app.repository import usuarios as repo_usuarios
from app.schemas.comun import MAX_ID

COOKIE = "sesion"

# Parámetros acotados: ids de ruta y paginación (pagina * por_pagina cabe en 64 bits).
IdPath = Annotated[int, Path(ge=1, le=MAX_ID)]
PaginaQ = Annotated[int, Query(ge=1, le=settings.pagina_max)]
PorPaginaQ = Annotated[int, Query(ge=1, le=settings.por_pagina_max)]


def solo_lectura(endpoint):
    """Marca un endpoint POST que no escribe hasta el final: su sesión usa BEGIN diferido."""
    endpoint.lectura = True
    return endpoint


def get_db(request: Request) -> Iterator[Session]:
    ruta = request.scope.get("route")
    lectura = request.method in ("GET", "HEAD") or getattr(getattr(ruta, "endpoint", None), "lectura", False)
    with request.app.state.sessionmaker() as db:  # cierra y revierte lo no confirmado
        db.info["lectura"] = lectura
        yield db


def usuario_actual(request: Request, db: Session = Depends(get_db)) -> Usuario:
    token = request.cookies.get(COOKIE)
    usuario = repo_usuarios.usuario_de_sesion(db, hash_token(token), ahora()) if token else None
    if usuario is None:
        raise NoAutenticado("Tu sesión no es válida o venció. Inicia sesión de nuevo.")
    request.scope["state"]["usuario"] = usuario.usuario
    return usuario


def requiere_admin(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
    if usuario.rol != "admin":
        raise SinPermiso("Solo un administrador puede hacer esto.")
    return usuario


def _origen_ok(valor: str, host: str | None) -> bool:
    return urlparse(valor).netloc == host or valor.rstrip("/") in settings.origenes_permitidos


def verificar_origen(request: Request) -> None:
    """Defensa CSRF extra a SameSite para escrituras (POST/PATCH/DELETE).

    - Si trae ``Origin`` (todo navegador lo envía en escrituras): debe ser el del servidor o uno de
      ``origenes_permitidos``. Vacío o ``null`` se rechaza.
    - Si no trae ``Origin`` pero trae la cookie de sesión: se exige un ``Referer`` del mismo origen.
    - Sin ``Origin`` ni cookie de sesión (curl, scripts, el propio login): se permite; sin cookie no hay
      sesión que secuestrar.
    """
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    host = request.headers.get("host")
    origen = request.headers.get("origin")
    if origen is not None:
        permitido = bool(origen) and _origen_ok(origen, host)
    elif request.cookies.get(COOKIE):
        referer = request.headers.get("referer", "")
        permitido = bool(referer) and _origen_ok(
            f"{urlparse(referer).scheme}://{urlparse(referer).netloc}", host)
    else:
        permitido = True
    if not permitido:
        raise SinPermiso("Origen de la solicitud no permitido.")

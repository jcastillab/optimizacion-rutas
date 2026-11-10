# ruff: noqa: B008  (idioma de FastAPI: Depends/Body en los valores por defecto)
from __future__ import annotations

import logging
import math
from datetime import timedelta

from fastapi import APIRouter, Depends, Request, Response

from app.api.deps import COOKIE, get_db, usuario_actual
from app.core.config import settings
from app.core.errores import DemasiadosIntentos, NoAutenticado
from app.core.seguridad import hash_falso, hash_token, nuevo_token, verificar_clave
from app.db.base import ahora
from app.db.modelos import Sesion, Usuario
from app.repository import intentos
from app.repository import usuarios as repo
from app.repository.auditoria import registrar
from app.schemas.usuarios import LoginIn, UsuarioOut

log = logging.getLogger("transporte")
router = APIRouter(prefix="/auth", tags=["auth"])


def _bloqueo(segundos: int) -> DemasiadosIntentos:
    minutos = max(1, math.ceil(segundos / 60))
    return DemasiadosIntentos(f"Demasiados intentos fallidos. Intenta de nuevo en {minutos} "
                              f"{'minuto' if minutos == 1 else 'minutos'}.")


@router.post("/login", response_model=UsuarioOut)
def login(datos: LoginIn, request: Request, response: Response, db=Depends(get_db)):
    """Misma respuesta exista o no el usuario: el contador es por nombre y la IP tiene su propio tope."""
    ahora_ = ahora()
    nombre = datos.usuario  # ya validado y en minúsculas (LoginIn)
    ip = request.client.host if request.client else "desconocida"
    limitador = request.app.state.limitador
    if limitador.bloqueada(ip):
        log.warning("login bloqueado por IP", extra={"usuario": nombre})
        raise _bloqueo(settings.ip_ventana_min * 60)
    espera = intentos.segundos_restantes(db, nombre, ahora_)
    if espera:
        log.warning("login bloqueado por intentos", extra={"usuario": nombre})
        raise _bloqueo(espera)

    u = repo.por_nombre(db, nombre)
    # Se verifica siempre (con un hash falso si no existe) para no delatar usuarios por el tiempo.
    ok = verificar_clave(datos.clave, u.clave_hash if u else hash_falso()) and u is not None and u.activo
    if not ok:
        limitador.registrar_fallo(ip)
        bloqueado = intentos.registrar_fallo(db, nombre, ahora_)
        if u:  # los intentos sobre nombres inexistentes solo van al log (no crecen en `eventos`)
            registrar(db, request, "login_fallido", "usuario", u.id, None, usuario=nombre)
        else:
            log.warning("login fallido de usuario inexistente", extra={"usuario": nombre})
        db.commit()
        if bloqueado:
            raise _bloqueo(intentos.segundos_restantes(db, nombre, ahora_))
        raise NoAutenticado("Usuario o clave incorrectos.")

    intentos.limpiar(db, nombre)
    repo.borrar_sesiones_vencidas(db, ahora_)
    token = nuevo_token()
    db.add(Sesion(token_hash=hash_token(token), usuario_id=u.id,
                  expira=ahora_ + timedelta(hours=settings.sesion_horas)))
    registrar(db, request, "login", "usuario", u.id, None, usuario=u.usuario)
    db.commit()
    response.set_cookie(COOKIE, token, max_age=settings.sesion_horas * 3600, httponly=True, samesite="lax",
                        path="/", secure=request.url.scheme == "https")
    request.scope["state"]["usuario"] = u.usuario
    return u


@router.post("/logout", status_code=204)
def logout(request: Request, db=Depends(get_db)):
    """Idempotente: sin sesión válida también responde 204."""
    token = request.cookies.get(COOKIE)
    if token:
        u = repo.usuario_de_sesion(db, hash_token(token), ahora())
        repo.borrar_sesion(db, hash_token(token))
        if u:
            registrar(db, request, "logout", "usuario", u.id, None, usuario=u.usuario)
        db.commit()
    resp = Response(status_code=204)
    resp.delete_cookie(COOKIE, path="/")
    return resp


@router.get("/yo", response_model=UsuarioOut)
def yo(u: Usuario = Depends(usuario_actual)):
    return u

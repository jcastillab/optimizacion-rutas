# ruff: noqa: B008  (idioma de FastAPI: Depends/Body en los valores por defecto)
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.exc import IntegrityError

from app.api.deps import COOKIE, IdPath, PaginaQ, PorPaginaQ, get_db, requiere_admin
from app.core.config import settings
from app.core.errores import Conflicto
from app.core.seguridad import hash_clave, hash_token
from app.db.modelos import Usuario
from app.repository import intentos
from app.repository import usuarios as repo
from app.repository.auditoria import cambios, registrar
from app.repository.base import listar, obtener
from app.schemas.comun import Pagina
from app.schemas.usuarios import UsuarioEdit, UsuarioIn, UsuarioOut

router = APIRouter(prefix="/usuarios", tags=["usuarios"], dependencies=[Depends(requiere_admin)])


def _ver(u: Usuario) -> dict:
    return UsuarioOut.model_validate(u).model_dump(mode="json")  # nunca incluye la clave


@router.get("", response_model=Pagina[UsuarioOut])
def lista(pagina: PaginaQ = 1, por_pagina: PorPaginaQ = settings.por_pagina_defecto, q: Annotated[str | None, Query(max_length=100)] = None,
          db=Depends(get_db)):
    items, total = listar(db, Usuario, pagina, por_pagina, q=q, cols_busqueda=("usuario", "nombre"))
    return {"items": items, "total": total, "pagina": pagina, "por_pagina": por_pagina}


@router.get("/{id_}", response_model=UsuarioOut)
def uno(id_: IdPath, db=Depends(get_db)):
    return obtener(db, Usuario, id_, "El usuario")


@router.post("", response_model=UsuarioOut, status_code=201)
def crear(datos: UsuarioIn, request: Request, db=Depends(get_db)):
    u = Usuario(usuario=datos.usuario, nombre=datos.nombre, rol=datos.rol, clave_hash=hash_clave(datos.clave))
    db.add(u)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise Conflicto("Ya existe un usuario con ese nombre de usuario.",
                        [{"campo": "usuario", "mensaje": "Ya existe."}]) from None
    registrar(db, request, "crear", "usuario", u.id, {"despues": _ver(u)})
    db.commit()
    return u


@router.patch("/{id_}", response_model=UsuarioOut)
def editar(id_: IdPath, datos: UsuarioEdit, request: Request, db=Depends(get_db),
           actual: Usuario = Depends(requiere_admin)):
    u = obtener(db, Usuario, id_, "El usuario")
    campos = datos.model_dump(exclude_unset=True)
    clave = campos.pop("clave", None)
    antes = _ver(u)
    nuevo_rol, nuevo_activo = campos.get("rol", u.rol), campos.get("activo", u.activo)
    if u.rol == "admin" and u.activo and not (nuevo_rol == "admin" and nuevo_activo) \
            and repo.otros_admins_activos(db, u.id) == 0:
        raise Conflicto("No se puede desactivar ni degradar al último administrador activo.")
    for k, v in campos.items():
        setattr(u, k, v)
    if clave:
        u.clave_hash = hash_clave(clave)
        intentos.limpiar(db, u.usuario)
    if clave or not nuevo_activo:
        # Cierra las sesiones abiertas; quien cambia su propia clave conserva la sesión actual.
        propia = actual.id == u.id and clave and nuevo_activo
        repo.borrar_sesiones_de(db, u.id, excepto=hash_token(request.cookies.get(COOKIE, "")) if propia else None)
    db.flush()
    despues = _ver(u)
    detalle = cambios(antes, despues)
    if clave:
        detalle = {**(detalle or {}), "clave": "cambiada"}
    if detalle:
        registrar(db, request, "editar", "usuario", u.id, detalle)
    db.commit()
    return u

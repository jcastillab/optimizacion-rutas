"""Fábrica de routers CRUD: paginación, filtros, validación de referencias,
409 por duplicado/dependencias y auditoría (antes → después) automática."""
# ruff: noqa: B008  (idioma de FastAPI: Depends/Body en los valores por defecto)

# Sin ``from __future__ import annotations``: FastAPI necesita las clases reales
# (parámetros de las funciones internas) al registrar cada ruta.

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import (
    IdPath,
    PaginaQ,
    PorPaginaQ,
    get_db,
    requiere_admin,
    usuario_actual,
)
from app.core.config import settings
from app.core.errores import Conflicto, Validacion
from app.repository.auditoria import cambios, registrar
from app.repository.base import listar, obtener
from app.schemas.comun import MAX_ID, Pagina


def _bool(v: str) -> bool:
    if v.lower() in ("true", "1"):
        return True
    if v.lower() in ("false", "0"):
        return False
    raise ValueError


def _int(v: str) -> int:
    n = int(v)
    if not 1 <= n <= MAX_ID:
        raise ValueError
    return n


def _conflicto(e: IntegrityError, que: str, borrando: bool) -> Conflicto:
    texto = str(e.orig)
    if borrando or "FOREIGN KEY" in texto:
        return Conflicto(f"No se puede borrar {que}: tiene registros asociados. Desactívalo en su lugar.")
    campos = [c.split(".")[-1] for c in texto.split(":", 1)[-1].split(",")] if "UNIQUE" in texto else []
    return Conflicto(f"Ya existe {que} con los mismos datos ({', '.join(c.strip() for c in campos)})."
                     if campos else f"El dato choca con otro existente de {que}.",
                     [{"campo": c.strip(), "mensaje": "Ya existe."} for c in campos] or None)


def crear_router_crud(*, prefijo: str, tag: str, entidad: str, modelo, entrada, edicion, salida,
                      buscar: tuple[str, ...], articulo: str, que: str,
                      filtros: dict[str, str] | None = None, refs: dict[str, type] | None = None) -> APIRouter:
    """``articulo``: 'La persona' (para "La persona 12 no existe."); ``que``: 'una persona'.
    ``filtros``: {columna: 'bool'|'int'}; ``refs``: {campo: Modelo} que debe existir (422)."""
    filtros, refs = filtros or {}, refs or {}
    conv = {"bool": _bool, "int": _int}
    router = APIRouter(prefix=prefijo, tags=[tag])

    def validar_refs(db: Session, datos: dict) -> None:
        malos = [{"campo": c, "mensaje": "No existe."} for c, m in refs.items()
                 if datos.get(c) is not None and db.get(m, datos[c]) is None]
        if malos:
            raise Validacion("Hay referencias a registros que no existen.", malos)

    def confirmar(db: Session, borrando: bool = False) -> None:
        try:
            db.flush()
        except IntegrityError as e:
            db.rollback()
            raise _conflicto(e, que, borrando) from e

    def ver(obj) -> dict:
        return salida.model_validate(obj).model_dump(mode="json")

    @router.get("", response_model=Pagina[salida])
    def listar_(request: Request, pagina: PaginaQ = 1, por_pagina: PorPaginaQ = settings.por_pagina_defecto,
                q: Annotated[str | None, Query(max_length=100)] = None, db: Session = Depends(get_db), _=Depends(usuario_actual)):
        condiciones = []
        for campo, tipo in filtros.items():
            if campo in request.query_params:
                try:
                    condiciones.append(getattr(modelo, campo) == conv[tipo](request.query_params[campo]))
                except ValueError:
                    raise Validacion("Hay datos no válidos en la solicitud.",
                                     [{"campo": campo, "mensaje": "Valor no válido."}]) from None
        items, total = listar(db, modelo, pagina, por_pagina, q=q, cols_busqueda=buscar, condiciones=condiciones)
        return {"items": items, "total": total, "pagina": pagina, "por_pagina": por_pagina}

    @router.get("/{id_}", response_model=salida)
    def uno(id_: IdPath, db: Session = Depends(get_db), _=Depends(usuario_actual)):
        return obtener(db, modelo, id_, articulo)

    @router.post("", response_model=salida, status_code=201)
    def crear(datos: entrada, request: Request, db: Session = Depends(get_db), _=Depends(requiere_admin)):
        valores = datos.model_dump()
        validar_refs(db, valores)
        obj = modelo(**valores)
        db.add(obj)
        confirmar(db)
        registrar(db, request, "crear", entidad, obj.id, {"despues": ver(obj)})
        db.commit()
        return obj

    @router.patch("/{id_}", response_model=salida)
    def editar(id_: IdPath, datos: edicion, request: Request, db: Session = Depends(get_db),
               _=Depends(requiere_admin)):
        obj = obtener(db, modelo, id_, articulo)
        campos = datos.model_dump(exclude_unset=True)
        validar_refs(db, campos)
        antes = ver(obj)
        for k, v in campos.items():
            setattr(obj, k, v)
        confirmar(db)
        despues = ver(obj)
        if detalle := cambios(antes, despues):
            registrar(db, request, "editar", entidad, obj.id, detalle)
        db.commit()
        return obj

    @router.delete("/{id_}", status_code=204)
    def borrar(id_: IdPath, request: Request, db: Session = Depends(get_db), _=Depends(requiere_admin)):
        obj = obtener(db, modelo, id_, articulo)
        antes = ver(obj)
        db.delete(obj)
        confirmar(db, borrando=True)
        registrar(db, request, "borrar", entidad, id_, {"antes": antes})
        db.commit()
        return Response(status_code=204)

    return router

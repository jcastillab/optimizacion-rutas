"""Consultas genéricas: obtener por id, lista paginada con búsqueda y condiciones."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errores import NoEncontrado
from app.db.base import plegar


def obtener(db: Session, modelo, id_: int, texto: str):
    """El registro o NoEncontrado("<texto> <id> no existe."), p. ej. texto="La persona"."""
    obj = db.get(modelo, id_)
    if obj is None:
        raise NoEncontrado(f"{texto} {id_} no existe.")
    return obj


def listar(db: Session, modelo, pagina: int, por_pagina: int, *, q: str | None = None,
           cols_busqueda: tuple[str, ...] = (), condiciones: list | tuple = (), orden=None,
           opciones: tuple = ()) -> tuple[list, int]:
    """``q`` busca sin distinguir mayúsculas ni tildes (``plegar`` en SQLite); ``%`` y ``_`` son texto."""
    stmt = select(modelo).where(*condiciones)
    if q and cols_busqueda:
        patron = "%" + plegar(q).replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_") + "%"
        stmt = stmt.where(or_(*[func.plegar(getattr(modelo, c)).like(patron, escape="\\")
                                for c in cols_busqueda]))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    orden = orden if orden is not None else modelo.id
    stmt = stmt.options(*opciones).order_by(orden).offset((pagina - 1) * por_pagina).limit(por_pagina)
    return list(db.scalars(stmt)), total

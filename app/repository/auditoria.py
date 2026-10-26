"""Auditoría: escribe en ``eventos`` dentro de un SAVEPOINT; nunca tumba la operación."""

from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from app.db.modelos import Evento

log = logging.getLogger("transporte")


def registrar_evento(db: Session, accion: str, *, usuario: str | None = None, entidad: str | None = None,
                     entidad_id: int | None = None, detalle=None, request_id: str | None = None) -> None:
    try:
        with db.begin_nested():
            db.add(Evento(
                usuario=usuario, accion=accion, entidad=entidad, entidad_id=entidad_id, request_id=request_id,
                detalle=None if detalle is None else json.dumps(detalle, ensure_ascii=False, default=str),
            ))
    except Exception:  # la auditoría no puede romper la operación de negocio
        log.exception("No se pudo registrar el evento de auditoría %s", accion)


def registrar(db: Session, request, accion: str, entidad: str | None = None, entidad_id: int | None = None,
              detalle=None, usuario: str | None = None) -> None:
    estado = request.scope.get("state", {})
    registrar_evento(db, accion, usuario=usuario or estado.get("usuario"), entidad=entidad,
                     entidad_id=entidad_id, detalle=detalle, request_id=estado.get("request_id"))


def cambios(antes: dict, despues: dict) -> dict | None:
    """{"antes": {...}, "despues": {...}} solo con los campos que cambiaron; None si no cambió nada."""
    campos = [k for k in despues if antes.get(k) != despues[k]]
    if not campos:
        return None
    return {"antes": {k: antes.get(k) for k in campos}, "despues": {k: despues[k] for k in campos}}

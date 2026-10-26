from __future__ import annotations

from app.schemas.comun import FechaUTC, Salida


class EventoOut(Salida):
    id: int
    fecha: FechaUTC
    usuario: str | None
    accion: str
    entidad: str | None
    entidad_id: int | None
    detalle: str | None
    request_id: str | None

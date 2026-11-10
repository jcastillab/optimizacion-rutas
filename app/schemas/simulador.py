"""Esquemas del simulador y las corridas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.config import settings
from app.schemas.comun import FechaUTC


class ParametrosIn(BaseModel):
    velocidad_kmh: float | None = Field(default=None, gt=0, le=settings.velocidad_max_kmh)
    tiempo_max_min: float | None = Field(default=None, gt=0, le=settings.tiempo_max_limite_min)


class ParaderoRuta(BaseModel):
    id: int
    nombre: str | None
    lat: float | None
    lon: float | None


class RutaOut(BaseModel):
    ruta_simulada: int
    finca_id: int
    finca_nombre: str | None = None
    paraderos: list[ParaderoRuta]
    personas: int
    km: float
    minutos_max: float
    tipo_bus: str
    capacidad: int
    buses: int
    costo_total: float


class SinServicioOut(BaseModel):
    finca_id: int
    paradero_id: int
    personas: int
    paradero_nombre: str | None = None
    lat: float | None = None
    lon: float | None = None
    finca_nombre: str | None = None


class CorridaResumenOut(BaseModel):
    id: int
    creada: FechaUTC
    usuario: str
    resumen: dict


class CorridaOut(CorridaResumenOut):
    parametros: dict
    rutas: list[RutaOut]
    sin_servicio: list[SinServicioOut]

"""Esquemas de fincas, paraderos, personas y tipos de bus."""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field

from app.schemas.comun import IdRef, Lat, Lon, Parcial, Salida, Texto

# Los paraderos se identifican por (nombre, lat, lon): se redondea a 6 decimales (~0,1 m) para que
# una diferencia de ruido no evite el duplicado.
Lat6 = Annotated[Lat, AfterValidator(lambda v: round(v, 6))]
Lon6 = Annotated[Lon, AfterValidator(lambda v: round(v, 6))]
Capacidad = Annotated[int, Field(gt=0, le=10_000)]
Costo = Annotated[float, Field(ge=0, le=1e12)]


class FincaIn(BaseModel):
    nombre: Texto
    cod_nivel2: IdRef | None = None
    lat: Lat
    lon: Lon
    activo: bool = True


class FincaEdit(Parcial):
    nulos = frozenset({"cod_nivel2"})
    nombre: Texto | None = None
    cod_nivel2: IdRef | None = None
    lat: Lat | None = None
    lon: Lon | None = None
    activo: bool | None = None


class FincaOut(Salida):
    id: int
    nombre: str
    cod_nivel2: IdRef | None
    lat: float
    lon: float
    activo: bool


class ParaderoIn(BaseModel):
    nombre: Texto
    lat: Lat6
    lon: Lon6
    activo: bool = True


class ParaderoEdit(Parcial):
    nombre: Texto | None = None
    lat: Lat6 | None = None
    lon: Lon6 | None = None
    activo: bool | None = None


class ParaderoOut(Salida):
    id: int
    nombre: str
    lat: float
    lon: float
    activo: bool


class PersonaIn(BaseModel):
    identificacion: Texto
    nombre: Texto
    paradero_id: IdRef | None = None
    finca_id: IdRef
    activo: bool = True


class PersonaEdit(Parcial):
    nulos = frozenset({"paradero_id"})
    identificacion: Texto | None = None
    nombre: Texto | None = None
    paradero_id: IdRef | None = None
    finca_id: IdRef | None = None
    activo: bool | None = None


class PersonaOut(Salida):
    id: int
    identificacion: str
    nombre: str
    paradero_id: int | None
    finca_id: IdRef
    activo: bool


class TipoBusIn(BaseModel):
    tipo: Texto
    capacidad: Capacidad
    costo: Costo
    activo: bool = True


class TipoBusEdit(Parcial):
    tipo: Texto | None = None
    capacidad: Capacidad | None = None
    costo: Costo | None = None
    activo: bool | None = None


class TipoBusOut(Salida):
    id: int
    tipo: str
    capacidad: int
    costo: float
    activo: bool

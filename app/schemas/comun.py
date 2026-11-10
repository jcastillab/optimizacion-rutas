"""Piezas comunes: paginación y fechas UTC con 'Z'."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, ClassVar, Generic, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    StringConstraints,
    model_validator,
)

T = TypeVar("T")

FechaUTC = Annotated[datetime, PlainSerializer(lambda d: d.strftime("%Y-%m-%dT%H:%M:%SZ"), return_type=str)]
Texto = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
MAX_ID = 2**63 - 1  # cabe en el INTEGER de SQLite
IdRef = Annotated[int, Field(ge=1, le=MAX_ID)]
Lat = Annotated[float, Field(ge=-90, le=90)]
Lon = Annotated[float, Field(ge=-180, le=180)]


class Pagina(BaseModel, Generic[T]):
    items: list[T]
    total: int
    pagina: int
    por_pagina: int


class Salida(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Parcial(BaseModel):
    """PATCH: solo los campos enviados; null solo en los de ``nulos``."""

    nulos: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def _sin_nulos(self):
        for campo in self.model_fields_set:
            if getattr(self, campo) is None and campo not in self.nulos:
                raise ValueError(f"{campo} no puede ser nulo")
        return self

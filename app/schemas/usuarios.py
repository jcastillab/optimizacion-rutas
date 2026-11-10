"""Esquemas de usuarios y login."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    Field,
    StringConstraints,
)

from app.core.config import settings
from app.core.seguridad import clave_trivial
from app.schemas.comun import FechaUTC, Parcial, Salida, Texto


def _simple(v: str) -> str:
    if clave_trivial(v):
        raise ValueError("La clave es demasiado simple: mezcla más caracteres, sin secuencias ni repeticiones.")
    return v


# Siempre en minúsculas: "Ana" y "ANA" son el mismo usuario.
Login = Annotated[str, BeforeValidator(lambda v: v.strip().lower() if isinstance(v, str) else v),
                  StringConstraints(pattern=r"^[a-z0-9_.-]{3,40}$")]
Clave = Annotated[str, Field(min_length=settings.clave_min_largo, max_length=200), AfterValidator(_simple)]
Rol = Literal["admin", "lector"]


class LoginIn(BaseModel):
    usuario: Login
    clave: str = Field(max_length=200)


class UsuarioIn(BaseModel):
    usuario: Login
    nombre: Texto
    rol: Rol
    clave: Clave


class UsuarioEdit(Parcial):
    nombre: Texto | None = None
    rol: Rol | None = None
    activo: bool | None = None
    clave: Clave | None = None


class UsuarioOut(Salida):
    id: int
    usuario: str
    nombre: str
    rol: str
    activo: bool
    creado: FechaUTC

"""Tablas del contrato (docs/CONTRATO_API.md)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, ahora


class Usuario(Base):
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario: Mapped[str] = mapped_column(String(60), unique=True)
    nombre: Mapped[str] = mapped_column(String(200))
    clave_hash: Mapped[str] = mapped_column(String(300))
    rol: Mapped[str] = mapped_column(String(10))  # admin | lector
    activo: Mapped[bool] = mapped_column(default=True)
    creado: Mapped[datetime] = mapped_column(default=ahora)


class Sesion(Base):
    __tablename__ = "sesiones"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"))
    creada: Mapped[datetime] = mapped_column(default=ahora)
    expira: Mapped[datetime]


class Finca(Base):
    __tablename__ = "fincas"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200), unique=True)
    cod_nivel2: Mapped[int | None] = mapped_column(unique=True, default=None)  # varios NULL permitidos
    lat: Mapped[float]
    lon: Mapped[float]
    activo: Mapped[bool] = mapped_column(default=True)


class Paradero(Base):
    __tablename__ = "paraderos"
    __table_args__ = (UniqueConstraint("nombre", "lat", "lon"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200))
    lat: Mapped[float]
    lon: Mapped[float]
    activo: Mapped[bool] = mapped_column(default=True)


class Persona(Base):
    __tablename__ = "personas"
    id: Mapped[int] = mapped_column(primary_key=True)
    identificacion: Mapped[str] = mapped_column(String(40), unique=True)
    nombre: Mapped[str] = mapped_column(String(200))
    paradero_id: Mapped[int | None] = mapped_column(ForeignKey("paraderos.id"), default=None)
    finca_id: Mapped[int] = mapped_column(ForeignKey("fincas.id"))
    activo: Mapped[bool] = mapped_column(default=True)


class TipoBus(Base):
    __tablename__ = "tipos_bus"
    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[str] = mapped_column(String(100), unique=True)
    capacidad: Mapped[int]
    costo: Mapped[float]
    activo: Mapped[bool] = mapped_column(default=True)


class Corrida(Base):
    __tablename__ = "corridas"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    creada: Mapped[datetime] = mapped_column(default=ahora)
    parametros: Mapped[dict] = mapped_column(JSON)
    resumen: Mapped[dict] = mapped_column(JSON)
    usuario: Mapped[Usuario] = relationship()
    rutas: Mapped[list[CorridaRuta]] = relationship(cascade="all, delete-orphan", order_by="CorridaRuta.id")
    sin_servicio: Mapped[list[CorridaSinServicio]] = relationship(
        cascade="all, delete-orphan", order_by="CorridaSinServicio.id")


class CorridaRuta(Base):
    __tablename__ = "corrida_rutas"
    id: Mapped[int] = mapped_column(primary_key=True)
    corrida_id: Mapped[int] = mapped_column(ForeignKey("corridas.id", ondelete="CASCADE"))
    ruta_simulada: Mapped[int]
    finca_id: Mapped[int]  # sin FK: la corrida es un histórico
    finca_nombre: Mapped[str | None] = mapped_column(String(200), default=None)  # snapshot
    # Snapshot en orden de visita: [{id, nombre, lat, lon}]. Corridas viejas guardaban solo [id, ...].
    paraderos: Mapped[list] = mapped_column(JSON)
    personas: Mapped[int]
    km: Mapped[float]
    minutos_max: Mapped[float]
    tipo_bus: Mapped[str] = mapped_column(String(100))
    capacidad: Mapped[int]
    buses: Mapped[int]
    costo_total: Mapped[float]


class CorridaSinServicio(Base):
    __tablename__ = "corrida_sin_servicio"
    id: Mapped[int] = mapped_column(primary_key=True)
    corrida_id: Mapped[int] = mapped_column(ForeignKey("corridas.id", ondelete="CASCADE"))
    finca_id: Mapped[int]
    paradero_id: Mapped[int]
    personas: Mapped[int]
    # Snapshot al crear la corrida (NULL en corridas viejas: se lee de la tabla viva).
    paradero_nombre: Mapped[str | None] = mapped_column(String(200), default=None)
    lat: Mapped[float | None] = mapped_column(default=None)
    lon: Mapped[float | None] = mapped_column(default=None)
    finca_nombre: Mapped[str | None] = mapped_column(String(200), default=None)


class Evento(Base):
    __tablename__ = "eventos"
    __table_args__ = (Index("ix_eventos_fecha", "fecha"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    fecha: Mapped[datetime] = mapped_column(default=ahora)
    usuario: Mapped[str | None] = mapped_column(String(60), default=None)
    accion: Mapped[str] = mapped_column(String(30))
    entidad: Mapped[str | None] = mapped_column(String(30), default=None)
    entidad_id: Mapped[int | None] = mapped_column(default=None)
    detalle: Mapped[str | None] = mapped_column(Text, default=None)
    request_id: Mapped[str | None] = mapped_column(String(16), default=None)


class Parametro(Base):
    __tablename__ = "parametros"
    clave: Mapped[str] = mapped_column(String(60), primary_key=True)
    valor: Mapped[str] = mapped_column(Text)


class IntentoLogin(Base):
    """Fallos de login por nombre normalizado, exista o no el usuario (misma respuesta en ambos casos)."""

    __tablename__ = "intentos_login"
    clave: Mapped[str] = mapped_column(String(60), primary_key=True)
    fallos: Mapped[int] = mapped_column(default=0)
    nivel: Mapped[int] = mapped_column(default=0)  # bloqueos seguidos: el retardo se duplica por nivel
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(default=None)
    ultimo: Mapped[datetime] = mapped_column(default=ahora)

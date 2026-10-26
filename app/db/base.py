"""Engine SQLite: claves foráneas, WAL, espera ante bloqueos y SAVEPOINT fiable."""

from __future__ import annotations

import unicodedata
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def ahora() -> datetime:
    """UTC sin zona (así se guarda en SQLite; la API lo serializa con 'Z')."""
    return datetime.now(UTC).replace(tzinfo=None)


def plegar(texto: str | None) -> str | None:
    """Minúsculas sin tildes (Unicode): 'Peñalisa' -> 'penalisa'. SQLite la expone como ``plegar()``."""
    if texto is None:
        return None
    return "".join(c for c in unicodedata.normalize("NFKD", str(texto)) if not unicodedata.combining(c)).casefold()


def preparar_directorio(url: str) -> None:
    u = make_url(url)
    if u.get_backend_name() == "sqlite" and u.database and u.database != ":memory:":
        Path(u.database).parent.mkdir(parents=True, exist_ok=True)


def crear_engine(url: str) -> Engine:
    """No toca el disco: el archivo y su carpeta se crean al conectar (ver ``preparar_directorio``)."""
    u = make_url(url)
    en_archivo = bool(u.database) and u.database != ":memory:"
    engine = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _al_conectar(dbapi, _):
        dbapi.isolation_level = None  # control manual de transacciones (ver crear_sessionmaker)
        dbapi.create_function("plegar", 1, plegar, deterministic=True)
        cur = dbapi.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute(f"PRAGMA busy_timeout={int(settings.db_espera_ms)}")  # espera, no "database is locked"
        if en_archivo:
            cur.execute("PRAGMA journal_mode=WAL")  # lectores y un escritor a la vez
        cur.close()

    return engine


def crear_sessionmaker(engine: Engine) -> sessionmaker:
    """Cada transacción empieza con BEGIN IMMEDIATE (toma el candado de escritura de una vez y espera
    con busy_timeout, en vez de fallar al subir de lectura a escritura), salvo las sesiones marcadas
    ``info["lectura"]`` (GET y endpoints de solo lectura), que usan BEGIN diferido."""
    fabrica = sessionmaker(engine, expire_on_commit=False)

    @event.listens_for(fabrica, "after_begin")
    def _comenzar(session, transaccion, conexion):
        if transaccion.nested:  # los SAVEPOINT los emite SQLAlchemy
            return
        conexion.exec_driver_sql("BEGIN" if session.info.get("lectura") else "BEGIN IMMEDIATE")

    return fabrica

"""Contador de fallos de login por nombre (exista o no el usuario) con retardo progresivo."""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.modelos import IntentoLogin


def segundos_restantes(db: Session, nombre: str, ahora: datetime) -> int:
    """>0 si el nombre está bloqueado ahora."""
    fila = db.get(IntentoLogin, nombre)
    if fila and fila.bloqueado_hasta and fila.bloqueado_hasta > ahora:
        return math.ceil((fila.bloqueado_hasta - ahora).total_seconds())
    return 0


def registrar_fallo(db: Session, nombre: str, ahora: datetime) -> bool:
    """Suma un fallo; True si este fallo dispara un bloqueo. También limpia filas viejas."""
    olvido = ahora - timedelta(minutes=settings.intentos_olvido_min)
    db.execute(delete(IntentoLogin).where(IntentoLogin.ultimo < olvido, IntentoLogin.clave != nombre))
    fila = db.get(IntentoLogin, nombre)
    if fila is None or fila.ultimo < olvido:
        if fila:
            db.delete(fila)
            db.flush()
        fila = IntentoLogin(clave=nombre, fallos=0, nivel=0)
        db.add(fila)
    fila.fallos += 1
    fila.ultimo = ahora
    if fila.fallos < settings.max_intentos:
        return False
    fila.fallos = 0
    fila.nivel += 1
    espera = min(settings.bloqueo_min * 2 ** (fila.nivel - 1), settings.bloqueo_max_min)
    fila.bloqueado_hasta = ahora + timedelta(minutes=espera)
    return True


def limpiar(db: Session, nombre: str) -> None:
    db.execute(delete(IntentoLogin).where(IntentoLogin.clave == nombre))

"""Usuarios y sesiones."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.modelos import Sesion, Usuario


def por_nombre(db: Session, usuario: str) -> Usuario | None:
    return db.scalar(select(Usuario).where(Usuario.usuario == usuario))


def otros_admins_activos(db: Session, excepto_id: int) -> int:
    return db.scalar(select(func.count()).select_from(Usuario).where(
        Usuario.rol == "admin", Usuario.activo.is_(True), Usuario.id != excepto_id))


def usuario_de_sesion(db: Session, token_hash: str, ahora: datetime) -> Usuario | None:
    return db.scalar(select(Usuario).join(Sesion, Sesion.usuario_id == Usuario.id).where(
        Sesion.token_hash == token_hash, Sesion.expira > ahora, Usuario.activo.is_(True)))


def borrar_sesion(db: Session, token_hash: str) -> None:
    db.execute(delete(Sesion).where(Sesion.token_hash == token_hash))


def borrar_sesiones_de(db: Session, usuario_id: int, excepto: str | None = None) -> None:
    """Revoca las sesiones del usuario salvo la de hash ``excepto`` (la que hace el cambio)."""
    stmt = delete(Sesion).where(Sesion.usuario_id == usuario_id)
    if excepto:
        stmt = stmt.where(Sesion.token_hash != excepto)
    db.execute(stmt)


def borrar_sesiones_vencidas(db: Session, ahora: datetime) -> None:
    db.execute(delete(Sesion).where(Sesion.expira <= ahora))

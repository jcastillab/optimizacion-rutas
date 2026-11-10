"""Corridas del simulador: guardar (con snapshots) y armar la respuesta del contrato.

Una corrida es un histórico: nombres y coordenadas de paraderos y nombres de fincas se guardan al
crearla y no cambian si luego se editan o borran. Las corridas del formato viejo (solo ids) se
completan con la tabla viva.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.modelos import Corrida, CorridaRuta, CorridaSinServicio, Finca, Paradero


def guardar(db: Session, usuario_id: int, parametros: dict, resumen: dict, rutas: list[dict],
            sin_servicio: list[dict]) -> Corrida:
    c = Corrida(usuario_id=usuario_id, parametros=parametros, resumen=resumen,
                rutas=[CorridaRuta(**r) for r in rutas],
                sin_servicio=[CorridaSinServicio(**s) for s in sin_servicio])
    db.add(c)
    db.flush()
    return c


def a_resumen(c: Corrida) -> dict:
    return {"id": c.id, "creada": c.creada, "usuario": c.usuario.usuario, "resumen": c.resumen}


def a_completa(db: Session, c: Corrida) -> dict:
    # Tabla viva solo para lo que no tiene snapshot (formato viejo).
    ids_p = {p for r in c.rutas for p in r.paraderos if not isinstance(p, dict)}
    ids_p |= {s.paradero_id for s in c.sin_servicio if s.paradero_nombre is None}
    ids_f = {r.finca_id for r in c.rutas if r.finca_nombre is None}
    ids_f |= {s.finca_id for s in c.sin_servicio if s.finca_nombre is None}
    vivos_p = {p.id: p for p in db.scalars(select(Paradero).where(Paradero.id.in_(ids_p)))} if ids_p else {}
    vivas_f = {f.id: f.nombre for f in db.scalars(select(Finca).where(Finca.id.in_(ids_f)))} if ids_f else {}

    def paradero(p) -> dict:
        if isinstance(p, dict):
            return p
        v = vivos_p.get(p)  # puede haberse borrado
        return {"id": p, "nombre": v.nombre if v else None, "lat": v.lat if v else None,
                "lon": v.lon if v else None}

    def sin(s: CorridaSinServicio) -> dict:
        v = vivos_p.get(s.paradero_id) if s.paradero_nombre is None else None
        return {"finca_id": s.finca_id, "paradero_id": s.paradero_id, "personas": s.personas,
                "paradero_nombre": s.paradero_nombre if s.paradero_nombre is not None else (v.nombre if v else None),
                "lat": s.lat if s.paradero_nombre is not None else (v.lat if v else None),
                "lon": s.lon if s.paradero_nombre is not None else (v.lon if v else None),
                "finca_nombre": s.finca_nombre if s.finca_nombre is not None else vivas_f.get(s.finca_id)}

    return {
        **a_resumen(c), "parametros": c.parametros,
        "rutas": [{"ruta_simulada": r.ruta_simulada, "finca_id": r.finca_id,
                   "finca_nombre": r.finca_nombre if r.finca_nombre is not None else vivas_f.get(r.finca_id),
                   "paraderos": [paradero(p) for p in r.paraderos], "personas": r.personas, "km": r.km,
                   "minutos_max": r.minutos_max, "tipo_bus": r.tipo_bus, "capacidad": r.capacidad,
                   "buses": r.buses, "costo_total": r.costo_total} for r in c.rutas],
        "sin_servicio": [sin(s) for s in c.sin_servicio],
    }

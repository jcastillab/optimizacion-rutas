"""Adapta la base de datos al simulador y guarda la corrida.

``calcular`` solo lee (puede correr en una sesión de lectura, sin retener el candado de escritura
durante el cálculo) y ``guardar`` escribe la corrida con sus snapshots.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errores import Validacion
from app.db.modelos import Corrida, Finca, Paradero, Parametro, Persona, TipoBus
from app.repository import corridas as repo
from app.services.simulador_rutas import simular

ADVERTENCIAS_FIJAS = [
    ("Comparación orientativa: la red actual se calcula como la suma de las tarifas REGULAR suponiendo un bus "
     "por fila de tarifa; no está confirmado con el proveedor."),
    "Distancias en línea recta (haversine); el recorrido real por carretera es mayor.",
]


def _inactivos(db: Session) -> dict[str, int]:
    return {nombre: db.scalar(select(func.count()).select_from(m).where(m.activo.is_(False)))
            for nombre, m in (("personas", Persona), ("fincas", Finca), ("tipos de bus", TipoBus),
                              ("paraderos", Paradero))}


def _advertencias_del_import(p: dict[str, str]) -> list[str]:
    avisos = []
    if "maestro_personas_total" in p:
        total, sim = int(p["maestro_personas_total"]), int(p["maestro_personas_simuladas"])
        pct = f"{sim / total * 100:.1f}".replace(".", ",") if total else "0,0"
        avisos.append(f"Solo {sim} de {total} personas del maestro cruzan con el catálogo de rutas ({pct} %); "
                      "las demás no se simularon.")
    if int(p.get("duplicados_paraderos_distintos", 0)) > 0:
        avisos.append(f"{p['duplicados_paraderos_distintos']} personas tienen identificación repetida con "
                      f"paraderos distintos; se usó la regla {p.get('regla_duplicados', settings.regla_duplicados)}.")
    return avisos


def calcular(db: Session, velocidad_kmh: float | None, tiempo_max_min: float | None) -> dict:
    velocidad = velocidad_kmh or settings.velocidad_bus_kmh
    tiempo = tiempo_max_min or settings.tiempo_max_viaje_min

    buses = db.scalars(select(TipoBus).where(TipoBus.activo.is_(True))).all()
    if not buses:
        raise Validacion("No hay tipos de bus activos: crea o activa al menos uno.")
    fincas = {f.id: f for f in db.scalars(select(Finca).where(Finca.activo.is_(True)))}
    paraderos = {p.id: p for p in db.scalars(select(Paradero).where(Paradero.activo.is_(True)))}
    personas = [p for p in db.scalars(select(Persona).where(Persona.activo.is_(True)))
                if p.finca_id in fincas]
    if not personas:
        raise Validacion("No hay personas activas con finca activa para simular.")
    con_paradero = [p for p in personas if p.paradero_id in paraderos]
    if not con_paradero:
        raise Validacion("Ninguna persona activa tiene un paradero activo asignado.")

    empleados = pd.DataFrame({"identificacion": [p.identificacion for p in con_paradero],
                              "parada_id": [p.paradero_id for p in con_paradero],
                              "cod_nivel2": [p.finca_id for p in con_paradero]})
    paradas = pd.DataFrame([{"parada_id": p.id, "nombre": p.nombre, "lat": p.lat, "lon": p.lon}
                            for p in paraderos.values()])
    tarifas = pd.DataFrame({"tipo_tarifa": "REGULAR", "tipo_vehiculo": [b.tipo for b in buses],
                            "capacidad": [b.capacidad for b in buses], "tarifa": [b.costo for b in buses]})
    destinos = {i: (fincas[i].lat, fincas[i].lon) for i in sorted(set(empleados["cod_nivel2"]))}

    rutas, sin = simular(empleados, paradas, tarifas, velocidad, tiempo, destinos)

    def snap(i: int) -> dict:
        return {"id": i, "nombre": paraderos[i].nombre, "lat": paraderos[i].lat, "lon": paraderos[i].lon}

    filas = [{"ruta_simulada": int(r.ruta_simulada), "finca_id": int(r.finca),
              "finca_nombre": fincas[int(r.finca)].nombre,
              "paraderos": [snap(int(x)) for x in r.parada_ids.split()], "personas": int(r.personas),
              "km": float(r.km), "minutos_max": float(r.minutos_max), "tipo_bus": r.tipo_bus,
              "capacidad": int(r.capacidad), "buses": int(r.buses), "costo_total": float(r.costo_total)}
             for r in rutas.itertuples()]
    filas_sin = [{"finca_id": int(s.finca), "finca_nombre": fincas[int(s.finca)].nombre,
                  "paradero_id": int(s.parada_id), "paradero_nombre": paraderos[int(s.parada_id)].nombre,
                  "lat": paraderos[int(s.parada_id)].lat, "lon": paraderos[int(s.parada_id)].lon,
                  "personas": int(s.personas)} for s in sin.itertuples()]

    costo = sum(f["costo_total"] for f in filas)
    parametros = {p.clave: p.valor for p in db.scalars(select(Parametro))}
    red = float(parametros["costo_red_actual"]) if "costo_red_actual" in parametros else None
    advertencias = [*ADVERTENCIAS_FIJAS, *_advertencias_del_import(parametros)]
    inactivos = _inactivos(db)
    diferencia = None
    if not filas:
        advertencias.append("No se calcula la diferencia con la red actual: no hay rutas simuladas.")
    elif not red:
        advertencias.append("No se calcula la diferencia con la red actual: no hay costo de la red actual "
                            "(importa los datos locales).")
    elif any(inactivos.values()):
        detalle = ", ".join(f"{n} {k}" for k, n in inactivos.items() if n)
        advertencias.append("No se calcula la diferencia con la red actual: hay registros inactivos "
                            f"({detalle}), así que el conjunto simulado no es comparable con el importado.")
    else:
        diferencia = round((costo - red) / red * 100, 1)
    resumen = {
        "rutas": len(filas), "buses": sum(f["buses"] for f in filas),
        "personas": sum(f["personas"] for f in filas), "costo_total": costo,
        "costo_red_actual": red, "diferencia_pct": diferencia,
        "personas_sin_servicio": sum(s["personas"] for s in filas_sin),
        "personas_sin_paradero": len(personas) - len(con_paradero),
        "advertencias": advertencias,
    }
    return {"parametros": {"velocidad_kmh": velocidad, "tiempo_max_min": tiempo}, "resumen": resumen,
            "rutas": filas, "sin_servicio": filas_sin}


def guardar(db: Session, usuario_id: int, calculo: dict) -> Corrida:
    return repo.guardar(db, usuario_id, calculo["parametros"], calculo["resumen"], calculo["rutas"],
                        calculo["sin_servicio"])

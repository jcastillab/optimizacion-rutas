"""Importa a la base los datos locales (Excel + KML) con el ETL existente.

Upsert que **crea lo que falta y no modifica lo existente**: las ediciones del administrador
sobreviven a una reimportación. Los registros que difieren del Excel se cuentan y se avisan;
``sobrescribir=True`` los pisa a propósito. Las fincas se emparejan por ``cod_nivel2`` (no por nombre,
que el administrador puede cambiar) y no se toca el campo ``activo``.
"""

from __future__ import annotations

import math
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errores import Validacion
from app.db.modelos import Finca, Paradero, Parametro, Persona, TipoBus
from app.etl.build_tables import construir_tablas
from app.etl.load_master import cargar_datos_crudos
from app.services.simulador_rutas import catalogo_buses


def _clave_kml(nombre: str) -> str:
    sin = "".join(c for c in unicodedata.normalize("NFKD", nombre) if not unicodedata.combining(c))
    return sin.strip().upper()


def leer_puntos_kml(ruta: Path) -> dict[str, tuple[float, float]]:
    """{NOMBRE EN MAYÚSCULAS SIN TILDES: (lat, lon)} de los Placemark de tipo punto."""
    puntos = {}
    for pm in ET.parse(ruta).iterfind(".//{*}Placemark"):
        coords = pm.find(".//{*}Point/{*}coordinates")
        if coords is None or not (coords.text or "").strip():
            continue
        lon, lat, *_ = (float(v) for v in coords.text.strip().split(","))
        puntos[_clave_kml(pm.findtext("{*}name") or "")] = (round(lat, 7), round(lon, 7))
    return puntos


def _distinto(a, b) -> bool:
    if isinstance(a, float) or isinstance(b, float):
        return a is None or b is None or not math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)
    return a != b


class _Cuenta(dict):
    """{creadas, actualizadas} (la forma del contrato) y ``difieren``: existentes que no coinciden con el Excel."""

    def __init__(self, sobrescribir: bool):
        super().__init__(creadas=0, actualizadas=0)
        self.sobrescribir, self.difieren = sobrescribir, 0

    def upsert(self, db: Session, existente, crear, valores: dict):
        if existente is None:
            existente = crear(**valores)
            db.add(existente)
            self["creadas"] += 1
        elif any(_distinto(getattr(existente, k), v) for k, v in valores.items()):
            if self.sobrescribir:
                for k, v in valores.items():
                    setattr(existente, k, v)
                self["actualizadas"] += 1
            else:
                self.difieren += 1
        return existente


def _ident(v) -> str:
    return str(int(v)) if isinstance(v, float) and v.is_integer() else str(v).strip()


def _parametro(db: Session, clave: str, valor) -> None:
    p = db.get(Parametro, clave)
    if p is None:
        db.add(Parametro(clave=clave, valor=str(valor)))
    else:
        p.valor = str(valor)


def importar_datos_locales(db: Session, sobrescribir: bool = False) -> dict:
    kml = settings.kml_file
    faltan = [p.name for p in (settings.maestro_file, settings.posiciones_file, kml) if not p.exists()]
    if faltan:
        raise Validacion(f"Faltan archivos de datos en {settings.datos_dir}: {', '.join(faltan)}.")

    datos = cargar_datos_crudos(settings.maestro_file, settings.posiciones_file)
    t = construir_tablas(datos)
    avisos: list[str] = []
    if t.issues:
        avisos.append(f"El ETL registró {len(t.issues)} observaciones de reconciliación "
                      "(ver data/reporte_reconciliacion.md).")

    # --- fincas: punto del KML; se emparejan por cod_nivel2 ---
    puntos = leer_puntos_kml(kml)
    cuenta_f = _Cuenta(sobrescribir)
    por_cod = {f.cod_nivel2: f for f in db.scalars(select(Finca)) if f.cod_nivel2 is not None}
    por_nombre = {f.nombre: f for f in db.scalars(select(Finca))}
    finca_por_cod: dict[int, Finca] = {}
    for r in t.fincas.itertuples():
        cod = int(r.cod_nivel2)
        punto = puntos.get(_clave_kml(settings.destino_kml.get(r.nombre, "")))
        if punto is None:
            avisos.append(f"La finca {r.nombre!r} no tiene punto en el KML: no se importó ni sus personas.")
            continue
        existente = por_cod.get(cod)
        if existente is None and (homonima := por_nombre.get(r.nombre)) is not None:
            if homonima.cod_nivel2 is not None:
                avisos.append(f"Ya existe una finca {r.nombre!r} con otro código: no se importó la del Excel.")
                continue
            homonima.cod_nivel2 = cod  # la finca creada a mano adopta el código del Excel
            existente = homonima
        finca_por_cod[cod] = cuenta_f.upsert(
            db, existente, Finca, {"nombre": r.nombre, "cod_nivel2": cod, "lat": punto[0], "lon": punto[1]})

    # --- paraderos físicos: únicos por (nombre, lat, lon), solo los que tienen personas ---
    cuenta_p = _Cuenta(sobrescribir)
    existentes_p = {(p.nombre, round(p.lat, 6), round(p.lon, 6)): p for p in db.scalars(select(Paradero))}
    paradas = t.paradas.set_index("parada_id")
    paradero_por_parada: dict[int, Paradero] = {}
    clave_por_parada: dict[int, tuple] = {}
    sin_coord = set()
    for pid in sorted(set(t.empleados["parada_id"].dropna().astype(int))):
        fila = paradas.loc[pid]
        if pd.isna(fila["lat"]) or pd.isna(fila["lon"]):
            sin_coord.add(pid)
            continue
        clave = (str(fila["nombre"]).strip(), round(float(fila["lat"]), 6), round(float(fila["lon"]), 6))
        if clave not in existentes_p:
            existentes_p[clave] = cuenta_p.upsert(db, None, Paradero,
                                                  {"nombre": clave[0], "lat": clave[1], "lon": clave[2]})
        paradero_por_parada[pid] = existentes_p[clave]
        clave_por_parada[pid] = clave
    if sin_coord:
        avisos.append(f"{len(sin_coord)} paradas con personas no tienen coordenadas: esas personas quedan "
                      "sin paradero.")
    db.flush()

    # --- identificaciones repetidas: se conserva una fila según settings.regla_duplicados ---
    emp = t.empleados.assign(ident=t.empleados["identificacion"].map(_ident),
                             pkey=t.empleados["parada_id"].map(clave_por_parada))
    repetidas = int(emp["ident"].duplicated().sum())
    con_paraderos_distintos = int((emp.groupby("ident")["pkey"].nunique() > 1).sum())
    if repetidas:
        avisos.append(f"{repetidas} filas repiten la identificación de otra persona "
                      f"({con_paraderos_distintos} personas tienen paraderos distintos); "
                      f"se usó la regla {settings.regla_duplicados}.")
    emp = emp.drop_duplicates("ident", keep="first" if settings.regla_duplicados == "primera" else "last")

    # --- personas ---
    cuenta_e = _Cuenta(sobrescribir)
    existentes_e = {p.identificacion: p for p in db.scalars(select(Persona))}
    sin_finca = 0
    for r in emp.itertuples():
        finca = finca_por_cod.get(int(r.cod_nivel2))
        if finca is None:
            sin_finca += 1
            continue
        paradero = None if pd.isna(r.parada_id) else paradero_por_parada.get(int(r.parada_id))
        existentes_e[r.ident] = cuenta_e.upsert(
            db, existentes_e.get(r.ident), Persona,
            {"identificacion": r.ident, "nombre": str(r.nombre).strip(),
             "paradero_id": paradero.id if paradero else None, "finca_id": finca.id})
    if sin_finca:
        avisos.append(f"{sin_finca} personas no se importaron por no tener finca con punto en el KML.")

    # --- tipos de bus (mediana REGULAR por tipo) ---
    cuenta_b = _Cuenta(sobrescribir)
    existentes_b = {b.tipo: b for b in db.scalars(select(TipoBus))}
    for b in catalogo_buses(t.tarifas):
        cuenta_b.upsert(db, existentes_b.get(b.tipo), TipoBus,
                        {"tipo": b.tipo, "capacidad": b.capacidad, "costo": b.costo})

    difieren = sum(c.difieren for c in (cuenta_f, cuenta_p, cuenta_e, cuenta_b))
    if difieren:
        avisos.append(f"{difieren} registros difieren del Excel y no se modificaron "
                      "(usa sobrescribir=true para reemplazarlos).")

    # --- parámetros derivados del Excel (se refrescan siempre) ---
    total = float(t.tarifas.loc[t.tarifas["tipo_tarifa"] == "REGULAR", "tarifa"].sum())
    _parametro(db, "costo_red_actual", int(total) if total.is_integer() else repr(total))
    _parametro(db, "maestro_personas_total", datos.empleados["identificacion"].map(_ident).nunique())
    _parametro(db, "maestro_personas_simuladas", emp["ident"].nunique())
    _parametro(db, "duplicados_filas", repetidas)
    _parametro(db, "duplicados_paraderos_distintos", con_paraderos_distintos)
    _parametro(db, "regla_duplicados", settings.regla_duplicados)
    db.flush()
    return {"fincas": dict(cuenta_f), "paraderos": dict(cuenta_p), "personas": dict(cuenta_e),
            "tipos_bus": dict(cuenta_b), "avisos": avisos}

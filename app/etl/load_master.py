"""Lectura cruda de los dos Excel fuente a DataFrames de pandas.

No normaliza ni cruza nada todavía — eso vive en ``build_tables.py``. Este
módulo solo centraliza nombres de hoja/columna para que un cambio en el
archivo fuente (p.ej. renombrar una columna) se arregle en un solo lugar.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass
class DatosCrudos:
    empleados: pd.DataFrame
    rutas_paradas: pd.DataFrame
    proveedores_tarifas: pd.DataFrame
    posiciones: pd.DataFrame


def cargar_datos_crudos(maestro_file: Path, posiciones_file: Path) -> DatosCrudos:
    empleados = pd.read_excel(maestro_file, sheet_name="Maestro_Empleados_Yarumo")
    rutas_paradas = pd.read_excel(maestro_file, sheet_name="Rutas_y_Paradas")
    proveedores_tarifas = pd.read_excel(
        maestro_file, sheet_name="Proveedores_y_Tarifas"
    )
    posiciones = pd.read_excel(posiciones_file, sheet_name="Hoja1")

    empleados.columns = [
        "identificacion",
        "apellidos",
        "nombres",
        "routes_id",
        "stops_id",
        "ruta",
        "parada",
        "configuracion",
        "cod_nivel2",
        "nombre_nivel2",
    ]
    rutas_paradas.columns = ["route_id", "stop_id", "ruta", "parada", "nivel2"]
    proveedores_tarifas.columns = [
        "cod_nivel2",
        "nivel2",
        "route_id",
        "ruta",
        "nit_proveedor",
        "proveedor",
        "tipo_vehiculo",
        "capacidad",
        "tarifa",
        "tipo_tarifa",
    ]
    posiciones.columns = [
        "nivel2",
        "cod_nivel2",
        "ruta",
        "parada",
        "latitude",
        "longitude",
        "address",
    ]

    return DatosCrudos(
        empleados=empleados,
        rutas_paradas=rutas_paradas,
        proveedores_tarifas=proveedores_tarifas,
        posiciones=posiciones,
    )

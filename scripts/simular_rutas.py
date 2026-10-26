"""CLI: simula rutas nuevas con paraderos existentes que terminan en cada finca.

Uso:
    python scripts/simular_rutas.py [--csv data/simulador/rutas_simuladas.csv]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd

from app.core.config import settings
from app.services.simulador_rutas import simular
from cruce_fincas import DATOS, leer_kml


def destinos_desde_kml(fincas: pd.DataFrame) -> dict[int, tuple[float, float]]:
    """{cod_nivel2: (lat, lng)} con el punto del KML asociado a cada finca."""
    puntos = {f["clave"]: (f["lat"], f["lng"]) for f in leer_kml(DATOS / "fincas_sunshine.kml")
              if f["tipo"] == "PUNTO"}
    destinos = {}
    for r in fincas.itertuples():
        clave = settings.destino_kml.get(r.nombre)
        if clave in puntos:
            destinos[r.cod_nivel2] = puntos[clave]
        else:
            print(f"AVISO sin punto en el KML para la finca {r.nombre!r}: no se simula")
    return destinos


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--csv",
        type=Path,
        default=settings.processed_dir.parent / "simulador" / "rutas_simuladas.csv",
    )
    args = ap.parse_args()

    d = settings.processed_dir
    fincas = pd.read_csv(d / "fincas.csv")
    rutas, sin = simular(
        pd.read_csv(d / "empleados.csv"),
        pd.read_csv(d / "paradas.csv"),
        pd.read_csv(d / "tarifas.csv"),
        settings.velocidad_bus_kmh,
        settings.tiempo_max_viaje_min,
        destinos_desde_kml(fincas),
    )
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    rutas.to_csv(args.csv, index=False)

    print(
        f"Rutas simuladas: {len(rutas)} | personas: {rutas['personas'].sum()} | "
        f"buses: {rutas['buses'].sum()} | costo total: {rutas['costo_total'].sum():,.0f}"
    )
    if len(rutas):
        resumen = rutas.groupby("tipo_bus").agg(
            rutas=("ruta_simulada", "size"), buses=("buses", "sum"), costo=("costo_total", "sum")
        )
        print(resumen.to_string())
        print(
            f"Ruta más larga: {rutas['km'].max()} km ({rutas['minutos_max'].max()} min). "
        )
    if len(sin):
        print(f"Sin servicio (a más de {settings.velocidad_bus_kmh * settings.tiempo_max_viaje_min / 60:.0f} km "
              f"de la finca): {len(sin)} paraderos, {sin['personas'].sum()} personas")
    print(f"Guardado en {args.csv}")


if __name__ == "__main__":
    main()

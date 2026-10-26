"""CLI: simula rutas nuevas con paraderos existentes, con bus y cantidad por ruta.

Uso:
    python scripts/simular_rutas.py [--csv data/simulador/rutas_simuladas.csv]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from app.core.config import settings
from app.services.simulador_rutas import simular


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--csv",
        type=Path,
        default=settings.processed_dir.parent / "simulador" / "rutas_simuladas.csv",
    )
    args = ap.parse_args()

    d = settings.processed_dir
    res = simular(
        pd.read_csv(d / "empleados.csv"),
        pd.read_csv(d / "paradas.csv"),
        pd.read_csv(d / "tarifas.csv"),
        settings.velocidad_bus_kmh,
        settings.tiempo_max_viaje_min,
    )
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(args.csv, index=False)

    print(
        f"Rutas simuladas: {len(res)} | personas: {res['personas'].sum()} | "
        f"buses: {res['buses'].sum()} | costo total: {res['costo_total'].sum():,.0f}"
    )
    resumen = res.groupby("tipo_bus").agg(
        rutas=("ruta_simulada", "size"), buses=("buses", "sum"), costo=("costo_total", "sum")
    )
    print(resumen.to_string())
    print(
        f"Ruta más larga: {res['km'].max()} km ({res['minutos_max'].max()} min). "
        f"Guardado en {args.csv}"
    )


if __name__ == "__main__":
    main()

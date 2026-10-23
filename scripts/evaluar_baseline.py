"""CLI: heurística de orden de paradas vs. orden original y óptimo exacto.

Uso:
    python scripts/evaluar_baseline.py            -> tabla por variante + resumen
    python scripts/evaluar_baseline.py --csv x.csv -> además guarda la tabla
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from app.core.config import settings
from app.services.baseline_orden import evaluar_variantes


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--csv", type=Path, help="ruta donde guardar la tabla")
    args = ap.parse_args()

    paradas = pd.read_csv(settings.processed_dir / "paradas.csv")
    variantes = pd.read_csv(settings.processed_dir / "rutas_variante.csv")
    tipo_dia_de = dict(zip(variantes["ruta_variante_id"], variantes["tipo_dia"]))
    tabla = evaluar_variantes(paradas, settings.umbral_atipico_km, tipo_dia_de=tipo_dia_de)
    tabla = tabla.merge(variantes[["ruta_variante_id", "tipo_dia"]], on="ruta_variante_id", how="left")
    sin_paradas = sorted(set(variantes["ruta_variante_id"]) - set(tabla["ruta_variante_id"]))

    with pd.option_context("display.width", 140, "display.float_format", "{:.2f}".format):
        print(tabla.to_string(index=False))

    con_optimo = tabla.dropna(subset=["distancia_optima_km"])
    con_optimo = con_optimo[con_optimo["n"] >= 3]
    print()
    print(f"Variantes: {len(tabla)} | con óptimo exacto (3..{settings.max_paradas_optimo_exacto} paradas): {len(con_optimo)}")
    if len(con_optimo):
        print(
            f"Gap heurística vs óptimo: medio {con_optimo['gap_pct'].mean():.2f} %, "
            f"máximo {con_optimo['gap_pct'].max():.2f} %, "
            f"rutas en el óptimo {(con_optimo['gap_pct'] < settings.tolerancia_gap_pct).sum()}/{len(con_optimo)}"
        )
    # "Original" = orden de filas del archivo (por ID en LABORAL), no el recorrido
    # ejecutado: la mejora mide cuánto ordena la heurística, no un ahorro operativo.
    # Una fila por conjunto de paradas. La distancia original sí depende del orden
    # de filas de cada copia, así que se usa el promedio del grupo, no la primera.
    grupo = tabla["duplicada_de"].fillna(tabla["ruta_variante_id"])
    unicas = tabla[tabla["duplicada_de"].isna()].copy()
    unicas["distancia_original_km"] = unicas["ruta_variante_id"].map(
        tabla.groupby(grupo)["distancia_original_km"].mean()
    )
    print(
        "Heurística vs. orden del archivo (no es el recorrido real ejecutado; "
        f"sin contar {len(tabla) - len(unicas)} variantes con las mismas paradas que otra):"
    )
    for tipo, grupo in unicas.groupby("tipo_dia", dropna=False):
        orig, heur = grupo["distancia_original_km"].sum(), grupo["distancia_heuristica_km"].sum()
        if orig:
            print(f"  {tipo}: {len(grupo)} variantes, {orig:.1f} km -> {heur:.1f} km ({(orig - heur) / orig * 100:.1f} % menos)")
    if sin_paradas:
        print(f"Variantes sin paradas en paradas.csv (no evaluadas): {sin_paradas}")
    if args.csv:
        tabla.to_csv(args.csv, index=False)
        print(f"Tabla guardada en {args.csv}")


if __name__ == "__main__":
    main()

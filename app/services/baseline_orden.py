"""Baseline para medir la heurística de orden de paradas.

Compara, por ruta, tres longitudes de camino abierto (haversine):
- **original**: las paradas en el orden en que vienen en el archivo fuente;
- **heurística**: ``ordenar_paradas`` (vecino más cercano + 2-opt);
- **óptimo exacto**: Held-Karp, solo para rutas de hasta
  ``settings.max_paradas_optimo_exacto`` paradas.

El gap % de la heurística contra el óptimo dice cuánto se aleja de lo mejor
posible; la mejora contra el original, cuánto aporta frente a no ordenar.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass

import pandas as pd

from app.core.config import settings
from app.etl.build_tables import variantes_con_mismas_paradas
from app.services.distancia import Coord, distancia_total_km, matriz_haversine_km
from app.services.orden_paradas import ordenar_paradas
from app.services.recorrido import calcular_recorrido

# Held-Karp guarda 2 tablas de 2^n × n en listas Python: con 16 son ~2 M celdas.
_MAX_N_SEGURO = 16


@dataclass(frozen=True)
class EvaluacionOrden:
    n: int
    distancia_original_km: float
    distancia_heuristica_km: float
    distancia_optima_km: float | None
    gap_pct: float | None
    mejora_vs_original_pct: float


def orden_optimo_exacto(coords: Sequence[Coord], max_n: int | None = None) -> list[int]:
    """Orden de camino abierto (inicio y fin libres) de longitud mínima."""
    max_n = settings.max_paradas_optimo_exacto if max_n is None else max_n
    if max_n > _MAX_N_SEGURO:
        raise ValueError(f"max_n={max_n} agotaría la memoria; el máximo seguro es {_MAX_N_SEGURO}")
    n = len(coords)
    if n > max_n:
        raise ValueError(f"{n} paradas supera el máximo para el óptimo exacto ({max_n})")
    if n <= 2:
        return list(range(n))

    dist = matriz_haversine_km(coords)
    # costo[mascara][j]: camino más corto que visita `mascara` y termina en j.
    costo = [[math.inf] * n for _ in range(1 << n)]
    previo = [[-1] * n for _ in range(1 << n)]
    for j in range(n):
        costo[1 << j][j] = 0.0
    for mascara in range(1, 1 << n):
        for j in range(n):
            c = costo[mascara][j]
            if c == math.inf:
                continue
            for k in range(n):
                if mascara & (1 << k):
                    continue
                nueva = mascara | (1 << k)
                if c + dist[j][k] < costo[nueva][k]:
                    costo[nueva][k] = c + dist[j][k]
                    previo[nueva][k] = j

    completa = (1 << n) - 1
    j = min(range(n), key=lambda i: costo[completa][i])
    orden, mascara = [], completa
    while j != -1:
        orden.append(j)
        j, mascara = previo[mascara][j], mascara & ~(1 << j)
    return orden[::-1]


def gap_pct(heuristica_km: float, optimo_km: float) -> float:
    """(heurística − óptimo) / óptimo · 100. Con óptimo 0, solo puede ser 0."""
    if optimo_km == 0:
        # shortcut: todas las paradas en el mismo punto; inf si la heurística no da 0.
        return 0.0 if heuristica_km == 0 else math.inf
    return (heuristica_km - optimo_km) / optimo_km * 100


def evaluar_orden(
    coords: Sequence[Coord],
    max_n: int | None = None,
    distancia_heuristica_km: float | None = None,
) -> EvaluacionOrden:
    """``distancia_heuristica_km`` evita recalcular la heurística si ya se tiene."""
    max_n = settings.max_paradas_optimo_exacto if max_n is None else max_n
    original = distancia_total_km(list(coords))
    heuristica = (
        distancia_total_km([coords[i] for i in ordenar_paradas(coords)])
        if distancia_heuristica_km is None
        else distancia_heuristica_km
    )
    optima = gap = None
    if len(coords) <= max_n:
        optima = distancia_total_km([coords[i] for i in orden_optimo_exacto(coords, max_n)])
        gap = gap_pct(heuristica, optima)
    mejora = (original - heuristica) / original * 100 if original else 0.0
    return EvaluacionOrden(len(coords), original, heuristica, optima, gap, mejora)


def evaluar_variantes(
    paradas: pd.DataFrame,
    umbral_atipico_km: float,
    max_n: int | None = None,
    tipo_dia_de: dict[int, str] | None = None,
) -> pd.DataFrame:
    """Una fila por ``ruta_variante_id`` de ``paradas.csv``.

    Usa las mismas exclusiones que ``calcular_recorrido`` (sin coordenada,
    atípicas); el orden original es el de las filas válidas en el archivo.
    ``duplicada_de`` es la primera variante con las mismas paradas (la fuente
    repite rutas FDS), para no sumarlas dos veces en los totales; con
    ``tipo_dia_de`` solo se compara dentro del mismo tipo de día.
    """
    duplicadas = variantes_con_mismas_paradas(paradas, tipo_dia_de)
    filas = []
    # dropna=False: una parada sin variante sale como fila con id NaN, no se pierde.
    for variante, sub in paradas.groupby("ruta_variante_id", sort=True, dropna=False):
        rec = calcular_recorrido(variante, "", "", sub, umbral_atipico_km)
        validas = {p.parada_id for p in rec.paradas}
        originales = sub[sub["parada_id"].isin(validas)]
        coords = list(zip(originales["lat"], originales["lon"]))
        evaluacion = evaluar_orden(coords, max_n, distancia_heuristica_km=rec.distancia_km)
        filas.append(
            {
                "ruta_variante_id": variante,
                **asdict(evaluacion),
                "duplicada_de": duplicadas.get(variante),
            }
        )
    return pd.DataFrame(
        filas,
        columns=[
            "ruta_variante_id",
            "n",
            "distancia_original_km",
            "distancia_heuristica_km",
            "distancia_optima_km",
            "gap_pct",
            "mejora_vs_original_pct",
            "duplicada_de",
        ],
    )

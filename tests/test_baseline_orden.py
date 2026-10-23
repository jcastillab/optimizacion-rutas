import itertools
import random

import pandas as pd
import pytest

from app.core.config import settings
from app.services.baseline_orden import (
    EvaluacionOrden,
    evaluar_orden,
    evaluar_variantes,
    gap_pct,
    orden_optimo_exacto,
)
from app.services.distancia import distancia_total_km
from app.services.orden_paradas import ordenar_paradas
from app.services.recorrido import calcular_recorrido


def _coords_aleatorias(rng, n):
    # Paradas realistas: ~±10 km alrededor de (4.8, -74.3).
    return [(4.8 + rng.uniform(-0.1, 0.1), -74.3 + rng.uniform(-0.1, 0.1)) for _ in range(n)]


def _dist(coords, orden):
    return distancia_total_km([coords[i] for i in orden])


def _minimo_fuerza_bruta(coords):
    return min(_dist(coords, p) for p in itertools.permutations(range(len(coords))))


# --- Criterio 1: óptimo exacto == fuerza bruta -------------------------------

@pytest.mark.parametrize("semilla", range(5))
@pytest.mark.parametrize("n", range(3, 8))
def test_optimo_exacto_coincide_con_fuerza_bruta(semilla, n):
    coords = _coords_aleatorias(random.Random(semilla * 100 + n), n)
    orden = orden_optimo_exacto(coords)

    assert sorted(orden) == list(range(n))
    assert abs(_dist(coords, orden) - _minimo_fuerza_bruta(coords)) < 1e-9


def test_optimo_exacto_instancia_colineal():
    # Por construcción: el óptimo recorre los puntos de un extremo al otro.
    coords = [(4.80, -74.30), (4.84, -74.34), (4.82, -74.32), (4.86, -74.36), (4.81, -74.31)]
    orden = orden_optimo_exacto(coords)
    assert orden in ([0, 4, 2, 1, 3], [3, 1, 2, 4, 0])


# --- Criterio 2: casos triviales y límite de tamaño --------------------------

def test_optimo_exacto_casos_triviales():
    assert orden_optimo_exacto([]) == []
    assert orden_optimo_exacto([(4.8, -74.3)]) == [0]
    assert sorted(orden_optimo_exacto([(4.8, -74.3), (4.9, -74.4)])) == [0, 1]


def test_optimo_exacto_rechaza_n_mayor_que_max_n():
    coords = _coords_aleatorias(random.Random(1), 5)
    with pytest.raises(ValueError):
        orden_optimo_exacto(coords, max_n=4)
    assert sorted(orden_optimo_exacto(coords, max_n=5)) == list(range(5))


def test_max_n_por_defecto_viene_de_config():
    assert settings.max_paradas_optimo_exacto == 12
    coords = _coords_aleatorias(random.Random(2), settings.max_paradas_optimo_exacto + 1)
    with pytest.raises(ValueError):
        orden_optimo_exacto(coords)


# --- Criterio 3: gap_pct -----------------------------------------------------

@pytest.mark.parametrize("h, o", [(11.0, 10.0), (10.0, 10.0), (3.7, 2.9), (125.5, 100.25)])
def test_gap_pct_formula(h, o):
    assert gap_pct(h, o) == pytest.approx((h - o) / o * 100, abs=1e-12)


def test_gap_pct_cero_cero():
    assert gap_pct(0, 0) == 0.0


# --- Criterio 4: evaluar_orden -----------------------------------------------

@pytest.mark.parametrize("semilla", range(10))
@pytest.mark.parametrize("n", [3, 5, 7, 9])
def test_evaluar_orden_invariantes(semilla, n):
    coords = _coords_aleatorias(random.Random(1000 + semilla * 10 + n), n)
    ev = evaluar_orden(coords)

    assert isinstance(ev, EvaluacionOrden)
    assert ev.n == n
    assert ev.distancia_original_km == pytest.approx(distancia_total_km(coords), abs=1e-9)
    assert ev.distancia_heuristica_km == pytest.approx(
        _dist(coords, ordenar_paradas(coords)), abs=1e-9
    )
    assert ev.distancia_optima_km is not None
    assert ev.distancia_optima_km <= ev.distancia_heuristica_km + 1e-9
    assert ev.distancia_optima_km <= ev.distancia_original_km + 1e-9
    assert ev.gap_pct >= -1e-9
    assert ev.gap_pct == pytest.approx(
        gap_pct(ev.distancia_heuristica_km, ev.distancia_optima_km), abs=1e-9
    )
    esperado = (
        (ev.distancia_original_km - ev.distancia_heuristica_km) / ev.distancia_original_km * 100
    )
    assert ev.mejora_vs_original_pct == pytest.approx(esperado, abs=1e-9)


@pytest.mark.parametrize("coords", [[], [(4.8, -74.3)], [(4.8, -74.3), (4.8, -74.3)]])
def test_evaluar_orden_original_cero_da_mejora_cero(coords):
    ev = evaluar_orden(coords)
    assert ev.n == len(coords)
    assert ev.distancia_original_km == 0.0
    assert ev.mejora_vs_original_pct == 0.0


def test_evaluar_orden_n_mayor_que_max_n_sin_optimo():
    coords = _coords_aleatorias(random.Random(7), 6)
    ev = evaluar_orden(coords, max_n=4)

    assert ev.n == 6
    assert ev.distancia_optima_km is None
    assert ev.gap_pct is None
    assert ev.distancia_original_km == pytest.approx(distancia_total_km(coords), abs=1e-9)
    assert ev.distancia_heuristica_km == pytest.approx(
        _dist(coords, ordenar_paradas(coords)), abs=1e-9
    )
    # Sin aserto "heurística <= original": no es una garantía de NN+2-opt
    # (en datos reales la variante 31 queda 1 % peor que el orden del archivo).


# --- Smoke sobre datos reales -------------------------------------------------

_PARADAS_REALES = settings.processed_dir / "paradas.csv"


@pytest.mark.skipif(not _PARADAS_REALES.exists(), reason="data/processed no generado (correr run_etl.py)")
def test_smoke_evaluar_variantes_datos_reales():
    paradas = pd.read_csv(_PARADAS_REALES)
    res = evaluar_variantes(paradas, settings.umbral_atipico_km)

    assert len(res) == paradas["ruta_variante_id"].nunique(dropna=False)
    assert (res["distancia_heuristica_km"] >= 0).all()
    con_opt = res.dropna(subset=["distancia_optima_km"])
    assert (con_opt["distancia_optima_km"] <= con_opt["distancia_heuristica_km"] + 1e-9).all()
    assert (con_opt["distancia_optima_km"] <= con_opt["distancia_original_km"] + 1e-9).all()


# --- Criterio 5: evaluar_variantes -------------------------------------------

def _paradas_dos_variantes():
    return pd.DataFrame(
        [
            (1, 10, "A", 4.80, -74.30),
            (2, 10, "B", 4.84, -74.34),
            (3, 10, "SIN", None, None),
            (4, 10, "C", 4.82, -74.32),
            (5, 10, "LEJOS", 5.14, -75.11),  # ~100 km de la ruta
            (6, 20, "D", 4.75, -74.25),
            (7, 20, "E", 4.78, -74.20),
            (8, 20, "F", 4.70, -74.22),
            (9, 20, "G", 4.73, -74.28),
        ],
        columns=["parada_id", "ruta_variante_id", "nombre", "lat", "lon"],
    )


def test_evaluar_variantes_una_fila_por_variante_con_exclusiones():
    paradas = _paradas_dos_variantes()
    umbral = 30.0
    res = evaluar_variantes(paradas, umbral_atipico_km=umbral)

    assert len(res) == 2
    assert {
        "ruta_variante_id",
        "n",
        "distancia_original_km",
        "distancia_heuristica_km",
        "distancia_optima_km",
        "gap_pct",
        "mejora_vs_original_pct",
    } <= set(res.columns)

    filas = res.set_index("ruta_variante_id")
    assert sorted(filas.index) == [10, 20]
    assert filas.loc[10, "n"] == 3  # sin SIN ni LEJOS
    assert filas.loc[20, "n"] == 4

    validas = {10: [(4.80, -74.30), (4.84, -74.34), (4.82, -74.32)]}
    assert filas.loc[10, "distancia_original_km"] == pytest.approx(
        distancia_total_km(validas[10]), abs=1e-9
    )

    for vid, grupo in paradas.groupby("ruta_variante_id"):
        rec = calcular_recorrido(vid, "R", "LABORAL", grupo, umbral_atipico_km=umbral)
        assert filas.loc[vid, "distancia_heuristica_km"] == pytest.approx(
            rec.distancia_km, abs=1e-9
        )
        assert filas.loc[vid, "distancia_optima_km"] <= rec.distancia_km + 1e-9


# --- Variantes con las mismas paradas no se cuentan dos veces ------------------

def test_evaluar_variantes_marca_duplicadas():
    filas = [
        (1, 1, "A", 4.80, -74.30), (2, 1, "B", 4.84, -74.34), (3, 1, "C", 4.82, -74.36),
        (4, 2, "C", 4.82, -74.36), (5, 2, "A", 4.80, -74.30), (6, 2, "B", 4.84, -74.34),
        (7, 3, "A", 4.80, -74.30), (8, 3, "D", 4.90, -74.20),
    ]
    paradas = pd.DataFrame(filas, columns=["parada_id", "ruta_variante_id", "nombre", "lat", "lon"])
    res = evaluar_variantes(paradas, umbral_atipico_km=30.0).set_index("ruta_variante_id")

    assert pd.isna(res.at[1, "duplicada_de"])
    assert res.at[2, "duplicada_de"] == 1
    assert pd.isna(res.at[3, "duplicada_de"])

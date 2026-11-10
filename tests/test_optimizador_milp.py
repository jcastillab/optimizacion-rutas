import itertools
import random
import sys

import pandas as pd
import pytest

from app.services import optimizador_milp as om
from app.services.distancia import haversine_km
from app.services.optimizador_milp import construir_rutas_milp
from app.services.simulador_rutas import Bus, construir_rutas, elegir_bus

BUSES = [Bus("MICRO", 19, 315000.0), Bus("BUSETA", 25, 378000.0), Bus("BUS", 40, 458000.0)]
FINCA = (4.70, -74.10)
V, T = 25.0, 20.0  # max 8,33 km: obliga a repartir los paraderos en varias rutas


def _instancia(semilla, n=7):
    rnd = random.Random(semilla)
    filas = [(i, rnd.randint(3, 18), 4.70 + rnd.uniform(-0.04, 0.04),
              -74.10 + rnd.uniform(-0.04, 0.04)) for i in range(1, n + 1)]
    return pd.DataFrame(filas, columns=["parada_id", "personas", "lat", "lon"])


def _km(coords, ruta):
    return (sum(haversine_km(coords[a], coords[b]) for a, b in zip(ruta, ruta[1:]))
            + haversine_km(coords[ruta[-1]], FINCA))


def _costo(dem, rutas):
    por = dict(zip(dem["parada_id"], dem["personas"]))
    return sum(elegir_bus(sum(por[p] for p in r), BUSES)[2] for r, _ in rutas)


def _banco_exhaustivo(dem):
    """{conjunto: costo} y columnas [(conjunto, costo)] de TODOS los subconjuntos factibles."""
    coords = {r.parada_id: (r.lat, r.lon) for r in dem.itertuples()}
    por = dict(zip(dem["parada_id"], dem["personas"]))
    max_km = V * T / 60
    cols = {}
    for k in range(1, len(coords) + 1):
        for sub in itertools.combinations(coords, k):
            if any(_km(coords, perm) <= max_km for perm in itertools.permutations(sub)):
                cols[frozenset(sub)] = elegir_bus(sum(por[p] for p in sub), BUSES)[2]
    return cols


def _optimo_por_enumeracion(cols, ids):
    """Mínimo costo de particionar ``ids`` con subconjuntos de ``cols`` (DP sobre subconjuntos)."""
    ids = sorted(ids)
    memo = {}

    def f(resto):
        if not resto:
            return 0.0
        if resto in memo:
            return memo[resto]
        primero = min(resto)
        mejor = float("inf")
        for c, costo in cols.items():
            if primero in c and c <= resto:
                mejor = min(mejor, costo + f(resto - c))
        memo[resto] = mejor
        return mejor

    return f(frozenset(ids))


@pytest.mark.parametrize("semilla", [1, 2, 3, 4])
def test_milp_con_banco_completo_coincide_con_el_optimo_por_enumeracion(semilla):
    dem = _instancia(semilla)
    cols = _banco_exhaustivo(dem)
    ids = list(dem["parada_id"])
    items = list(cols.items())
    elegidas = om._resolver(items, ids, 30)
    assert sum(items[i][1] for i in elegidas) == pytest.approx(_optimo_por_enumeracion(cols, ids))
    # y la partición elegida cubre cada paradero exactamente una vez
    assert sorted(p for i in elegidas for p in items[i][0]) == sorted(ids)


@pytest.mark.parametrize("semilla", [1, 2, 3, 4])
def test_milp_no_es_peor_que_la_heuristica_ni_mejor_que_el_optimo(semilla):
    dem = _instancia(semilla)
    heur, _ = construir_rutas(dem, FINCA, V, T, BUSES)
    rutas, sin = construir_rutas_milp(dem, FINCA, V, T, BUSES, tiempo_limite_s=30, semillas=5)
    optimo = _optimo_por_enumeracion(_banco_exhaustivo(dem), dem["parada_id"])
    assert sin == []
    assert optimo - 1e-6 <= _costo(dem, rutas) <= _costo(dem, heur) + 1e-6


def test_milp_rutas_factibles_cubren_una_vez_o_sin_servicio_y_es_determinista():
    dem = pd.concat([_instancia(7), pd.DataFrame([(99, 5, 5.2, -74.1)], columns=_instancia(7).columns)],
                    ignore_index=True)
    coords = {r.parada_id: (r.lat, r.lon) for r in dem.itertuples()}
    a = construir_rutas_milp(dem, FINCA, V, T, BUSES, tiempo_limite_s=30, semillas=5)
    b = construir_rutas_milp(dem, FINCA, V, T, BUSES, tiempo_limite_s=30, semillas=5)
    assert a == b
    rutas, sin = a
    asignadas = [p for r, _ in rutas for p in r]
    assert sin == [99]
    assert sorted(asignadas + sin) == sorted(dem["parada_id"])
    for ruta, km in rutas:
        assert km <= V * T / 60 + 1e-9
        assert km == pytest.approx(_km(coords, ruta))


def test_error_claro_si_no_hay_solver(monkeypatch):
    monkeypatch.setitem(sys.modules, "highspy", None)  # import highspy -> ImportError
    with pytest.raises(RuntimeError, match="highspy"):
        construir_rutas_milp(_instancia(1), FINCA, V, T, BUSES, semillas=1)


def test_error_claro_si_el_solver_no_da_solucion(monkeypatch):
    import highspy

    class Roto(highspy.Highs):
        def run(self):  # no resuelve: no hay solución primal factible
            return highspy.HighsStatus.kOk

    monkeypatch.setattr(highspy, "Highs", Roto)
    with pytest.raises(RuntimeError, match="HiGHS"):
        construir_rutas_milp(_instancia(1), FINCA, V, T, BUSES, semillas=1)

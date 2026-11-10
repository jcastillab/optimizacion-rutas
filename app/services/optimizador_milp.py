"""Rutas por partición de conjuntos (MILP) sobre un banco de rutas candidatas.

Método: se genera un banco de rutas factibles (recorrido <= máximo) y se elige,
con HiGHS, el subconjunto de costo mínimo que cubre cada paradero alcanzable
exactamente una vez.

GARANTÍA: óptimo SOBRE EL BANCO, no óptimo global. Una ruta que no esté en el
banco (otro conjunto de paraderos) no se considera; además cada conjunto se
guarda solo con su orden de menor km encontrado (orden heurístico, no TSP exacto).
Como el banco incluye las rutas de Clarke-Wright+reubicación, el resultado nunca
cuesta más que esa heurística (salvo que el solver se quede sin tiempo sin
mejorar; se parte de esa solución como punto inicial).
"""

from __future__ import annotations

import itertools
import random

import pandas as pd

from app.services.distancia import haversine_km
from app.services.simulador_rutas import Bus, construir_rutas, elegir_bus


def _banco_candidatas(dem, destino, velocidad_kmh, tiempo_max_min, buses, semillas,
                      vecinos=6, rutas_extra=()):
    max_km = velocidad_kmh * tiempo_max_min / 60
    """{frozenset(paraderos): (km, ruta)} con el orden de menor km por conjunto."""
    coords = {r.parada_id: (r.lat, r.lon) for r in dem.itertuples()}
    banco: dict[frozenset, tuple[float, tuple]] = {}

    def km_de(ruta):
        tramos = sum(haversine_km(coords[a], coords[b]) for a, b in zip(ruta, ruta[1:]))
        return tramos + haversine_km(coords[ruta[-1]], destino)

    def agregar(ruta):
        ruta = tuple(ruta)
        km = km_de(ruta)
        if km > max_km:
            return
        clave = frozenset(ruta)
        if clave not in banco or km < banco[clave][0] - 1e-12:
            banco[clave] = (km, ruta)

    alcanzables = [p for p, c in coords.items() if haversine_km(c, destino) <= max_km]
    for p in alcanzables:
        agregar((p,))
    # Heurística determinista + `semillas` órdenes iniciales barajados.
    for s in [None, *range(semillas)]:
        d = dem
        if s is not None:
            orden = list(range(len(dem)))
            random.Random(s).shuffle(orden)
            d = dem.iloc[orden]
        for ruta, _ in construir_rutas(d, destino, velocidad_kmh, tiempo_max_min, buses)[0]:
            agregar(ruta)
    for ruta in rutas_extra:
        agregar(ruta)
    # Rutas de 2 y 3 paraderos desde los k vecinos más cercanos.
    for p in alcanzables:
        cerca = sorted((q for q in alcanzables if q != p),
                       key=lambda q: (haversine_km(coords[p], coords[q]), q))[:vecinos]
        for q in cerca:
            agregar((p, q))
        for q, r in itertools.permutations(cerca, 2):
            agregar((p, q, r))
    # Sub-rutas: cada ruta del banco sin uno de sus paraderos.
    for _, ruta in list(banco.values()):
        if len(ruta) > 1:
            for i in range(len(ruta)):
                agregar(ruta[:i] + ruta[i + 1:])
    return banco


def _resolver(columnas, cubrir, tiempo_limite_s, inicial=None):
    """Partición de conjuntos de costo mínimo. ``columnas``: [(conjunto, costo)].

    Devuelve los índices de las columnas elegidas. Lanza RuntimeError si no hay
    solver o no se obtiene una solución factible que cubra todo exactamente una vez.
    """
    try:
        import highspy
        import numpy as np
    except ImportError as e:
        raise RuntimeError(f"El método MILP necesita highspy (pip install highspy): {e}") from e

    fila = {p: i for i, p in enumerate(cubrir)}
    start, index = [0], []
    for conj, _ in columnas:
        index.extend(sorted(fila[p] for p in conj))
        start.append(len(index))
    n = len(columnas)
    lp = highspy.HighsLp()
    lp.num_col_, lp.num_row_ = n, len(cubrir)
    lp.col_cost_ = np.array([c for _, c in columnas], dtype=float)
    lp.col_lower_ = np.zeros(n)
    lp.col_upper_ = np.ones(n)
    lp.row_lower_ = np.ones(len(cubrir))
    lp.row_upper_ = np.ones(len(cubrir))
    lp.a_matrix_.format_ = highspy.MatrixFormat.kColwise
    lp.a_matrix_.start_ = np.array(start, dtype=np.int32)
    lp.a_matrix_.index_ = np.array(index, dtype=np.int32)
    lp.a_matrix_.value_ = np.ones(len(index))
    lp.integrality_ = [highspy.HighsVarType.kInteger] * n

    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    h.setOptionValue("time_limit", float(tiempo_limite_s))
    h.setOptionValue("threads", 1)  # reproducible
    h.setOptionValue("random_seed", 0)
    h.passModel(lp)
    if inicial:
        sol = highspy.HighsSolution()
        sol.col_value = [1.0 if i in inicial else 0.0 for i in range(n)]
        h.setSolution(sol)
    h.run()
    estado = h.getModelStatus()
    info = h.getInfo()
    if info.primal_solution_status != 2 or estado not in (
            highspy.HighsModelStatus.kOptimal, highspy.HighsModelStatus.kTimeLimit,
            highspy.HighsModelStatus.kInterrupt, highspy.HighsModelStatus.kSolutionLimit):
        raise RuntimeError(f"HiGHS no encontró solución factible (estado: {h.modelStatusToString(estado)})")
    x = h.getSolution().col_value
    _resolver.diagnostico = {"estado": h.modelStatusToString(estado), "gap_mip": info.mip_gap,
                             "columnas": n}
    elegidas = [i for i, v in enumerate(x) if v > 0.5]
    cubiertos = sorted(p for i in elegidas for p in columnas[i][0])
    if cubiertos != sorted(cubrir):
        raise RuntimeError("La solución de HiGHS no cubre cada paradero exactamente una vez")
    return elegidas


def construir_rutas_milp(
    dem: pd.DataFrame,
    destino: tuple[float, float],
    velocidad_kmh: float,
    tiempo_max_min: float,
    buses: list[Bus],
    *,
    tiempo_limite_s: float = 60,
    semillas: int = 200,
    rutas_extra: list[list[int]] = (),
) -> tuple[list[tuple[list[int], float]], list[int]]:
    """Misma firma de retorno que ``construir_rutas``; óptimo sobre el banco de rutas.

    ``rutas_extra``: rutas adicionales (listas de parada_id) para el banco, p. ej.
    de otro método; las que excedan el recorrido máximo se ignoran. El último
    estado/gap del solver queda en ``_resolver.diagnostico``.
    """
    max_km = velocidad_kmh * tiempo_max_min / 60
    coords = {r.parada_id: (r.lat, r.lon) for r in dem.itertuples()}
    sin_servicio = [p for p, c in coords.items() if haversine_km(c, destino) > max_km]
    cubrir = sorted(p for p in coords if p not in sin_servicio)
    if not cubrir:
        return [], sin_servicio
    carga = dict(zip(dem["parada_id"], dem["personas"]))

    banco = _banco_candidatas(dem, destino, velocidad_kmh, tiempo_max_min, buses, semillas,
                              rutas_extra=rutas_extra)
    # Orden estable: la salida del solver no depende del orden de inserción.
    items = sorted(banco.items(), key=lambda kv: sorted(kv[0]))
    columnas = [(c, elegir_bus(sum(carga[p] for p in c), buses)[2]) for c, _ in items]

    base = construir_rutas(dem, destino, velocidad_kmh, tiempo_max_min, buses)[0]
    pos = {c: i for i, (c, _) in enumerate(items)}
    inicial = {pos[frozenset(r)] for r, _ in base}
    elegidas = _resolver(columnas, cubrir, tiempo_limite_s, inicial)
    return [(list(items[i][1][1]), items[i][1][0]) for i in elegidas], sin_servicio

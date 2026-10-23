"""Orden estimado de visita de las paradas de una ruta.

Los datos fuente no traen el orden real de recogida, así que se calcula un
camino abierto (sin destino fijo) con:
1. Heurística de vecino más cercano, empezando en la parada más alejada del
   centroide de la ruta.
2. Mejora 2-opt para camino abierto, para quitar cruces evidentes.

Todo sobre distancia haversine (ver ``distancia.py``). Es una estimación.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.services.distancia import Coord, haversine_km, matriz_haversine_km

_EPSILON = 1e-9


def ordenar_paradas(coords: Sequence[Coord]) -> list[int]:
    """Devuelve los índices de ``coords`` en orden de visita estimado."""
    n = len(coords)
    if n <= 2:
        return list(range(n))

    centroide = (
        sum(lat for lat, _ in coords) / n,
        sum(lon for _, lon in coords) / n,
    )
    inicio = max(range(n), key=lambda i: haversine_km(coords[i], centroide))

    dist = matriz_haversine_km(coords)
    pendientes = set(range(n)) - {inicio}
    ruta = [inicio]
    while pendientes:
        actual = ruta[-1]
        siguiente = min(pendientes, key=lambda j: dist[actual][j])
        ruta.append(siguiente)
        pendientes.remove(siguiente)

    return _two_opt_abierto(ruta, dist)


def _two_opt_abierto(ruta: list[int], dist: list[list[float]]) -> list[int]:
    """Invierte segmentos mientras acorte el camino abierto."""
    n = len(ruta)
    mejorado = True
    while mejorado:
        mejorado = False
        for i in range(n - 2):
            for j in range(i + 2, n):
                a, b, c = ruta[i], ruta[i + 1], ruta[j]
                if j + 1 < n:
                    d = ruta[j + 1]
                    delta = dist[a][c] + dist[b][d] - dist[a][b] - dist[c][d]
                else:
                    # Extremo abierto: solo cambian las aristas (a,b) -> (a,c).
                    delta = dist[a][c] - dist[a][b]
                if delta < -_EPSILON:
                    ruta[i + 1 : j + 1] = reversed(ruta[i + 1 : j + 1])
                    mejorado = True
    return ruta

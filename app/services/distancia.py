"""Cálculo de distancias entre coordenadas (lat, lon) en grados.

Usa la fórmula de haversine (línea recta sobre la esfera terrestre). Es el
único punto de cálculo de distancia del proyecto: si más adelante se pasa a
ruteo por carretera (OSRM u otro), el cambio queda contenido aquí.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

RADIO_TIERRA_KM = 6371.0088

Coord = tuple[float, float]


def haversine_km(a: Coord, b: Coord) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * RADIO_TIERRA_KM * math.asin(math.sqrt(h))


def distancia_total_km(coords: Sequence[Coord]) -> float:
    """Suma de los tramos consecutivos de una secuencia ordenada de coordenadas."""
    return sum(haversine_km(a, b) for a, b in zip(coords, coords[1:]))


def matriz_haversine_km(coords: Sequence[Coord]) -> list[list[float]]:
    n = len(coords)
    m = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            m[i][j] = m[j][i] = haversine_km(coords[i], coords[j])
    return m

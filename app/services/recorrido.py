"""Recorrido por variante de ruta: paradas ordenadas, excluidas y distancia.

Una parada se excluye del trazado si no tiene coordenada o si está muy lejos
de la mediana de la ruta (coordenada atípica, p. ej. un error de captura).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app.services.distancia import Coord, distancia_total_km, haversine_km
from app.services.orden_paradas import ordenar_paradas


@dataclass(frozen=True)
class ParadaRecorrido:
    parada_id: int
    nombre: str
    lat: float
    lon: float
    orden: int


@dataclass
class Recorrido:
    ruta_variante_id: int
    ruta_base: str
    tipo_dia: str
    paradas: list[ParadaRecorrido] = field(default_factory=list)
    excluidas: list[tuple[str, str]] = field(default_factory=list)  # (nombre, motivo)
    distancia_km: float = 0.0


def _mediana(valores: list[float]) -> float:
    ordenados = sorted(valores)
    n = len(ordenados)
    mitad = n // 2
    return ordenados[mitad] if n % 2 else (ordenados[mitad - 1] + ordenados[mitad]) / 2


def calcular_recorrido(
    ruta_variante_id: int,
    ruta_base: str,
    tipo_dia: str,
    paradas: pd.DataFrame,
    umbral_atipico_km: float,
) -> Recorrido:
    """``paradas`` son las filas de ``paradas.csv`` de una sola variante."""
    rec = Recorrido(ruta_variante_id=ruta_variante_id, ruta_base=ruta_base, tipo_dia=tipo_dia)

    con_coord = []
    for row in paradas.itertuples():
        if pd.isna(row.lat) or pd.isna(row.lon):
            rec.excluidas.append((row.nombre, "sin coordenada"))
        else:
            con_coord.append(row)

    if not con_coord:
        return rec

    centro = (
        _mediana([r.lat for r in con_coord]),
        _mediana([r.lon for r in con_coord]),
    )
    validas = []
    for row in con_coord:
        d = haversine_km((row.lat, row.lon), centro)
        if d > umbral_atipico_km:
            rec.excluidas.append((row.nombre, f"coordenada atípica ({d:.0f} km de la ruta)"))
        else:
            validas.append(row)

    coords: list[Coord] = [(r.lat, r.lon) for r in validas]
    orden = ordenar_paradas(coords)
    rec.paradas = [
        ParadaRecorrido(
            parada_id=validas[i].parada_id,
            nombre=validas[i].nombre,
            lat=validas[i].lat,
            lon=validas[i].lon,
            orden=posicion + 1,
        )
        for posicion, i in enumerate(orden)
    ]
    rec.distancia_km = distancia_total_km([(p.lat, p.lon) for p in rec.paradas])
    return rec

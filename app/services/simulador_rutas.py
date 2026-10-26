"""Simulador de rutas nuevas a partir de paraderos existentes.

Cada ruta arranca en un paradero, recoge personas en paraderos existentes y
termina en la finca de destino (Nivel2 de los datos; coordenadas del KML). Para
cada ruta se elige el tipo de bus y la cantidad que cuestan menos.

Supuestos:
- Una persona viaja desde su paradero hasta la finca: el tiempo máximo incluye
  el tramo final, y todo el recorrido de la ruta cuenta para cada persona.
- Una ruta puede necesitar varios buses del mismo tipo; cada bus hace el mismo
  recorrido.
- Costo de un bus = mediana de las tarifas REGULAR de ese tipo en los datos.
- Un paradero a más de velocidad × tiempo de la finca no puede servirse: se
  devuelve aparte en vez de descartarse en silencio.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from app.services.distancia import haversine_km


@dataclass(frozen=True)
class Bus:
    tipo: str
    capacidad: int
    costo: float


def catalogo_buses(tarifas: pd.DataFrame) -> list[Bus]:
    regular = tarifas[tarifas["tipo_tarifa"] == "REGULAR"]
    return [
        Bus(tipo, int(g["capacidad"].median()), float(g["tarifa"].median()))
        for tipo, g in regular.groupby("tipo_vehiculo")
    ]


def demanda_por_paradero(empleados: pd.DataFrame, paradas: pd.DataFrame) -> pd.DataFrame:
    """Personas por (paradero, finca de destino) con coordenadas del paradero."""
    por_parada = (
        empleados.dropna(subset=["parada_id"])
        .groupby(["cod_nivel2", "parada_id"]).size()
        .rename("personas").reset_index()
    )
    return por_parada.merge(paradas[["parada_id", "nombre", "lat", "lon"]], on="parada_id")


def elegir_bus(personas: int, buses: list[Bus]) -> tuple[Bus, int, float]:
    """Tipo, cantidad y costo total que cubren ``personas`` al menor costo."""
    bus, n = min(
        ((b, math.ceil(personas / b.capacidad)) for b in buses),
        key=lambda bn: (bn[1] * bn[0].costo, bn[0].costo),
    )
    return bus, n, n * bus.costo


def construir_rutas(
    dem: pd.DataFrame,
    destino: tuple[float, float],
    velocidad_kmh: float,
    tiempo_max_min: float,
) -> tuple[list[tuple[list[int], float]], list[int]]:
    """Rutas hacia ``destino`` y paraderos sin servicio.

    ``dem`` trae ``parada_id, personas, lat, lon`` de una sola finca. Devuelve
    ``([(ruta, km_total), ...], sin_servicio)``. Cada ruta arranca en el paradero
    con más personas sin asignar y crece hacia el más cercano mientras el
    recorrido total (paraderos + tramo final a la finca) quepa en el máximo.
    """
    max_km = velocidad_kmh * tiempo_max_min / 60
    coords = {r.parada_id: (r.lat, r.lon) for r in dem.itertuples()}
    sin_servicio = [p for p, c in coords.items() if haversine_km(c, destino) > max_km]
    pendientes = set(coords) - set(sin_servicio)
    orden = dem.sort_values(["personas", "parada_id"], ascending=[False, True])
    rutas: list[tuple[list[int], float]] = []
    for semilla in orden["parada_id"]:
        if semilla not in pendientes:
            continue
        ruta, km = [semilla], 0.0
        pendientes.remove(semilla)
        while True:
            ult = coords[ruta[-1]]
            factibles = [
                p for p in pendientes
                if km + haversine_km(ult, coords[p]) + haversine_km(coords[p], destino) <= max_km
            ]
            if not factibles:
                break
            c = min(factibles, key=lambda p: (haversine_km(ult, coords[p]), p))
            km += haversine_km(ult, coords[c])
            ruta.append(c)
            pendientes.remove(c)
        rutas.append((ruta, km + haversine_km(coords[ruta[-1]], destino)))
    return rutas, sin_servicio


def simular(
    empleados: pd.DataFrame,
    paradas: pd.DataFrame,
    tarifas: pd.DataFrame,
    velocidad_kmh: float,
    tiempo_max_min: float,
    destinos: dict[int, tuple[float, float]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rutas simuladas y paraderos sin servicio, por finca (``cod_nivel2``) de ``destinos``."""
    dem = demanda_por_paradero(empleados, paradas)
    buses = catalogo_buses(tarifas)
    filas, sin = [], []
    for cod, destino in destinos.items():
        d = dem[dem["cod_nivel2"] == cod]
        rutas, sin_servicio = construir_rutas(d, destino, velocidad_kmh, tiempo_max_min)
        por_id = d.set_index("parada_id")
        for ruta, km in rutas:
            personas = int(por_id.loc[ruta, "personas"].sum())
            bus, n, costo = elegir_bus(personas, buses)
            filas.append({
                "ruta_simulada": len(filas) + 1,
                "finca": cod,
                "paradas": len(ruta),
                "parada_ids": " ".join(str(p) for p in ruta),
                "personas": personas,
                "km": round(km, 2),
                "minutos_max": round(km / velocidad_kmh * 60, 1),
                "tipo_bus": bus.tipo,
                "capacidad": bus.capacidad,
                "buses": n,
                "costo_total": costo,
            })
        for p in sin_servicio:
            fila = por_id.loc[p]
            sin.append({"finca": cod, "parada_id": p, "personas": int(fila["personas"])})
    return pd.DataFrame(filas), pd.DataFrame(sin, columns=["finca", "parada_id", "personas"])

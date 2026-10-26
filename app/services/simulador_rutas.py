"""Simulador de rutas nuevas a partir de paraderos existentes.

Arma rutas con paraderos ya existentes según cuántas personas tiene asignadas
cada uno, y para cada ruta elige el tipo de bus y la cantidad que minimizan el
costo (tarifa de Proveedores_y_Tarifas).

Supuestos:
- Una persona viaja desde su paradero hasta el último paradero de la ruta: el
  destino real (planta) no está en los datos. El tiempo máximo se mide así.
- Una ruta puede necesitar varios buses del mismo tipo; cada bus hace el mismo
  recorrido.
- Costo de un bus = mediana de las tarifas REGULAR de ese tipo en los datos.
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
    por_parada = empleados.dropna(subset=["parada_id"]).groupby("parada_id").size()
    dem = por_parada.rename("personas").reset_index()
    return dem.merge(paradas[["parada_id", "nombre", "lat", "lon"]], on="parada_id")


def elegir_bus(personas: int, buses: list[Bus]) -> tuple[Bus, int, float]:
    """Tipo, cantidad y costo total que cubren ``personas`` al menor costo."""
    bus, n = min(
        ((b, math.ceil(personas / b.capacidad)) for b in buses),
        key=lambda bn: (bn[1] * bn[0].costo, bn[0].costo),
    )
    return bus, n, n * bus.costo


def construir_rutas(paradas: pd.DataFrame, velocidad_kmh: float, tiempo_max_min: float) -> list[list[int]]:
    """Rutas (listas de parada_id en orden) con recorrido <= velocidad * tiempo.

    Cada ruta arranca en la parada con más personas sin asignar y crece hacia la
    más cercana mientras el recorrido acumulado quepa en el tiempo máximo. Como
    el primer paradero es el de mayor recorrido, con el recorrido total basta.
    """
    max_km = velocidad_kmh * tiempo_max_min / 60
    coords = {r.parada_id: (r.lat, r.lon) for r in paradas.itertuples()}
    pendientes = set(coords)
    orden = paradas.sort_values(["personas", "parada_id"], ascending=[False, True])
    rutas: list[list[int]] = []
    for semilla in orden["parada_id"]:
        if semilla not in pendientes:
            continue
        ruta, km = [semilla], 0.0
        pendientes.remove(semilla)
        while pendientes:
            ult = coords[ruta[-1]]
            cercana = min(pendientes, key=lambda p: (haversine_km(ult, coords[p]), p))
            paso = haversine_km(ult, coords[cercana])
            if km + paso > max_km:
                break  # la más cercana no cabe => ninguna otra cabe
            km += paso
            ruta.append(cercana)
            pendientes.remove(cercana)
        rutas.append(ruta)
    return rutas


def simular(
    empleados: pd.DataFrame,
    paradas: pd.DataFrame,
    tarifas: pd.DataFrame,
    velocidad_kmh: float,
    tiempo_max_min: float,
) -> pd.DataFrame:
    dem = demanda_por_paradero(empleados, paradas)
    buses = catalogo_buses(tarifas)
    por_id = dem.set_index("parada_id")
    coords = {r.parada_id: (r.lat, r.lon) for r in dem.itertuples()}
    filas = []
    for i, ruta in enumerate(construir_rutas(dem, velocidad_kmh, tiempo_max_min), 1):
        personas = int(por_id.loc[ruta, "personas"].sum())
        bus, n, costo = elegir_bus(personas, buses)
        km = sum(haversine_km(coords[a], coords[b]) for a, b in zip(ruta, ruta[1:]))
        filas.append({
            "ruta_simulada": i,
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
    return pd.DataFrame(filas)

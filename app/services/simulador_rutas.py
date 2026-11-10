"""Simulador de rutas nuevas a partir de paraderos existentes.

Cada ruta recoge personas en paraderos existentes y termina en la finca de
destino (Nivel2 de los datos; coordenadas del KML). Para cada ruta se elige el
tipo de bus y la cantidad que cuestan menos.

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
    buses: list[Bus],
) -> tuple[list[tuple[list[int], float]], list[int]]:
    """Rutas hacia ``destino`` y paraderos sin servicio (ahorros de Clarke-Wright).

    ``dem`` trae ``parada_id, personas, lat, lon`` de una sola finca. Empieza con
    una ruta por paradero y fusiona, mientras baje el costo de buses, dos rutas
    concatenadas (la de atrás termina donde empieza la otra) si el recorrido total
    (paraderos + tramo final a la finca) sigue dentro del máximo.
    Devuelve ``([(ruta, km_total), ...], sin_servicio)``.
    """
    max_km = velocidad_kmh * tiempo_max_min / 60
    coords = {r.parada_id: (r.lat, r.lon) for r in dem.itertuples()}
    carga = dict(zip(dem["parada_id"], dem["personas"]))
    sin_servicio = [p for p, c in coords.items() if haversine_km(c, destino) > max_km]

    def km_de(ruta: list[int]) -> float:
        tramos = sum(haversine_km(coords[a], coords[b]) for a, b in zip(ruta, ruta[1:]))
        return tramos + haversine_km(coords[ruta[-1]], destino)

    def costo_de(ruta: list[int]) -> float:
        return elegir_bus(sum(carga[p] for p in ruta), buses)[2]

    rutas = {p: [p] for p in coords if p not in sin_servicio}
    # Cada paso baja el costo total de forma estricta: el ciclo termina.
    while _fusionar_mejor(rutas, km_de, costo_de, max_km) or _reubicar(rutas, km_de, costo_de, max_km):
        pass
    return [(ruta, km_de(ruta)) for ruta in rutas.values()], sin_servicio


def construir_rutas_voraz(
    dem: pd.DataFrame,
    destino: tuple[float, float],
    velocidad_kmh: float,
    tiempo_max_min: float,
    buses: list[Bus],
) -> tuple[list[tuple[list[int], float]], list[int]]:
    """Voraz con tope de capacidad; mismo retorno que ``construir_rutas``.

    Semilla = paradero libre con más personas; crece al paradero libre más cercano
    al último mientras el recorrido total quepa y la carga no pase la capacidad del
    bus más grande del catálogo (así cada ruta usa un solo bus).
    """
    max_km = velocidad_kmh * tiempo_max_min / 60
    cap = max(b.capacidad for b in buses)
    c = {r.parada_id: (r.lat, r.lon) for r in dem.itertuples()}
    carga = dict(zip(dem["parada_id"], dem["personas"]))
    sin = [p for p in c if haversine_km(c[p], destino) > max_km]
    libres = {p for p in c if p not in sin}

    def km(r):
        return (sum(haversine_km(c[a], c[b]) for a, b in zip(r, r[1:]))
                + haversine_km(c[r[-1]], destino))

    rutas = []
    while libres:
        ruta = [max(sorted(libres), key=lambda p: carga[p])]
        libres.discard(ruta[0])
        total = carga[ruta[0]]
        while True:
            cand = sorted(libres, key=lambda q: (haversine_km(c[ruta[-1]], c[q]), q))
            nuevo = next((q for q in cand
                          if total + carga[q] <= cap and km(ruta + [q]) <= max_km), None)
            if nuevo is None:
                break
            ruta.append(nuevo)
            total += carga[nuevo]
            libres.discard(nuevo)
        rutas.append((ruta, km(ruta)))
    return rutas, sin


def construir_rutas_mejor(dem, destino, velocidad_kmh, tiempo_max_min, buses):
    """Corre Clarke-Wright+reubicación y el voraz con tope; deja la de menor costo
    total (empate: menos rutas)."""
    carga = dict(zip(dem["parada_id"], dem["personas"]))
    candidatas = [f(dem, destino, velocidad_kmh, tiempo_max_min, buses)
                  for f in (construir_rutas, construir_rutas_voraz)]
    return min(candidatas, key=lambda rs: (
        sum(elegir_bus(sum(carga[p] for p in r), buses)[2] for r, _ in rs[0]), len(rs[0])))


def _fusionar_mejor(rutas, km_de, costo_de, max_km) -> bool:
    """Concatena el par de rutas que más baja el costo (si hay alguno)."""
    mejor = None
    for a in rutas:
        for b in rutas:
            if a == b:
                continue
            nueva = rutas[a] + rutas[b]
            if km_de(nueva) > max_km:
                continue
            ahorro = costo_de(rutas[a]) + costo_de(rutas[b]) - costo_de(nueva)
            if ahorro > 0 and (mejor is None or ahorro > mejor[0]):
                mejor = (ahorro, a, b)
    if mejor is None:
        return False
    _, a, b = mejor
    rutas[a] = rutas[a] + rutas.pop(b)
    return True


def _reubicar(rutas, km_de, costo_de, max_km) -> bool:
    """Mueve un paradero al inicio o al final de otra ruta si baja el costo total.

    Quitar un paradero nunca alarga el recorrido (desigualdad triangular), así que
    la ruta de origen sigue dentro del máximo.
    """
    for a in list(rutas):
        for p in list(rutas[a]):
            resto = [x for x in rutas[a] if x != p]
            if not resto:
                continue
            for b in rutas:
                if b == a:
                    continue
                for nueva in ([*rutas[b], p], [p, *rutas[b]]):
                    if km_de(nueva) > max_km:
                        continue
                    ganancia = (costo_de(rutas[a]) + costo_de(rutas[b])
                                - costo_de(resto) - costo_de(nueva))
                    if ganancia > 0:
                        rutas[a] = resto
                        rutas[b] = nueva
                        return True
    return False


def simular(
    empleados: pd.DataFrame,
    paradas: pd.DataFrame,
    tarifas: pd.DataFrame,
    velocidad_kmh: float,
    tiempo_max_min: float,
    destinos: dict[int, tuple[float, float]],
    metodo: str = "heuristica",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rutas simuladas y paraderos sin servicio, por finca (``cod_nivel2``) de ``destinos``.

    ``metodo``: "heuristica" (rápida, segundos: por finca corre Clarke-Wright +
    reubicación y el voraz con tope de capacidad y deja la de menor costo) o
    "milp" (partición de conjuntos sobre un banco de rutas; ver
    ``optimizador_milp``; tarda minutos y no está pensado para la web).
    """
    if metodo == "milp":
        from app.services.optimizador_milp import construir_rutas_milp as construir
    elif metodo == "heuristica":
        construir = construir_rutas_mejor
    else:
        raise ValueError(f"metodo desconocido: {metodo!r} (use 'heuristica' o 'milp')")
    dem = demanda_por_paradero(empleados, paradas)
    buses = catalogo_buses(tarifas)
    filas, sin = [], []
    for cod, destino in destinos.items():
        d = dem[dem["cod_nivel2"] == cod]
        rutas, sin_servicio = construir(d, destino, velocidad_kmh, tiempo_max_min, buses)
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

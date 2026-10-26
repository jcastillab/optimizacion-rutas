import math

import pandas as pd
import pytest

from app.core.config import settings
from app.services.distancia import haversine_km
from app.services.simulador_rutas import (
    Bus,
    catalogo_buses,
    construir_rutas,
    demanda_por_paradero,
    elegir_bus,
    simular,
)

BUSES = [Bus("MICRO", 19, 315000.0), Bus("BUSETA", 25, 378000.0), Bus("BUS", 40, 458000.0)]


def _paradas(filas):
    """filas = [(parada_id, personas, lat, lon)] -> DataFrame como en paradas + demanda."""
    return pd.DataFrame(filas, columns=["parada_id", "personas", "lat", "lon"])


def _km(paradas, ruta):
    coords = {r.parada_id: (r.lat, r.lon) for r in paradas.itertuples()}
    return sum(haversine_km(coords[a], coords[b]) for a, b in zip(ruta, ruta[1:]))


def test_catalogo_buses_usa_mediana_regular_y_capacidad():
    tarifas = pd.DataFrame(
        [("BUS", 40, 400000, "REGULAR"), ("BUS", 40, 500000, "REGULAR"),
         ("BUS", 40, 999999, "FESTIVOS"), ("MICRO", 19, 300000, "REGULAR")],
        columns=["tipo_vehiculo", "capacidad", "tarifa", "tipo_tarifa"],
    )
    buses = {b.tipo: b for b in catalogo_buses(tarifas)}
    assert buses["BUS"] == Bus("BUS", 40, 450000.0)  # mediana de REGULAR, sin FESTIVOS
    assert buses["MICRO"].capacidad == 19


def test_demanda_cuenta_empleados_por_paradero():
    empleados = pd.DataFrame({"parada_id": [1, 1, 2, None]})
    paradas = pd.DataFrame({"parada_id": [1, 2, 3], "nombre": ["A", "B", "C"],
                            "lat": [4.7, 4.8, 4.9], "lon": [-74.2, -74.3, -74.4]})
    dem = demanda_por_paradero(empleados, paradas).set_index("parada_id")
    assert dem.loc[1, "personas"] == 2
    assert dem.loc[2, "personas"] == 1
    assert 3 not in dem.index  # sin personas no entra a la demanda


def test_elegir_bus_minimiza_costo_total_no_el_bus_mas_grande():
    # 19 personas: un MICRO basta y cuesta menos que un BUS de 40 plazas.
    bus, n, costo = elegir_bus(19, BUSES)
    assert (bus.tipo, n, costo) == ("MICRO", 1, 315000.0)
    # 45 personas: BUSETA x2 = 756000 < BUS x2 = 916000 < MICRO x3 = 945000.
    bus, n, costo = elegir_bus(45, BUSES)
    assert (bus.tipo, n) == ("BUSETA", 2)
    assert costo == pytest.approx(756000.0)


def test_construir_rutas_asigna_cada_parada_una_vez():
    paradas = _paradas([(i, 5, 4.7 + i * 0.01, -74.2) for i in range(1, 9)])
    rutas = construir_rutas(paradas, velocidad_kmh=25.0, tiempo_max_min=60.0)
    asignadas = [p for r in rutas for p in r]
    assert sorted(asignadas) == list(range(1, 9))


def test_construir_rutas_respeta_tiempo_maximo_de_viaje():
    # Paradas separadas ~10,9 km en línea; con 25 km/h y 60 min el máximo es 25 km.
    # Dos tramos (~21,8 km) caben; un tercero (~32,7 km) no => rutas de 3 paradas.
    paradas = _paradas([(i, 5, 4.7, -74.2 + i * 0.1) for i in range(1, 7)])
    max_km = settings.velocidad_bus_kmh * settings.tiempo_max_viaje_min / 60
    rutas = construir_rutas(paradas, settings.velocidad_bus_kmh, settings.tiempo_max_viaje_min)
    for ruta in rutas:
        assert _km(paradas, ruta) <= max_km + 1e-9
    assert sorted(len(r) for r in rutas) == [3, 3]


def test_construir_rutas_semilla_es_la_parada_con_mas_personas():
    paradas = _paradas([(1, 2, 4.70, -74.20), (2, 30, 4.71, -74.20), (3, 1, 4.72, -74.20)])
    assert construir_rutas(paradas, 25.0, 60.0)[0][0] == 2


def test_simular_personas_y_buses_cuadran():
    empleados = pd.DataFrame({"parada_id": [1] * 45 + [2] * 3})
    paradas = pd.DataFrame({"parada_id": [1, 2], "nombre": ["A", "B"],
                            "lat": [4.70, 4.705], "lon": [-74.20, -74.20]})
    tarifas = pd.DataFrame(
        [("MICRO", 19, 315000, "REGULAR"), ("BUSETA", 25, 378000, "REGULAR"),
         ("BUS", 40, 458000, "REGULAR")],
        columns=["tipo_vehiculo", "capacidad", "tarifa", "tipo_tarifa"],
    )
    res = simular(empleados, paradas, tarifas, 25.0, 60.0)
    assert res["personas"].sum() == 48
    assert (res["buses"] * res["capacidad"] >= res["personas"]).all()
    tarifa_de = {"MICRO": 315000, "BUSETA": 378000, "BUS": 458000}
    assert (res["costo_total"] == res["buses"] * res["tipo_bus"].map(tarifa_de)).all()


@pytest.mark.skipif(not (settings.processed_dir / "empleados.csv").exists(),
                    reason="falta data/processed (correr run_etl.py)")
def test_simulador_datos_reales_cubre_a_todos_con_parada():
    e = pd.read_csv(settings.processed_dir / "empleados.csv")
    p = pd.read_csv(settings.processed_dir / "paradas.csv")
    res = simular(e, p, pd.read_csv(settings.processed_dir / "tarifas.csv"),
                  settings.velocidad_bus_kmh, settings.tiempo_max_viaje_min)
    assert res["personas"].sum() == e["parada_id"].notna().sum()
    assert res["paradas"].sum() == e["parada_id"].nunique()
    assert (res["km"] <= settings.velocidad_bus_kmh * settings.tiempo_max_viaje_min / 60 + 1e-6).all()

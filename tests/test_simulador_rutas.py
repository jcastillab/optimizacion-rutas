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
FINCA = (4.70, -74.10)  # destino de prueba: la ruta termina aquí


def _dem(filas):
    """filas = [(parada_id, personas, lat, lon)] -> demanda de una sola finca."""
    return pd.DataFrame(filas, columns=["parada_id", "personas", "lat", "lon"])


def _km_total(dem, ruta, destino):
    coords = {r.parada_id: (r.lat, r.lon) for r in dem.itertuples()}
    tramos = list(zip(ruta, ruta[1:]))
    km = sum(haversine_km(coords[a], coords[b]) for a, b in tramos)
    return km + haversine_km(coords[ruta[-1]], destino)


def test_catalogo_buses_usa_mediana_regular_y_capacidad():
    tarifas = pd.DataFrame(
        [("BUS", 40, 400000, "REGULAR"), ("BUS", 40, 500000, "REGULAR"),
         ("BUS", 40, 999999, "FESTIVOS"), ("MICRO", 19, 300000, "REGULAR")],
        columns=["tipo_vehiculo", "capacidad", "tarifa", "tipo_tarifa"],
    )
    buses = {b.tipo: b for b in catalogo_buses(tarifas)}
    assert buses["BUS"] == Bus("BUS", 40, 450000.0)  # mediana de REGULAR, sin FESTIVOS
    assert buses["MICRO"].capacidad == 19


def test_demanda_agrupa_por_paradero_y_finca():
    empleados = pd.DataFrame({"parada_id": [1, 1, 1, 2, None],
                              "cod_nivel2": [86, 86, 87, 86, 86]})
    paradas = pd.DataFrame({"parada_id": [1, 2, 3], "nombre": ["A", "B", "C"],
                            "lat": [4.7, 4.8, 4.9], "lon": [-74.2, -74.3, -74.4]})
    dem = demanda_por_paradero(empleados, paradas)
    por = {(r.parada_id, r.cod_nivel2): r.personas for r in dem.itertuples()}
    assert por == {(1, 86): 2, (1, 87): 1, (2, 86): 1}
    assert 3 not in set(dem["parada_id"])  # sin personas no entra


def test_elegir_bus_minimiza_costo_total_no_el_bus_mas_grande():
    # 19 personas: un MICRO basta y cuesta menos que un BUS de 40 plazas.
    bus, n, costo = elegir_bus(19, BUSES)
    assert (bus.tipo, n, costo) == ("MICRO", 1, 315000.0)
    # 45 personas: BUSETA x2 = 756000 < BUS x2 = 916000 < MICRO x3 = 945000.
    bus, n, costo = elegir_bus(45, BUSES)
    assert (bus.tipo, n) == ("BUSETA", 2)
    assert costo == pytest.approx(756000.0)


def test_construir_rutas_asigna_cada_parada_una_vez_o_la_marca_sin_servicio():
    # Paradas cerca de la finca y una lejana (fuera de 25 km): esa queda sin servicio.
    dem = _dem([(i, 5, 4.70, -74.10 - i * 0.02) for i in range(1, 9)] + [(99, 5, 5.2, -74.1)])
    rutas, sin = construir_rutas(dem, FINCA, 25.0, 60.0)
    asignadas = [p for ruta, _ in rutas for p in ruta]
    assert sorted(asignadas + sin) == sorted(dem["parada_id"])
    assert len(asignadas) == len(set(asignadas))
    assert sin == [99]


def test_construir_rutas_respeta_tiempo_maximo_incluido_el_tramo_a_la_finca():
    # Paradas en línea hacia el oeste, cada una ~6,5 km de la siguiente y la finca
    # al este de la primera. Parada i queda a ~6,5·i km de la finca: 1, 2 y 3 son
    # alcanzables (3 ~19,6 km), 4, 5 y 6 quedan fuera de 25 km.
    dem = _dem([(i, 5, 4.70, -74.10 - i * 0.06) for i in range(1, 7)])
    max_km = settings.velocidad_bus_kmh * settings.tiempo_max_viaje_min / 60
    rutas, sin = construir_rutas(dem, FINCA, settings.velocidad_bus_kmh,
                                 settings.tiempo_max_viaje_min)
    assert sorted(sin) == [4, 5, 6]
    # ruta 1 = [1, 2] (19,5 km); con 3 el tramo final supera 25 km => ruta 2 = [3]
    assert sorted(len(r) for r, _ in rutas) == [1, 2]
    for ruta, km in rutas:
        assert km <= max_km + 1e-9
        assert km == pytest.approx(_km_total(dem, ruta, FINCA))  # incluye tramo final


def test_construir_rutas_semilla_es_la_parada_con_mas_personas():
    dem = _dem([(1, 2, 4.70, -74.11), (2, 30, 4.70, -74.12), (3, 1, 4.70, -74.13)])
    rutas, _ = construir_rutas(dem, FINCA, 25.0, 60.0)
    assert rutas[0][0][0] == 2


def test_simular_cuadra_personas_buses_y_costo_por_finca():
    empleados = pd.DataFrame({"parada_id": [1] * 45 + [2] * 3,
                              "cod_nivel2": [86] * 48})
    paradas = pd.DataFrame({"parada_id": [1, 2], "nombre": ["A", "B"],
                            "lat": [4.70, 4.705], "lon": [-74.11, -74.11]})
    tarifas = pd.DataFrame(
        [("MICRO", 19, 315000, "REGULAR"), ("BUSETA", 25, 378000, "REGULAR"),
         ("BUS", 40, 458000, "REGULAR")],
        columns=["tipo_vehiculo", "capacidad", "tarifa", "tipo_tarifa"],
    )
    rutas, sin = simular(empleados, paradas, tarifas, 25.0, 60.0, {86: FINCA})
    assert rutas["personas"].sum() == 48
    assert sin.empty
    assert (rutas["buses"] * rutas["capacidad"] >= rutas["personas"]).all()
    tarifa_de = {"MICRO": 315000, "BUSETA": 378000, "BUS": 458000}
    assert (rutas["costo_total"] == rutas["buses"] * rutas["tipo_bus"].map(tarifa_de)).all()
    assert (rutas["finca"] == 86).all()


@pytest.mark.skipif(not (settings.processed_dir / "empleados.csv").exists(),
                    reason="falta data/processed (correr run_etl.py)")
def test_simulador_datos_reales_cubre_a_todos_con_destino():
    e = pd.read_csv(settings.processed_dir / "empleados.csv")
    p = pd.read_csv(settings.processed_dir / "paradas.csv")
    t = pd.read_csv(settings.processed_dir / "tarifas.csv")
    yarumo = (4.804296, -74.2466673)  # punto "Yarumo" del KML (fincas_sunshine.kml)
    rutas, sin = simular(e, p, t, settings.velocidad_bus_kmh, settings.tiempo_max_viaje_min,
                         {86: yarumo})
    en_yarumo = e[e["cod_nivel2"] == 86]
    assert rutas["personas"].sum() + sin["personas"].sum() == len(en_yarumo)
    max_km = settings.velocidad_bus_kmh * settings.tiempo_max_viaje_min / 60
    assert (rutas["km"] <= max_km + 1e-6).all()

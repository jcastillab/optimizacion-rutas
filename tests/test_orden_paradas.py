from app.services.distancia import distancia_total_km
from app.services.orden_paradas import ordenar_paradas


def test_puntos_en_linea_se_recorren_de_extremo_a_extremo():
    # Puntos colineales en orden desordenado: el camino óptimo es recorrerlos
    # de un extremo al otro, sin retrocesos.
    coords = [(4.80, -74.30), (4.84, -74.34), (4.82, -74.32), (4.86, -74.36), (4.81, -74.31)]
    orden = ordenar_paradas(coords)

    assert sorted(orden) == list(range(len(coords)))
    recorrido = [coords[i] for i in orden]
    longitud_extremos = distancia_total_km([min(coords), max(coords)])
    assert abs(distancia_total_km(recorrido) - longitud_extremos) < 0.01


def test_resultado_es_permutacion_de_indices():
    coords = [(4.7 + i * 0.01, -74.2 - (i % 3) * 0.02) for i in range(10)]
    orden = ordenar_paradas(coords)
    assert sorted(orden) == list(range(10))


def test_pocos_puntos_se_devuelven_tal_cual():
    assert ordenar_paradas([]) == []
    assert ordenar_paradas([(4.0, -74.0)]) == [0]
    assert sorted(ordenar_paradas([(4.0, -74.0), (4.1, -74.1)])) == [0, 1]

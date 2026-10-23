from app.services.distancia import distancia_total_km, haversine_km


def test_un_grado_de_latitud_es_about_111_km():
    assert abs(haversine_km((0.0, 0.0), (1.0, 0.0)) - 111.19) < 0.1


def test_distancia_a_si_mismo_es_cero():
    assert haversine_km((4.8, -74.3), (4.8, -74.3)) == 0.0


def test_distancia_total_suma_tramos():
    a, b, c = (0.0, 0.0), (1.0, 0.0), (2.0, 0.0)
    assert abs(distancia_total_km([a, b, c]) - 2 * 111.19) < 0.2


def test_distancia_total_de_lista_vacia_o_unica_es_cero():
    assert distancia_total_km([]) == 0.0
    assert distancia_total_km([(4.0, -74.0)]) == 0.0

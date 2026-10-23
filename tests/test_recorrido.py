import pandas as pd

from app.services.recorrido import calcular_recorrido


def _paradas(filas):
    return pd.DataFrame(
        filas, columns=["parada_id", "nombre", "lat", "lon"]
    )


def test_excluye_sin_coordenada_y_atipicas():
    paradas = _paradas(
        [
            (1, "A", 4.80, -74.30),
            (2, "B", 4.82, -74.32),
            (3, "C", 4.84, -74.34),
            (4, "SIN", None, None),
            (5, "LEJOS", 5.14, -75.11),  # ~100 km de la ruta
        ]
    )
    rec = calcular_recorrido(1, "RUTA(R1)", "LABORAL", paradas, umbral_atipico_km=30.0)

    nombres = [p.nombre for p in rec.paradas]
    assert sorted(nombres) == ["A", "B", "C"]
    motivos = dict(rec.excluidas)
    assert motivos["SIN"] == "sin coordenada"
    assert motivos["LEJOS"].startswith("coordenada atípica")
    assert [p.orden for p in rec.paradas] == [1, 2, 3]
    assert rec.distancia_km > 0


def test_ruta_sin_paradas_validas_tiene_distancia_cero():
    paradas = _paradas([(1, "SIN", None, None)])
    rec = calcular_recorrido(2, "RUTA(R2)", "FESTIVO", paradas, umbral_atipico_km=30.0)
    assert rec.paradas == []
    assert rec.distancia_km == 0.0
    assert rec.excluidas == [("SIN", "sin coordenada")]


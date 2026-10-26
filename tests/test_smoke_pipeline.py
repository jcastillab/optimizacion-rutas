import math

import pytest

from app.core.config import settings
from app.etl.build_tables import construir_tablas
from app.etl.load_master import cargar_datos_crudos
from app.services.recorrido import calcular_recorrido

_FUENTES = settings.maestro_file.exists() and settings.posiciones_file.exists()


@pytest.mark.skipif(not _FUENTES, reason="faltan los Excel fuente en datos/")
def test_pipeline_completo_sobre_datos_reales():
    tablas = construir_tablas(cargar_datos_crudos(settings.maestro_file, settings.posiciones_file))
    paradas = tablas.paradas
    assert not paradas.empty
    assert set(paradas["ruta_variante_id"]) <= set(tablas.rutas_variante["ruta_variante_id"])

    for variante, sub in paradas.groupby("ruta_variante_id"):
        rec = calcular_recorrido(variante, "", "", sub, settings.umbral_atipico_km)
        ids = [p.parada_id for p in rec.paradas]
        # Ninguna parada se pierde ni se repite: cada una queda incluida o excluida.
        assert len(ids) == len(set(ids))
        assert len(rec.paradas) + len(rec.excluidas) == len(sub)
        assert [p.orden for p in rec.paradas] == list(range(1, len(ids) + 1))
        assert math.isfinite(rec.distancia_km) and rec.distancia_km >= 0

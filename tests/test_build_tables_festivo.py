"""Variantes FESTIVO en construir_tablas: sin fusión por alias y reporte de
variantes con las mismas paradas (rama fix/variantes-festivo)."""

import pandas as pd
import pytest

from app.core.config import settings
from app.etl.build_tables import construir_tablas
from app.etl.load_master import DatosCrudos, cargar_datos_crudos

FINCA = "YARUMO"
COORDS = {
    "A": (4.700001, -74.200001),
    "B": (4.710002, -74.210002),
    "C": (4.720003, -74.220003),
    "D": (4.730004, -74.230004),
    "E": (4.740005, -74.240005),
}


def _datos(posiciones, catalogo=(("FUNZA(R1)", "A"),)):
    """DatosCrudos mínimo: un empleado YARUMO, catálogo laboral y tarifas
    para las rutas de ``catalogo``; ``posiciones`` = [(ruta, parada)]."""
    rutas_paradas = pd.DataFrame(
        [(100 + i, 200 + i, ruta, parada, FINCA) for i, (ruta, parada) in enumerate(catalogo)],
        columns=["route_id", "stop_id", "ruta", "parada", "nivel2"],
    )
    primera = rutas_paradas.iloc[0]
    empleados = pd.DataFrame(
        [(1, "PEREZ", "ANA", primera.route_id, primera.stop_id, primera.ruta,
          primera.parada, "OK", 10, FINCA)],
        columns=["identificacion", "apellidos", "nombres", "routes_id", "stops_id",
                 "ruta", "parada", "configuracion", "cod_nivel2", "nombre_nivel2"],
    )
    tarifas = pd.DataFrame(
        [(10, FINCA, 100 + i, ruta, 900, "PROV", "BUS", 40, 1000, "DIA")
         for i, ruta in enumerate(dict.fromkeys(r for r, _ in catalogo))],
        columns=["cod_nivel2", "nivel2", "route_id", "ruta", "nit_proveedor",
                 "proveedor", "tipo_vehiculo", "capacidad", "tarifa", "tipo_tarifa"],
    )
    pos = pd.DataFrame(
        [(FINCA, 10, ruta, parada, *COORDS[parada], "") for ruta, parada in posiciones],
        columns=["nivel2", "cod_nivel2", "ruta", "parada", "latitude", "longitude", "address"],
    )
    return DatosCrudos(empleados=empleados, rutas_paradas=rutas_paradas,
                       proveedores_tarifas=tarifas, posiciones=pos)


def _paradas_por_base(tablas, tipo_dia):
    """{nombre_ruta_base: set(nombres de parada)} para las variantes de ``tipo_dia``."""
    rv = tablas.rutas_variante.merge(tablas.rutas_base, on="ruta_base_id")
    rv = rv[rv["tipo_dia"] == tipo_dia]
    out = {}
    for v in rv.itertuples():
        out[v.nombre] = set(tablas.paradas.loc[
            tablas.paradas["ruta_variante_id"] == v.ruta_variante_id, "nombre"])
    return out


# --- criterio 1: FESTIVO no se fusiona por alias ---------------------------

POS_FUNZA = [
    ("FUNZA(R1) FDS", "A"),
    ("FUNZA(R1) FDS", "B"),
    ("FUNZA, MSOQUERA(R1) FDS", "C"),
    ("FUNZA, MSOQUERA(R1) FDS", "D"),
]


def test_festivo_no_fusiona_rutas_con_alias():
    tablas = construir_tablas(_datos(POS_FUNZA))

    nombres_base = set(tablas.rutas_base["nombre"])
    assert {"FUNZA(R1)", "FUNZA, MSOQUERA(R1)"} <= nombres_base

    festivo = _paradas_por_base(tablas, "FESTIVO")
    assert festivo.get("FUNZA(R1)") == {"A", "B"}
    assert festivo.get("FUNZA, MSOQUERA(R1)") == {"C", "D"}
    # dos variantes FESTIVO distintas
    assert len([b for b in festivo if b.startswith("FUNZA")]) == 2


# --- criterio 2: LABORAL sigue usando el alias para coordenadas ------------

def test_laboral_usa_alias_para_coordenadas():
    tablas = construir_tablas(_datos(POS_FUNZA, catalogo=(("FUNZA(R1)", "C"),)))

    rv = tablas.rutas_variante.merge(tablas.rutas_base, on="ruta_base_id")
    vid = rv.loc[(rv["nombre"] == "FUNZA(R1)") & (rv["tipo_dia"] == "LABORAL"),
                 "ruta_variante_id"]
    assert len(vid) == 1
    p = tablas.paradas[(tablas.paradas["ruta_variante_id"] == vid.iloc[0])
                       & (tablas.paradas["nombre"] == "C")]
    assert len(p) == 1
    assert p.iloc[0]["lat"] == pytest.approx(COORDS["C"][0])
    assert p.iloc[0]["lon"] == pytest.approx(COORDS["C"][1])
    assert p.iloc[0]["coord_match_status"] == "EXACTO"


# --- criterio 3: reporte de variantes FDS con las mismas paradas -----------

def test_issue_reporta_variantes_con_mismas_paradas():
    pos = [
        ("ROSAL(R1) FDS", "A"), ("ROSAL(R1) FDS", "B"), ("ROSAL(R1) FDS", "C"),
        ("ROSAL(R2) FDS", "C"), ("ROSAL(R2) FDS", "A"), ("ROSAL(R2) FDS", "B"),
        ("ROSAL(R3) FDS", "D"), ("ROSAL(R3) FDS", "E"),
    ]
    tablas = construir_tablas(_datos(pos))

    duplicadas = [i for i in tablas.issues if "mismas paradas" in i.lower()]
    assert duplicadas, tablas.issues
    assert any("ROSAL(R1)" in i and "ROSAL(R2)" in i for i in duplicadas)
    assert not any("ROSAL(R3)" in i for i in duplicadas)

    # las variantes no se tocan, solo se reportan
    festivo = _paradas_por_base(tablas, "FESTIVO")
    assert festivo.get("ROSAL(R1)") == {"A", "B", "C"}
    assert festivo.get("ROSAL(R2)") == {"A", "B", "C"}


def test_sin_duplicadas_no_hay_issue_de_mismas_paradas():
    tablas = construir_tablas(_datos(POS_FUNZA))
    assert not any("mismas paradas" in i.lower() for i in tablas.issues)


# --- criterio 4: variantes_con_mismas_paradas ------------------------------

def _paradas_df(filas):
    return pd.DataFrame(filas, columns=["ruta_variante_id", "nombre", "lat", "lon"])


def test_variantes_con_mismas_paradas_agrupa_sin_importar_orden():
    from app.etl.build_tables import variantes_con_mismas_paradas

    paradas = _paradas_df([
        (3, "B", 4.71, -74.21), (3, "A", 4.70, -74.20),
        (1, "A", 4.70, -74.20), (1, "B", 4.71, -74.21),
        (7, "A", 4.70, -74.20), (7, "B", 4.71, -74.21),
        (2, "A", 4.70, -74.20),                          # subconjunto: única
        (5, "A", 4.70, -74.20), (5, "B", 4.71, -74.22),  # otra coordenada: única
        (6, "A", 4.70, -74.20), (6, "X", 4.71, -74.21),  # otro nombre: única
    ])
    assert variantes_con_mismas_paradas(paradas) == {3: 1, 7: 1}


def test_variantes_con_mismas_paradas_redondea_a_6_decimales():
    from app.etl.build_tables import variantes_con_mismas_paradas

    paradas = _paradas_df([
        (1, "A", 4.1234561, -74.1234561),
        (2, "A", 4.1234564, -74.1234564),  # igual a 6 decimales
        (3, "A", 4.1234661, -74.1234561),  # distinta en el 5.o decimal
    ])
    assert variantes_con_mismas_paradas(paradas) == {2: 1}


def test_variantes_con_mismas_paradas_bordes():
    from app.etl.build_tables import variantes_con_mismas_paradas

    assert variantes_con_mismas_paradas(_paradas_df([])) == {}
    assert variantes_con_mismas_paradas(_paradas_df([(1, "A", 4.7, -74.2)])) == {}


def test_variantes_con_mismas_paradas_no_cruza_tipo_dia():
    from app.etl.build_tables import variantes_con_mismas_paradas

    df = _paradas_df([(1, "A", 4.7, -74.2), (2, "A", 4.7, -74.2), (3, "A", 4.7, -74.2)])
    # 1 FESTIVO y 2 LABORAL con las mismas paradas no son duplicadas; 3 FESTIVO sí.
    tipo = {1: "FESTIVO", 2: "LABORAL", 3: "FESTIVO"}
    assert variantes_con_mismas_paradas(df, tipo_dia_de=tipo) == {3: 1}


# --- criterio 5: smoke con datos reales -----------------------------------

@pytest.mark.skipif(
    not (settings.maestro_file.exists() and settings.posiciones_file.exists()),
    reason="faltan los Excel fuente en datos/",
)
def test_smoke_datos_reales_festivo():
    tablas = construir_tablas(
        cargar_datos_crudos(settings.maestro_file, settings.posiciones_file))

    rv = tablas.rutas_variante.merge(tablas.rutas_base, on="ruta_base_id")
    rv = rv[rv["tipo_dia"] == "FESTIVO"]
    vid = dict(zip(rv["nombre"], rv["ruta_variante_id"]))
    n_paradas = tablas.paradas["ruta_variante_id"].value_counts()

    assert n_paradas.get(vid.get("FUNZA(R1)"), 0) == 20
    assert n_paradas.get(vid.get("FUNZA, MSOQUERA(R1)"), 0) == 31

    from app.etl.build_tables import variantes_con_mismas_paradas

    dup = variantes_con_mismas_paradas(tablas.paradas)
    grupos = {
        "FACATATIVA": [f"FACATATIVA(R{i})" for i in range(1, 4)],
        "MADRID": [f"MADRID(R{i})" for i in range(1, 4)],
        "ROSAL": [f"ROSAL(R{i})" for i in range(1, 6)],
    }
    for grupo, bases in grupos.items():
        assert all(b in vid for b in bases), (grupo, sorted(vid))
        representantes = {dup.get(vid[b], vid[b]) for b in bases}
        assert len(representantes) == 1, (grupo, representantes)
        # al menos todas menos una aparecen como duplicadas
        assert sum(vid[b] in dup for b in bases) >= len(bases) - 1, grupo

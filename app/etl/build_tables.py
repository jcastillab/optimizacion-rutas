"""Construye las tablas procesadas (fincas, rutas_base, rutas_variante,
paradas, proveedores, tarifas, empleados) a partir de los DataFrames crudos,
normalizando y cruzando ruta/parada entre el maestro y el archivo de
posiciones.

Devuelve también una lista de "issues" (texto) que alimenta el reporte de
reconciliación — todo lo que no se pudo cruzar con certeza queda registrado
ahí en vez de fallar silenciosamente.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app.core.config import settings
from app.etl.load_master import DatosCrudos
from app.etl.normalize import (
    colapsar_espacios,
    mejor_coincidencia,
    normalizar_clave,
    resolver_alias,
    separar_tipo_dia,
)


@dataclass
class TablasProcesadas:
    fincas: pd.DataFrame
    rutas_base: pd.DataFrame
    rutas_variante: pd.DataFrame
    paradas: pd.DataFrame
    proveedores: pd.DataFrame
    tarifas: pd.DataFrame
    empleados: pd.DataFrame
    issues: list[str] = field(default_factory=list)


def _id_map(claves: set[str]) -> dict[str, int]:
    return {clave: i + 1 for i, clave in enumerate(sorted(claves))}


def variantes_con_mismas_paradas(
    paradas: pd.DataFrame, tipo_dia_de: dict[int, str] | None = None
) -> dict[int, int]:
    """{variante: primera variante (menor id) con el mismo conjunto de paradas}.

    Compara (nombre, lat, lon) redondeadas a ``settings.decimales_coordenada``,
    sin importar el orden. Con ``tipo_dia_de`` solo compara variantes del mismo
    tipo de día. Las variantes únicas no aparecen como clave; las paradas sin
    coordenada (NaN) nunca coinciden.
    """
    if paradas.empty:
        return {}
    dec = settings.decimales_coordenada
    firmas: dict[tuple, int] = {}
    duplicadas: dict[int, int] = {}
    for variante, sub in paradas.groupby("ruta_variante_id", sort=True):
        conjunto = frozenset(zip(sub["nombre"], sub["lat"].round(dec), sub["lon"].round(dec)))
        firma = ((tipo_dia_de or {}).get(variante), conjunto)
        if firma in firmas:
            duplicadas[variante] = firmas[firma]
        else:
            firmas[firma] = variante
    return duplicadas


def construir_tablas(datos: DatosCrudos) -> TablasProcesadas:
    issues: list[str] = []

    # --- fincas -------------------------------------------------------
    fincas = (
        datos.empleados[["cod_nivel2", "nombre_nivel2"]]
        .drop_duplicates()
        .rename(columns={"nombre_nivel2": "nombre"})
        .sort_values("cod_nivel2")
        .reset_index(drop=True)
    )

    # --- normalizar ruta/parada en cada fuente -------------------------
    rp = datos.rutas_paradas.copy()
    rp["ruta_norm"] = rp["ruta"].map(normalizar_clave)
    rp["ruta_base_norm"], rp["tipo_dia"] = zip(*rp["ruta_norm"].map(separar_tipo_dia))
    rp["ruta_base_norm"] = rp["ruta_base_norm"].map(resolver_alias)
    rp["parada_norm"] = rp["parada"].map(normalizar_clave)

    tf = datos.proveedores_tarifas.copy()
    tf["ruta_norm"] = tf["ruta"].map(normalizar_clave)
    tf["ruta_base_norm"], tf["tipo_dia"] = zip(*tf["ruta_norm"].map(separar_tipo_dia))
    tf["ruta_base_norm"] = tf["ruta_base_norm"].map(resolver_alias)

    pos = datos.posiciones.copy()
    pos["ruta_norm"] = pos["ruta"].map(normalizar_clave)
    pos["ruta_base_norm"], pos["tipo_dia"] = zip(*pos["ruta_norm"].map(separar_tipo_dia))
    pos["ruta_base_norm"] = pos["ruta_base_norm"].map(resolver_alias)
    pos["parada_norm"] = pos["parada"].map(normalizar_clave)
    pos["nivel2_norm"] = pos["nivel2"].map(colapsar_espacios).str.upper()

    # Alcance: solo fincas Yarumo (las que están en el maestro de empleados).
    fincas_alcance = set(fincas["nombre"])
    pos_yarumo = pos[pos["nivel2_norm"].isin(fincas_alcance)].copy()
    if len(pos_yarumo) == 0:
        issues.append(
            "No se encontró ninguna fila del archivo de posiciones para las "
            f"fincas en alcance ({sorted(fincas_alcance)})."
        )

    # --- rutas_base: unión de nombres base normalizados ----------------
    claves_base = (
        set(rp["ruta_base_norm"]) | set(tf["ruta_base_norm"]) | set(pos_yarumo["ruta_base_norm"])
    )
    mapa_ruta_base = _id_map(claves_base)
    rutas_base = pd.DataFrame(
        [{"ruta_base_id": rid, "nombre": nombre} for nombre, rid in mapa_ruta_base.items()]
    ).sort_values("ruta_base_id").reset_index(drop=True)

    rp["ruta_base_id"] = rp["ruta_base_norm"].map(mapa_ruta_base)
    tf["ruta_base_id"] = tf["ruta_base_norm"].map(mapa_ruta_base)
    pos_yarumo["ruta_base_id"] = pos_yarumo["ruta_base_norm"].map(mapa_ruta_base)
    pos["ruta_base_id"] = pos["ruta_base_norm"].map(mapa_ruta_base)

    rutas_sin_tarifa = set(rp["ruta_base_norm"]) - set(tf["ruta_base_norm"])
    if rutas_sin_tarifa:
        issues.append(
            "Rutas del catálogo sin tarifa asociada en Proveedores_y_Tarifas: "
            f"{sorted(rutas_sin_tarifa)}."
        )

    # --- rutas_variante: (ruta_base, tipo_dia) que aparece en alguna fuente
    variantes = set(zip(rp["ruta_base_id"], rp["tipo_dia"]))
    variantes |= set(zip(tf["ruta_base_id"], tf["tipo_dia"]))
    variantes |= set(zip(pos_yarumo["ruta_base_id"], pos_yarumo["tipo_dia"]))
    rutas_variante = (
        pd.DataFrame(sorted(variantes), columns=["ruta_base_id", "tipo_dia"])
        .reset_index(drop=True)
    )
    rutas_variante.insert(0, "ruta_variante_id", rutas_variante.index + 1)

    variante_id_de = {
        (row.ruta_base_id, row.tipo_dia): row.ruta_variante_id
        for row in rutas_variante.itertuples()
    }

    solo_en_tarifa_o_posiciones = {
        (b, t)
        for b, t in variantes
        if not ((rp["ruta_base_id"] == b) & (rp["tipo_dia"] == t)).any()
    }
    if solo_en_tarifa_o_posiciones:
        nombres = {
            rutas_base.set_index("ruta_base_id")["nombre"].get(b): t
            for b, t in solo_en_tarifa_o_posiciones
        }
        issues.append(
            "Variantes de ruta (base, tipo_dia) que NO están en el catálogo "
            f"Rutas_y_Paradas (solo en tarifas o posiciones), sin paradas "
            f"oficiales: {nombres}."
        )

    # --- paradas --------------------------------------------------------
    paradas_rows: list[dict] = []
    parada_counter = 0
    paradas_sin_coordenada = 0
    paradas_aproximadas: list[str] = []
    paradas_otra_ruta: list[str] = []

    for base_id, tipo_dia in variante_id_de:
        variante_id = variante_id_de[(base_id, tipo_dia)]

        if tipo_dia == "LABORAL":
            # El archivo de posiciones suele traer las coordenadas de una
            # ruta bajo su variante " FDS" aunque la parada también exista
            # entre semana (la ubicación física es la misma); por eso el
            # candidato de coordenadas para LABORAL busca en ambas
            # variantes de la misma ruta base, no solo en la LABORAL.
            # Las coordenadas se buscan en TODAS las fincas del archivo de posiciones:
            # muchas paradas (p. ej. LA AURORA) están bajo BQT PRADERA / PRADERA SECTOR.
            # Si un nombre aparece en varias, gana la fila de Yarumo (alcance).
            candidatas_pos = (
                pos[pos["ruta_base_id"] == base_id]
                .assign(en_alcance=lambda d: d["nivel2_norm"].isin(fincas_alcance))
                .sort_values("en_alcance", ascending=False, kind="stable")
            )
            candidatas_norm = candidatas_pos["parada_norm"].tolist()
            origen = rp[rp["ruta_base_id"] == base_id]
            for row in origen.itertuples():
                parada_counter += 1
                match = mejor_coincidencia(row.parada_norm, candidatas_norm)
                lat = lon = None
                status = match.tipo
                if match.clave_encontrada is not None:
                    coinc = candidatas_pos[candidatas_pos["parada_norm"] == match.clave_encontrada]
                    lat = float(coinc.iloc[0]["latitude"])
                    lon = float(coinc.iloc[0]["longitude"])
                    if match.tipo == "APROXIMADO":
                        paradas_aproximadas.append(
                            f"{row.parada_norm!r} ~ {match.clave_encontrada!r} "
                            f"(score={match.score:.2f})"
                        )
                else:
                    # Último recurso: el archivo de posiciones suele asociar la
                    # misma parada a otra ruta (p. ej. LA AURORA bajo otra ruta).
                    # Se toma por nombre exacto, Yarumo primero, y se marca para revisión.
                    otra = (
                        pos[pos["parada_norm"] == row.parada_norm]
                        .assign(en_alcance=lambda d: d["nivel2_norm"].isin(fincas_alcance))
                        .sort_values("en_alcance", ascending=False, kind="stable")
                    )
                    if len(otra):
                        lat = float(otra.iloc[0]["latitude"])
                        lon = float(otra.iloc[0]["longitude"])
                        status = "OTRA_RUTA"
                        paradas_otra_ruta.append(row.parada_norm)
                    else:
                        paradas_sin_coordenada += 1

                paradas_rows.append(
                    {
                        "parada_id": parada_counter,
                        "ruta_variante_id": variante_id,
                        "route_id_origen": row.route_id,
                        "stop_id_origen": row.stop_id,
                        "nombre": row.parada_norm,
                        "lat": lat,
                        "lon": lon,
                        "coord_match_status": status,
                    }
                )
        else:  # FESTIVO: no hay catálogo oficial, solo lo que trae posiciones
            candidatas_pos = pos_yarumo[
                (pos_yarumo["ruta_base_id"] == base_id) & (pos_yarumo["tipo_dia"] == tipo_dia)
            ]
            for row in candidatas_pos.itertuples():
                parada_counter += 1
                paradas_rows.append(
                    {
                        "parada_id": parada_counter,
                        "ruta_variante_id": variante_id,
                        "route_id_origen": None,
                        "stop_id_origen": None,
                        "nombre": row.parada_norm,
                        "lat": float(row.latitude),
                        "lon": float(row.longitude),
                        "coord_match_status": "EXACTO",
                    }
                )

    paradas = pd.DataFrame(paradas_rows)
    tipo_dia_de = dict(zip(rutas_variante["ruta_variante_id"], rutas_variante["tipo_dia"]))
    duplicadas = variantes_con_mismas_paradas(paradas, tipo_dia_de)
    if duplicadas:
        nombre_base = rutas_base.set_index("ruta_base_id")["nombre"]
        variante = rutas_variante.set_index("ruta_variante_id")

        def etiqueta(v: int) -> str:
            return f"{nombre_base[variante.at[v, 'ruta_base_id']]} {variante.at[v, 'tipo_dia']}"

        grupos: dict[int, list[int]] = {}
        for dup, primera in duplicadas.items():
            grupos.setdefault(primera, [primera]).append(dup)
        issues.append(
            "Variantes con las mismas paradas (nombre y coordenadas) que otra, tal "
            "como vienen en el archivo de posiciones; se conservan separadas: "
            + "; ".join(" = ".join(etiqueta(v) for v in sorted(g)) for g in grupos.values())
            + "."
        )
    if paradas_otra_ruta:
        issues.append(
            f"{len(paradas_otra_ruta)} paradas tomaron coordenada de otra ruta del "
            "archivo de posiciones (mismo nombre, distinta ruta). Revisar: "
            + "; ".join(sorted(set(paradas_otra_ruta)))
        )
    if paradas_sin_coordenada:
        issues.append(
            f"{paradas_sin_coordenada} paradas del catálogo laboral quedaron sin "
            "coordenada (no se encontró ni match exacto ni aproximado en el "
            "archivo de posiciones)."
        )
    if paradas_aproximadas:
        issues.append(
            "Paradas resueltas por coincidencia aproximada (revisar manualmente): "
            + "; ".join(paradas_aproximadas)
        )

    # --- proveedores / tarifas ------------------------------------------
    proveedores = (
        tf[["nit_proveedor", "proveedor"]]
        .drop_duplicates()
        .rename(columns={"proveedor": "nombre"})
        .reset_index(drop=True)
    )

    tarifas = tf[
        [
            "ruta_base_id",
            "nit_proveedor",
            "tipo_vehiculo",
            "capacidad",
            "tarifa",
            "tipo_tarifa",
        ]
    ].reset_index(drop=True)

    # --- empleados --------------------------------------------------------
    cat_por_ids = {
        (row.route_id, row.stop_id): row for row in rp.itertuples()
    }
    # índice de respaldo por (ruta_base_norm, parada_norm) para filas
    # "ERROR" cuyo routes_id/stops_id no corresponde al catálogo.
    cat_por_nombre: dict[tuple[str, str], object] = {}
    for row in rp.itertuples():
        cat_por_nombre.setdefault((row.ruta_base_norm, row.parada_norm), row)

    parada_id_por_route_stop = {
        (r["route_id_origen"], r["ruta_variante_id"]): r["parada_id"]
        for r in paradas_rows
        if r["route_id_origen"] is not None
    }
    parada_id_por_origen = {
        (r["route_id_origen"], r["stop_id_origen"]): r["parada_id"]
        for r in paradas_rows
        if r["route_id_origen"] is not None
    }

    empleados_rows: list[dict] = []
    sin_ruta_valida = 0

    for emp in datos.empleados.itertuples():
        cat_row = cat_por_ids.get((emp.routes_id, emp.stops_id))
        if cat_row is None:
            ruta_norm, tipo_dia = separar_tipo_dia(emp.ruta)
            ruta_norm = resolver_alias(ruta_norm)
            parada_norm = normalizar_clave(emp.parada)
            cat_row = cat_por_nombre.get((ruta_norm, parada_norm))

        if cat_row is None:
            sin_ruta_valida += 1
            continue

        parada_id = parada_id_por_origen.get((cat_row.route_id, cat_row.stop_id))
        empleados_rows.append(
            {
                "identificacion": emp.identificacion,
                "nombre": colapsar_espacios(f"{emp.nombres} {emp.apellidos}"),
                "parada_id": parada_id,
                "cod_nivel2": emp.cod_nivel2,
            }
        )

    if sin_ruta_valida:
        issues.append(
            f"{sin_ruta_valida} empleados del maestro no se pudieron asociar a "
            "ninguna ruta/parada del catálogo (quedaron marcados 'ERROR' en "
            "Configuracion y tampoco cruzaron por nombre). No se incluyen en "
            "empleados.csv."
        )

    empleados = pd.DataFrame(empleados_rows)

    return TablasProcesadas(
        fincas=fincas,
        rutas_base=rutas_base,
        rutas_variante=rutas_variante,
        paradas=paradas,
        proveedores=proveedores,
        tarifas=tarifas,
        empleados=empleados,
        issues=issues,
    )

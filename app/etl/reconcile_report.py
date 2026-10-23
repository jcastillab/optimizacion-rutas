from __future__ import annotations

from pathlib import Path

from app.etl.build_tables import TablasProcesadas


def generar_reporte(tablas: TablasProcesadas, destino: Path) -> Path:
    lineas = ["# Reporte de reconciliación ETL", ""]

    lineas.append("## Resumen")
    lineas.append(f"- Fincas: {len(tablas.fincas)}")
    lineas.append(f"- Rutas base: {len(tablas.rutas_base)}")
    lineas.append(f"- Variantes de ruta (base x tipo_dia): {len(tablas.rutas_variante)}")
    lineas.append(f"- Paradas: {len(tablas.paradas)}")
    sin_coord = (tablas.paradas["coord_match_status"] == "SIN_COORDENADA").sum()
    aprox = (tablas.paradas["coord_match_status"] == "APROXIMADO").sum()
    lineas.append(f"  - Sin coordenada: {sin_coord}")
    lineas.append(f"  - Coincidencia aproximada (revisar): {aprox}")
    lineas.append(f"- Proveedores: {len(tablas.proveedores)}")
    lineas.append(f"- Tarifas: {len(tablas.tarifas)}")
    lineas.append(f"- Empleados cargados: {len(tablas.empleados)}")
    lineas.append("")

    lineas.append("## Hallazgos a revisar")
    if not tablas.issues:
        lineas.append("Sin hallazgos.")
    else:
        for issue in tablas.issues:
            lineas.append(f"- {issue}")
    lineas.append("")

    if sin_coord:
        lineas.append("## Paradas sin coordenada")
        faltantes = tablas.paradas[tablas.paradas["coord_match_status"] == "SIN_COORDENADA"]
        for row in faltantes.itertuples():
            lineas.append(f"- ruta_variante_id={row.ruta_variante_id}: {row.nombre}")
        lineas.append("")

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(lineas), encoding="utf-8")
    return destino

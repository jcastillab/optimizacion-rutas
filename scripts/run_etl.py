"""CLI: datos/*.xlsx -> data/processed/*.csv + reporte de reconciliación.

Uso:
    python scripts/run_etl.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.etl.build_tables import construir_tablas
from app.etl.export_csv import exportar_csv
from app.etl.load_master import cargar_datos_crudos
from app.etl.reconcile_report import generar_reporte


def main() -> None:
    print(f"Leyendo {settings.maestro_file.name} y {settings.posiciones_file.name}...")
    datos = cargar_datos_crudos(settings.maestro_file, settings.posiciones_file)

    print("Normalizando y cruzando rutas/paradas...")
    tablas = construir_tablas(datos)

    rutas_csv = exportar_csv(tablas, settings.processed_dir)
    print(f"CSV generados en {settings.processed_dir}:")
    for ruta in rutas_csv:
        print(f"  - {ruta.name}")

    reporte = generar_reporte(tablas, settings.reconciliation_report)
    print(f"Reporte de reconciliación: {reporte}")

    if tablas.issues:
        print(f"\n{len(tablas.issues)} hallazgo(s) a revisar (ver reporte).")


if __name__ == "__main__":
    main()

from __future__ import annotations

from pathlib import Path

from app.etl.build_tables import TablasProcesadas

_ARCHIVOS = {
    "fincas": "fincas.csv",
    "rutas_base": "rutas_base.csv",
    "rutas_variante": "rutas_variante.csv",
    "paradas": "paradas.csv",
    "proveedores": "proveedores.csv",
    "tarifas": "tarifas.csv",
    "empleados": "empleados.csv",
}


def exportar_csv(tablas: TablasProcesadas, processed_dir: Path) -> list[Path]:
    processed_dir.mkdir(parents=True, exist_ok=True)
    rutas_escritas = []
    for atributo, nombre_archivo in _ARCHIVOS.items():
        df = getattr(tablas, atributo)
        destino = processed_dir / nombre_archivo
        df.to_csv(destino, index=False)
        rutas_escritas.append(destino)
    return rutas_escritas

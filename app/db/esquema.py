"""Comprueba que la base existente coincide con los modelos (sin Alembic: ver contrato).

``create_all`` crea tablas que faltan pero no altera las existentes: una base de una versión anterior
arrancaría "bien" y fallaría después con 500. Aquí se detecta al arrancar con un mensaje claro.
"""

from __future__ import annotations

from sqlalchemy.engine import Engine

from app.db.base import Base


def problemas_de_esquema(engine: Engine) -> list[str]:
    problemas = []
    with engine.connect() as con:
        for tabla in Base.metadata.tables.values():
            filas = con.exec_driver_sql(f'PRAGMA table_info("{tabla.name}")').fetchall()
            # (cid, nombre, tipo, notnull, valor_por_defecto, pk)
            reales = {f[1]: f for f in filas}
            problemas += [f"falta {tabla.name}.{c.name}" for c in tabla.columns if c.name not in reales]
            problemas += [f"columna obsoleta obligatoria {tabla.name}.{n} (sin valor por defecto)"
                          for n, f in reales.items()
                          if n not in tabla.columns and f[3] and f[4] is None and not f[5]]
    return problemas


def verificar_esquema(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    problemas = problemas_de_esquema(engine)
    if problemas:
        raise RuntimeError(
            "La base de datos es de una versión anterior y no coincide con la aplicación ("
            + "; ".join(problemas) + "). Haz una copia, elimina el archivo de la base (data/app.db) y "
            "vuelve a crear el administrador e importar los datos, o migra las tablas a mano.")

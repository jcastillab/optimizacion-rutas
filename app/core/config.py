from pathlib import Path

from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    datos_dir: Path = PROJECT_ROOT / "datos"
    maestro_file: Path = datos_dir / "info de rutas a 19-09-2026.xlsx"
    posiciones_file: Path = datos_dir / "rutas y paradas con posicion.xlsx"

    processed_dir: Path = PROJECT_ROOT / "data" / "processed"
    reconciliation_report: Path = PROJECT_ROOT / "data" / "reporte_reconciliacion.md"

    # Radio máximo (metros) para considerar dos paradas "geográficamente
    # compatibles" al consolidar rutas en el optimizador.
    max_desvio_metros: float = 1200.0

    # Distancia (km) a la mediana de la ruta a partir de la cual una parada se
    # considera coordenada atípica (error de captura) y se excluye del recorrido.
    umbral_atipico_km: float = 30.0

    # Máximo de paradas para calcular el óptimo exacto (Held-Karp, O(n²·2ⁿ))
    # al medir la heurística contra el baseline. 12 paradas ≈ 600 mil pasos.
    max_paradas_optimo_exacto: int = 12

    # Gap (%) por debajo del cual se cuenta que la heurística llegó al óptimo
    # (absorbe el ruido de punto flotante al sumar tramos en otro orden).
    tolerancia_gap_pct: float = 1e-6

    # Simulador de rutas nuevas: velocidad media del bus y tiempo máximo que una
    # persona puede pasar en el bus (confirmados por el usuario).
    velocidad_bus_kmh: float = 25.0
    tiempo_max_viaje_min: float = 60.0

    # Fincas de destino: nombre en fincas.csv (Nivel2) -> clave del punto en el KML.
    # Los sectores se asociaron por nombre; confirmar antes de costear.
    destino_kml: dict[str, str] = {
        "YARUMO": "YARUMO",
        "YARUMO SECTOR LOS LAURELES": "LAURELES",
        "YARUMO SECTOR PAPIROS": "PAPIROS",
    }

    # Cruce parada↔finca (scripts/cruce_fincas.py): distancia máxima en metros y
    # similitud mínima de nombre (difflib) para aceptar una coincidencia.
    umbral_cruce_metros: float = 300.0
    umbral_cruce_nombre: float = 0.85

    # Rutas FDS cuya variante FESTIVO se oculta de las salidas hasta confirmar su
    # tarifa y su nombre. Sus filas siguen dando coordenadas a las paradas LABORAL.
    rutas_festivo_ocultas: list[str] = ["FUNZA, MSOQUERA(R1)"]

    # Decimales (6 ≈ 0,1 m) con que se comparan coordenadas para detectar
    # variantes con las mismas paradas (la fuente repite rutas FDS).
    decimales_coordenada: int = 6


settings = Settings()

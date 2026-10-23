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


settings = Settings()

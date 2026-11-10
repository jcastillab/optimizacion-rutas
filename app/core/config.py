from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # Toda variable de entorno lleva el prefijo TRANSPORTE_ (p. ej. TRANSPORTE_DB_URL).
    model_config = SettingsConfigDict(env_prefix="TRANSPORTE_")

    # --- App web (ver docs/CONTRATO_API.md) ---
    version: str = "1.0.0"
    db_url: str = f"sqlite:///{(PROJECT_ROOT / 'data' / 'app.db').as_posix()}"
    logs_dir: Path = PROJECT_ROOT / "logs"
    db_espera_ms: int = 5000  # busy_timeout de SQLite ante escrituras simultáneas
    sesion_horas: int = 12
    # Bloqueo de login por nombre (exista o no el usuario): tras ``max_intentos`` fallos seguidos
    # espera ``bloqueo_min`` minutos, luego el doble, el doble... hasta ``bloqueo_max_min``.
    # Corto a propósito: un tercero que falle a propósito solo retrasa al usuario unos minutos.
    max_intentos: int = 5
    bloqueo_min: int = 1
    bloqueo_max_min: int = 15
    intentos_olvido_min: int = 60  # sin fallos durante este tiempo el contador y el nivel se reinician
    # Límite por IP (en memoria, ventana deslizante): fallos de login permitidos por ventana.
    ip_max_registradas: int = 10_000  # tope de IP recordadas en memoria
    ip_max_fallos: int = 20
    ip_ventana_min: int = 10
    clave_min_largo: int = 10
    puerto: int = 8000  # scripts/iniciar_app.py
    # Paginación de las listas y límites de los parámetros del simulador (422 si se exceden).
    por_pagina_defecto: int = 50
    por_pagina_max: int = 200
    pagina_max: int = 1_000_000
    velocidad_max_kmh: float = 150.0
    tiempo_max_limite_min: float = 600.0
    # Importación: qué fila de una identificación repetida se conserva.
    regla_duplicados: Literal["ultima", "primera"] = "ultima"
    # Optimizador MILP/heurístico (lo lee app/services/optimizador_milp.py).
    milp_tiempo_limite_s: int = 60
    milp_semillas: int = 200
    milp_vecinos: int = 6
    # Swagger/OpenAPI apagados por defecto; TRANSPORTE_DOCS=1 los activa (desarrollo).
    docs: bool = False
    # Hosts aceptados en la cabecera Host (anti DNS rebinding); añade los tuyos si publicas la app.
    hosts_permitidos: list[str] = ["localhost", "127.0.0.1", "[::1]"]
    # Orígenes extra aceptados en escrituras (además del propio servidor): ng serve en desarrollo.
    origenes_permitidos: list[str] = ["http://localhost:4200", "http://127.0.0.1:4200"]
    frontend_dist: Path = PROJECT_ROOT / "frontend" / "dist" / "transporte" / "browser"

    datos_dir: Path = PROJECT_ROOT / "datos"
    maestro_file: Path = datos_dir / "info de rutas a 19-09-2026.xlsx"
    posiciones_file: Path = datos_dir / "rutas y paradas con posicion.xlsx"
    kml_file: Path = datos_dir / "fincas_sunshine.kml"

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

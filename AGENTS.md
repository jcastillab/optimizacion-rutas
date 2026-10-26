# AGENTS.md - optimizacion rutas

Reconciliación y ordenamiento de las rutas de transporte de personal a las
fincas de Sunshine Bouquet: normaliza los Excel/KML de rutas, paradas y
fincas, estima el orden de visita de cada ruta y genera mapas interactivos y
un reporte de reconciliación.

## Reglas de oro

1. **El "optimizador" es una heurística TSP de camino abierto, no LP.**
   Vecino más cercano + 2-opt sobre distancia haversine
   (`app/services/orden_paradas.py`). `pulp` está en `requirements.txt` pero
   no se usa en ningún archivo propio. Cualquier cambio al algoritmo se mide
   contra el baseline (regla 2).
2. **Baseline obligatorio para tocar el orden de paradas**: orden original del
   archivo fuente y óptimo exacto en rutas chicas; métrica `distancia_km` y
   gap % contra el óptimo (skill `protocolo-matematico`, sección
   optimización combinatoria).
3. **La distancia se calcula solo en `app/services/distancia.py`** (haversine,
   línea recta). Si se pasa a distancia por carretera (OSRM u otro), el cambio
   queda contenido ahí.
4. **El orden de visita no puede leer el orden real ejecutado** (los datos
   fuente no lo traen; si algún día lo traen, es "leakage": va como columna de
   evaluación, nunca como insumo del optimizador).
5. **Todo parámetro vive en `app/core/config.py`**, nunca hardcodeado.
   Deuda conocida: `UMBRAL_METROS` y `UMBRAL_NOMBRE` en
   `scripts/cruce_fincas.py:38-39`; `max_desvio_metros` en config no se usa.
6. **FESTIVO sale solo del archivo de posiciones y no usa `ALIAS_RUTAS`**
   (el alias es para cruzar LABORAL con el maestro y buscar coordenadas). La
   fuente repite el mismo conjunto de paradas en varias rutas FDS de un
   municipio (FACATATIVA R1-R3, MADRID R1-R3, ROSAL R1-R5): se conservan
   separadas, el reporte de reconciliación las lista y `evaluar_baseline.py`
   las cuenta una vez (distancia original = promedio del grupo).
   La variante FESTIVO `FUNZA, MSOQUERA(R1)` (31 paradas) está oculta en
   `rutas_festivo_ocultas` (config): no se sabe a qué ruta corresponde ni
   tiene tarifa. Sus filas siguen dando coordenadas a FUNZA(R1) LABORAL.
   Al confirmar la ruta: la tarifa va en el Excel como `<RUTA> FDS` con
   `tipo_tarifa = FESTIVOS` (como FACATATIVA(R1) FDS), y el nombre debe
   coincidir con el de las paradas (el alias `MSOQUERA` está en normalize.py).
7. **Los insumos crudos (`datos/`, Excel/KML) no se editan a mano ni se
   versionan**; `data/` es salida regenerable del ETL.

## Qué es realmente el núcleo

- `app/etl/` lee el maestro (`info de rutas a 19-09-2026.xlsx`) y las
  posiciones (`rutas y paradas con posicion.xlsx`), normaliza nombres, cruza
  rutas/paradas y exporta `data/processed/*.csv` + `data/reporte_reconciliacion.md`.
- `app/services/recorrido.py`: por variante de ruta, excluye paradas sin
  coordenada o atípicas (> `umbral_atipico_km` = 30 km de la mediana), ordena
  con `ordenar_paradas` y suma la distancia.
- `scripts/cruce_fincas.py`: cruza paradas con las fincas del KML por
  distancia (300 m) y similitud de nombre (0.85).
- `app/services/simulador_rutas.py`: arma rutas nuevas que recogen personas en
  paraderos existentes y terminan en la finca (Nivel2, punto del KML según
  `destino_kml` en config). Semilla = más personas; crece hacia la más cercana
  mientras paraderos + tramo final quepan en `velocidad_bus_kmh` ×
  `tiempo_max_viaje_min`. Elige bus y cantidad por costo mínimo. Costo de bus =
  mediana REGULAR por tipo. Paraderos a más de 25 km de la finca salen como sin
  servicio. Los sectores de YARUMO se asociaron a sus puntos del KML por nombre:
  confirmar.
- `app/api/`, `app/repository/`, `app/schemas/`: esqueletos vacíos (la API
  FastAPI aún no existe).

## Estructura

```text
app/core/config.py   Parámetros (pydantic-settings)
app/etl/             Excel -> tablas normalizadas -> CSV + reporte
app/services/        distancia, orden de paradas, recorrido
scripts/             CLIs: run_etl, build_map, mapa_rutas, cruce_fincas
tests/               pytest
datos/               Insumos crudos (no versionado)
data/                Salidas generadas (no versionado)
manual/              Manuales para personas (skill estilo-documentacion)
```

## Entorno y comandos

```powershell
# Entorno: venv (Python 3.14)
.\venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt

# Tests (también los corre el hook al terminar cada turno):
.\venv\Scripts\python.exe -m pytest -q

# ETL: datos/*.xlsx -> data/processed/*.csv + data/reporte_reconciliacion.md
.\venv\Scripts\python.exe scripts\run_etl.py

# Mapa interactivo de recorridos: data/processed -> data/mapa_rutas.html
.\venv\Scripts\python.exe scripts\build_map.py

# Heurística vs. orden original y óptimo exacto (gap %) por variante:
.\venv\Scripts\python.exe scripts\evaluar_baseline.py [--csv tabla.csv]

# Simulador: rutas nuevas con paraderos existentes, bus y cantidad por ruta
# (velocidad y tiempo máximo en config; salida en data/simulador/):
.\venv\Scripts\python.exe scripts\simular_rutas.py

# Mapa de rutas y fincas del KML (orden de aparición en el Excel):
.\venv\Scripts\python.exe scripts\mapa_rutas.py [--ruta "PAPIROS"]
```

## Cómo validar un cambio

1. `pytest -q` verde.
2. Si tocaste ETL o servicios: `run_etl.py` y `build_map.py` corren sin error
   y `data/mapa_rutas.html` abre con todas las rutas.
3. Si tocaste el orden de paradas: corre `scripts\evaluar_baseline.py` antes y
   después y reporta el gap medio/máximo y las rutas en el óptimo. Referencia
   2026-10-23: 12/14 rutas en el óptimo, gap medio 0,38 %, máximo 4,38 %.

## Cómo se trabaja aquí

Con el plugin `equipo`: `/desarrollar <tarea>` (tests primero, revisión,
commit), `/documentar` para manuales, `/revisar-rigor-matematico` para
auditar. Commits semánticos en español.

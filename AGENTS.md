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
6. **Los insumos crudos (`datos/`, Excel/KML) no se editan a mano ni se
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

# Mapa de rutas y fincas del KML (orden de aparición en el Excel):
.\venv\Scripts\python.exe scripts\mapa_rutas.py [--ruta "PAPIROS"]
```

## Cómo validar un cambio

1. `pytest -q` verde.
2. Si tocaste ETL o servicios: `run_etl.py` y `build_map.py` corren sin error
   y `data/mapa_rutas.html` abre con todas las rutas.
3. Si tocaste el orden de paradas: reporta `distancia_km` total antes/después
   y el gap contra el óptimo en las rutas chicas.

## Cómo se trabaja aquí

Con el plugin `equipo`: `/desarrollar <tarea>` (tests primero, revisión,
commit), `/documentar` para manuales, `/revisar-rigor-matematico` para
auditar. Commits semánticos en español.

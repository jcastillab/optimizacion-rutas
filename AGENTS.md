# AGENTS.md - optimizacion rutas

Reconciliación y ordenamiento de las rutas de transporte de personal a las
fincas de Sunshine Bouquet: normaliza los Excel/KML de rutas, paradas y
fincas, estima el orden de visita de cada ruta y genera mapas interactivos y
un reporte de reconciliación.

## Reglas de oro

1. **El "optimizador" es una heurística TSP de camino abierto, no LP.**
   Vecino más cercano + 2-opt sobre distancia haversine
   (`app/services/orden_paradas.py`). Cualquier cambio al algoritmo se mide
   contra el baseline (regla 2). `pulp` ya no está: el MILP del simulador usa
   `highspy` (HiGHS) directamente.
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
  `destino_kml` en config). `simular(metodo="heuristica")` corre dos
  construcciones y deja la más barata por finca: Clarke-Wright + reubicación y
  voraz con tope de capacidad (el tope cambia mucho el costo: evita buses con
  asientos vacíos). `metodo="milp"` (`optimizador_milp.py`, partición de
  conjuntos sobre un banco de rutas con HiGHS) tarda minutos y es óptimo solo
  sobre el banco: úsalo desde `scripts/comparar_metodos.py`, no desde la web.
  Cada ruta debe caber en `velocidad_bus_kmh` × `tiempo_max_viaje_min` incluido
  el tramo final (haversine, línea recta). Elige bus y cantidad por costo mínimo. Costo de bus =
  mediana REGULAR por tipo. Paraderos a más de 25 km de la finca salen como sin
  servicio. Los sectores de YARUMO se asociaron a sus puntos del KML por nombre:
  confirmar.
- **App web** (contrato en `docs/CONTRATO_API.md`, manda sobre el código):
  backend FastAPI + SQLite (`app/api`, `app/db`, `app/schemas`, `app/repository`,
  `app/core/{seguridad,errores,logging_config}.py`) y frontend Angular en
  `frontend/` (proyecto `transporte`). Sesión por cookie `HttpOnly` con token
  revocable (solo se guarda su SHA-256), roles `admin`/`lector`, auditoría
  automática de crear/editar/borrar en la tabla `eventos`, logs JSON rotativos
  en `logs/app.log`, errores con formato único y `request_id`. No hay usuario
  por defecto: el primer admin se crea con `scripts/crear_admin.py`.
  `app/services/importar.py` carga fincas, paraderos, personas y tipos de bus
  desde el ETL (idempotente) y `app/services/simulacion.py` corre el simulador
  sobre la base y guarda la corrida.
- **Límites de los datos (leer antes de citar un ahorro):**
  1. **Cobertura:** el ETL solo carga 473 de 1.258 filas del maestro (415 de
     1.160 personas, 35,8 %). Las 785 restantes (sectores LAURELES 545 y
     PAPIROS 218) tienen rutas como FACA2, MADRID4, SUBA (AER)R2 cuyos paraderos
     no están en `Rutas_y_Paradas`; un mapeo de nombres solo recupera 72 filas.
     Faltan paraderos con coordenadas de esas rutas.
  2. **Red actual:** `costo_red_actual` = suma de 18 tarifas REGULAR suponiendo
     un bus por fila. Seis rutas tienen más personas que asientos (p. ej.
     FACATATIVA(R1) 32 vs 25), así que podrían ser varios buses por ruta: con
     `ceil(personas/capacidad)` costaría ~8,99 M, no 6,60 M. La diferencia es
     orientativa, no un ahorro.
  3. **Duplicados:** 58 filas repiten identificación (54 personas, 18 con
     paraderos distintos). `regla_duplicados` ("ultima"/"primera") cambia el
     costo hasta 5,4 %. Hay que decidir cómo contar personas con varias asignaciones.
  4. Un solo turno; el maestro trae turnos 1-4 que no se modelan.

## Estructura

```text
app/core/             config (env TRANSPORTE_*), seguridad, errores, logs
app/etl/             Excel -> tablas normalizadas -> CSV + reporte
app/services/        distancia, orden de paradas, recorrido, simulador, importar
app/api/ db/ ...     API FastAPI, modelos SQLAlchemy, schemas, repositorios
frontend/            Angular (standalone, sin librerías de UI)
docs/                CONTRATO_API.md
scripts/             CLIs: run_etl, build_map, simular_rutas, crear_admin, iniciar_app
tests/               pytest (tests/web = API con base SQLite temporal)
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

# App web: crear el primer admin (pide la clave), construir el frontend e iniciar
# en http://127.0.0.1:8000 (API en /api, Swagger en /api/docs):
.\venv\Scripts\python.exe scripts\crear_admin.py <usuario>
cd frontend; npm install; npm run build; cd ..
.\venv\Scripts\python.exe scripts\iniciar_app.py
# Desarrollo del frontend con recarga (proxy de /api al backend): cd frontend; npm start

# Presentación (HTML autocontenido en docs/) desde data/demo/*.json (API sobre una base de
# demo, nunca la real) y pantallazos con marcas (requiere Chromium de Playwright):
.\venv\Scripts\python.exe scripts\generar_presentacion.py
.\venv\Scripts\python.exe scripts\capturar_demo.py <carpeta> [--base http://127.0.0.1:8765]

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

# Informe del código — optimización de rutas

Guía para explicar la aplicación: qué hace cada módulo, dónde está cada cosa importante y cómo se conectan. Los detalles de negocio y de límites de los datos están en `AGENTS.md` y en `docs/CONTRATO_API.md` (que manda sobre el código para la API).

## 1. Visión general en un párrafo

El proyecto hace tres cosas encadenadas:

1. **ETL**: lee los Excel de rutas, paradas y el KML de fincas (`datos/`), los normaliza y los deja como tablas CSV (`data/processed/`) y un reporte de reconciliación.
2. **Análisis**: estima el orden de visita de cada ruta existente y mide qué tan buena es esa estimación; también simula rutas nuevas que recogen gente en paraderos existentes y terminan en cada finca.
3. **App web**: una API FastAPI + SQLite que guarda los datos, permite administrarlos (con usuarios, roles y auditoría) y ejecutar el simulador desde un frontend Angular.

Todo el código Python está en `app/` (librería) y `scripts/` (líneas de comando que la usan). La app web es `app/api` + `app/db` + `app/schemas` + `app/repository` + `frontend/`.

## 2. Mapa de carpetas

| Carpeta | Qué contiene |
|---|---|
| `app/core/` | Configuración, seguridad, errores, logs, límites de intentos y cabeceras HTTP |
| `app/etl/` | Lectura de Excel, normalización de nombres, cruce ruta/parada, exportación y reporte |
| `app/services/` | Lógica de negocio: distancias, orden de paradas, recorridos, simulador, importación |
| `app/db/` | Motor SQLite, modelos de tablas y verificación del esquema |
| `app/schemas/` | Esquemas de entrada/salida (Pydantic) de la API |
| `app/repository/` | Consultas y escrituras sobre la base (usuarios, corridas, auditoría) |
| `app/api/` | Aplicación FastAPI, dependencias, CRUD genérico y routers |
| `frontend/` | Aplicación Angular (proyecto `transporte`) |
| `scripts/` | CLIs: ETL, mapas, simulador, baseline, crear admin, iniciar app, presentación |
| `tests/` | Pytest; `tests/web/` prueba la API sobre una base SQLite temporal |
| `docs/` | `CONTRATO_API.md` y la presentación HTML |
| `datos/` | Insumos crudos (Excel/KML). No se editan a mano ni se versionan |
| `data/` | Salidas generadas (ETL, mapas, simulador, base `app.db`). No se versionan |

## 3. Flujo de datos de punta a punta

```
datos/*.xlsx + KML
   │  scripts/run_etl.py
   ▼
app/etl (load_master → build_tables → export_csv / reconcile_report)
   │                                   │
   ▼                                   ▼
data/processed/*.csv              data/reporte_reconciliacion.md
   │
   ├─ scripts/build_map.py ──────────► data/mapa_rutas.html
   ├─ scripts/evaluar_baseline.py ───► app/services/baseline_orden (orden de paradas)
   ├─ scripts/simular_rutas.py ──────► app/services/simulador_rutas (CSV en data/simulador/)
   │
   └─ app/services/importar.py  (POST /api/importar/datos-locales)
          │  upsert: crea lo que falta, no pisa lo editado por el admin
          ▼
      data/app.db (SQLite)  ◄── app/api (FastAPI) ◄── frontend Angular (/api)
          │
          └─ app/services/simulacion.py → simulador_rutas → tabla corridas (con snapshots)
```

Idea clave: **el ETL es la fuente de la base**. La app no lee los Excel directamente; importa desde el ETL y, a partir de ahí, el administrador puede editar la base.

## 4. Módulos, uno por uno

### 4.1 `app/core/` — base transversal

| Archivo | Función | Se conecta con |
|---|---|---|
| `config.py` | Clase `Settings` (variables de entorno con prefijo `TRANSPORTE_`). Todo parámetro vive aquí. | Casi todos los módulos importan `settings` |
| `errores.py` | Excepciones de dominio (`NoEncontrado`, `Validacion`, `Conflicto`, `NoAutenticado`, `SinPermiso`, `DemasiadosIntentos`) y handlers globales con el formato único de error y `request_id`. | `api/main.py` registra los handlers; repositorios y servicios lanzan las excepciones |
| `seguridad.py` | Hash de claves con scrypt y sal; tokens de sesión (en la base solo se guarda su SHA-256). Solo stdlib. | `routers/auth.py`, `routers/usuarios.py`, `schemas/usuarios.py`, `scripts/crear_admin.py` |
| `seguridad_http.py` | Middleware: hosts permitidos (contra DNS rebinding) y cabeceras de seguridad (CSP, etc.). | `api/main.py` |
| `limitador.py` | Límite de fallos de login por IP, en memoria. Shortcut documentado: no sirve con varios procesos. | `api/main.py` |
| `logging_config.py` | Logs JSON por línea, archivo rotativo `logs/app.log` y middleware que pone `request_id`. | `api/main.py`, `errores.py` |

### 4.2 `app/etl/` — de Excel a tablas limpias

Orden de lectura: `load_master.py` → `normalize.py` → `build_tables.py` → `export_csv.py` / `reconcile_report.py`.

| Archivo | Función |
|---|---|
| `load_master.py` | Lee los dos Excel fuente a DataFrames (`DatosCrudos`). Centraliza nombres de hojas y columnas: si cambia el Excel, se toca solo aquí. No normaliza nada. |
| `normalize.py` | Normalización de textos y claves: espacios, mayúsculas, separación de tipo de día (LABORAL / FESTIVO / FDS), alias de nombres de ruta (`ALIAS_RUTAS`, p. ej. `MSOQUERA`). |
| `build_tables.py` | **El corazón del ETL.** Cruza ruta y parada entre el maestro y el archivo de posiciones y produce `TablasProcesadas` (fincas, rutas base, variantes, paradas, proveedores, tarifas, empleados). Todo lo que no se puede cruzar con certeza se registra como "issue", no falla. También detecta variantes con las mismas paradas (p. ej. FACATATIVA R1-R3 en FDS). |
| `export_csv.py` | Escribe `TablasProcesadas` como CSV en `data/processed/`. |
| `reconcile_report.py` | Escribe `data/reporte_reconciliacion.md` con los issues. |

Reglas importantes del dominio (de `AGENTS.md`): FESTIVO sale solo del archivo de posiciones; la variante `FUNZA, MSOQUERA(R1)` está oculta en la configuración `rutas_festivo_ocultas`.

### 4.3 `app/services/` — lógica de negocio

Esta carpeta es donde están los algoritmos. Dependencias internas:

```
distancia.py  (haversine: el único cálculo de distancia)
   ├─ orden_paradas.py  (vecino más cercano + 2-opt, camino abierto)
   │     └─ recorrido.py  (paradas ordenadas, excluye atípicas, suma km)
   │           └─ (scripts/build_map.py)
   ├─ baseline_orden.py  (original vs heurística vs óptimo Held-Karp; gap %)
   │     └─ (scripts/evaluar_baseline.py)
   └─ simulador_rutas.py  (Clarke-Wright, voraz con tope de capacidad, reubicación)
         ├─ optimizador_milp.py  (partición de conjuntos con HiGHS sobre un banco de rutas)
         │     └─ (scripts/comparar_metodos.py, NO la web)
         ├─ simulacion.py  (adapta la base al simulador: calcular y guardar)
         │     └─ routers/simulador.py
         └─ importar.py  (carga la base desde el ETL; usa catalogo_buses)
               └─ routers/importar.py
```

| Archivo | Función clave |
|---|---|
| `distancia.py` | `haversine_km`, `matriz_haversine_km`, `distancia_total_km`. Si algún día se usa ruteo por carretera (OSRM), el cambio queda aquí. |
| `orden_paradas.py` | `ordenar_paradas`: estima el orden de visita. Es una heurística, **no** un LP ni un óptimo garantizado. Los datos fuente no traen el orden real. |
| `recorrido.py` | `calcular_recorrido`: por variante, excluye paradas sin coordenada o a más de `umbral_atipico_km` (30 km) de la mediana, ordena y suma la distancia. Lo usan el mapa y el baseline. |
| `baseline_orden.py` | `evaluar_variantes`: compara orden original, heurística y óptimo exacto (Held-Karp, hasta `max_paradas_optimo_exacto` paradas). Reporta gap %. Es la referencia obligatoria antes de tocar el orden de paradas. |
| `simulador_rutas.py` | Núcleo del simulador. `catalogo_buses` (tipos y costo mediano REGULAR), `demanda_por_paradero`, `elegir_bus` (bus y cantidad de costo mínimo), `construir_rutas_voraz`, `construir_rutas_mejor` (Clarke-Wright + reubicación), y `simular(...)` que elige la más barata por finca. Respeta el tope `velocidad × tiempo_max_viaje` (línea recta) y deja fuera paraderos a más de 25 km de la finca. |
| `optimizador_milp.py` | `construir_rutas_milp`: genera un banco de rutas factibles y resuelve con HiGHS el subconjunto de costo mínimo. Óptimo **solo sobre el banco**, por eso tarda minutos y se usa desde scripts. |
| `simulacion.py` | `calcular(db, velocidad, tiempo)`: solo lee la base y llama a `simular`. `guardar(db, usuario_id, calculo)`: escribe la corrida con sus snapshots. Separar leer y escribir evita retener el candado de escritura durante el cálculo. |
| `importar.py` | `importar_datos_locales(db, sobrescribir=False)`: upsert idempotente. Fincas se emparejan por `cod_nivel2` (no por nombre). Lo que difiere del Excel se cuenta y se avisa; solo se pisa con `sobrescribir=True`. Lee el KML con `leer_puntos_kml`. |

### 4.4 `app/db/` — base de datos

| Archivo | Función |
|---|---|
| `base.py` | `Base` de SQLAlchemy, `crear_engine` (SQLite con claves foráneas, WAL, espera ante bloqueos), `crear_sessionmaker`, `preparar_directorio`, `ahora`, `plegar` (normaliza texto para búsquedas). |
| `modelos.py` | Tablas del contrato: `usuarios`, `sesiones`, `fincas`, `paraderos`, `personas`, `tipos_bus`, `corridas`, `corrida_rutas`, `corrida_sin_servicio`, `eventos` (auditoría), `parametros`, `intentos_login`. |
| `esquema.py` | `verificar_esquema`: como no hay Alembic, al arrancar compara la base con los modelos y avisa con un mensaje claro si es de una versión anterior (si no, la app arrancaría y fallaría después con 500). |

### 4.5 `app/schemas/` — contrato de entrada y salida

| Archivo | Contenido |
|---|---|
| `comun.py` | `Pagina[T]` (paginación), `Salida`, `Parcial`, tipos reutilizables (`Lat`, `Lon`, `Texto`, `FechaUTC` con `Z`). |
| `recursos.py` | Entrada/edición/salida de fincas, paraderos, personas y tipos de bus. |
| `usuarios.py` | `LoginIn`, `UsuarioIn`, `UsuarioEdit`, `UsuarioOut`; valida claves triviales con `clave_trivial`. |
| `simulador.py` | `ParametrosIn`, `CorridaOut`, `CorridaResumenOut`. |
| `eventos.py` | `EventoOut`. |

### 4.6 `app/repository/` — acceso a datos

| Archivo | Función |
|---|---|
| `base.py` | `obtener` (por id) y `listar` (paginado, con búsqueda y condiciones). Lo usan CRUD, usuarios, corridas y eventos. |
| `usuarios.py` | Usuarios por nombre, sesiones activas, `usuario_de_sesion`, conteo de admins activos (para no dejar la app sin admin). |
| `corridas.py` | `guardar` (con snapshots de paraderos y fincas: una corrida es histórica) y armado de la respuesta. |
| `auditoria.py` | `registrar` escribe en `eventos` dentro de un SAVEPOINT: si falla la auditoría no tumba la operación. `cambios` calcula el antes/después. |
| `intentos.py` | Contador de fallos de login por nombre (exista o no el usuario), con retardo progresivo. Complementa al limitador por IP. |

### 4.7 `app/api/` — la API FastAPI

| Archivo | Función |
|---|---|
| `main.py` | `create_app()` (y `app = create_app()`, usado por uvicorn). Monta middlewares, handlers, logs, el limitador, el esquema y **todos los routers bajo `/api`**. También sirve el frontend compilado. |
| `deps.py` | Dependencias: `get_db` (sesión), `usuario_actual` (cookie `HttpOnly` → sesión), `requiere_admin`, `verificar_origen` (protección CSRF por origen), y alias de paginación. |
| `crud.py` | `crear_router_crud(...)`: **fábrica** de CRUD genérico (listar, obtener, crear, editar, borrar) con auditoría, conflictos de integridad y paginación. Evita escribir cuatro routers casi iguales. |

Routers (`app/api/routers/`):

| Router | Prefijo | Acceso | Endpoints |
|---|---|---|---|
| `auth.py` | `/api/auth` | público / sesión | `POST /login`, `POST /logout`, `GET /yo` |
| `recursos.py` | `/api/fincas`, `/api/paraderos`, `/api/personas`, `/api/tipos-bus` | sesión (escritura: admin) | CRUD generado por `crud.py` |
| `simulador.py` | `/api/simulador`, `/api/corridas` | sesión | `POST /simulador/ejecutar`, `GET/DELETE /corridas`, `GET /corridas/{id}` |
| `usuarios.py` | `/api/usuarios` | solo admin | CRUD de usuarios |
| `eventos.py` | `/api/eventos` | solo admin | listado de auditoría |
| `importar.py` | `/api/importar` | solo admin | `POST /datos-locales` |
| `salud.py` | `/api/salud` | público | estado de la app |

Flujo típico de una petición protegida: cookie → `usuario_actual` (busca el hash del token en `sesiones`) → `requiere_admin` si aplica → servicio o repositorio → auditoría si es escritura → respuesta con el esquema de `schemas/`. Errores: excepciones de `errores.py` → formato único con `request_id`.

Contrato completo: `docs/CONTRATO_API.md` (manda sobre el código).

### 4.8 `scripts/` — líneas de comando

| Script | Para qué | Usa |
|---|---|---|
| `run_etl.py` | Corre el ETL completo | `app/etl/*` |
| `build_map.py` | Mapa interactivo de recorridos | `recorrido.py` |
| `mapa_rutas.py` | Mapas Leaflet de rutas y fincas del KML (orden del Excel) | lectura directa de `datos/` |
| `evaluar_baseline.py` | Heurística vs. original vs. óptimo, con gap % | `baseline_orden.py` |
| `simular_rutas.py` | Simulación de rutas nuevas, salida en `data/simulador/` | `simulador_rutas.py` |
| `comparar_metodos.py` | Compara voraz, Clarke-Wright y MILP por finca | `simulador_rutas`, `optimizador_milp` |
| `cruce_fincas.py` | Cruza paraderos con fincas del KML (300 m y similitud de nombre 0,85) | `config` (tiene dos umbrales hardcodeados, deuda conocida) |
| `crear_admin.py` | Crea el primer administrador (no hay usuario por defecto) | `seguridad`, `repository` |
| `iniciar_app.py` | Levanta la app en `http://127.0.0.1:8000` | `api/main.py` |
| `capturar_demo.py` | Pantallazos para la presentación (Playwright) sobre una base de demo | app corriendo |
| `generar_presentacion.py` | Genera `docs/presentacion_primera_version.html` desde `data/demo/*.json` | — |

### 4.9 `frontend/` — Angular

Angular standalone, sin librerías de UI. Estructura en `frontend/src/app/`:

| Carpeta / archivo | Función |
|---|---|
| `app.routes.ts` | Rutas. Login público; el resto detrás de `sesionGuard`; Usuarios, Importar y Eventos además con `adminGuard`. Cada página se carga con `loadComponent` (lazy). |
| `app.ts`, `app.config.ts` | Componente raíz y configuración (proveedores, HttpClient, locale). |
| `core/api.service.ts` | Único punto de llamadas HTTP: prefijo `/api`, traduce errores a `ApiError`, y emite un aviso de escritura por ruta. |
| `core/auth.service.ts` | Estado de sesión (`/auth/yo`), login y logout. |
| `core/guards.ts` | `sesionGuard`, `adminGuard`, `loginGuard`. |
| `core/catalogos.service.ts` | Catálogos (fincas, paraderos, tipos de bus) cacheados para formularios y el simulador. |
| `core/notificaciones.service.ts` | Avisos al usuario (éxito, error). |
| `core/lista.ts`, `core/locale.ts` y otros | Modelos y utilidades (`ListaPaginada`, `Pagina`, `Usuario`, `Rol`, locale). |
| `shared/crud-table.ts` | Tabla CRUD reutilizable que usan Personas, Paraderos, Fincas y Tipos de bus. |
| `shared/mapa-ruta.ts` | Componente de mapa de una ruta (coordenadas proyectadas). |
| `shared/paginador.ts` | Paginador reutilizable. |
| `pages/inicio.ts` | Página de inicio. |
| `pages/login.ts` | Ingreso. |
| `pages/personas.ts`, `paraderos.ts`, `fincas.ts`, `tipos-bus.ts` | CRUD de recursos (sobre `crud-table`). |
| `pages/simulador.ts` | Formulario de parámetros (velocidad, tiempo máximo) y ejecución. |
| `pages/corridas.ts`, `corrida-detalle.ts` | Historial de corridas y detalle (rutas, buses, sin servicio, mapa). |
| `pages/usuarios.ts` | Administración de usuarios (solo admin). |
| `pages/importar.ts` | Botón de importar desde el ETL, con resultado (`ResultadoImportar`). |
| `pages/eventos.ts` | Auditoría (solo admin). |

Conexión con la API: las páginas usan los servicios de `core/`, que llaman a `api.service.ts`; este agrega `/api` y la cookie de sesión viaja sola (`HttpOnly`). En desarrollo, `npm start` hace proxy de `/api` al backend; en producción, `npm run build` deja el frontend que FastAPI sirve.

### 4.10 `tests/`

- `tests/*.py`: unidades de ETL, orden de paradas, recorrido, baseline, MILP, simulador y smoke test del pipeline.
- `tests/web/`: API con base SQLite temporal (`conftest.py`). `test_auth`, `test_permisos` (roles), `test_recursos`, `test_simulacion_basica`, `test_importar_simular`, `test_seguridad`, `test_revision`, `test_infra`.
- Comando: `.\venv\Scripts\python.exe -m pytest -q`.

## 5. Cómo explicar la app en una reunión (orden sugerido)

1. **El problema**: transporte de personal a las fincas; hay rutas existentes y se quiere saber cuánto cuestan y si se pueden armar mejores.
2. **Los datos**: ETL (`app/etl`) y sus límites (ver `AGENTS.md`: solo 473 de 1.258 filas cubiertas, duplicados, red actual orientativa).
3. **El orden de paradas** (`orden_paradas.py` + `baseline_orden.py`): heurística medida contra el óptimo exacto.
4. **El simulador** (`simulador_rutas.py`): cómo se construyen rutas y cómo se elige el bus.
5. **La app**: base SQLite → API con roles y auditoría → frontend.
6. **Cómo se valida**: pytest, `evaluar_baseline.py` (referencia 2026-10-23: 12/14 rutas en el óptimo, gap medio 0,38 %, máximo 4,38 %).

## 6. Deudas y puntos a aclarar

- `scripts/cruce_fincas.py` tiene umbrales hardcodeados (`UMBRAL_METROS`, `UMBRAL_NOMBRE`); `max_desvio_metros` en `config.py` no se usa.
- Limitador de login en memoria: no sirve con varios procesos.
- Sin Alembic: cambios de esquema requieren migrar a mano; `esquema.py` solo avisa.
- Regla de duplicados (`regla_duplicados`) cambia el costo hasta 5,4 %: falta decidir cómo contar personas con varias asignaciones.
- Los sectores de YARUMO se asociaron a puntos del KML por nombre: confirmar.
- Un solo turno; el maestro trae turnos 1-4 que no se modelan.

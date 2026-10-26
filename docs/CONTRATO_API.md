# Contrato de la aplicación web (backend ↔ frontend)

Fuente única para backend (FastAPI + SQLite) y frontend (Angular). Si algo cambia,
se cambia aquí primero.

## Arquitectura

```text
app/                   Backend Python (paquete existente)
  core/                config.py, logging_config.py, errores.py, seguridad.py
  db/                  base.py (engine/sesión), modelos.py, semilla.py
  schemas/             pydantic: entrada/salida por recurso
  repository/          acceso a datos por recurso
  api/                 main.py (create_app), deps.py, routers/*.py
  services/            simulador_rutas.py (existente), simulacion.py (adapta DB -> simulador)
frontend/              Angular (standalone components, signals)
data/app.db            SQLite (no versionado)   logs/app.log   Logs en JSON por línea
```

- API bajo `/api`. El backend sirve el build de Angular en `/` si existe.
- Dev: `ng serve` con proxy `/api` → `http://127.0.0.1:8000`.
- Zona horaria: fechas en UTC ISO-8601 (`2026-10-26T14:03:00Z`).

## Autenticación y roles

- `POST /api/auth/login` crea una sesión en el servidor (token aleatorio; en
  `sesiones` solo se guarda su SHA-256, por eso se puede revocar) y la entrega en una
  **cookie** `sesion` (`HttpOnly`, `SameSite=Lax`, `Path=/`, `Secure` si hay HTTPS).
  El frontend nunca ve el token: usa `withCredentials: true`. Expira en 12 h.
  `POST /api/auth/logout` borra la sesión y la cookie; `GET /api/auth/yo` devuelve
  el usuario actual (`401` si no hay sesión). Sin `Authorization` header.
- Las rutas de escritura rechazan peticiones con `Origin` distinto al del servidor (`403`).
- Contraseñas: `hashlib.scrypt` con sal (stdlib). Nunca se devuelven ni se registran.
- Roles: **admin** (todo) y **lector** (ver datos y correr/consultar simulaciones).
- No hay usuario por defecto. El primer admin se crea con
  `python scripts/crear_admin.py <usuario>` (la clave se pide por `getpass`).
- Usuarios en minúsculas (único sin distinguir mayúsculas), 3-40 caracteres
  `[a-z0-9._-]`. Claves de al menos 10 caracteres y no triviales.
- Login fallido: misma respuesta (y mismo bloqueo) para usuario inexistente o clave
  mala, sin revelar si el usuario existe. Bloqueo **progresivo** por usuario
  (5 fallos → 1 min, luego 2, 4… hasta 15 min) y límite por IP (`429`,
  `DEMASIADOS_INTENTOS`). Los intentos de usuarios inexistentes no se guardan en
  `eventos` (sí en el log de archivo).
- Cambiar la propia clave conserva la sesión actual y revoca las demás.
- Escrituras con cookie exigen `Origin` (o `Referer`) del mismo origen o de
  `origenes_permitidos`; sin ninguno `403`. Se valida `Host` (`hosts_permitidos`).
  Cabeceras: `X-Content-Type-Options`, `X-Frame-Options: DENY`,
  `Referrer-Policy: same-origin` y `Content-Security-Policy`. Swagger
  (`/api/docs`) apagado salvo `TRANSPORTE_DOCS=1`.
- No se puede desactivar ni degradar al último admin activo (`409`).

## Formato de errores (todas las rutas)

```json
{"error": {"codigo": "NO_ENCONTRADO", "mensaje": "La persona 12 no existe.",
           "detalle": null, "request_id": "9f1c2a7e"}}
```

| HTTP | codigo | Cuándo |
|---|---|---|
| 401 | `NO_AUTENTICADO` | falta token, vencido o inválido |
| 403 | `SIN_PERMISO` | rol insuficiente |
| 404 | `NO_ENCONTRADO` | id inexistente |
| 409 | `CONFLICTO` | duplicado único o borrado con dependencias; puede traer `detalle` con el campo |
| 422 | `VALIDACION` | `detalle` = `[{"campo": "lat", "mensaje": "..."}]` |
| 429 | `DEMASIADOS_INTENTOS` | bloqueo de login |
| 500 | `ERROR_INTERNO` | mensaje genérico; el detalle queda en el log con `request_id` |

Mensajes en español. Todas las respuestas llevan el header `X-Request-ID`.

## Listas

`GET` de lista acepta `?pagina=1&por_pagina=50&q=texto` y responde
`{"items": [...], "total": 123, "pagina": 1, "por_pagina": 50}`.
`por_pagina` máximo 200.

## Recursos (CRUD)

Escritura (`POST`, `PATCH`, `DELETE`) solo **admin**; lectura admin y lector.
`PATCH` parcial. Todo `DELETE` devuelve `204`.

| Recurso | Ruta | Campos | Filtros extra | Reglas |
|---|---|---|---|---|
| Fincas | `/api/fincas` | `id, nombre*, cod_nivel2, lat*, lon*, activo` | `activo` | `nombre` único; no se borra con personas (`409`: desactivar) |
| Paraderos | `/api/paraderos` | `id, nombre*, lat*, lon*, activo` | `activo` | (nombre, lat, lon) único; no se borra con personas |
| Personas | `/api/personas` | `id, identificacion*, nombre*, paradero_id, finca_id*, activo` | `paradero_id, finca_id, activo` | `identificacion` única; `finca_id` debe existir |
| Tipos de bus | `/api/tipos-bus` | `id, tipo*, capacidad*, costo*, activo` | — | `tipo` único; `capacidad > 0`, `costo >= 0` |
| Usuarios | `/api/usuarios` | `id, usuario*, nombre*, rol*, activo`, `clave` (solo entrada) | — | solo admin (también lectura); sin `DELETE` (se desactiva) |

`lat` entre -90 y 90, `lon` entre -180 y 180 (`422` si no).

## Importar datos

`POST /api/importar/datos-locales` (admin). Lee los Excel/KML locales con el ETL
existente (`construir_tablas`) y **crea lo que falta, sin modificar lo que ya existe**
(las ediciones del administrador se conservan; idempotente). Fincas se emparejan por
`cod_nivel2`; paraderos físicos únicos por nombre+lat+lon (6 decimales); tipos de bus
con la mediana REGULAR por tipo; personas por identificación (si se repite, rige
`regla_duplicados`: `ultima` por defecto o `primera`). Con `?sobrescribir=true` se
pisan los existentes a propósito. Guarda en `parametros`: `costo_red_actual` (suma de
tarifas REGULAR), `maestro_personas_total` y `maestro_personas_simuladas`.
Respuesta: `{"fincas": {"creadas": 3, "actualizadas": 0}, "paraderos": {...},
"personas": {...}, "tipos_bus": {...}, "avisos": ["..."]}`. `avisos` informa, entre
otras cosas, cuántos registros difieren del Excel y no se modificaron, cuántas filas
repiten identificación (y cuántas con paraderos distintos) y cuántas personas del
maestro no cruzan con el catálogo de rutas.

## Simulador

- `POST /api/simulador/ejecutar` (admin y lector), cuerpo opcional
  `{"velocidad_kmh": 25, "tiempo_max_min": 60}` (por defecto, de configuración).
  Usa solo registros `activo`. Guarda y devuelve la corrida:

```json
{"id": 7, "creada": "...", "usuario": "ana",
 "parametros": {"velocidad_kmh": 25, "tiempo_max_min": 60},
 "resumen": {"rutas": 14, "buses": 14, "personas": 413, "costo_total": 5840000,
             "costo_red_actual": 6604600, "diferencia_pct": -11.6,
             "personas_sin_servicio": 2, "personas_sin_paradero": 0,
             "advertencias": ["Comparación orientativa: la red actual ..."]},
 "rutas": [{"ruta_simulada": 1, "finca_id": 1, "paraderos": [{"id": 3, "nombre": "A", "lat": 4.7, "lon": -74.2}],
            "personas": 40, "km": 18.2, "minutos_max": 43.7,
            "tipo_bus": "BUS", "capacidad": 40, "buses": 1, "costo_total": 458000}],
 "sin_servicio": [{"finca_id": 1, "paradero_id": 9, "personas": 2}]}
```

- `diferencia_pct` es `null` cuando no es comparable (0 rutas, sin `costo_red_actual`, o
  el conjunto simulado difiere del importado por registros inactivos). **La cifra es
  orientativa:** `costo_red_actual` supone un bus por fila de tarifa (no confirmado con
  el proveedor) y la simulación cubre solo a las personas que cruzan con el catálogo de
  rutas; `advertencias` lo dice siempre y la pantalla debe mostrarlas junto al resultado.
- Las corridas son **inmutables**: cada ruta guarda un snapshot de sus paraderos
  (`id, nombre, lat, lon`) y de la finca (`finca_nombre`); editar o borrar paraderos,
  fincas o buses después no cambia una corrida ya guardada.
- `GET /api/corridas` (lista paginada, solo `id, creada, usuario, resumen`),
  `GET /api/corridas/{id}` (completa), `DELETE /api/corridas/{id}` (admin).
- Sin personas o sin tipos de bus activos: `422` `VALIDACION` con mensaje claro.

## Logs y auditoría

- Archivo `logs/app.log`: una línea JSON por evento
  (`fecha, nivel, mensaje, request_id, usuario, metodo, ruta, estado, ms`), rotación 5 × 2 MB.
- Tabla `eventos` (auditoría): `login`, `login_fallido`, `logout`, `crear`, `editar`,
  `borrar`, `importar`, `simular`, con `usuario, entidad, entidad_id, detalle`
  (qué cambió: antes → después, sin claves).
- `GET /api/eventos` (admin): filtros `accion, usuario, entidad, desde, hasta`, paginado.

## Salud

`GET /api/salud` (público) → `{"estado": "ok", "version": "...", "base_datos": "ok"}`.

## Base de datos (SQLite, SQLAlchemy 2)

| Tabla | Columnas |
|---|---|
| `usuarios` | id, usuario único (sin distinguir mayúsculas), nombre, clave_hash, rol (`admin`/`lector`), activo, creado |
| `intentos_login` | usuario normalizado PK, fallos, bloqueado_hasta (cualquier nombre, exista o no) |
| `sesiones` | token_hash PK, usuario_id FK, creada, expira |
| `fincas` | id, nombre único, cod_nivel2 (único si no es NULL), lat, lon, activo |
| `paraderos` | id, nombre, lat, lon, activo; único (nombre, lat, lon a 6 decimales) |
| `personas` | id, identificacion único, nombre, paradero_id FK null, finca_id FK, activo |
| `tipos_bus` | id, tipo único, capacidad, costo, activo |
| `corridas` | id, usuario_id FK, creada, parametros (JSON), resumen (JSON) |
| `corrida_rutas` | id, corrida_id FK, ruta_simulada, finca_id, paraderos (JSON ids), personas, km, minutos_max, tipo_bus, capacidad, buses, costo_total |
| `corrida_sin_servicio` | id, corrida_id FK, finca_id, paradero_id, personas |
| `eventos` | id, fecha, usuario, accion, entidad, entidad_id, detalle, request_id |
| `parametros` | clave PK, valor |

Claves foráneas activas (`PRAGMA foreign_keys=ON`). Tablas con `create_all` al
arrancar. Alembic queda fuera de la primera versión (`shortcut`).

## Pantallas del frontend

Login · Inicio (resumen y última corrida) · Personas · Paraderos · Fincas ·
Tipos de bus · Simulador (parámetros, ejecutar, resultados, comparación orientativa
con la red actual y sus `advertencias`) · Corridas (historial y detalle) ·
Importar (admin; con casilla «sobrescribir existentes» y confirmación) ·
Usuarios (admin) · Eventos (admin).
Guards: sesión (todo menos login) y admin (Usuarios, Eventos, edición).
Errores del API se muestran con el `mensaje` del contrato; `401` redirige al login.

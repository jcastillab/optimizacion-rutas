<img src="img/logo_sunshine_bouquet.png" alt="Sunshine Bouquet" width="240">

# Manual de administrador — Optimización de rutas

> **Para quién es:** la persona que instala la aplicación en un PC, crea los usuarios, carga los datos de referencia y cuida que todo siga funcionando. No hace falta saber programar; sí copiar y pegar comandos.
> **Qué NO cubre:** usar el simulador día a día (elegir velocidad, ejecutar, leer corridas) — eso es del lector/usuario y no tiene manual propio todavía. Tampoco cubre cambiar el algoritmo (ver `AGENTS.md`).
> Hay una versión interactiva con checklists y buscador de errores en `manual/manual_administrador.html` (ábrela con doble clic).
>
> Última revisión: 2026-10-26.

## Índice

0. [Tu papel](#0-tu-papel)
1. [Requisitos del PC](#1-requisitos-del-pc)
2. [Instalar y arrancar](#2-instalar-y-arrancar)
3. [Usuarios y roles](#3-usuarios-y-roles)
4. [Importar los datos del Excel](#4-importar-los-datos-del-excel)
5. [Editar los datos de referencia](#5-editar-los-datos-de-referencia)
6. [Eventos (auditoría) y logs](#6-eventos-auditoría-y-logs)
7. [Copias de seguridad](#7-copias-de-seguridad)
8. [Trampas silenciosas (no dan error)](#8-trampas-silenciosas-no-dan-error)
9. [Problemas comunes](#9-problemas-comunes)
10. [Anexo técnico](#10-anexo-técnico)

---

## 0. Tu papel

La aplicación simula rutas de transporte de personal nuevas (qué paraderos recoge cada bus, qué bus conviene y cuánto costaría) y las compara con la red actual. Tú dejas todo listo para que otros la usen:

1. **Instalas y arrancas** la aplicación en un PC.
2. **Gestionas usuarios**: quién entra y si solo mira (*lector*) o también edita (*administrador*).
3. **Mantienes los datos de referencia**: personas, paraderos, fincas y tipos de bus (el costo del bus es la palanca principal del simulador).

**Tu trabajo en 5 pasos:** Instalar → Crear el primer administrador → Importar el Excel → Revisar y ajustar datos → Copiar la base de vez en cuando.

### Palabras que vas a ver

| Palabra | Qué significa |
|---|---|
| Lector | Usuario que puede ver datos y correr simulaciones, pero no cambiar nada. |
| Administrador | Usuario que además edita datos, importa y ve Usuarios y Eventos. |
| Paradero | Punto físico donde sube la gente (nombre + coordenadas). |
| Finca | Destino de la ruta; su punto sale del archivo KML. |
| Corrida | Resultado guardado de una simulación. No cambia aunque luego edites datos. |
| Importar | Leer los Excel/KML locales y crear en la base lo que falte. |
| Auditoría / Eventos | Libro donde queda anotado quién hizo qué y cuándo. |
| Haversine | Distancia en línea recta sobre la Tierra (no por carretera). |

## 1. Requisitos del PC

- [ ] Windows con **Python 3.14** (el entorno del proyecto usa `venv`).
- [ ] **Node.js** solo si vas a reconstruir el frontend (`npm run build`). Si ya existe `frontend\dist\transporte\browser`, no hace falta para solo usar la app.
- [ ] Los archivos de datos en la carpeta `datos\`: `info de rutas a 19-09-2026.xlsx`, `rutas y paradas con posicion.xlsx` y `fincas_sunshine.kml`.
- [ ] Un navegador moderno (Edge, Chrome).

> 💡 **Tip:** la app solo escucha en `127.0.0.1`: se usa desde el mismo PC donde corre. No se ve desde otros equipos de la red.

## 2. Instalar y arrancar

Todos los comandos se escriben en PowerShell, dentro de la carpeta del proyecto.

1. Crea el entorno virtual (una sola vez):
   ```powershell
   python -m venv venv
   ```
2. Instala las dependencias:
   ```powershell
   .\venv\Scripts\python.exe -m pip install -r requirements.txt
   ```
3. Construye el frontend (necesita Node):
   ```powershell
   cd frontend; npm install; npm run build; cd ..
   ```
4. Crea el primer administrador (pide la clave dos veces; no se ve al escribir):
   ```powershell
   .\venv\Scripts\python.exe scripts\crear_admin.py <usuario>
   ```
   Opciones: `--nombre "Nombre"` y `--rol admin|lector` (por defecto `admin`).
5. Inicia la aplicación (deja esa ventana abierta: es el motor):
   ```powershell
   .\venv\Scripts\python.exe scripts\iniciar_app.py
   ```
   Para otro puerto: `--puerto 8001`.
6. Abre `http://127.0.0.1:8000` en el navegador e ingresa con el usuario y la contraseña del paso 4. (captura pendiente)

<!-- CAPTURA PENDIENTE: pantalla de login (img/instalar-login.webp). Marcas: 1 campo Usuario, 2 campo Contraseña, 3 botón de ingresar. -->

✅ **Listo cuando** ves la pantalla **Inicio** con tu nombre ("Hola, …") y el menú lateral. Para apagar, vuelve a la ventana negra y pulsa `Ctrl + C`.

> ⚠️ **Cuidado:** no hay usuario por defecto. Sin el paso 4 nadie puede entrar.

Dónde queda todo:

| Qué | Dónde |
|---|---|
| Base de datos (usuarios, personas, corridas…) | `data\app.db` (se crea sola al arrancar o al crear el admin) |
| Logs | `logs\app.log` |
| Frontend construido | `frontend\dist\transporte\browser` |

Si la carpeta del frontend no existe, la API funciona pero la página principal no se muestra: repite el paso 3.

## 3. Usuarios y roles

Menú **Usuarios** (solo administradores).

| Rol | Puede |
|---|---|
| **Lector** | Ver todos los datos, ejecutar el simulador, ver corridas. |
| **Administrador** | Todo lo anterior + crear/editar/borrar datos, importar, Usuarios y Eventos. |

**Crear un usuario:** **Usuarios → Nuevo**; llena Usuario, Nombre, Rol, Contraseña y pulsa **Guardar**. (captura pendiente)

<!-- CAPTURA PENDIENTE: formulario Nuevo de Usuarios (img/usuarios-nuevo.webp). Marcas: 1 Usuario, 2 Rol, 3 Contraseña, 4 Guardar. -->

- El usuario va en minúsculas, de 3 a 40 caracteres: letras, números, `.`, `_`, `-`.
- La contraseña: al menos 10 caracteres y no simple (no `123456…`, `abcdef…`, ni 3 o menos caracteres distintos).

**Cambiar la clave de alguien:** **Editar** en su fila, escribe la nueva contraseña y **Guardar**. Si la dejas vacía, no cambia.

**Desactivar:** **Editar**, quita la casilla **Activo** y **Guardar**. Los usuarios no se borran (queda su historial).

> ⚠️ **Cuidado:** no se puede desactivar ni degradar al último administrador activo: la app responde *"No se puede desactivar ni degradar al último administrador activo."* Crea otro admin primero.

**Bloqueo de login:** tras 5 intentos fallidos el usuario espera 1 minuto; luego 2, 4… hasta 15 minutos. Además hay un límite por IP. Si la persona esperó 60 minutos sin fallar, el contador se reinicia. Aplica igual a usuarios que no existen (así no se revela quién existe).

También puedes crear usuarios desde la consola con `crear_admin.py <usuario> --rol lector`.

## 4. Importar los datos del Excel

Menú **Importar** (solo administradores). Lee los archivos de `datos\` en el PC servidor.

1. Ve a **Importar**.
2. Deja desmarcado **Sobrescribir registros existentes** (lo normal).
3. Pulsa **Importar datos del Excel local** y, en *Confirmar importación*, **Importar**. Espera: *"Importando, puede tardar unos segundos…"*. (captura pendiente)

<!-- CAPTURA PENDIENTE: pantalla Importar con resultado (img/importar-resultado.webp). Marcas: 1 casilla Sobrescribir, 2 botón Importar datos del Excel local, 3 bloque Avisos, 4 tabla Resultado. -->

✅ **Listo cuando** aparece **Resultado** con la tabla Fincas / Paraderos / Personas / Tipos de bus (columnas Creadas y Actualizadas).

Qué hace:

| Recurso | Cómo se empareja / qué crea |
|---|---|
| Fincas | Por código `cod_nivel2`; el punto sale del KML. |
| Paraderos | Únicos por nombre + latitud + longitud (6 decimales); solo los que tienen personas. |
| Personas | Por identificación; si se repite, rige `regla_duplicados` (`ultima` por defecto, o `primera`). |
| Tipos de bus | Costo = mediana de la tarifa REGULAR por tipo. |

También guarda tres parámetros: `costo_red_actual` (suma de tarifas REGULAR), `maestro_personas_total` y `maestro_personas_simuladas`.

**No pisa tus ediciones.** Importar es repetible: crea lo que falta y deja lo existente como está. Solo con **Sobrescribir registros existentes** se reemplazan los datos con los del Excel, y se pierden las ediciones hechas en la aplicación. La pantalla pide confirmar y lo advierte ("Modo: sobrescribir existentes.").

> ⚠️ **Cuidado:** haz una copia de `data\app.db` (sección 7) antes de sobrescribir.

### Qué significan los avisos

| Aviso (resumido) | Qué significa |
|---|---|
| *"El ETL registró N observaciones de reconciliación (ver data/reporte_reconciliacion.md)."* | Hay diferencias entre las fuentes; el detalle está en ese reporte. |
| *"La finca '…' no tiene punto en el KML: no se importó ni sus personas."* | Falta el destino de esa finca en `destino_kml`/KML. Sus personas no entran. |
| *"Ya existe una finca '…' con otro código: no se importó la del Excel."* | Una finca con ese nombre ya existe con otro código. |
| *"N paradas con personas no tienen coordenadas: esas personas quedan sin paradero."* | Se importan, pero no se pueden simular. |
| *"N filas repiten la identificación de otra persona (M personas tienen paraderos distintos); se usó la regla …"* | Ver trampa 3. |
| *"N personas no se importaron por no tener finca con punto en el KML."* | Sin finca válida no hay persona. |
| *"N registros difieren del Excel y no se modificaron (usa sobrescribir=true para reemplazarlos)."* | Ediciones tuyas que se respetaron. Es normal si editaste. |

## 5. Editar los datos de referencia

Menús **Personas**, **Paraderos**, **Fincas** y **Tipos de bus**. En todos: **Nuevo** para crear, **Editar** y **Borrar** en cada fila (el borrado pide *"¿Borrar este registro? Esta acción no se puede deshacer."*), y buscador con **Buscar**.

| Menú | Campos | Reglas |
|---|---|---|
| Personas | identificación, nombre, paradero, finca, activo | identificación única; la finca debe existir |
| Paraderos | nombre, latitud, longitud, activo | latitud -90 a 90, longitud -180 a 180; no se borra si tiene personas |
| Fincas | nombre, código nivel2, latitud, longitud, activo | nombre único; no se borra si tiene personas |
| Tipos de bus | **Tipo**, **Capacidad (mayor a 0)**, **Costo (0 o más)**, activo | tipo único |

> 💡 **Tip:** si algo tiene registros asociados, **desactívalo** (quita **Activo**) en vez de borrarlo. El simulador usa solo registros activos.

**El costo del bus es la palanca principal del simulador:** el simulador elige bus y cantidad por costo mínimo. Cambiar **Costo** o **Capacidad** de un tipo cambia qué rutas conviene armar y el costo total. Las corridas ya guardadas no cambian (son inmutables: guardan una foto de sus paraderos y finca).

Si importas con *sobrescribir*, el costo vuelve a la mediana del Excel.

## 6. Eventos (auditoría) y logs

**Eventos** (menú **Eventos**, solo admin) lista quién hizo qué. Columnas: **Fecha**, **Usuario**, **Acción**, **Entidad**, **Id**, **Detalle**. Filtros: **Acción**, **Usuario**, **Entidad**, **Desde**, **Hasta** y **Filtrar**. Fechas en UTC.

| Acción | Cuándo se registra |
|---|---|
| `login`, `login_fallido`, `logout` | Entradas, fallos y salidas (los fallos de usuarios inexistentes solo van al log de archivo) |
| `crear`, `editar`, `borrar` | Cambios de datos; el Detalle muestra antes → después, sin claves |
| `importar` | Cada importación |
| `simular` | Cada simulación |

Cómo leerlo: filtra por **Entidad** (p. ej. `tipo_bus`) para ver quién cambió un costo, y abre el **Detalle** para ver el antes y después. Los usuarios creados con el script aparecen con usuario `(script)`.

(captura pendiente)
<!-- CAPTURA PENDIENTE: pantalla Eventos (img/eventos-lista.webp). Marcas: 1 filtro Acción, 2 filtros Desde/Hasta, 3 botón Filtrar, 4 columna Detalle. -->

**Logs:** `logs\app.log`, una línea JSON por evento con `fecha, nivel, mensaje, request_id, usuario, metodo, ruta, estado, ms`. Rota solos (5 archivos de 2 MB). Cuando una persona ve un error, el `request_id` (también en la cabecera `X-Request-ID`) te lleva a la línea exacta. Para ver el final:

```powershell
Get-Content logs\app.log -Tail 30
```

## 7. Copias de seguridad

Todo lo que se edita vive en un solo archivo: `data\app.db`.

1. Apaga la app (`Ctrl + C` en la ventana negra).
2. Copia `data\app.db` a un lugar seguro con fecha, p. ej. `app_2026-10-26.db`.
3. Vuelve a iniciar la app.

Para restaurar: con la app apagada, reemplaza `data\app.db` por la copia.

> ⚠️ **Cuidado:** no copies el archivo con la app encendida: puede quedar a medias.

Los Excel y KML de `datos\` no se editan a mano ni se versionan; guárdalos aparte.

## 8. Trampas silenciosas (no dan error)

1. **La red actual supone un bus por fila de tarifa.** `costo_red_actual` suma las tarifas REGULAR asumiendo un bus por fila; no está confirmado con el proveedor. La comparación (`diferencia_pct`) es **orientativa**; la pantalla lo dice en las advertencias, no la presentes como ahorro cierto.
2. **El ETL descarta filas que no cruzan con el catálogo de rutas.** Hoy 785 de 1.258 filas del maestro se pierden, y solo 415 de 1.160 personas se simulan. Los sectores Laureles y Papiros casi no tienen datos. Detéctalo en los parámetros `maestro_personas_total` y `maestro_personas_simuladas` y en el aviso del ETL. Un resultado "bueno" puede cubrir poca gente.
3. **Identificaciones repetidas.** 58 filas repiten la identificación de otra persona. La importación deja una fila por persona según `regla_duplicados` (`ultima` por defecto); las otras asignaciones se pierden sin más aviso que el contador.
4. **Destinos de los sectores asociados al KML por nombre.** YARUMO, LAURELES y PAPIROS se emparejan por nombre (`destino_kml` en `app/core/config.py`). Por confirmar: si el punto fuera otro, los costos cambiarían sin error.
5. **Distancia haversine.** Es línea recta, no carretera: los kilómetros y minutos son menores a los reales.
6. **Un solo turno.** Cada persona se simula en un único turno; no se reparten buses entre turnos.
7. **Importar no actualiza lo ya existente.** Si el Excel cambia un costo y ya existe el tipo de bus, no se refleja (aviso "registros difieren…") salvo con sobrescribir.
8. **Solo registros activos.** Una persona, paradero o finca desactivado desaparece de la simulación sin aviso.

## 9. Problemas comunes

| Ves esto… | Qué pasa | Qué hacer |
|---|---|---|
| *"Ingresa tu usuario y tu contraseña."* | Falta un campo en el login. | Llena ambos. |
| *"Usuario o clave incorrectos."* | Dato mal escrito (o usuario inexistente; no se distingue). | Revisa; si olvidó la clave, edítala en **Usuarios**. |
| *"Demasiados intentos fallidos. Intenta de nuevo en …"* | Bloqueo progresivo. | Espera el tiempo indicado (máx. 15 min). |
| *"Tu sesión no es válida o venció. Inicia sesión de nuevo."* | La sesión dura 12 horas o fue revocada. | Entra de nuevo. |
| *"Solo un administrador puede hacer esto."* | Un lector intentó escribir. | Cambia su rol en **Usuarios** si corresponde. |
| *"Origen de la solicitud no permitido."* | La petición viene de otra dirección. | Abre la app en `http://127.0.0.1:8000` o `localhost`. |
| *"Ya existe un usuario con ese nombre de usuario."* | Nombre repetido (sin distinguir mayúsculas). | Usa otro. |
| *"No se puede desactivar ni degradar al último administrador activo."* | Quedarías sin admin. | Crea otro admin antes. |
| *"No se puede borrar …: tiene registros asociados. Desactívalo en su lugar."* | Hay personas ligadas. | Quita **Activo**. |
| *"Ya existe … con los mismos datos (…)."* | Duplicado único. | Edita el existente. |
| *"Faltan archivos de datos en …: …."* | `datos\` incompleta. | Copia los Excel/KML (sección 1). |
| *"No hay tipos de bus activos: crea o activa al menos uno."* | El simulador no tiene buses. | Activa uno en **Tipos de bus**. |
| *"No hay personas activas con finca activa para simular."* | Todo desactivado o sin importar. | Importa o activa datos. |
| *"Ninguna persona activa tiene un paradero activo asignado."* | Las personas no tienen paradero. | Revisa avisos de importación. |
| *"Usuario no válido: 3 a 40 caracteres …"* (script) | Nombre fuera de reglas. | Corrígelo. |
| *"Las claves no coinciden."* / *"La clave debe tener entre 10 y 200 caracteres."* / *"La clave es demasiado simple: …"* (script) | Contraseña no válida. | Usa otra más larga y variada. |
| *"Ya existe el usuario '…'."* (script) | Ya fue creado. | Entra con él o usa otro nombre. |
| Pantalla en blanco o 404 en `/` | No se construyó el frontend. | Repite `npm run build`. |
| Error 500 / mensaje genérico | Falla interna. | Busca su `request_id` en `logs\app.log` y avisa a desarrollo. |

Avisa a desarrollo (con el mensaje exacto o una captura, `Win + Shift + S`) si aparece un error 500, si la base no abre o si los números de una corrida parecen imposibles.

## 10. Anexo técnico

**Variables de entorno** (prefijo `TRANSPORTE_`, definidas en `app/core/config.py`):

| Variable | Defecto | Para qué |
|---|---|---|
| `TRANSPORTE_DB_URL` | `sqlite:///data/app.db` | Base de datos |
| `TRANSPORTE_LOGS_DIR` | `logs` | Carpeta de logs |
| `TRANSPORTE_PUERTO` | 8000 | Puerto (el script usa `--puerto`) |
| `TRANSPORTE_SESION_HORAS` | 12 | Duración de la sesión |
| `TRANSPORTE_MAX_INTENTOS` / `BLOQUEO_MIN` / `BLOQUEO_MAX_MIN` | 5 / 1 / 15 | Bloqueo de login |
| `TRANSPORTE_CLAVE_MIN_LARGO` | 10 | Largo mínimo de clave |
| `TRANSPORTE_REGLA_DUPLICADOS` | `ultima` | `ultima` o `primera` |
| `TRANSPORTE_VELOCIDAD_BUS_KMH` / `TIEMPO_MAX_VIAJE_MIN` | 25 / 60 | Parámetros del simulador |
| `TRANSPORTE_DOCS` | 0 | `1` activa Swagger en `/api/docs` |
| `TRANSPORTE_HOSTS_PERMITIDOS` / `ORIGENES_PERMITIDOS` | localhost… | Hosts y orígenes aceptados |

**Endpoints** (detalle en `docs/CONTRATO_API.md`): `/api/auth/{login,logout,yo}`, `/api/{fincas,paraderos,personas,tipos-bus,usuarios}` (CRUD), `POST /api/importar/datos-locales[?sobrescribir=true]`, `POST /api/simulador/ejecutar`, `/api/corridas`, `GET /api/eventos`, `GET /api/salud`.

**Carpetas:** `app/` (backend), `frontend/` (Angular), `scripts/`, `tests/`, `datos/` (insumos), `data/` (salidas y `app.db`), `logs/`, `docs/`, `manual/`.

**Pruebas:**

```powershell
.\venv\Scripts\python.exe -m pytest -q
```

**Historial:** 2026-10-26, primera versión.

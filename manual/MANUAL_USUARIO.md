<img src="img/logo_sunshine_bouquet.png" alt="Sunshine Bouquet" width="240">

# Manual de usuario (lector) — Transporte Sunshine

> **Para quién es:** quien consulta los datos de transporte (personas, paraderos, fincas, buses), corre el simulador de rutas y lee los resultados. No hace falta saber de informática.
> **Qué NO cubre:** crear usuarios, importar datos, editar o borrar registros, ver el registro de eventos y arrancar el servidor — está en `manual/MANUAL_ADMINISTRADOR.md`.
> Hay una versión interactiva con checklists y buscador de errores en `manual/manual_usuario.html` (ábrela con doble clic).
>
> Última revisión: 2026-10-26.

> **Estado de las capturas:** este manual aún no tiene capturas de pantalla. Cada lugar donde irá una está marcado como *(captura pendiente)*.

## Índice

0. [¿Qué es esto?](#0-qué-es-esto)
1. [Antes de empezar](#1-antes-de-empezar)
2. [Entrar y salir](#2-entrar-y-salir)
3. [Las partes de la aplicación](#3-las-partes-de-la-aplicación)
4. [Consultar datos](#4-consultar-datos)
5. [Correr el simulador](#5-correr-el-simulador)
6. [Cómo leer el resultado](#6-cómo-leer-el-resultado)
7. [Ver corridas anteriores](#7-ver-corridas-anteriores)
8. [Problemas comunes](#8-problemas-comunes)
9. [Cuándo llamar al administrador](#9-cuándo-llamar-al-administrador)

---

## 0. ¿Qué es esto?

**Transporte Sunshine** es una página web interna para estudiar cómo se transporta al personal a las fincas de Sunshine Bouquet. Hace tres cosas:

1. **Te muestra los datos**: personas, paraderos, fincas y tipos de bus.
2. **Propone rutas nuevas**: con el simulador, que arma rutas que recogen personas en los paraderos que ya existen y terminan en su finca.
3. **Compara el costo** de esas rutas con el de la red actual, de forma orientativa (ver [sección 6](#6-cómo-leer-el-resultado)).

Funciona en el navegador, en la dirección `http://127.0.0.1:8000`. No cambia nada de la operación real: solo calcula y guarda cada cálculo en un historial.

**Tu trabajo en 4 pasos:** Entrar → Revisar los datos → Ejecutar el simulador → Leer el resultado.

### Palabras que vas a ver

| Palabra | Qué significa |
|---|---|
| **Finca** | Lugar de trabajo adonde llegan las rutas. Ejemplo: YARUMO. |
| **Paradero** | Sitio donde sube la gente al bus. Cada persona tiene uno asignado. |
| **Ruta propuesta** | Recorrido que arma el simulador: varios paraderos seguidos y al final una finca. |
| **Bus, buseta, micro** | Tipos de vehículo. Cada uno tiene **capacidad** (cuántas personas lleva) y **costo**. El simulador elige el tipo y la cantidad más baratos que alcancen. Los tipos y capacidades que existen salen de la pantalla **Tipos de bus**. |
| **Corrida** | Una ejecución del simulador, guardada con número, fecha y usuario. Una corrida guardada no cambia nunca. |
| **Sin servicio** | Personas que el simulador no pudo atender (ver sección 6). |

## 1. Antes de empezar

- [ ] La dirección **http://127.0.0.1:8000** abre en tu navegador (si no abre, ver [sección 8](#8-problemas-comunes)).
- [ ] Tienes **usuario y contraseña**. Te los da el administrador; no hay un usuario por defecto.

> 💡 **Tip:** no puedes crearte una cuenta tú solo. Si no tienes usuario, pídelo al administrador.

## 2. Entrar y salir

1. Abre **http://127.0.0.1:8000** en el navegador.
2. Escribe tu **Usuario** y tu **Contraseña**.
3. Pulsa **Ingresar**.

(captura pendiente)
<!-- CAPTURA PENDIENTE: pantalla de entrada "Transporte Sunshine / Ingresa con tu usuario". Marcas: 1 campo Usuario, 2 campo Contraseña, 3 botón Ingresar -->

✅ **Listo cuando** ves *"Hola, <tu nombre>"* y arriba el menú con **Inicio, Personas, Paraderos, Fincas, Tipos de bus, Simulador, Corridas**.

Para salir, pulsa **Salir** (arriba a la derecha, junto a tu nombre y rol). La sesión dura 12 horas; después la aplicación te lleva sola a la pantalla de entrada.

> ⚠️ **Cuidado:** si fallas la contraseña **5 veces seguidas**, el usuario se bloquea un rato (1 minuto; si sigues fallando, 2, 4… hasta 15). Espera y vuelve a intentar con calma. Por seguridad, el mensaje es el mismo si el usuario no existe o si la contraseña es mala.

## 3. Las partes de la aplicación

El menú de arriba tiene siete opciones. Como lector no ves **Usuarios**, **Importar** ni **Eventos**.

(captura pendiente)
<!-- CAPTURA PENDIENTE: barra superior con el menú. Marcas: 1 menú (Inicio…Corridas), 2 tu nombre y rol, 3 botón Salir -->

| Menú | Para qué sirve | Sección |
|---|---|---|
| **Inicio** | Totales de personas, fincas, paraderos y tipos de bus, y la última corrida. | [4](#4-consultar-datos) |
| **Personas** | Lista de personas con su finca y su paradero. | [4](#4-consultar-datos) |
| **Paraderos** | Lista de paraderos con sus coordenadas. | [4](#4-consultar-datos) |
| **Fincas** | Lista de fincas con sus coordenadas. | [4](#4-consultar-datos) |
| **Tipos de bus** | Tipos de vehículo, capacidad y costo. | [4](#4-consultar-datos) |
| **Simulador** | Ejecuta una simulación y muestra el resultado. | [5](#5-correr-el-simulador) |
| **Corridas** | Historial de simulaciones guardadas. | [7](#7-ver-corridas-anteriores) |

## 4. Consultar datos

**Inicio** muestra cuatro totales (**Personas**, **Fincas**, **Paraderos**, **Tipos de bus**); cada número es un enlace a su lista. Debajo, la **Última corrida** completa, o *"Aún no hay corridas."* si nadie ha simulado.

Las cuatro listas (**Personas**, **Paraderos**, **Fincas**, **Tipos de bus**) funcionan igual:

1. Pulsa el nombre de la lista en el menú.
2. Para buscar, escribe en **Buscar** (por ejemplo, parte de un nombre) y pulsa **Buscar**.
3. Para ver solo activos o inactivos, cambia **Estado** (**Todos / Activos / Inactivos**). Está en las cuatro listas.
4. Si hay más de una página, usa el paginador de abajo (25 filas por página).

(captura pendiente)
<!-- CAPTURA PENDIENTE: lista de Personas. Marcas: 1 cuadro Buscar, 2 selector Estado, 3 botón Buscar, 4 paginador -->

| Lista | Columnas |
|---|---|
| **Personas** | Identificación, Nombre, Finca, Paradero, Activa |
| **Paraderos** | Nombre, Latitud, Longitud, Activo |
| **Fincas** | Nombre, Cód. nivel 2, Latitud, Longitud, Activa |
| **Tipos de bus** | Tipo, Capacidad, Costo, Activo |

Una fila **inactiva** no entra en el simulador. Una persona sin paradero aparece con la celda de **Paradero** vacía y tampoco se simula.

> ⚠️ **Cuidado:** como lector solo miras. No verás botones **Nuevo**, **Editar** ni **Borrar**. Si encuentras un dato mal, avisa al administrador.

✅ **Listo cuando** ves la tabla con los registros. Si no hay coincidencias dice *"No hay registros."*

## 5. Correr el simulador

El simulador arma rutas nuevas con los **paraderos que ya existen**: empieza con una ruta por paradero, junta rutas mientras eso baje el costo, y elige el tipo de bus y la cantidad más baratos. Cada ruta debe caber en el tiempo máximo.

1. Ve a **Simulador**.
2. Revisa **Velocidad (km/h)**. Viene en **25**: es la velocidad media que se supone para el bus.
3. Revisa **Tiempo máximo de viaje (min)**. Viene en **60**: ninguna ruta puede tardar más, contando el tramo final hasta la finca.
4. Pulsa **Ejecutar simulación**.
5. Espera: el botón dice *"Calculando…"* y debajo *"Calculando rutas, puede tardar unos segundos…"*. No recargues la página.

(captura pendiente)
<!-- CAPTURA PENDIENTE: pantalla Simulador antes de ejecutar. Marcas: 1 Velocidad (km/h) = 25, 2 Tiempo máximo de viaje (min) = 60, 3 botón Ejecutar simulación -->

| Si cambias… | Qué pasa |
|---|---|
| **Velocidad** más alta | Los buses "llegan antes", caben más paraderos por ruta: suelen salir menos rutas. |
| **Velocidad** más baja | Cada ruta cubre menos paraderos: suelen salir más rutas y buses. |
| **Tiempo máximo** más bajo | Rutas más cortas, más buses. |
| **Tiempo máximo** más alto | Rutas más largas, menos buses, pero viajes más largos para la gente. |
| Dejas un campo vacío | El servidor usa su valor por defecto (25 km/h y 60 min). |

La velocidad debe ser mayor que 0 y no pasar de 150 km/h; el tiempo, mayor que 0 y no pasar de 600 min.

✅ **Listo cuando** aparece el aviso *"Simulación terminada."* y *"Corrida #… guardada en el historial."* con el resultado debajo.

> 💡 **Tip:** cada vez que ejecutas, se guarda una corrida nueva. Puedes probar varios valores y comparar luego en **Corridas**.

## 6. Cómo leer el resultado

> ⚠️ **Cuidado:** lee primero el recuadro **Antes de leer las cifras**. El resultado es una **estimación para orientar una decisión, no un costo confirmado**.

Las advertencias que ves, y por qué importan:

| Advertencia | Qué significa para ti |
|---|---|
| *"Comparación orientativa: la red actual se calcula como la suma de las tarifas REGULAR suponiendo un bus por fila de tarifa; no está confirmado con el proveedor."* | El **Costo red actual** es una suposición: un bus por cada tarifa del archivo. Puede estar por encima o por debajo del costo real. |
| *"Solo … de … personas del maestro cruzan con el catálogo de rutas (… %); las demás no se simularon."* | El simulador cubre solo a las personas que cruzan con el catálogo de rutas. Si el % es bajo, comparar contra toda la red actual es injusto. |
| *"Distancias en línea recta (haversine); el recorrido real por carretera es mayor."* | Los **Km** y **Min. máx.** son los de una línea recta entre puntos. Por carretera serán más. |
| *"… personas tienen identificación repetida con paraderos distintos; se usó la regla …"* | Una misma persona aparecía con varios paraderos; se eligió uno. |

### El resumen

| Cifra | Qué significa |
|---|---|
| **Rutas** | Cuántas rutas propone el simulador. |
| **Buses** | Total de vehículos entre todas las rutas. |
| **Personas** | Personas incluidas en la simulación. |
| **Costo propuesto** | Costo de todos los buses propuestos. |
| **Costo red actual** | Costo supuesto de la red de hoy (ver primera advertencia). |
| **Comparación orientativa con la red actual** | Diferencia en %. Con **−** (verde, *"(más barato)"*) lo propuesto cuesta menos; con **+** (rojo, *"(más caro)"*) cuesta más. |
| **Sin servicio** | Personas que no quedaron en ninguna ruta. |

> **No comparable:** si en lugar del porcentaje ves *"No comparable"*, no hay base honesta para comparar: no hubo rutas, no hay costo de la red actual, o las personas simuladas no son las mismas que se importaron (hay registros inactivos). Mira solo las cifras propuestas; no concluyas "más barato" ni "más caro".

El pie del resumen dice con qué parámetros se corrió: *"Parámetros: 25 km/h, máximo 60 min."*

Si ves *"… persona(s) no tienen paradero asignado y no entraron en la simulación."*, esas personas faltan en **Personas** por una causa de datos: avisa al administrador.

### Por qué hay «Sin servicio»

El simulador **no pone en una ruta** a los paraderos que quedan a **más de 25 km de la finca**: serían viajes demasiado largos. Esas personas aparecen en la sección **Sin servicio** así: *"2 persona(s) en el paradero #9, finca YARUMO"*. Si todo está cubierto dice *"Todas las personas tienen servicio."* Que haya "Sin servicio" no es un error de la aplicación: es una señal de que ese paradero necesita otra solución (decídelo con tu jefe y el administrador).

### Rutas propuestas: qué es cada columna

(captura pendiente)
<!-- CAPTURA PENDIENTE: tabla "Rutas propuestas" de una corrida. Marcas: 1 columna Paraderos, 2 Personas, 3 Km y Min. máx., 4 Bus y Cant., 5 Costo -->

| Columna | Qué significa |
|---|---|
| **Ruta** | Número de la ruta dentro de la corrida. |
| **Finca** | Finca donde termina. |
| **Paraderos** | Nombres de los paraderos que recoge y, entre paréntesis, cuántos son. |
| **Personas** | Personas que viajan en esa ruta. |
| **Km** | Distancia total en línea recta. |
| **Min. máx.** | Minutos del viaje más largo de la ruta; nunca pasa del tiempo máximo que fijaste. |
| **Bus** | Tipo de bus y, entre paréntesis, su capacidad. Ejemplo: *BUS (40)*. |
| **Cant.** | Cuántos buses de ese tipo hacen falta. |
| **Costo** | Costo de esa ruta (buses × costo del tipo). |

## 7. Ver corridas anteriores

1. Ve a **Corridas**.
2. Verás una fila por corrida: **#**, **Fecha**, **Usuario**, **Rutas**, **Buses**, **Costo** y **Dif. vs. actual**.
3. Pulsa **Ver** para abrir el detalle (misma pantalla de resultado de la sección 6). Para volver, pulsa **← Volver a corridas**.

(captura pendiente)
<!-- CAPTURA PENDIENTE: historial de Corridas. Marcas: 1 columna Dif. vs. actual, 2 botón Ver -->

En **Dif. vs. actual** un guion (**—**) equivale a *No comparable*. Una corrida guardada **no cambia**, aunque después se editen paraderos, fincas o buses: siempre muestra lo que se vio ese día. Como lector no ves el botón **Borrar**.

Si aún no hay corridas dice *"Aún no hay corridas. Ejecuta una desde el simulador."*

## 8. Problemas comunes

| Ves esto… | Qué pasa | Qué hacer |
|---|---|---|
| La página no abre en `http://127.0.0.1:8000` | La aplicación no está encendida. | **Avisa al administrador**: "la app no abre en 127.0.0.1:8000". |
| *"No se pudo conectar con el servidor."* | Se cayó la aplicación o la conexión. | Espera un minuto, recarga con <kbd>F5</kbd>; si sigue, **avisa al administrador**. |
| *"Ingresa tu usuario y tu contraseña."* | Dejaste un campo vacío. | Llena los dos y pulsa **Ingresar**. |
| *"Usuario o clave incorrectos."* | Usuario o contraseña mal escritos. | Revisa mayúsculas y bloqueo de mayúsculas. Si no los recuerdas, pídelos al administrador. |
| *"Demasiados intentos fallidos. Intenta de nuevo en … "* | Fallaste 5 veces: bloqueo temporal (1 a 15 min). | Espera ese tiempo sin intentar de nuevo. |
| *"Demasiados intentos, espera unos minutos."* | Hay muchos intentos desde este equipo. | Espera unos minutos. |
| *"No se pudo ingresar."* | Falló la entrada sin explicación. | Intenta otra vez; si se repite, **avisa al administrador**. |
| *"Tu sesión no es válida o venció. Inicia sesión de nuevo."* | Pasaron 12 horas o se cerró tu sesión. | Vuelve a ingresar. |
| *"No tienes permiso para esta acción."* / *"Solo un administrador puede hacer esto."* | Intentaste algo que es solo del administrador. | Pídeselo al administrador. |
| *"No hay tipos de bus activos: crea o activa al menos uno."* | En **Tipos de bus** no hay ninguno activo. | **Avisa al administrador**: "no hay tipos de bus activos". |
| *"No hay personas activas con finca activa para simular."* | No hay personas activas o sus fincas están inactivas (o no se cargaron datos). | **Avisa al administrador**: "el simulador dice que no hay personas activas con finca activa". |
| *"Ninguna persona activa tiene un paradero activo asignado."* | A nadie le queda un paradero activo. | **Avisa al administrador** con ese mensaje. |
| Un error bajo **Velocidad (km/h)** o **Tiempo máximo de viaje (min)** | El valor es 0, negativo o demasiado alto. | Usa velocidad entre 1 y 150, tiempo entre 1 y 600. |
| *"Calculando rutas, puede tardar unos segundos…"* mucho rato | La simulación es larga con muchos paraderos. | Espera sin recargar. Si pasan varios minutos, **avisa al administrador**. |
| *"No comparable"* | No hay base para comparar con la red actual. | Mira la sección 6. Si no lo esperabas, avisa al administrador. |
| *"Error inesperado (…)"* o un mensaje con *"Código de soporte: …"* | Falla interna de la aplicación. | **Avisa al administrador** y dale el mensaje y el código. |
| *"No hay registros."* | La búsqueda o el filtro no encontró nada. | Borra el texto de **Buscar**, pon **Estado** en **Todos** y busca de nuevo. |

## 9. Cuándo llamar al administrador

- No tienes usuario o contraseña, o tu cuenta sigue bloqueada pasado el tiempo que indica el mensaje.
- La aplicación no abre o dice *"No se pudo conectar con el servidor."* y no vuelve tras recargar.
- Ves un mensaje con *"Código de soporte: …"*.
- Un dato está mal (una persona sin paradero, una finca con coordenadas raras, un tipo de bus sin costo).
- El simulador dice que faltan tipos de bus, personas o paraderos activos.
- Una cifra del resultado te parece absurda (por ejemplo, casi todas las personas en **Sin servicio**).
- Necesitas importar datos nuevos, crear usuarios o editar registros.

> 💡 **Tip:** cuando avises, copia el mensaje exacto o haz una captura con <kbd>Win</kbd> + <kbd>Shift</kbd> + <kbd>S</kbd>.

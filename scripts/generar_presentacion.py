"""CLI: genera docs/presentacion_primera_version.html (un solo archivo, sin internet).

Lee data/demo/corridas.json y data/demo/catalogos.json (resultados de la API sobre una
base de demostración) y dibuja mapas, gráficos y tablas en SVG/HTML.
Navegación: flechas, espacio o clic en los puntos. Imprimible a PDF (una diapositiva por hoja).

Uso: python scripts/generar_presentacion.py
"""

from __future__ import annotations

import html
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Medidos el 2026-10-29 en este equipo (ver AGENTS.md para el baseline del orden de paradas).
TIEMPOS = [("ETL (Excel → CSV)", 4.7), ("Baseline del orden", 3.7), ("Simulador (script)", 5.2),
           ("Importar a la BD (API)", 1.0), ("Simular (API)", 0.6)]
BASELINE = {"variantes": 30, "con_optimo": 14, "en_optimo": 12, "gap_medio": 0.38, "gap_max": 4.38,
            "laboral": (459.1, 324.2, 29.4), "festivo": (375.7, 113.9, 69.7)}
PALETA = ["#e6007e", "#00a3a1", "#f5a300", "#5b4bc4", "#2e9e44", "#d9480f", "#1c7ed6", "#a61e4d",
          "#7048e8", "#0b7285", "#e67700", "#364fc7", "#c2255c", "#5c940d"]
n0 = lambda v: f"{v:,.0f}".replace(",", ".")
n1 = lambda v: f"{v:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
e = html.escape


def mapa_svg(c: dict, fincas: list[dict]) -> str:
    pts = [(p["lat"], p["lon"]) for r in c["rutas"] for p in r["paraderos"]] + [(f["lat"], f["lon"]) for f in fincas]
    la0 = sum(p[0] for p in pts) / len(pts)
    k = math.cos(math.radians(la0))
    xs = [p[1] * k for p in pts]
    ys = [-p[0] for p in pts]
    W, H, m = 860, 520, 30
    esc = min((W - 2 * m) / (max(xs) - min(xs)), (H - 2 * m) / (max(ys) - min(ys)))
    proy = lambda la, lo: (m + (lo * k - min(xs)) * esc, m + (-la - min(ys)) * esc)
    fin = {f["id"]: f for f in fincas}
    out = [f'<svg viewBox="0 0 {W} {H}" class="mapa" role="img" aria-label="Mapa de rutas propuestas">']
    for r in c["rutas"]:
        col = PALETA[(r["ruta_simulada"] - 1) % len(PALETA)]
        f = fin[r["finca_id"]]
        trazo = [proy(p["lat"], p["lon"]) for p in r["paraderos"]] + [proy(f["lat"], f["lon"])]
        d = " ".join(f"{x:.1f},{y:.1f}" for x, y in trazo)
        out.append(f'<g class="ruta"><title>Ruta {r["ruta_simulada"]} · {e(r["finca_nombre"])} · {r["personas"]} pers. · '
                   f'{n1(r["km"])} km · {r["tipo_bus"]}</title><polyline points="{d}" fill="none" stroke="{col}" '
                   f'stroke-width="3" stroke-linejoin="round" opacity=".85"/>')
        for x, y in trazo[:-1]:
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="{col}" stroke="#fff" stroke-width="1.5"/>')
        out.append("</g>")
    for f in fincas:
        x, y = proy(f["lat"], f["lon"])
        out.append(f'<g><polygon points="{x:.1f},{y-13:.1f} {x+4:.1f},{y-4:.1f} {x+13:.1f},{y-4:.1f} {x+6:.1f},{y+2:.1f} '
                   f'{x+9:.1f},{y+12:.1f} {x:.1f},{y+6:.1f} {x-9:.1f},{y+12:.1f} {x-6:.1f},{y+2:.1f} {x-13:.1f},{y-4:.1f} '
                   f'{x-4:.1f},{y-4:.1f}" fill="#222" stroke="#fff" stroke-width="1.5"/>'
                   f'<text x="{x+14:.1f}" y="{y+4:.1f}" class="fin">{e(f["nombre"].replace("YARUMO SECTOR ", "Y. "))}</text></g>')
    for fc in c["sin_servicio"]:
        if fc.get("lat"):
            x, y = proy(fc["lat"], fc["lon"])
            out.append(f'<g><title>Sin servicio: {e(fc["paradero_nombre"])} ({fc["personas"]} pers.)</title>'
                       f'<circle cx="{x:.1f}" cy="{y:.1f}" r="9" fill="none" stroke="#d00" stroke-width="3"/>'
                       f'<path d="M{x-6:.1f},{y-6:.1f}L{x+6:.1f},{y+6:.1f}M{x+6:.1f},{y-6:.1f}L{x-6:.1f},{y+6:.1f}" stroke="#d00" stroke-width="3"/></g>')
    out.append("</svg>")
    return "".join(out)


def barras(items: list[tuple[str, float]], unidad: str, fmt=n1, color="#e6007e", ancho=640) -> str:
    mx = max(v for _, v in items) or 1
    h = 38 * len(items)
    s = [f'<svg viewBox="0 0 {ancho} {h}" class="barras">']
    for i, (n, v) in enumerate(items):
        w = max(2, (ancho - 330) * v / mx)
        y = i * 38
        s.append(f'<text x="0" y="{y+24}" class="bl">{e(n)}</text>'
                 f'<rect x="230" y="{y+6}" width="{w:.0f}" height="24" rx="5" fill="{color}"/>'
                 f'<text x="{238+w:.0f}" y="{y+24}" class="bv">{fmt(v)} {unidad}</text>')
    s.append("</svg>")
    return "".join(s)


def kpi(valor: str, etiqueta: str, nota: str = "") -> str:
    return f'<div class="kpi"><b>{valor}</b><span>{etiqueta}</span><i>{nota}</i></div>'


def tabla(cab: list[str], filas: list[list[str]]) -> str:
    th = "".join(f"<th>{c}</th>" for c in cab)
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in f) + "</tr>" for f in filas)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>"


def diapos() -> list[str]:
    D = json.loads((ROOT / "data/demo/corridas.json").read_text(encoding="utf-8"))
    cat = json.loads((ROOT / "data/demo/catalogos.json").read_text(encoding="utf-8"))
    base, t40 = D["corridas"]["base"], D["corridas"]["t40"]
    R = base["resumen"]
    fincas = cat["fincas"]
    S = []

    S.append("""<section class="portada"><h1>Optimización de rutas de transporte</h1>
<p class="sub">Primera versión funcional · Sunshine Bouquet</p>
<p class="peq">Reconciliación de datos · simulador de rutas · aplicación web con roles y auditoría<br>29 de octubre de 2026</p></section>""")

    S.append(f"""<section><h2>Resumen ejecutivo</h2>
<div class="kpis">{kpi(n0(R["personas"]), "personas atendidas", f'cobertura {n1(R["cobertura_pct"])} %')}
{kpi(str(R["rutas"]), "rutas propuestas", f'{R["buses"]} buses')}
{kpi(n1(abs(R["diferencia_pct"])) + " %", "menos que la red actual", "orientativo, ver límites")}
{kpi(n0(R["costo_por_persona"]), "costo por persona", "COP por periodo de tarifa")}
{kpi(n1(R["ocupacion_pct"]) + " %", "ocupación de asientos", "")}
{kpi(n0(R["minutos_prom"]) + " min", "viaje promedio", f'máx. {n0(R["minutos_max"])} min')}</div>
<ul class="lista"><li>Aplicación web completa: importar datos, catálogos, simulador, historial de corridas, usuarios, auditoría.</li>
<li>Simulación en <b>menos de 1 segundo</b>; ETL completo en 5 s; 285 tests de backend y 84 de frontend en verde.</li>
<li><b>Límite principal:</b> solo el 35,8 % de las personas del maestro tiene paraderos con coordenadas; la cifra de ahorro es orientativa.</li></ul></section>""")

    S.append(f"""<section><h2>Los datos que tenemos hoy</h2><div class="dos"><div>
<div class="embudo"><div style="width:100%">1.160 personas en el maestro</div><div style="width:35.8%;background:#e6007e">415 con ruta y paradero conocidos</div></div>
<p class="peq">785 personas (sectores LAURELES y PAPIROS) tienen rutas como FACA2, MADRID4 o SUBA(AER)R2 cuyos paraderos no están en el archivo de posiciones.</p></div>
{tabla(["Dato cargado", "Cantidad"], [["Fincas (destinos)", len(fincas)], ["Paraderos con coordenadas", cat["p"]], ["Personas", cat["pe"]], ["Tipos de bus (tarifa REGULAR)", len(cat["tipos"])]])}
</div><p class="nota">Un solo turno modelado; 58 filas repiten identificación (54 personas, 18 con paraderos distintos): regla «última».</p></section>""")

    S.append("""<section><h2>Arquitectura</h2><div class="flujo">
<div class="caja">Excel + KML<br><small>datos/ (no versionado)</small></div><span>→</span>
<div class="caja">ETL<br><small>normaliza y cruza</small></div><span>→</span>
<div class="caja">SQLite<br><small>7 tablas + auditoría</small></div><span>→</span>
<div class="caja">API FastAPI<br><small>sesión, roles, logs</small></div><span>→</span>
<div class="caja rosa">Angular<br><small>11 pantallas</small></div></div>
<div class="dos"><div class="tarjeta"><h3>Núcleo de cálculo</h3><p>Distancias (haversine) en un solo módulo; orden de paradas (vecino más cercano + 2-opt); simulador de rutas nuevas; MILP opcional (HiGHS) para comparar.</p></div>
<div class="tarjeta"><h3>Contrato primero</h3><p><code>docs/CONTRATO_API.md</code> manda sobre el código; la interfaz y las pruebas se escriben contra él.</p></div></div></section>""")

    S.append("""<section><h2>Algoritmo del simulador</h2><div class="pasos">
<div><b>1</b>Demanda por paradero y finca de destino</div>
<div><b>2</b>Descarta paraderos a más de <i>velocidad × tiempo</i> de la finca (25 km/h × 60 min = 25 km) → «sin servicio»</div>
<div><b>3</b>Construye rutas por dos caminos: Clarke-Wright con reubicación, y voraz con tope de capacidad</div>
<div><b>4</b>Elige bus y cantidad por costo mínimo (mediana de tarifa REGULAR por tipo)</div>
<div><b>5</b>Se queda, por finca, con la construcción más barata</div></div>
<p class="nota">Cada ruta debe caber en el tiempo máximo incluido el tramo final a la finca. El tope de capacidad evita buses con asientos vacíos: es lo que más mueve el costo.</p></section>""")

    b = BASELINE
    S.append(f"""<section><h2>Orden de paradas: validado contra el óptimo</h2><div class="kpis">
{kpi(f'{b["en_optimo"]}/{b["con_optimo"]}', "rutas en el óptimo exacto", "Held-Karp, 3 a 12 paradas")}
{kpi(n1(b["gap_medio"] * 1) + " %", "brecha media vs óptimo", f'máxima {n1(b["gap_max"])} %')}
{kpi(f'−{n1(b["laboral"][2])} %', "km LABORAL vs orden del archivo", f'{n1(b["laboral"][0])} → {n1(b["laboral"][1])} km')}
{kpi(f'−{n1(b["festivo"][2])} %', "km FESTIVO vs orden del archivo", f'{n1(b["festivo"][0])} → {n1(b["festivo"][1])} km')}</div>
<p class="nota">El «orden del archivo» no es el recorrido real ejecutado (no viene en los datos); es una referencia, no un ahorro garantizado. Distancia en línea recta.</p></section>""")

    S.append(f"""<section><h2>Tiempos de ejecución</h2>{barras(TIEMPOS, "s")}
<p class="nota">Suite de pruebas: 157 s (285 tests). Compilar el frontend: 13 s. Todo el flujo de una demo cabe en segundos; el MILP (minutos) queda fuera de la web a propósito.</p></section>""")

    S.append("""<section><h2>Base de datos</h2><div class="tablas">
<div class="t"><b>usuarios</b><small>rol admin/lector, hash de clave</small></div><div class="t"><b>sesiones</b><small>solo SHA-256 del token</small></div>
<div class="t"><b>fincas</b><small>destino + coordenada KML</small></div><div class="t"><b>paraderos</b><small>72, con lat/lon</small></div>
<div class="t"><b>personas</b><small>415, paradero y finca</small></div><div class="t"><b>tipos_bus</b><small>capacidad y costo</small></div>
<div class="t"><b>corridas</b><small>snapshot inmutable</small></div><div class="t"><b>eventos</b><small>auditoría automática</small></div>
<div class="t"><b>parametros</b><small>costo red actual, avisos</small></div></div>
<p class="nota">SQLite con WAL. Las corridas guardan copia de rutas y paraderos: editar un catálogo no reescribe el pasado. La importación es idempotente y no pisa lo editado a mano.</p></section>""")

    S.append("""<section><h2>Backend: seguridad y trazabilidad</h2><div class="rej">
<div class="tarjeta"><h3>Sesión</h3><p>Cookie HttpOnly, token revocable, bloqueo progresivo de login y límite por IP.</p></div>
<div class="tarjeta"><h3>Roles</h3><p>Admin gestiona todo; lector consulta y puede simular.</p></div>
<div class="tarjeta"><h3>Auditoría</h3><p>Todo crear, editar y borrar queda en <code>eventos</code> con usuario y cambios.</p></div>
<div class="tarjeta"><h3>Logs</h3><p>JSON rotativos con <code>request_id</code>; errores con formato único.</p></div>
<div class="tarjeta"><h3>Cabeceras</h3><p>CSP, Host permitido, origen en escrituras (anti CSRF).</p></div>
<div class="tarjeta"><h3>Sin usuario por defecto</h3><p>El primer admin se crea por consola con clave mínima de 10 caracteres.</p></div></div></section>""")

    S.append("""<section><h2>Pantallas de la aplicación</h2><div class="rej tres">
<div class="tarjeta"><h3>Inicio</h3><p>Totales y última corrida con indicadores.</p></div>
<div class="tarjeta"><h3>Personas · Paraderos · Fincas · Tipos de bus</h3><p>Listas con búsqueda, paginación y edición (admin).</p></div>
<div class="tarjeta rosa"><h3>Simulador</h3><p>Velocidad y tiempo máximo; resultado con advertencias, KPIs, tabla y mapa.</p></div>
<div class="tarjeta"><h3>Corridas</h3><p>Historial inmutable para comparar escenarios.</p></div>
<div class="tarjeta"><h3>Importar</h3><p>Carga desde el Excel local con confirmación y avisos.</p></div>
<div class="tarjeta"><h3>Usuarios · Eventos</h3><p>Administración y auditoría (solo admin).</p></div></div>
<p class="nota">Accesibilidad: etiquetas, regiones <i>aria-live</i>, tablas con encabezados. Los pantallazos reales se generan con <code>scripts/capturar_demo.py</code>.</p></section>""")

    def kp(c):
        r = c["resumen"]
        return [kpi(n0(r["costo_total"]), "costo propuesto", f'red actual {n0(r["costo_red_actual"])}'),
                kpi(f'{n1(r["diferencia_pct"])} %', "vs. red actual", "orientativo"),
                kpi(n1(r["ocupacion_pct"]) + " %", "ocupación", ""), kpi(n0(r["costo_por_persona"]), "costo / persona", ""),
                kpi(n0(r["km_total"]) + " km", "km de buses", ""), kpi(f'{n0(r["minutos_prom"])} / {n0(r["minutos_max"])} min', "viaje prom. / máx.", "")]
    S.append(f"""<section><h2>Resultado de la simulación</h2><div class="kpis">{"".join(kp(base))}</div>
<div class="aviso"><b>Antes de leer las cifras:</b> la red actual supone un bus por fila de tarifa (sin confirmar con el proveedor); distancias en línea recta; solo se simuló el 35,8 % del maestro. La pantalla muestra estas advertencias junto al resultado.</div></section>""")

    S.append(f"""<section><h2>Mapa de rutas propuestas</h2><div class="botones"><button class="act" onclick="mapa(this,0)">Base · 60 min</button><button onclick="mapa(this,1)">Estricto · 40 min</button></div>
<div class="mapas"><div class="m">{mapa_svg(base, fincas)}</div><div class="m" style="display:none">{mapa_svg(t40, fincas)}</div></div>
<p class="nota">Cada color es una ruta; ★ finca de destino; ✕ paraderos sin servicio (a más de 25 km). Pasa el cursor por una ruta para ver detalles.</p></section>""")

    filas = [[r["ruta_simulada"], e(r["finca_nombre"].replace("YARUMO SECTOR ", "Y. ")), len(r["paraderos"]), r["personas"],
              n1(r["km"]), n0(r["minutos_max"]), f'{r["tipo_bus"]} ({r["capacidad"]})', n0(r["costo_total"])] for r in base["rutas"]]
    S.append(f"""<section><h2>Rutas propuestas (escenario base)</h2>{tabla(["Ruta", "Finca", "Paraderos", "Personas", "Km", "Min.", "Bus", "Costo"], filas)}</section>""")

    esc = [("Base: 25 km/h, 60 min", base), ("Estricto: 40 min", t40), ("Holgado: 90 min", D["corridas"]["t90"]), ("Más rápido: 35 km/h", D["corridas"]["v35"])]
    S.append(f"""<section><h2>Sensibilidad a los parámetros</h2>{tabla(["Escenario", "Rutas", "Costo", "vs. red", "Viaje prom.", "Viaje máx."],
        [[n, c["resumen"]["rutas"], n0(c["resumen"]["costo_total"]), n1(c["resumen"]["diferencia_pct"]) + " %", n0(c["resumen"]["minutos_prom"]) + " min", n0(c["resumen"]["minutos_max"]) + " min"] for n, c in esc])}
<p class="nota">El costo no cambia entre 60 y 90 min: lo limita la capacidad de los buses, no el tiempo. Solo un tope de 40 min obliga a una ruta más (+5,4 % de costo) y baja el viaje máximo en 20 min.</p></section>""")

    S.append("""<section><h2>Límites que hay que decir en voz alta</h2><div class="rej">
<div class="tarjeta"><h3>Cobertura</h3><p>64 % de las personas del maestro no tiene paraderos con coordenadas.</p></div>
<div class="tarjeta"><h3>Red actual</h3><p>6,60 M supone un bus por fila; con <code>ceil(personas/capacidad)</code> sería ~8,99 M. La diferencia no es un ahorro firme.</p></div>
<div class="tarjeta"><h3>Distancia y tiempo</h3><p>Línea recta y velocidad media fija; sin tiempo de parada ni tráfico. Real por carretera será mayor.</p></div>
<div class="tarjeta"><h3>Duplicados</h3><p>58 filas repetidas; la regla cambia el costo hasta 5,4 %.</p></div>
<div class="tarjeta"><h3>Un turno</h3><p>El maestro trae turnos 1 a 4 que no se modelan.</p></div>
<div class="tarjeta"><h3>Sectores YARUMO</h3><p>Su punto en el KML se asignó por nombre: confirmar.</p></div></div></section>""")

    S.append("""<section><h2>Siguientes pasos</h2><div class="pasos">
<div><b>1</b>Conseguir paraderos con coordenadas de LAURELES y PAPIROS (cierra el 64 % faltante)</div>
<div><b>2</b>Confirmar con el proveedor cómo se cobra la red actual (buses por ruta)</div>
<div><b>3</b>Distancia por carretera (OSRM) contenida en <code>distancia.py</code> + tiempo de parada</div>
<div><b>4</b>Modelar turnos y decidir el tratamiento de personas con varias asignaciones</div>
<div><b>5</b>Despliegue en servidor interno con HTTPS y respaldo de la base</div></div></section>""")

    S.append("""<section><h2>Cómo correr la demostración</h2><pre>.\\venv\\Scripts\\python.exe scripts\\run_etl.py
.\\venv\\Scripts\\python.exe scripts\\crear_admin.py &lt;usuario&gt;
cd frontend; npm install; npm run build; cd ..
.\\venv\\Scripts\\python.exe scripts\\iniciar_app.py     # http://127.0.0.1:8000
# Ingresar → Importar → Simulador → Ejecutar → Corridas</pre>
<p class="nota">Guion sugerido (10 min): inicio → importar → catálogos → simulador (60 min) → mapa → comparar con 40 min en Corridas → eventos de auditoría → límites.</p></section>""")
    return S


CSS = """
:root{--rosa:#e6007e;--tinta:#1f2430;--gris:#5b6372;--fondo:#fff;--suave:#fdf0f7}
@media(prefers-color-scheme:dark){:root{--tinta:#f1f2f6;--gris:#a9afbd;--fondo:#14161d;--suave:#241a22}}
*{box-sizing:border-box}html,body{margin:0;height:100%;background:var(--fondo);color:var(--tinta);font:18px/1.45 Calibri,Arial,sans-serif}
main{height:100vh;overflow-y:auto;overflow-x:hidden;scroll-snap-type:y mandatory}
section{min-height:100vh;scroll-snap-align:start;padding:5vh 7vw 8vh;display:flex;flex-direction:column;justify-content:center;gap:1.1rem}
h1{font-size:3.2rem;margin:0;color:var(--rosa)}h2{font-size:2.1rem;margin:0 0 .4rem;color:var(--rosa)}h3{margin:0 0 .3rem;font-size:1.1rem}
.portada{background:var(--suave)}.sub{font-size:1.6rem;margin:0}.peq,.nota{color:var(--gris);font-size:.95rem}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:.8rem}
.kpi{background:var(--suave);border-radius:12px;padding:.9rem 1rem;display:flex;flex-direction:column}
.kpi b{font-size:2rem;color:var(--rosa);line-height:1.1}.kpi span{font-weight:600}.kpi i{font-size:.85rem;color:var(--gris);font-style:normal}
.lista li{margin:.3rem 0}.dos{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;align-items:start}
.tarjeta,.t,.caja{background:var(--suave);border-radius:12px;padding:.9rem 1rem}.tarjeta p{margin:0;color:var(--gris);font-size:.95rem}
.rosa{background:var(--rosa)!important;color:#fff}.rosa p{color:#fff}
.rej{display:grid;grid-template-columns:repeat(3,1fr);gap:.8rem}.tablas{display:grid;grid-template-columns:repeat(3,1fr);gap:.7rem}
.t b{display:block}.t small{color:var(--gris)}.flujo{display:flex;align-items:center;gap:.6rem;flex-wrap:wrap}.flujo span{font-size:1.6rem;color:var(--rosa)}
.caja{text-align:center;font-weight:700}.caja small{font-weight:400;color:inherit;opacity:.8}
.pasos{display:grid;gap:.6rem}.pasos div{background:var(--suave);border-radius:12px;padding:.7rem 1rem;display:flex;gap:1rem;align-items:center}
.pasos b{background:var(--rosa);color:#fff;border-radius:50%;min-width:2rem;height:2rem;display:flex;align-items:center;justify-content:center}
.embudo div{background:#aab;color:#fff;padding:.7rem 1rem;margin:.4rem 0;border-radius:8px;white-space:nowrap;overflow:visible;font-weight:600}
table{border-collapse:collapse;width:100%;font-size:.9rem}th{background:var(--rosa);color:#fff;text-align:left}th,td{padding:.35rem .6rem;border-bottom:1px solid #8883}
.aviso{border:2px solid var(--rosa);border-radius:12px;padding:.8rem 1rem}
.mapa{width:100%;max-height:64vh;background:var(--suave);border-radius:12px}.fin{font:700 13px sans-serif;fill:var(--tinta)}
.ruta:hover polyline{stroke-width:6}.botones{display:flex;gap:.5rem}button{font:inherit;padding:.4rem 1rem;border-radius:20px;border:2px solid var(--rosa);background:none;color:var(--tinta);cursor:pointer}
button.act{background:var(--rosa);color:#fff}
.barras{width:100%;max-width:760px}.bl{font:15px sans-serif;fill:var(--tinta)}.bv{font:700 15px sans-serif;fill:var(--tinta)}
pre{background:#111;color:#eee;padding:1rem;border-radius:10px;font-size:.9rem;overflow:auto}code{background:#8882;padding:0 .3rem;border-radius:4px}
nav{position:fixed;right:14px;top:50%;transform:translateY(-50%);display:flex;flex-direction:column;gap:7px}
nav a{width:11px;height:11px;border-radius:50%;background:#8886;display:block}nav a.on{background:var(--rosa)}
@media(max-width:800px){.dos,.rej,.tablas{grid-template-columns:1fr}h1{font-size:2.2rem}}
@media print{main{height:auto;overflow:visible}section{min-height:0;height:100vh;break-after:page}nav{display:none}}
"""

JS = """
const S=[...document.querySelectorAll('section')],nav=document.querySelector('nav'),M=document.querySelector('main');
S.forEach((s,i)=>{const a=document.createElement('a');a.href='#';a.title='Diapositiva '+(i+1);a.onclick=ev=>{ev.preventDefault();S[i].scrollIntoView()};nav.append(a)});
const pt=[...nav.children];let cur=0;
const obs=new IntersectionObserver(es=>es.forEach(x=>{if(x.isIntersecting){cur=S.indexOf(x.target);pt.forEach((p,j)=>p.classList.toggle('on',cur===j))}}),{root:M,rootMargin:'-50% 0px -50% 0px'});
S.forEach(s=>obs.observe(s));
document.addEventListener('keydown',ev=>{const i=cur;
 if(['ArrowRight','ArrowDown','PageDown',' '].includes(ev.key)){ev.preventDefault();S[Math.min(i+1,S.length-1)].scrollIntoView()}
 if(['ArrowLeft','ArrowUp','PageUp'].includes(ev.key)){ev.preventDefault();S[Math.max(i-1,0)].scrollIntoView()}});
function mapa(b,i){b.parentNode.querySelectorAll('button').forEach(x=>x.classList.remove('act'));b.classList.add('act');
 b.parentNode.nextElementSibling.querySelectorAll('.m').forEach((m,j)=>m.style.display=i===j?'':'none')}
"""


def main() -> None:
    cuerpo = "\n".join(diapos())
    doc = (f'<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
           f"<title>Optimización de rutas - primera versión</title><style>{CSS}</style></head><body><nav></nav><main>{cuerpo}</main>"
           f"<script>{JS}</script></body></html>")
    destino = ROOT / "docs" / "presentacion_primera_version.html"
    destino.write_text(doc, encoding="utf-8")
    print(f"{destino} ({len(doc) // 1024} KB)")


if __name__ == "__main__":
    main()

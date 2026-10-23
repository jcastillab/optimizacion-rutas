"""Genera mapas locales (Leaflet) de las rutas y las fincas del KML.

Uso:
    python scripts/mapa_rutas.py                  -> datos/mapa_rutas.html (todas)
    python scripts/mapa_rutas.py --ruta "PAPIROS" -> datos/mapa_ruta_ejemplo.html
    python scripts/mapa_rutas.py --ruta ""        -> la ruta con más paradas

La secuencia de cada ruta es el orden de aparición de sus filas en
``datos/rutas y paradas con posicion.xlsx``. Reutiliza el cruce de
``scripts/cruce_fincas.py`` para mostrar la finca de cada parada.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cruce_fincas import (
    DATOS,
    EXCEL_PARADAS,
    construir_diccionario,
    cruzar,
    leer_kml,
    leer_paradas,
)

KML = DATOS / "fincas_sunshine.kml"
SALIDA = DATOS / "mapa_rutas.html"
PALETA = [
    "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#42d4f4",
    "#f032e6", "#bfef45", "#469990", "#9a6324", "#800000", "#000075",
]


def agrupar_rutas(paradas: list[dict], cruce: list[dict]) -> list[dict]:
    """Una ruta por (Nivel2, Ruta), con sus paradas en orden de aparición."""
    rutas: dict[tuple[str, str], dict] = {}
    for p, c in zip(paradas, cruce):
        if p["lat"] is None or p["lng"] is None:
            continue
        llave = (p["nivel2"], p["ruta"])
        ruta = rutas.setdefault(
            llave, {"nivel2": p["nivel2"], "ruta": p["ruta"], "paradas": []}
        )
        ruta["paradas"].append(
            {
                "parada": p["parada"],
                "lat": p["lat"],
                "lng": p["lng"],
                "finca": c["finca_kml"],
            }
        )
    lista = sorted(rutas.values(), key=lambda r: (r["nivel2"], r["ruta"]))
    for i, ruta in enumerate(lista):
        ruta["color"] = PALETA[i % len(PALETA)]
    return lista


HTML = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rutas y fincas</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">
<style>
  :root { --panel: #ffffff; --texto: #1d1d1f; --borde: #d0d0d5; }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) { --panel: #202124; --texto: #e8eaed; --borde: #3c4043; }
  }
  :root[data-theme="dark"] { --panel: #202124; --texto: #e8eaed; --borde: #3c4043; }
  html, body { height: 100%; margin: 0; background: var(--panel); color: var(--texto);
    font-family: system-ui, sans-serif; font-size: 14px; }
  #wrap { display: flex; height: 100%; }
  #panel { width: 300px; overflow-y: auto; border-right: 1px solid var(--borde); padding: 12px; box-sizing: border-box; }
  #mapa { flex: 1; }
  #panel h1 { font-size: 16px; margin: 0 0 8px; }
  #panel input, #panel select { width: 100%; box-sizing: border-box; margin: 4px 0 8px; padding: 6px; }
  .ruta { display: flex; align-items: center; gap: 6px; padding: 3px 0; }
  .sw { width: 12px; height: 12px; border-radius: 3px; flex: none; }
  .ayuda { color: #888; font-size: 12px; }
  @media (max-width: 700px) {
    #wrap { flex-direction: column; }
    #panel { width: auto; max-height: 40%; border-right: 0; border-bottom: 1px solid var(--borde); }
  }
</style>
</head>
<body>
<div id="wrap">
  <div id="panel">
    <h1>Rutas y fincas</h1>
    <input id="buscar" placeholder="Buscar ruta o parada">
    <select id="filtro-nivel2"><option value="">Todos los Nivel2</option></select>
    <div class="ayuda" id="resumen"></div>
    <h1 style="font-size:14px;margin-top:12px">Rutas</h1>
    <div id="lista-rutas"></div>
    <h1 style="font-size:14px;margin-top:12px">Capas</h1>
    <label><input type="checkbox" id="ver-fincas" checked> Fincas (puntos)</label><br>
    <label><input type="checkbox" id="ver-regiones" checked> Regiones (polígonos)</label>
    <div style="margin-top:8px">
      <button id="todas">Mostrar todas</button> <button id="ninguna">Ocultar todas</button>
    </div>
    <p class="ayuda">Las paradas siguen el orden de aparición en el Excel de rutas.</p>
  </div>
  <div id="mapa"></div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<script>
const DATOS = __DATOS__;

const mapa = L.map('mapa').setView([4.8, -74.2], 9);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19, attribution: '&copy; OpenStreetMap'
}).addTo(mapa);

const capaRegiones = L.layerGroup().addTo(mapa);
const capaRutas = L.layerGroup().addTo(mapa);
const capaFincas = L.layerGroup().addTo(mapa);
const elementos = [];

function escapar(t) {
  return String(t ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
}

DATOS.rutas.forEach(ruta => {
  const coords = ruta.paradas.map(p => [p.lat, p.lng]);
  const linea = L.polyline(coords, { color: ruta.color, weight: 3, opacity: 0.8 });
  linea.bindTooltip(escapar(ruta.ruta));
  const grupo = L.featureGroup([linea]);
  ruta.paradas.forEach((p, i) => {
    const m = L.circleMarker([p.lat, p.lng], {
      radius: 4, color: ruta.color, fillColor: '#fff', fillOpacity: 1, weight: 2
    });
    m.bindPopup(
      `<b>${escapar(ruta.ruta)}</b><br>Parada ${i + 1}: ${escapar(p.parada)}` +
      (p.finca ? `<br>Finca: ${escapar(p.finca)}` : '') +
      `<br><small>${escapar(ruta.nivel2)}</small>`
    );
    grupo.addLayer(m);
  });
  grupo.addTo(capaRutas);
  elementos.push({ ruta, grupo });
});

DATOS.regiones.forEach(r => {
  const pol = L.polygon(r.contorno, {
    color: '#555', weight: 1, fillColor: '#4363d8', fillOpacity: 0.12
  });
  pol.bindTooltip(escapar(r.nombre));
  pol.bindPopup(`<b>${escapar(r.nombre)}</b><br><small>${escapar(r.carpeta)} · ${r.vertices} vértices</small>`);
  pol.addTo(capaRegiones);
});

DATOS.fincas.forEach(f => {
  // Las fincas con paradas cruzadas son destinos: se dibujan más grandes y con etiqueta.
  const destino = f.paradas > 0;
  const m = L.circleMarker([f.lat, f.lng], {
    radius: destino ? 9 : 5,
    color: destino ? '#7a0000' : '#222',
    fillColor: '#ffd000', fillOpacity: 0.95, weight: destino ? 2 : 1
  });
  m.bindPopup(
    `<b>${escapar(f.nombre)}</b><br><small>${escapar(f.carpeta)}</small>` +
    `<br>Paradas cruzadas: ${f.paradas}`
  );
  m.bindTooltip(escapar(f.nombre) + (destino ? ` (${f.paradas})` : ''), { permanent: destino, direction: 'top' });
  m.addTo(capaFincas);
});

const niveles = [...new Set(DATOS.rutas.map(r => r.nivel2))].sort();
const selNivel = document.getElementById('filtro-nivel2');
niveles.forEach(n => selNivel.insertAdjacentHTML('beforeend', `<option value="${escapar(n)}">${escapar(n)}</option>`));

const lista = document.getElementById('lista-rutas');
elementos.forEach((e, i) => {
  const fila = document.createElement('label');
  fila.className = 'ruta';
  fila.dataset.idx = i;
  fila.innerHTML = `<input type="checkbox" checked><span class="sw" style="background:${e.ruta.color}"></span>` +
    `<span>${escapar(e.ruta.ruta)} <small>(${e.ruta.paradas.length})</small></span>`;
  fila.querySelector('input').addEventListener('change', ev => {
    ev.target.checked ? capaRutas.addLayer(e.grupo) : capaRutas.removeLayer(e.grupo);
  });
  lista.appendChild(fila);
});

function aplicarFiltro() {
  const texto = document.getElementById('buscar').value.trim().toUpperCase();
  const nivel = selNivel.value;
  let visibles = 0;
  elementos.forEach((e, i) => {
    const fila = lista.children[i];
    const coincideRuta = e.ruta.ruta.toUpperCase().includes(texto);
    const coincideParada = e.ruta.paradas.some(p => p.parada.toUpperCase().includes(texto));
    const ok = (!texto || coincideRuta || coincideParada) && (!nivel || e.ruta.nivel2 === nivel);
    fila.style.display = ok ? '' : 'none';
    const marcado = fila.querySelector('input').checked;
    if (ok && marcado) { capaRutas.addLayer(e.grupo); visibles++; }
    else { capaRutas.removeLayer(e.grupo); }
  });
  document.getElementById('resumen').textContent = `${visibles} rutas visibles de ${elementos.length}`;
}
document.getElementById('buscar').addEventListener('input', aplicarFiltro);
selNivel.addEventListener('change', aplicarFiltro);
function alternarCapa(capa, activa) {
  activa ? capa.addTo(mapa) : mapa.removeLayer(capa);
}
document.getElementById('ver-fincas').addEventListener('change', ev => alternarCapa(capaFincas, ev.target.checked));
document.getElementById('ver-regiones').addEventListener('change', ev => alternarCapa(capaRegiones, ev.target.checked));

function marcarRutas(valor) {
  lista.querySelectorAll('input').forEach(c => { c.checked = valor; c.dispatchEvent(new Event('change')); });
}
document.getElementById('todas').addEventListener('click', () => marcarRutas(true));
document.getElementById('ninguna').addEventListener('click', () => marcarRutas(false));

aplicarFiltro();

const bordes = L.featureGroup(elementos.map(e => e.grupo));
if (elementos.length) mapa.fitBounds(bordes.getBounds(), { padding: [20, 20] });
</script>
</body>
</html>
"""


HTML_RUTA = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ruta de ejemplo</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">
<style>
  :root { --panel: #ffffff; --texto: #1d1d1f; --borde: #d0d0d5; }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) { --panel: #202124; --texto: #e8eaed; --borde: #3c4043; }
  }
  :root[data-theme="dark"] { --panel: #202124; --texto: #e8eaed; --borde: #3c4043; }
  html, body { height: 100%; margin: 0; background: var(--panel); color: var(--texto);
    font-family: system-ui, sans-serif; font-size: 14px; }
  #wrap { display: flex; height: 100%; }
  #panel { width: 280px; overflow-y: auto; border-right: 1px solid var(--borde); padding: 12px; box-sizing: border-box; }
  #mapa { flex: 1; }
  #panel h1 { font-size: 16px; margin: 0 0 6px; }
  .leyenda-item { display: flex; align-items: center; gap: 8px; margin: 6px 0; }
  .num { width: 22px; height: 22px; border-radius: 50%; background: #1f5fbf; color: #fff;
    display: inline-flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; flex: none; }
  .finca { width: 16px; height: 16px; background: #ffd000; border: 2px solid #7a0000; transform: rotate(45deg); flex: none; }
  .linea { width: 26px; height: 0; border-top: 3px solid #1f5fbf; flex: none; }
  .linea.punto { border-top-style: dashed; border-top-color: #7a0000; }
  .aviso { background: #fff7d6; color: #5a4500; padding: 8px; border-radius: 6px; font-size: 12px; margin-top: 12px; }
  @media (max-width: 700px) {
    #wrap { flex-direction: column; }
    #panel { width: auto; max-height: 40%; border-right: 0; border-bottom: 1px solid var(--borde); }
  }
  .etiqueta-num { background: #1f5fbf; color: #fff; border-radius: 50%; width: 22px; height: 22px;
    line-height: 22px; text-align: center; font-size: 11px; font-weight: 700; border: 2px solid #fff; }
  .etiqueta-finca { background: #ffd000; border: 2px solid #7a0000; color: #000; padding: 2px 6px;
    font-weight: 700; white-space: nowrap; transform: translate(-50%, -150%); }
</style>
</head>
<body>
<div id="wrap">
  <div id="panel">
    <h1>__TITULO__</h1>
    <div style="color:#888;font-size:12px">__NIVEL2__</div>
    <p><b>__NPARADAS__ paradas</b> · finca destino: <b>__FINCA__</b></p>
    <div class="leyenda-item"><span class="num">1</span> Parada (número = orden)</div>
    <div class="leyenda-item"><span class="finca"></span> Finca destino</div>
    <div class="leyenda-item"><span class="linea"></span> Recorrido de la ruta</div>
    <div class="leyenda-item"><span class="linea punto"></span> Tramo hasta la finca</div>
    <div class="aviso">El orden de las paradas es el de aparición en el Excel de rutas, no necesariamente el de recogida. Las líneas son rectas entre paradas.</div>
  </div>
  <div id="mapa"></div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<script>
const RUTA = __DATOS__;
const mapa = L.map('mapa');
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19, attribution: '&copy; OpenStreetMap'
}).addTo(mapa);

const coords = RUTA.paradas.map(p => [p.lat, p.lng]);
const capa = L.featureGroup().addTo(mapa);

L.polyline(coords, { color: '#1f5fbf', weight: 4, opacity: 0.85 }).addTo(capa);
if (RUTA.finca) {
  L.polyline([coords[coords.length - 1], [RUTA.finca.lat, RUTA.finca.lng]],
    { color: '#7a0000', weight: 3, dashArray: '8 6' }).addTo(capa);
}

function escapar(t) {
  return String(t ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
}

RUTA.paradas.forEach((p, i) => {
  const icono = L.divIcon({
    className: '', html: `<div class="etiqueta-num">${i + 1}</div>`,
    iconSize: [22, 22], iconAnchor: [11, 11]
  });
  L.marker([p.lat, p.lng], { icon: icono })
    .bindPopup(`<b>${i + 1}. ${escapar(p.parada)}</b><br>${escapar(RUTA.ruta)}`)
    .addTo(capa);
});

if (RUTA.finca) {
  const icono = L.divIcon({
    className: '', html: `<div class="etiqueta-finca">${escapar(RUTA.finca.nombre)}</div>`,
    iconSize: [0, 0]
  });
  L.marker([RUTA.finca.lat, RUTA.finca.lng], { icon: icono })
    .bindPopup(`<b>${escapar(RUTA.finca.nombre)}</b><br>Finca destino`)
    .addTo(capa);
}

mapa.fitBounds(capa.getBounds(), { padding: [40, 40] });
</script>
</body>
</html>
"""


def ruta_de_ejemplo(rutas: list[dict], nombre: str | None) -> dict:
    """Ruta por nombre (contiene, sin distinguir mayúsculas) o la de más paradas."""
    if not nombre:
        return max(rutas, key=lambda r: len(r["paradas"]))
    exactas = [r for r in rutas if r["ruta"].upper() == nombre.upper()]
    if exactas:
        return exactas[0]
    coincidencias = [r for r in rutas if nombre.upper() in r["ruta"].upper()]
    if not coincidencias:
        sys.exit(f"No hay ruta que contenga '{nombre}'.")
    if len(coincidencias) > 1:
        nombres = ", ".join(r["ruta"] for r in coincidencias[:8])
        sys.exit(f"'{nombre}' coincide con varias rutas: {nombres}. Sé más específico.")
    return coincidencias[0]


def generar_ejemplo(rutas: list[dict], fincas: list[dict], nombre: str | None) -> None:
    ruta = ruta_de_ejemplo(rutas, nombre)
    conteo = Counter(p["finca"] for p in ruta["paradas"] if p["finca"])
    finca_nombre = conteo.most_common(1)[0][0] if conteo else ""
    finca = next((f for f in fincas if f["nombre_kml"] == finca_nombre and f["tipo"] == "PUNTO"), None)
    datos = {
        "ruta": ruta["ruta"],
        "paradas": ruta["paradas"],
        "finca": {"nombre": finca["nombre_kml"], "lat": finca["lat"], "lng": finca["lng"]} if finca else None,
    }
    html = (
        HTML_RUTA.replace("__DATOS__", json.dumps(datos, ensure_ascii=False))
        .replace("__TITULO__", ruta["ruta"])
        .replace("__NIVEL2__", ruta["nivel2"])
        .replace("__NPARADAS__", str(len(ruta["paradas"])))
        .replace("__FINCA__", finca_nombre or "sin finca cruzada")
    )
    salida = DATOS / "mapa_ruta_ejemplo.html"
    salida.write_text(html, encoding="utf-8")
    print(f"Ruta: {ruta['ruta']} ({ruta['nivel2']})")
    print(f"Paradas: {len(ruta['paradas'])}")
    print(f"Finca destino: {finca_nombre or 'sin finca cruzada'}")
    print(f"HTML: {salida}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ruta", help="Genera solo esta ruta (nombre parcial). Sin esta opción, mapa general.")
    args = parser.parse_args()

    fincas = leer_kml(KML)
    diccionario = construir_diccionario(fincas)
    paradas = leer_paradas(EXCEL_PARADAS)
    cruce = cruzar(paradas, fincas, diccionario)

    rutas = agrupar_rutas(paradas, cruce)
    if args.ruta is not None:
        generar_ejemplo(rutas, fincas, args.ruta)
        return
    omitidas = sum(1 for p in paradas if p["lat"] is None or p["lng"] is None)

    # Paradas cruzadas a cada finca: sirve para destacar los destinos reales.
    paradas_por_finca: dict[str, int] = {}
    for c in cruce:
        if c["finca_kml"]:
            paradas_por_finca[c["finca_kml"]] = paradas_por_finca.get(c["finca_kml"], 0) + 1

    datos = {
        "rutas": rutas,
        "fincas": [
            {"nombre": f["nombre_kml"], "tipo": f["tipo"], "carpeta": f["carpeta"],
             "lat": f["lat"], "lng": f["lng"],
             "paradas": paradas_por_finca.get(f["nombre_kml"], 0)}
            for f in fincas if f["tipo"] == "PUNTO"
        ],
        "regiones": [
            {"nombre": f["nombre_kml"], "carpeta": f["carpeta"],
             "vertices": f["vertices"], "contorno": f["contorno"]}
            for f in fincas if f["tipo"] == "POLIGONO"
        ],
    }
    SALIDA.write_text(
        HTML.replace("__DATOS__", json.dumps(datos, ensure_ascii=False)),
        encoding="utf-8",
    )

    total = sum(len(r["paradas"]) for r in rutas)
    print(f"Rutas dibujadas: {len(rutas)}")
    print(f"Paradas dibujadas: {total} (omitidas sin coordenada: {omitidas})")
    print(f"Fincas (puntos): {len(datos['fincas'])}")
    print(f"Regiones (polígonos): {len(datos['regiones'])}")
    print(f"HTML: {SALIDA}")


if __name__ == "__main__":
    main()

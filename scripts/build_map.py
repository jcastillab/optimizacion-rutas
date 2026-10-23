"""CLI: data/processed/*.csv -> data/mapa_rutas.html (mapa interactivo).

Uso:
    python scripts/build_map.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from collections import Counter

import pandas as pd

from app.core.config import settings
from app.services.recorrido import calcular_recorrido
from cruce_fincas import (
    DATOS,
    EXCEL_PARADAS,
    construir_diccionario,
    cruzar,
    leer_kml,
    leer_paradas,
)

DESTINO = settings.processed_dir.parent / "mapa_rutas.html"

PLANTILLA = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mapa de rutas</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">
<style>
  body {{ margin: 0; font-family: system-ui, sans-serif; display: flex; height: 100vh; }}
  #panel {{ width: 320px; padding: 16px; box-sizing: border-box; overflow-y: auto; border-right: 1px solid #ddd; }}
  #mapa {{ flex: 1; }}
  select {{ width: 100%; padding: 6px; margin-bottom: 12px; }}
  .aviso {{ font-size: 12px; color: #555; background: #fff8e1; padding: 8px; border-radius: 4px; }}
  .metrica {{ font-size: 15px; margin: 8px 0; }}
  .leyenda-item {{ font-size: 13px; margin: 4px 0; }}
  .swatch {{ display: inline-block; width: 14px; height: 10px; margin-right: 6px; border-radius: 2px; }}
  .num {{ background: #1565c0; color: #fff; border-radius: 50%; width: 22px; height: 22px;
          line-height: 22px; text-align: center; font-size: 12px; border: 2px solid #fff; position: relative; }}
  .num.sin {{ background: #9e9e9e; }}
  .badge {{ position: absolute; top: -8px; right: -10px; background: #2e7d32; color: #fff;
            border-radius: 10px; padding: 0 5px; font-size: 11px; line-height: 16px; }}
  .persona-lista {{ margin: 4px 0 0 0; padding-left: 18px; font-size: 13px; }}
  .finca-dest {{ background: #ffd000; border: 2px solid #7a0000; color: #000; padding: 2px 6px;
                 font-weight: 700; white-space: nowrap; transform: translate(-50%, -150%); }}
  @media (max-width: 700px) {{
    body {{ flex-direction: column; height: auto; }}
    #panel {{ width: auto; border-right: none; }}
    #mapa {{ height: 60vh; }}
  }}
</style>
</head>
<body>
<div id="panel">
  <h3>Rutas</h3>
  <label>Ver todas las rutas de<select id="grupo"></select></label>
  <label>Ruta<select id="ruta"></select></label>
  <label>Tipo de día<select id="tipo"></select></label>
  <div class="metrica"><b>Distancia en línea recta:</b> <span id="dist"></span></div>
  <div class="metrica"><b>Finca destino:</b> <span id="finca"></span></div>
  <div class="metrica"><b>Paradas trazadas:</b> <span id="npar"></span></div>
  <div class="metrica"><b>Personas en la ruta:</b> <span id="npers"></span></div>
  <p class="aviso">El orden de paradas es una estimación (no el orden real de recogida)
  y la distancia es en línea recta, por lo que subestima la distancia por carretera.
  No incluye el tramo hasta la finca.</p>
  <div id="leyenda"></div>
  <h4>Paradas excluidas</h4>
  <ul id="excluidas"></ul>
</div>
<div id="mapa"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<script>
const RECORRIDOS = {datos};

const selRuta = document.getElementById("ruta");
const selTipo = document.getElementById("tipo");
const mapa = L.map("mapa");
L.tileLayer("https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors"
}}).addTo(mapa);
const capa = L.layerGroup().addTo(mapa);

const rutasUnicas = [...new Set(RECORRIDOS.map(r => r.ruta_base))].sort();
for (const nombre of rutasUnicas) {{
  selRuta.add(new Option(nombre, nombre));
}}

function tiposDe(ruta) {{
  return RECORRIDOS.filter(r => r.ruta_base === ruta).map(r => r.tipo_dia);
}}

function actualizarTipos() {{
  const tipos = selGrupo.value
    ? [...new Set(RECORRIDOS.filter(r => nombreGrupo(r) === selGrupo.value).map(r => r.tipo_dia))]
    : tiposDe(selRuta.value);
  selTipo.innerHTML = "";
  for (const t of tipos) selTipo.add(new Option(t, t));
  // Por defecto LABORAL; si no hay laboral, queda el primero disponible.
  if (tipos.includes("LABORAL")) selTipo.value = "LABORAL";
  dibujar();
}}

// Marca la finca destino de la ruta y añade su punto a los límites del mapa.
function ponerFinca(rec, capa, puntos) {{
  if (!rec.finca) return;
  L.marker([rec.finca.lat, rec.finca.lng], {{
    icon: L.divIcon({{ className: "", html: `<div class="finca-dest">${{rec.finca.nombre}}</div>`, iconSize: [0, 0] }})
  }}).bindPopup(`<b>Finca destino: ${{rec.finca.nombre}}</b>`).addTo(capa);
  puntos.push([rec.finca.lat, rec.finca.lng]);
}}

function dibujar() {{
  if (selGrupo.value) return dibujarGrupo();
  selRuta.disabled = false;
  leyenda.innerHTML = "";
  const rec = RECORRIDOS.find(r => r.ruta_base === selRuta.value && r.tipo_dia === selTipo.value);
  capa.clearLayers();
  document.getElementById("excluidas").innerHTML = "";
  if (!rec) return;

  document.getElementById("dist").textContent = rec.distancia_km.toFixed(1) + " km";
  document.getElementById("finca").textContent = rec.finca ? rec.finca.nombre : "sin finca cruzada";
  document.getElementById("npar").textContent = rec.paradas.length;
  document.getElementById("npers").textContent = rec.paradas.reduce((n, p) => n + p.personas.length, 0);

  const puntos = rec.paradas.map(p => [p.lat, p.lon]);
  for (const p of rec.paradas) {{
    const clases = p.personas.length ? "num" : "num sin";
    const badge = p.personas.length ? `<span class="badge">${{p.personas.length}}</span>` : "";
    const icono = L.divIcon({{
      className: "",
      html: `<div class="${{clases}}">${{p.orden}}${{badge}}</div>`,
      iconSize: [22, 22]
    }});
    const lista = p.personas.map(n => `<li>${{n}}</li>`).join("");
    const detalle = p.personas.length
      ? `<ul class="persona-lista">${{lista}}</ul>`
      : "<div>Sin personas asignadas</div>";
    L.marker([p.lat, p.lon], {{ icon: icono }})
      .bindPopup(`<b>${{p.orden}}. ${{p.nombre}}</b>${{detalle}}`)
      .addTo(capa);
  }}
  ponerFinca(rec, capa, puntos);
  if (puntos.length) mapa.fitBounds(puntos, {{ padding: [30, 30] }});

  const ul = document.getElementById("excluidas");
  if (!rec.excluidas.length) {{
    ul.innerHTML = "<li>Ninguna</li>";
  }}
  for (const [nombre, motivo] of rec.excluidas) {{
    const li = document.createElement("li");
    li.textContent = `${{nombre}} — ${{motivo}}`;
    ul.appendChild(li);
  }}
}}

// Vista de grupo: todas las variantes con el mismo nombre (p. ej. FACATATIVA(R1..R4)).
const selGrupo = document.getElementById("grupo");
const leyenda = document.getElementById("leyenda");
const COLORES = ["#1565c0", "#c62828", "#2e7d32", "#ef6c00", "#6a1b9a", "#00838f", "#ad1457", "#4e342e"];
const nombreGrupo = r => r.ruta_base.split("(")[0].trim();

selGrupo.add(new Option("Ninguno (una ruta)", ""));
for (const g of [...new Set(RECORRIDOS.map(nombreGrupo))].sort()) {{
  selGrupo.add(new Option("Todas las " + g, g));
}}

function dibujarGrupo() {{
  const recs = RECORRIDOS.filter(r => nombreGrupo(r) === selGrupo.value && r.tipo_dia === selTipo.value);
  capa.clearLayers();
  selRuta.disabled = true;
  leyenda.innerHTML = "";
  const excl = document.getElementById("excluidas");
  excl.innerHTML = "";

  const todos = [];
  let personas = 0;
  recs.forEach((rec, i) => {{
    const color = COLORES[i % COLORES.length];
    const puntos = rec.paradas.map(p => [p.lat, p.lon]);
    for (const p of rec.paradas) {{
      const n = p.personas.length;
      personas += n;
      const icono = L.divIcon({{
        className: "",
        html: `<div class="num" style="background:${{color}}">${{p.orden}}${{n ? `<span class="badge">${{n}}</span>` : ""}}</div>`,
        iconSize: [22, 22]
      }});
      const lista = n
        ? `<ul class="persona-lista">${{p.personas.map(x => `<li>${{x}}</li>`).join("")}}</ul>`
        : "<div>Sin personas</div>";
      L.marker([p.lat, p.lon], {{ icon: icono }})
        .bindTooltip(`<b>${{p.nombre}}</b> · ${{rec.ruta_base}}${{lista}}`, {{ direction: "top" }})
        .addTo(capa);
    }}
    ponerFinca(rec, capa, puntos);
    todos.push(...puntos);
    leyenda.insertAdjacentHTML("beforeend",
      `<div class="leyenda-item"><span class="swatch" style="background:${{color}}"></span>` +
      `${{rec.ruta_base}}: ${{rec.paradas.length}} paradas, ${{rec.distancia_km.toFixed(1)}} km` +
      ` → ${{rec.finca ? rec.finca.nombre : "sin finca cruzada"}}</div>`);
    for (const [nombre, motivo] of rec.excluidas) {{
      const li = document.createElement("li");
      li.textContent = `${{rec.ruta_base}}: ${{nombre}} — ${{motivo}}`;
      excl.appendChild(li);
    }}
  }});
  if (!recs.length) excl.innerHTML = "<li>No hay rutas de este grupo para el tipo de día elegido</li>";

  document.getElementById("dist").textContent = "ver leyenda";
  document.getElementById("finca").textContent = "ver leyenda";
  document.getElementById("npar").textContent = recs.reduce((s, r) => s + r.paradas.length, 0);
  document.getElementById("npers").textContent = personas;
  if (todos.length) mapa.fitBounds(todos, {{ padding: [30, 30] }});
}}

selGrupo.addEventListener("change", actualizarTipos);
selRuta.addEventListener("change", actualizarTipos);
selTipo.addEventListener("change", dibujar);
mapa.setView([4.8, -74.3], 11);
actualizarTipos();
</script>
</body>
</html>
"""


def clave_coord(lat, lon) -> tuple[float, float]:
    return round(float(lat), 5), round(float(lon), 5)


def fincas_por_coordenada() -> tuple[dict, dict]:
    """Finca del KML que cruza cada parada del Excel (por coordenada) y punto KML por nombre.

    Las paradas de data/processed/paradas.csv tienen las mismas coordenadas que el Excel,
    así que el cruce de cruce_fincas.py se puede reutilizar sin repetir la lógica.
    """
    fincas = leer_kml(DATOS / "fincas_sunshine.kml")
    cruce = cruzar(leer_paradas(EXCEL_PARADAS), fincas, construir_diccionario(fincas))
    por_coord = {
        clave_coord(c["lat"], c["lng"]): c["finca_kml"]
        for c in cruce
        if c["lat"] is not None and c["finca_kml"]
    }
    puntos: dict[str, dict] = {}
    for f in fincas:
        if f["tipo"] == "PUNTO":
            puntos.setdefault(f["nombre_kml"], f)
    return por_coord, puntos


def finca_destino(paradas, por_coord: dict, puntos: dict) -> dict | None:
    """Finca donde cruzan más paradas de la ruta: nombre y coordenadas del punto."""
    conteo = Counter(
        por_coord[clave_coord(p.lat, p.lon)]
        for p in paradas
        if clave_coord(p.lat, p.lon) in por_coord
    )
    for nombre, _ in conteo.most_common():
        if nombre in puntos:
            f = puntos[nombre]
            return {"nombre": nombre, "lat": f["lat"], "lng": f["lng"]}
    return None


def construir_recorridos() -> list[dict]:
    processed = settings.processed_dir
    paradas = pd.read_csv(processed / "paradas.csv")
    variantes = pd.read_csv(processed / "rutas_variante.csv")
    bases = pd.read_csv(processed / "rutas_base.csv")
    nombres = dict(zip(bases["ruta_base_id"], bases["nombre"]))
    por_coord, puntos = fincas_por_coordenada()

    # Solo nombres: la identificación no sale al HTML.
    empleados = pd.read_csv(processed / "empleados.csv")
    personas_por_parada: dict[int, list[str]] = {}
    for e in empleados.dropna(subset=["parada_id"]).itertuples():
        personas_por_parada.setdefault(int(e.parada_id), []).append(e.nombre)

    salida = []
    for var in variantes.itertuples():
        sub = paradas[paradas["ruta_variante_id"] == var.ruta_variante_id]
        rec = calcular_recorrido(
            ruta_variante_id=var.ruta_variante_id,
            ruta_base=nombres[var.ruta_base_id],
            tipo_dia=var.tipo_dia,
            paradas=sub,
            umbral_atipico_km=settings.umbral_atipico_km,
        )
        salida.append(
            {
                "ruta_variante_id": rec.ruta_variante_id,
                "ruta_base": rec.ruta_base,
                "tipo_dia": rec.tipo_dia,
                "distancia_km": round(rec.distancia_km, 2),
                "finca": finca_destino(rec.paradas, por_coord, puntos),
                "paradas": [
                    {
                        "parada_id": p.parada_id,
                        "nombre": p.nombre,
                        "lat": p.lat,
                        "lon": p.lon,
                        "orden": p.orden,
                        "personas": personas_por_parada.get(p.parada_id, []),
                    }
                    for p in rec.paradas
                ],
                "excluidas": rec.excluidas,
            }
        )
    return salida


def main() -> None:
    recorridos = construir_recorridos()
    # "<" escapado para que ningún nombre pueda cerrar el <script>.
    datos = json.dumps(recorridos, ensure_ascii=False).replace("<", "\\u003c")
    DESTINO.write_text(PLANTILLA.format(datos=datos), encoding="utf-8")
    print(f"Mapa generado: {DESTINO}")
    print(f"Variantes: {len(recorridos)}")


if __name__ == "__main__":
    main()

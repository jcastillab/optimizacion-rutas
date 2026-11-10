"""CLI: captura los pantallazos de la app para la presentación (Playwright).

Uso (con la app corriendo sobre una base de demostración, NO la real):
    python scripts/capturar_demo.py <carpeta_salida> [--base http://127.0.0.1:8765]
Claves de demo por variables: DEMO_ADMIN / DEMO_LECTOR (formato usuario:clave).
Marca zonas de interés con recuadro rosa y círculo numerado.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

MARCAR = """([sel, n]) => {
  const el = document.querySelector(sel); if (!el) return false;
  const r = el.getBoundingClientRect(), sx = scrollX, sy = scrollY;
  const caja = document.createElement('div'); caja.dataset.marca = '1';
  caja.style.cssText = `position:absolute;left:${r.left+sx-6}px;top:${r.top+sy-6}px;width:${r.width+12}px;height:${r.height+12}px;border:3px solid #e6007e;border-radius:8px;pointer-events:none;z-index:9999`;
  const c = document.createElement('div'); c.textContent = n;
  c.style.cssText = 'position:absolute;left:-14px;top:-14px;width:28px;height:28px;border-radius:50%;background:#e6007e;color:#fff;font:700 15px sans-serif;display:flex;align-items:center;justify-content:center';
  caja.appendChild(c); document.body.appendChild(caja); return true; }"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("salida", type=Path)
    ap.add_argument("--base", default="http://127.0.0.1:8765")
    a = ap.parse_args()
    out, base = a.salida, a.base
    out.mkdir(parents=True, exist_ok=True)
    admin = os.environ.get("DEMO_ADMIN", "demo:demo-Sunshine-2026").split(":", 1)
    lector = os.environ.get("DEMO_LECTOR", "lector:lector-Sunshine-2026").split(":", 1)
    tiempos: dict[str, float] = {}

    def foto(page, nombre, marcas=(), full=False):
        for sel, n in marcas:
            if not page.evaluate(MARCAR, [sel, n]):
                print("sin marca", nombre, sel)
        page.screenshot(path=str(out / f"{nombre}.png"), full_page=full)
        page.evaluate("document.querySelectorAll('[data-marca]').forEach(e => e.remove())")

    def ir(page, ruta):
        page.goto(base + ruta)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)

    def entrar(page, cred):
        ir(page, "/login")
        page.fill("#usuario", cred[0])
        page.fill("#clave", cred[1])
        page.click("button[type=submit]")
        page.wait_for_url(base + "/")
        page.wait_for_load_state("networkidle")

    def simular(page, destino_t):
        t = time.time()
        page.click("button[type=submit]")
        page.wait_for_selector("text=Rutas propuestas", timeout=300000)
        tiempos[destino_t] = round(time.time() - t, 1)
        page.wait_for_timeout(800)

    with sync_playwright() as p:
        b = p.chromium.launch(channel=os.environ.get("DEMO_CANAL") or None)
        ctx = b.new_context(viewport={"width": 1440, "height": 900}, locale="es-CO")
        page = ctx.new_page()
        ir(page, "/login")
        foto(page, "01_login")
        entrar(page, admin)
        foto(page, "02_inicio_vacio")

        ir(page, "/importar")
        page.click("text=Importar datos del Excel local")
        page.wait_for_timeout(300)
        foto(page, "03_importar_confirmar")
        t = time.time()
        page.click("dialog button.primario")
        page.wait_for_selector("text=Resultado", timeout=120000)
        tiempos["importar_s"] = round(time.time() - t, 1)
        page.wait_for_timeout(400)
        foto(page, "04_importar_resultado", [("table", 1), (".estado.aviso", 2)], full=True)

        ir(page, "/")
        foto(page, "05_inicio", [("dl.kpis", 1)])
        for r, n in [("personas", "06_personas"), ("paraderos", "07_paraderos"),
                     ("fincas", "08_fincas"), ("tipos-bus", "09_tipos_bus")]:
            ir(page, "/" + r)
            foto(page, n)

        ir(page, "/simulador")
        foto(page, "10_simulador_form")
        simular(page, "simular_60min_s")
        foto(page, "11_resultado_resumen", [("dl.kpis", 1), (".estado.aviso", 2), ("dl.kpis[aria-label]", 3)])
        page.get_by_role("heading", name="Rutas propuestas").scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        foto(page, "12_resultado_rutas", [("table", 1)])
        page.get_by_role("heading", name="Mapa de la ruta").scroll_into_view_if_needed()
        page.wait_for_timeout(500)
        foto(page, "13_resultado_mapa", [("svg.mapa-ruta", 1)])
        foto(page, "14_resultado_completo", full=True)

        # Variante más estricta para mostrar la sensibilidad a los parámetros.
        ir(page, "/simulador")
        page.locator("input[type=number]").nth(1).fill("40")
        simular(page, "simular_40min_s")
        foto(page, "15_resultado_40min", [("dl.kpis", 1)])

        ir(page, "/corridas")
        foto(page, "16_corridas", [("table", 1)])
        ir(page, "/eventos")
        foto(page, "17_eventos", [("table", 1)])
        ir(page, "/usuarios")
        foto(page, "18_usuarios")
        ctx.close()

        ctx = b.new_context(viewport={"width": 1440, "height": 900}, locale="es-CO")
        page = ctx.new_page()
        entrar(page, lector)
        foto(page, "19_inicio_lector")
        ctx2 = b.new_context(viewport={"width": 390, "height": 844}, locale="es-CO")
        m = ctx2.new_page()
        entrar(m, lector)
        foto(m, "20_inicio_movil")
        b.close()

    (out / "tiempos.json").write_text(json.dumps(tiempos, indent=1))
    print(tiempos)


if __name__ == "__main__":
    main()

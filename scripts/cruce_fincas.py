"""Cruza las fincas del mapa "Locaciones Sunshine Bouquet Colombia" (KML)
con las paradas de ``datos/rutas y paradas con posicion.xlsx``.

Genera:
    datos/diccionario_fincas.json   -> nombre de finca del KML <-> clave normalizada
    datos/cruce_rutas_fincas.xlsx   -> hojas: paradas_vs_fincas, fincas, diccionario

Criterio de cruce:
    1. COORD: finca de punto más cercana a <= UMBRAL_METROS.
    2. NOMBRE: la clave normalizada de la parada (Ruta/Parada/Nivel2) coincide
       con la clave de una finca del diccionario (exacta o aproximada).
    Si ambos métodos dan finca distinta se marca CONFLICTO.

Uso:
    python scripts/cruce_fincas.py [ruta_al_kml]

Sin argumento usa datos/fincas_sunshine.kml.
"""

from __future__ import annotations

import csv
import difflib
import json
import math
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

import openpyxl

RAIZ = Path(__file__).resolve().parents[1]
DATOS = RAIZ / "datos"
EXCEL_PARADAS = DATOS / "rutas y paradas con posicion.xlsx"
KML_NS = "{http://www.opengis.net/kml/2.2}"
UMBRAL_METROS = 300.0
UMBRAL_NOMBRE = 0.85

# Alias manuales: texto normalizado que aparece en el archivo de paradas
# -> clave normalizada de la finca en el KML. Completar al revisar el reporte.
ALIAS_MANUALES: dict[str, str] = {
    "PRADERA": "PRADERA",
    "PRADERA SECTOR 1": "PRADERA",  # supuesto: sectores de La Pradera
    "PRADERA SECTOR 3": "PRADERA",
    "BERLIN": "",  # sin finca conocida en el KML (no es nombre de finca)
}



def sin_tildes(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def clave(texto: str) -> str:
    """Clave de cruce: sin tildes, mayúsculas, sin prefijos/sufijos genéricos."""
    t = sin_tildes(texto or "").upper()
    t = re.sub(r"\bSUNSHINE BOUQUET\b", " ", t)
    t = re.sub(r"^\s*R\s*-\s*", " ", t)  # "R - Altamira" -> "Altamira"
    t = re.sub(r"\bBQT\b", " ", t)
    t = re.sub(r"\(?\b(FDS|FESTIVOS?)\b\.?\)?", " ", t)
    t = re.sub(r"\(.*?\)", " ", t)  # "ESC FACA(PAPIROS)" -> "ESC FACA"
    t = re.sub(r"[^A-Z0-9 ]", " ", t)
    t = re.sub(r"\b(LA|EL|LAS|LOS)\b", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def distancia_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radio = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radio * math.asin(math.sqrt(a))


def leer_kml(ruta_kml: Path) -> list[dict]:
    """Devuelve una entrada por Placemark. Polígonos quedan con centroide."""
    arbol = ET.parse(ruta_kml)
    fincas: list[dict] = []
    for pm in arbol.iter(f"{KML_NS}Placemark"):
        nombre = (pm.findtext(f"{KML_NS}name") or "").strip()
        carpeta = _carpeta(pm, arbol)
        punto = pm.find(f".//{KML_NS}Point/{KML_NS}coordinates")
        if punto is not None:
            tipo = "PUNTO"
            coords = [_par(punto.text)]
        else:
            tipo = "POLIGONO"
            texto = pm.find(f".//{KML_NS}Polygon//{KML_NS}coordinates")
            coords = [_par(x) for x in (texto.text or "").split() if x.strip()] if texto is not None else []
        if not coords:
            continue
        lat = sum(c[1] for c in coords) / len(coords)
        lng = sum(c[0] for c in coords) / len(coords)
        fincas.append(
            {
                "nombre_kml": nombre,
                "carpeta": carpeta,
                "tipo": tipo,
                "lat": round(lat, 7),
                "lng": round(lng, 7),
                "vertices": len(coords) if tipo == "POLIGONO" else 1,
                "clave": clave(nombre),
                # Contorno [lat, lng] para dibujar polígonos; no va al Excel.
                "contorno": [[round(c[1], 7), round(c[0], 7)] for c in coords]
                if tipo == "POLIGONO"
                else None,
            }
        )
    return fincas


def _par(texto: str) -> tuple[float, float]:
    lng, lat, *_ = [float(v) for v in texto.strip().split(",")]
    return lng, lat


def _carpeta(pm: ET.Element, arbol: ET.ElementTree) -> str:
    # Búsqueda simple: el nombre de la carpeta que contiene el Placemark.
    for carpeta in arbol.iter(f"{KML_NS}Folder"):
        if pm in list(carpeta):
            return (carpeta.findtext(f"{KML_NS}name") or "").strip()
    return ""


def leer_paradas(ruta_excel: Path) -> list[dict]:
    libro = openpyxl.load_workbook(ruta_excel, read_only=True)
    hoja = libro.worksheets[0]
    filas = hoja.iter_rows(values_only=True)
    encabezado = [str(h).strip() for h in next(filas)]
    idx = {nombre: i for i, nombre in enumerate(encabezado)}
    paradas = []
    for fila in filas:
        if not any(fila):
            continue
        lat, lng = fila[idx["latitude"]], fila[idx["longitude"]]
        paradas.append(
            {
                "nivel2": str(fila[idx["Nivel2"]] or "").strip(),
                "cod_nivel2": fila[idx["cod_nivel2"]],
                "ruta": str(fila[idx["Ruta"]] or "").strip(),
                "parada": str(fila[idx["Parada"]] or "").strip(),
                "lat": float(lat) if lat not in (None, "") else None,
                "lng": float(lng) if lng not in (None, "") else None,
            }
        )
    return paradas


def construir_diccionario(fincas: list[dict]) -> dict[str, str]:
    """clave normalizada -> nombre de finca del KML (solo PUNTO y POLIGONO)."""
    diccionario: dict[str, str] = {}
    # Puntos primero: si una finca tiene punto y polígono, gana el nombre del punto.
    for f in sorted(fincas, key=lambda f: f["tipo"] != "PUNTO"):
        if f["clave"]:
            diccionario.setdefault(f["clave"], f["nombre_kml"])
    for alias, destino in ALIAS_MANUALES.items():
        if destino:
            diccionario.setdefault(alias, diccionario.get(destino, destino))
    return diccionario


def finca_por_nombre(texto: str, diccionario: dict[str, str]) -> tuple[str, str] | None:
    """Devuelve (finca_kml, tipo_match) o None."""
    candidatas = [clave(texto)] + [clave(p) for p in re.split(r"[,/()]", texto)]
    for c in candidatas:
        if not c:
            continue
        if c in diccionario:
            return diccionario[c], "NOMBRE"
    for c in candidatas:
        if not c or len(c) < 4:
            continue
        mejor = difflib.get_close_matches(c, list(diccionario), n=1, cutoff=UMBRAL_NOMBRE)
        if mejor:
            return diccionario[mejor[0]], "NOMBRE_APROX"
    return None


def cruzar(paradas: list[dict], fincas: list[dict], diccionario: dict[str, str]) -> list[dict]:
    puntos = [f for f in fincas if f["tipo"] == "PUNTO"]
    filas = []
    for p in paradas:
        por_coord = None
        if p["lat"] is not None and p["lng"] is not None:
            cercana = min(
                puntos,
                key=lambda f: distancia_m(p["lat"], p["lng"], f["lat"], f["lng"]),
                default=None,
            )
            if cercana:
                d = distancia_m(p["lat"], p["lng"], cercana["lat"], cercana["lng"])
                if d <= UMBRAL_METROS:
                    por_coord = (cercana["nombre_kml"], round(d, 1))

        # El Nivel2 (p. ej. "BQT PRADERA") suele ser la finca; si no cruza,
        # se prueba con la ruta y luego con la parada.
        por_nombre = None
        for texto in (p["nivel2"], p["ruta"], p["parada"]):
            por_nombre = finca_por_nombre(texto, diccionario)
            if por_nombre:
                break

        if por_coord and por_nombre and por_coord[0] != por_nombre[0]:
            finca, metodo = por_coord[0], "CONFLICTO"
        elif por_coord and por_nombre:
            finca, metodo = por_coord[0], "COORD+NOMBRE"
        elif por_coord:
            finca, metodo = por_coord[0], "COORD"
        elif por_nombre:
            finca, metodo = por_nombre[0], por_nombre[1]
        else:
            finca, metodo = "", "SIN_MATCH"

        filas.append(
            {
                "nivel2": p["nivel2"],
                "cod_nivel2": p["cod_nivel2"],
                "ruta": p["ruta"],
                "parada": p["parada"],
                "lat": p["lat"],
                "lng": p["lng"],
                "finca_kml": finca,
                "metodo": metodo,
                "distancia_m": por_coord[1] if por_coord else "",
                "finca_por_nombre": por_nombre[0] if por_nombre else "",
            }
        )
    return filas


def escribir_hoja(libro: openpyxl.Workbook, nombre: str, filas: list[dict]) -> None:
    hoja = libro.create_sheet(nombre)
    if not filas:
        return
    encabezados = list(filas[0].keys())
    hoja.append(encabezados)
    for fila in filas:
        hoja.append([fila[h] for h in encabezados])
    hoja.freeze_panes = "A2"
    hoja.auto_filter.ref = hoja.dimensions
    for i, columna in enumerate(encabezados, start=1):
        ancho = max(len(str(columna)), *(len(str(f[columna])) for f in filas))
        hoja.column_dimensions[openpyxl.utils.get_column_letter(i)].width = min(ancho + 2, 45)


def escribir_libro(ruta: Path, fincas: list[dict], cruce: list[dict], diccionario: dict[str, str]) -> None:
    libro = openpyxl.Workbook()
    libro.remove(libro.active)
    escribir_hoja(libro, "paradas_vs_fincas", cruce)
    escribir_hoja(
        libro,
        "fincas",
        [{k: v for k, v in f.items() if k != "contorno"} for f in fincas],
    )
    escribir_hoja(
        libro,
        "diccionario",
        [{"clave": c, "finca_kml": n} for c, n in sorted(diccionario.items())],
    )
    libro.save(ruta)


def main() -> None:
    if len(sys.argv) > 2:
        sys.exit(__doc__)
    ruta_kml = Path(sys.argv[1]) if len(sys.argv) == 2 else DATOS / "fincas_sunshine.kml"
    fincas = leer_kml(ruta_kml)
    diccionario = construir_diccionario(fincas)
    paradas = leer_paradas(EXCEL_PARADAS)
    cruce = cruzar(paradas, fincas, diccionario)

    (DATOS / "diccionario_fincas.json").write_text(
        json.dumps(
            {"aliases_manuales": ALIAS_MANUALES, "claves": diccionario},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    escribir_libro(DATOS / "cruce_rutas_fincas.xlsx", fincas, cruce, diccionario)

    print(f"Fincas KML: {len(fincas)} ({sum(f['tipo'] == 'PUNTO' for f in fincas)} puntos)")
    print(f"Paradas: {len(paradas)}")
    conteo: dict[str, int] = {}
    for fila in cruce:
        conteo[fila["metodo"]] = conteo.get(fila["metodo"], 0) + 1
    for metodo, n in sorted(conteo.items()):
        print(f"  {metodo}: {n}")


if __name__ == "__main__":
    main()

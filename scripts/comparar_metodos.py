"""CLI: compara métodos de armado de rutas sobre los datos reales (por finca).

Métodos: voraz sin tope (referencia), voraz con tope de capacidad,
Clarke-Wright+reubicación, MILP sobre el banco de rutas y, con --multi-inicio,
multi-inicio barajado. Guarda la mejor solución por costo en
data/simulador/mejor_propuesta[_dedup].csv.

Uso:
    python scripts/comparar_metodos.py [--deduplicar] [--sin-milp] [--multi-inicio]
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
from simular_rutas import destinos_desde_kml

from app.core.config import settings
from app.services.optimizador_milp import _resolver, construir_rutas_milp
from app.services.simulador_rutas import (
    Bus,
    catalogo_buses,
    construir_rutas,
    construir_rutas_voraz,
    demanda_por_paradero,
    elegir_bus,
)

V, T = settings.velocidad_bus_kmh, settings.tiempo_max_viaje_min


def voraz_sin_tope(dem, destino, velocidad_kmh, tiempo_max_min, buses):
    """Primera versión del voraz, SIN tope de capacidad (solo para reconciliar cifras):
    una ruta puede acumular más personas que el bus más grande y usar varios buses."""
    cap_inf = [Bus("INF", 10**9, 0.0)]
    return construir_rutas_voraz(dem, destino, velocidad_kmh, tiempo_max_min, cap_inf)


def multi_inicio(dem, destino, velocidad_kmh, tiempo_max_min, buses, semillas=300):
    """Clarke-Wright+reubicación desde órdenes iniciales barajados; devuelve la mejor."""
    costos = []
    mejor = None
    for s in range(semillas):
        orden = list(range(len(dem)))
        random.Random(s).shuffle(orden)
        rutas, sin = construir_rutas(dem.iloc[orden], destino, velocidad_kmh, tiempo_max_min, buses)
        dem_c = dict(zip(dem["parada_id"], dem["personas"]))
        costo = sum(elegir_bus(sum(dem_c[p] for p in r), buses)[2] for r, _ in rutas)
        costos.append(costo)
        if mejor is None or costo < mejor[0]:
            mejor = (costo, rutas, sin)
    return mejor[1], mejor[2]


def milp(dem, destino, tiempo_limite, buses, semillas=200):
    extra = [r for r, _ in construir_rutas_voraz(dem, destino, V, T, buses)[0]]
    res = construir_rutas_milp(dem, destino, V, T, buses, tiempo_limite_s=tiempo_limite,
                               semillas=semillas, rutas_extra=extra)
    print(f"  [milp] {len(dem)} paraderos: {_resolver.diagnostico}")
    return res


def evaluar(nombre, fn, doms, buses):
    filas, t0 = [], time.perf_counter()
    for cod, (d, destino) in doms.items():
        por = dict(zip(d["parada_id"], d["personas"]))
        rutas, sin = fn(d, destino)
        for ruta, km in rutas:
            p = sum(por[x] for x in ruta)
            bus, n, costo = elegir_bus(p, buses)
            filas.append({"metodo": nombre, "finca": cod, "parada_ids": " ".join(map(str, ruta)),
                          "paradas": len(ruta), "personas": p, "km": round(km, 2),
                          "minutos_max": round(km / V * 60, 1), "tipo_bus": bus.tipo,
                          "capacidad": bus.capacidad, "buses": n, "costo_total": costo})
        filas.append({"metodo": nombre, "finca": cod, "sin_servicio": sum(por[x] for x in sin)})
    seg = time.perf_counter() - t0
    df = pd.DataFrame(filas)
    sin_personas = int(df["sin_servicio"].sum()) if "sin_servicio" in df else 0
    return df[df["parada_ids"].notna()].drop(columns="sin_servicio", errors="ignore"), seg, sin_personas


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--semillas", type=int, default=300, help="semillas del multi-inicio")
    ap.add_argument("--multi-inicio", action="store_true",
                    help="incluye el multi-inicio barajado (lento; no mejora al determinista)")
    ap.add_argument("--sin-milp", action="store_true", help="omite el MILP (tarda minutos)")
    ap.add_argument("--tiempo-limite", type=float, default=60)
    ap.add_argument("--deduplicar", action="store_true",
                    help="una fila por identificacion (la última), como la app web")
    ap.add_argument("--csv", type=Path, default=None)
    args = ap.parse_args()
    sufijo = "_dedup" if args.deduplicar else ""
    if args.csv is None:
        args.csv = settings.processed_dir.parent / "simulador" / f"mejor_propuesta{sufijo}.csv"

    d = settings.processed_dir
    fincas = pd.read_csv(d / "fincas.csv")
    tarifas = pd.read_csv(d / "tarifas.csv")
    buses = catalogo_buses(tarifas)
    empleados = pd.read_csv(d / "empleados.csv")
    if args.deduplicar:
        empleados = empleados.drop_duplicates("identificacion", keep="last")
    print(f"Empleados: {len(empleados)} filas ({'deduplicado' if args.deduplicar else 'tal cual'})")
    dem = demanda_por_paradero(empleados, pd.read_csv(d / "paradas.csv"))
    destinos = destinos_desde_kml(fincas)
    doms = {cod: (dem[dem["cod_nivel2"] == cod], dest) for cod, dest in destinos.items()}

    metodos = {
        "voraz sin tope": lambda x, y: voraz_sin_tope(x, y, V, T, buses),
        "voraz con tope": lambda x, y: construir_rutas_voraz(x, y, V, T, buses),
        "clarke-wright+reubic.": lambda x, y: construir_rutas(x, y, V, T, buses),
    }
    if args.multi_inicio:
        metodos[f"multi-inicio({args.semillas})"] = (
            lambda x, y: multi_inicio(x, y, V, T, buses, args.semillas))
    if not args.sin_milp:
        # el banco recibe también las rutas del voraz (otra fuente de candidatas)
        metodos["milp(banco)"] = lambda x, y: milp(x, y, args.tiempo_limite, buses, 20 if args.deduplicar else 200)
    resultados = {}
    print(f"{'metodo':24}{'rutas':>6}{'buses':>6}{'costo':>12}{'min_max':>9}{'seg':>8}{'sin_serv':>9}")
    for nombre, fn in metodos.items():
        df, seg, sin = evaluar(nombre, fn, doms, buses)
        resultados[nombre] = df
        print(f"{nombre:24}{len(df):>6}{int(df['buses'].sum()):>6}{df['costo_total'].sum():>12,.0f}"
              f"{df['minutos_max'].max():>9.1f}{seg:>8.1f}{sin:>9}")

    actual = tarifas[tarifas["tipo_tarifa"] == "REGULAR"]
    print(f"Red actual: {len(actual)} tarifas REGULAR (1 bus por fila) = {actual['tarifa'].sum():,.0f}")
    mejor = min(resultados, key=lambda m: resultados[m]["costo_total"].sum())
    costo = resultados[mejor]["costo_total"].sum()
    print(f"Mejor: {mejor} = {costo:,.0f} ({costo / actual['tarifa'].sum() - 1:+.1%} vs red actual)")
    print("Por finca (costo):")
    print(pd.DataFrame({m: df.groupby("finca")["costo_total"].sum() for m, df in resultados.items()})
          .to_string(float_format=lambda x: f"{x:,.0f}"))
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    resultados[mejor].to_csv(args.csv, index=False)
    print(f"Guardado en {args.csv}")


if __name__ == "__main__":
    main()

"""Simulación con datos creados por la API (no requiere los Excel)."""

from __future__ import annotations


def test_sin_datos_422_claro(admin):
    r = admin.post("/api/simulador/ejecutar")
    assert r.status_code == 422 and "tipos de bus" in r.json()["error"]["mensaje"]
    admin.post("/api/tipos-bus", json={"tipo": "BUS", "capacidad": 40, "costo": 100})
    r = admin.post("/api/simulador/ejecutar")
    assert r.status_code == 422 and "personas" in r.json()["error"]["mensaje"]


def test_simulacion_minima(admin):
    f = admin.post("/api/fincas", json={"nombre": "F", "lat": 4.80, "lon": -74.24}).json()["id"]
    p = admin.post("/api/paraderos", json={"nombre": "P", "lat": 4.81, "lon": -74.25}).json()["id"]
    lejos = admin.post("/api/paraderos", json={"nombre": "Lejos", "lat": 6.0, "lon": -75.0}).json()["id"]
    admin.post("/api/tipos-bus", json={"tipo": "BUS", "capacidad": 2, "costo": 100})
    for i, par in enumerate((p, p, p, lejos)):
        admin.post("/api/personas", json={"identificacion": str(i), "nombre": "x", "finca_id": f, "paradero_id": par})
    c = admin.post("/api/simulador/ejecutar").json()
    res = c["resumen"]
    assert res["personas"] == 3 and res["buses"] == 2 and res["costo_total"] == 200
    assert res["personas_sin_servicio"] == 1 and c["sin_servicio"][0]["paradero_id"] == lejos
    assert res["costo_red_actual"] is None and res["diferencia_pct"] is None
    # Un paradero inactivo deja de contar.
    admin.patch(f"/api/paraderos/{p}", json={"activo": False})
    assert admin.post("/api/simulador/ejecutar").json()["resumen"]["personas"] == 0

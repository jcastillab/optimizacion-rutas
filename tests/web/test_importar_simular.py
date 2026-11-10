"""Importación idempotente y simulación sobre los datos importados (usan los Excel locales)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("hay_datos_locales")


def _cuentas(admin):
    return {r: admin.get(f"/api/{r}", params={"por_pagina": 1}).json()["total"]
            for r in ("fincas", "paraderos", "personas", "tipos-bus")}


def test_importacion_idempotente(admin):
    r1 = admin.post("/api/importar/datos-locales")
    assert r1.status_code == 200, r1.text
    j1 = r1.json()
    assert set(j1) == {"fincas", "paraderos", "personas", "tipos_bus", "avisos"}
    assert j1["fincas"]["creadas"] == 3 and j1["personas"]["creadas"] > 400
    cuentas = _cuentas(admin)
    j2 = admin.post("/api/importar/datos-locales").json()
    for k in ("fincas", "paraderos", "personas", "tipos_bus"):
        assert j2[k] == {"creadas": 0, "actualizadas": 0}, k
    assert _cuentas(admin) == cuentas
    assert cuentas["personas"] == j1["personas"]["creadas"] and cuentas["tipos-bus"] == j1["tipos_bus"]["creadas"]
    acciones = [e["accion"] for e in admin.get("/api/eventos", params={"accion": "importar"}).json()["items"]]
    assert acciones == ["importar", "importar"]


def test_importacion_no_pisa_lo_desactivado(admin):
    admin.post("/api/importar/datos-locales")
    f = admin.get("/api/fincas").json()["items"][0]
    admin.patch(f"/api/fincas/{f['id']}", json={"activo": False})
    admin.post("/api/importar/datos-locales")
    assert admin.get(f"/api/fincas/{f['id']}").json()["activo"] is False


def test_simulacion_sobre_datos_importados(admin, lector):
    admin.post("/api/importar/datos-locales")
    total = admin.get("/api/personas", params={"por_pagina": 1}).json()["total"]
    r = lector.post("/api/simulador/ejecutar")  # un lector puede correr simulaciones
    assert r.status_code == 200, r.text
    c = r.json()
    res = c["resumen"]
    assert c["usuario"] == "luis" and c["parametros"] == {"velocidad_kmh": 25.0, "tiempo_max_min": 60.0}
    # Cubiertas + sin servicio (+ sin paradero asignado) = todas las personas activas.
    assert res["personas"] + res["personas_sin_servicio"] + res["personas_sin_paradero"] == total
    assert sum(r_["personas"] for r_ in c["rutas"]) == res["personas"]
    assert res["rutas"] == len(c["rutas"]) > 0 and res["buses"] == sum(r_["buses"] for r_ in c["rutas"])
    assert res["costo_total"] == pytest.approx(sum(r_["costo_total"] for r_ in c["rutas"]))
    assert res["costo_red_actual"] > 0
    assert res["diferencia_pct"] == pytest.approx(
        (res["costo_total"] - res["costo_red_actual"]) / res["costo_red_actual"] * 100, abs=0.06)
    assert all(p["nombre"] and p["lat"] for r_ in c["rutas"] for p in r_["paraderos"])
    asientos = sum(r_["buses"] * r_["capacidad"] for r_ in c["rutas"])
    assert res["ocupacion_pct"] == pytest.approx(res["personas"] / asientos * 100, abs=0.06)
    assert res["costo_por_persona"] == pytest.approx(res["costo_total"] / res["personas"], abs=1)
    assert res["km_total"] == pytest.approx(sum(r_["km"] * r_["buses"] for r_ in c["rutas"]), abs=0.06)
    assert res["minutos_max"] == max(r_["minutos_max"] for r_ in c["rutas"])
    assert 0 < res["minutos_prom"] <= res["minutos_max"] and 0 < res["cobertura_pct"] <= 100
    assert sum(s["personas"] for s in c["sin_servicio"]) == res["personas_sin_servicio"]
    # Persistida: aparece en el historial y se recupera completa.
    assert lector.get(f"/api/corridas/{c['id']}").json() == c
    hist = lector.get("/api/corridas").json()
    assert hist["total"] == 1 and set(hist["items"][0]) == {"id", "creada", "usuario", "resumen"}
    assert c["creada"].endswith("Z")
    assert admin.get("/api/eventos", params={"accion": "simular"}).json()["total"] == 1
    assert admin.delete(f"/api/corridas/{c['id']}").status_code == 204
    assert lector.get(f"/api/corridas/{c['id']}").status_code == 404


def _por_nombre(admin, ruta, **filtros):
    return admin.get(f"/api/{ruta}", params={"por_pagina": 200, **filtros}).json()["items"]


def test_reimportar_conserva_las_ediciones_y_sobrescribir_las_restaura(admin):
    admin.post("/api/importar/datos-locales")
    f0 = _por_nombre(admin, "fincas")[0]
    b0 = _por_nombre(admin, "tipos-bus")[0]
    p0 = _por_nombre(admin, "personas")[0]
    admin.patch(f"/api/fincas/{f0['id']}", json={"nombre": "Finca Editada", "lat": 1.5})
    admin.patch(f"/api/tipos-bus/{b0['id']}", json={"costo": 1, "capacidad": 7})
    admin.patch(f"/api/personas/{p0['id']}", json={"nombre": "Nombre Editado"})

    r = admin.post("/api/importar/datos-locales").json()
    assert all(r[k] == {"creadas": 0, "actualizadas": 0} for k in ("fincas", "paraderos", "personas", "tipos_bus"))
    assert any("difieren del Excel y no se modificaron" in a for a in r["avisos"])
    fincas = _por_nombre(admin, "fincas")
    assert len(fincas) == 3  # la finca renombrada no se duplica: se empareja por cod_nivel2
    assert next(f for f in fincas if f["id"] == f0["id"])["nombre"] == "Finca Editada"
    assert admin.get(f"/api/tipos-bus/{b0['id']}").json()["costo"] == 1
    assert admin.get(f"/api/personas/{p0['id']}").json()["nombre"] == "Nombre Editado"

    r = admin.post("/api/importar/datos-locales", params={"sobrescribir": "true"}).json()
    assert (r["fincas"]["actualizadas"], r["tipos_bus"]["actualizadas"], r["personas"]["actualizadas"]) == (1, 1, 1)
    assert admin.get(f"/api/fincas/{f0['id']}").json() == f0
    assert admin.get(f"/api/tipos-bus/{b0['id']}").json() == b0
    assert admin.get(f"/api/personas/{p0['id']}").json() == p0
    assert len(_por_nombre(admin, "fincas")) == 3


def test_sobrescribir_es_solo_de_admin(lector):
    assert lector.post("/api/importar/datos-locales", params={"sobrescribir": "true"}).status_code == 403


def test_aviso_de_duplicados_y_parametros_del_maestro(api, admin):
    from app.db.modelos import Parametro

    avisos = admin.post("/api/importar/datos-locales").json()["avisos"]
    texto = " ".join(avisos)
    assert "58 filas repiten" in texto and "personas tienen paraderos distintos" in texto
    with api.db() as db:
        p = {x.clave: x.valor for x in db.query(Parametro)}
    assert (p["maestro_personas_total"], p["maestro_personas_simuladas"]) == ("1160", "415")
    assert p["regla_duplicados"] == "ultima" and int(p["duplicados_paraderos_distintos"]) > 0
    a = admin.post("/api/simulador/ejecutar").json()["resumen"]["advertencias"]
    assert any(x.startswith("Solo 415 de 1160 personas del maestro cruzan con el catálogo de rutas") for x in a)
    assert any("identificación repetida con paraderos distintos; se usó la regla ultima" in x for x in a)


def test_regla_de_duplicados_primera_o_ultima(admin, monkeypatch):
    from app.core.config import settings

    admin.post("/api/importar/datos-locales")
    ultima = {p["identificacion"]: p["paradero_id"] for p in _por_nombre(admin, "personas")}
    monkeypatch.setattr(settings, "regla_duplicados", "primera")
    r = admin.post("/api/importar/datos-locales", params={"sobrescribir": "true"}).json()
    primera = {p["identificacion"]: p["paradero_id"] for p in _por_nombre(admin, "personas")}
    assert r["personas"]["actualizadas"] > 0 and primera != ultima

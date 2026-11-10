"""CRUD genérico: validación, 409, referencias, filtros, paginación y auditoría."""

from __future__ import annotations

import json

import pytest

FINCA = {"nombre": "F1", "cod_nivel2": 86, "lat": 4.8, "lon": -74.2}
PARADERO = {"nombre": "P1", "lat": 4.7, "lon": -74.3}
BUS = {"tipo": "BUS", "capacidad": 40, "costo": 450000}


def _persona(finca_id, ident="100", **extra):
    return {"identificacion": ident, "nombre": "Pepe", "finca_id": finca_id, **extra}


@pytest.mark.parametrize("ruta,cuerpo,campo", [
    ("fincas", {**FINCA, "lat": 95}, "lat"),
    ("fincas", {**FINCA, "lon": -181}, "lon"),
    ("fincas", {**FINCA, "nombre": "  "}, "nombre"),
    ("paraderos", {**PARADERO, "lat": -90.5}, "lat"),
    ("paraderos", {"nombre": "x", "lat": 1}, "lon"),
    ("tipos-bus", {**BUS, "capacidad": 0}, "capacidad"),
    ("tipos-bus", {**BUS, "costo": -1}, "costo"),
    ("personas", {"identificacion": "1", "nombre": "x"}, "finca_id"),
])
def test_validacion_422(admin, ruta, cuerpo, campo):
    r = admin.post(f"/api/{ruta}", json=cuerpo)
    assert r.status_code == 422
    e = r.json()["error"]
    assert e["codigo"] == "VALIDACION" and campo in [d["campo"] for d in e["detalle"]]


def test_patch_no_acepta_null_en_obligatorios(admin):
    fid = admin.post("/api/fincas", json=FINCA).json()["id"]
    assert admin.patch(f"/api/fincas/{fid}", json={"nombre": None}).status_code == 422
    assert admin.patch(f"/api/fincas/{fid}", json={"cod_nivel2": None}).status_code == 200


def test_por_pagina_maximo_200(admin):
    assert admin.get("/api/fincas", params={"por_pagina": 201}).status_code == 422
    assert admin.get("/api/fincas", params={"por_pagina": 200}).status_code == 200


def test_crud_completo_y_formato_de_lista(admin, lector):
    r = admin.post("/api/fincas", json=FINCA)
    assert r.status_code == 201 and r.json()["activo"] is True
    fid = r.json()["id"]
    assert admin.patch(f"/api/fincas/{fid}", json={"nombre": "F1b"}).json()["nombre"] == "F1b"
    lista = lector.get("/api/fincas", params={"q": "f1"}).json()
    assert lista == {"items": [{**FINCA, "nombre": "F1b", "id": fid, "activo": True}], "total": 1,
                     "pagina": 1, "por_pagina": 50}
    assert lector.get("/api/fincas", params={"activo": "false"}).json()["total"] == 0
    assert lector.get("/api/fincas", params={"activo": "quizas"}).status_code == 422
    assert admin.delete(f"/api/fincas/{fid}").status_code == 204
    r = admin.get(f"/api/fincas/{fid}")
    assert r.status_code == 404 and r.json()["error"]["mensaje"] == f"La finca {fid} no existe."


def test_paginacion(admin):
    for i in range(5):
        admin.post("/api/tipos-bus", json={**BUS, "tipo": f"T{i}"})
    p = admin.get("/api/tipos-bus", params={"pagina": 2, "por_pagina": 2}).json()
    assert p["total"] == 5 and [x["tipo"] for x in p["items"]] == ["T2", "T3"]


def test_409_duplicados(admin):
    fid = admin.post("/api/fincas", json=FINCA).json()["id"]
    assert admin.post("/api/fincas", json=FINCA).status_code == 409
    assert admin.post("/api/paraderos", json=PARADERO).status_code == 201
    r = admin.post("/api/paraderos", json=PARADERO)
    assert r.status_code == 409 and r.json()["error"]["codigo"] == "CONFLICTO"
    assert admin.post("/api/paraderos", json={**PARADERO, "lat": 4.71}).status_code == 201  # otra posición
    admin.post("/api/tipos-bus", json=BUS)
    assert admin.post("/api/tipos-bus", json=BUS).status_code == 409
    admin.post("/api/personas", json=_persona(fid))
    assert admin.post("/api/personas", json=_persona(fid)).status_code == 409
    otra = admin.post("/api/fincas", json={**FINCA, "nombre": "F2", "cod_nivel2": 87}).json()["id"]
    assert admin.patch(f"/api/fincas/{otra}", json={"nombre": "F1"}).status_code == 409


def test_409_borrar_con_dependencias_y_422_referencias(admin):
    fid = admin.post("/api/fincas", json=FINCA).json()["id"]
    pid = admin.post("/api/paraderos", json=PARADERO).json()["id"]
    r = admin.post("/api/personas", json=_persona(fid, paradero_id=pid))
    assert r.status_code == 201
    for ruta, i in (("fincas", fid), ("paraderos", pid)):
        d = admin.delete(f"/api/{ruta}/{i}")
        assert d.status_code == 409 and "Desactívalo" in d.json()["error"]["mensaje"]
    assert admin.get(f"/api/fincas/{fid}").status_code == 200  # nada se perdió
    r = admin.post("/api/personas", json=_persona(9999, "7"))
    assert r.status_code == 422 and r.json()["error"]["detalle"][0]["campo"] == "finca_id"
    persona = admin.get("/api/personas").json()["items"][0]["id"]
    assert admin.post("/api/personas", json=_persona(fid, "8", paradero_id=9999)).status_code == 422
    assert admin.patch(f"/api/personas/{persona}", json={"finca_id": 9999}).status_code == 422
    assert admin.get("/api/personas", params={"finca_id": fid, "paradero_id": pid}).json()["total"] == 1


def _eventos(admin, **f):
    return admin.get("/api/eventos", params=f).json()["items"]


def test_auditoria_antes_despues(admin):
    fid = admin.post("/api/fincas", json=FINCA).json()["id"]
    admin.patch(f"/api/fincas/{fid}", json={"nombre": "Nueva", "activo": False})
    admin.delete(f"/api/fincas/{fid}")
    ev = {e["accion"]: e for e in _eventos(admin, entidad="finca")}
    assert set(ev) == {"crear", "editar", "borrar"}
    assert ev["editar"]["usuario"] == "ana" and ev["editar"]["entidad_id"] == fid
    d = json.loads(ev["editar"]["detalle"])
    assert d == {"antes": {"nombre": "F1", "activo": True}, "despues": {"nombre": "Nueva", "activo": False}}
    assert json.loads(ev["crear"]["detalle"])["despues"]["nombre"] == "F1"
    assert json.loads(ev["borrar"]["detalle"])["antes"]["nombre"] == "Nueva"
    assert ev["crear"]["request_id"]


def test_auditoria_fallida_no_tumba_la_operacion(admin, monkeypatch):
    import app.repository.auditoria as aud

    def roto(**_):
        raise RuntimeError("falla la auditoría")

    monkeypatch.setattr(aud, "Evento", roto)
    r = admin.post("/api/fincas", json=FINCA)
    assert r.status_code == 201
    assert admin.get(f"/api/fincas/{r.json()['id']}").status_code == 200


def test_eventos_filtros_por_fecha(admin):
    admin.post("/api/fincas", json=FINCA)
    hoy = _eventos(admin)[0]["fecha"][:10]
    assert len(_eventos(admin, desde=hoy, hasta=hoy)) >= 1  # hasta inclusivo, día completo
    assert _eventos(admin, hasta="2000-01-01") == []
    assert admin.get("/api/eventos", params={"desde": "ayer"}).status_code == 422

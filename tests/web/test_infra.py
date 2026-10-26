"""Formato de errores, request_id, 500 sin traza, Origin, logs, frontend estático."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.api.main import create_app


def test_formato_de_error_y_request_id(anon, admin):
    for r, status, codigo in ((anon.get("/api/personas"), 401, "NO_AUTENTICADO"),
                              (admin.get("/api/nada"), 404, "NO_ENCONTRADO"),
                              (admin.post("/api/fincas", json={}), 422, "VALIDACION")):
        assert r.status_code == status
        e = r.json()["error"]
        assert set(e) == {"codigo", "mensaje", "detalle", "request_id"} and e["codigo"] == codigo
        assert e["request_id"] == r.headers["X-Request-ID"] and len(e["request_id"]) >= 8
    assert anon.get("/api/salud").headers["X-Request-ID"]


def test_salud(anon):
    assert anon.get("/api/salud").json() == {"estado": "ok", "version": anon.get("/api/salud").json()["version"],
                                             "base_datos": "ok"}


def test_500_no_expone_traza_y_queda_en_el_log(api, anon):
    @api.app.get("/api/boom")
    def boom():
        raise RuntimeError("secreto-interno-xyz")

    r = anon.get("/api/boom")
    assert r.status_code == 500
    e = r.json()["error"]
    assert e["codigo"] == "ERROR_INTERNO" and e["request_id"] == r.headers["X-Request-ID"]
    assert "secreto-interno-xyz" not in r.text and "Traceback" not in r.text
    lineas = [json.loads(x) for x in api.log().splitlines()]
    err = [x for x in lineas if x["nivel"] == "ERROR"]
    assert err and "secreto-interno-xyz" in err[0]["traza"] and err[0]["request_id"] == e["request_id"]


def test_log_json_con_campos_del_contrato(api, admin):
    admin.get("/api/fincas")
    reg = [json.loads(x) for x in api.log().splitlines() if '"/api/fincas"' in x][-1]
    assert set(reg) >= {"fecha", "nivel", "mensaje", "request_id", "usuario", "metodo", "ruta", "estado", "ms"}
    assert (reg["usuario"], reg["metodo"], reg["estado"]) == ("ana", "GET", 200)


def test_origen_ajeno_rechazado_en_escrituras(admin):
    cuerpo = {"nombre": "F", "lat": 1, "lon": 1}
    r = admin.post("/api/fincas", json=cuerpo, headers={"Origin": "http://evil.example"})
    assert r.status_code == 403 and r.json()["error"]["codigo"] == "SIN_PERMISO"
    assert admin.get("/api/fincas").status_code == 200  # lectura no se ve afectada
    assert admin.post("/api/fincas", json=cuerpo, headers={"Origin": "http://testserver"}).status_code == 201
    cuerpo["nombre"] = "G"  # el Origin de ng serve está permitido en desarrollo
    assert admin.post("/api/fincas", json=cuerpo, headers={"Origin": "http://localhost:4200"}).status_code == 201


def test_la_clave_nunca_aparece_en_logs_ni_respuestas(api, anon):
    secreta = "Sup3r-Secreta-Unica-777"
    api.crear_usuario("ana", "admin", clave=secreta)
    respuestas = [anon.post("/api/auth/login", json={"usuario": "ana", "clave": "mala-mala-mala"}),
                  anon.post("/api/auth/login", json={"usuario": "ana", "clave": secreta})]
    token = anon.cookies["sesion"]  # ya es admin: crea un usuario con otra clave y revisa listas y auditoría
    respuestas += [anon.post("/api/usuarios", json={"usuario": "zeta", "nombre": "Z", "rol": "lector",
                                                    "clave": secreta + "y"}),
                   anon.get("/api/usuarios"), anon.get("/api/eventos")]
    log = api.log()
    for texto in [r.text for r in respuestas] + [log]:
        assert secreta not in texto and secreta + "y" not in texto and "scrypt$" not in texto
    assert token not in log


def test_frontend_estatico_con_fallback_spa(api, tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>SPA</html>", encoding="utf-8")
    (dist / "main.js").write_text("console.log(1)", encoding="utf-8")
    app = create_app(db_url=f"sqlite:///{(tmp_path / 'x.db').as_posix()}", logs_dir=tmp_path / "l2",
                     frontend_dist=dist, hosts=["testserver"])
    with TestClient(app) as c:
        assert "SPA" in c.get("/").text
        assert "SPA" in c.get("/personas/12").text  # ruta del frontend -> index.html
        assert c.get("/main.js").text == "console.log(1)"
        assert c.get("/api/salud").json()["estado"] == "ok"  # /api sigue siendo la API
        r = c.get("/api/no-existe")
        assert r.status_code == 404 and r.json()["error"]["codigo"] == "NO_ENCONTRADO"
        assert "SPA" in c.get("/%2e%2e/test.db").text  # no sale de la carpeta

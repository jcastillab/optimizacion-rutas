"""Endurecimiento: bloqueo de login, valores extremos (nunca 500), Origin, hosts, cabeceras, docs, claves."""

from __future__ import annotations

import hashlib
import re
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.core.config import settings
from app.db.base import ahora
from tests.web.conftest import CLAVE

MALA = "mala-mala-mala-1"


def _login(c, usuario, clave):
    return c.post("/api/auth/login", json={"usuario": usuario, "clave": clave})


def _forma(r):
    e = r.json().get("error", {})
    return r.status_code, e.get("codigo"), e.get("mensaje")


# ---------------------------------------------------------------- 1. bloqueo de login
def test_bloqueo_identico_exista_o_no_el_usuario(api, anon):
    api.crear_usuario("bea", "lector")
    real = [_forma(_login(anon, "bea", MALA)) for _ in range(5)] + [_forma(_login(anon, "bea", CLAVE))]
    falso = [_forma(_login(anon, "fantasma", MALA)) for _ in range(5)] + [_forma(_login(anon, "fantasma", CLAVE))]
    assert real == falso
    assert [s for s, *_ in real] == [401, 401, 401, 401, 429, 429]


def test_bloqueo_con_retardo_progresivo_y_reinicio(api, anon):
    from app.db.modelos import IntentoLogin

    api.crear_usuario("bea", "lector")

    def bloqueo_seg():
        with api.db() as db:
            fila = db.get(IntentoLogin, "bea")
            return (fila.bloqueado_hasta - ahora()).total_seconds()

    def vencer():
        with api.db() as db:
            db.get(IntentoLogin, "bea").bloqueado_hasta = ahora() - timedelta(seconds=1)
            db.commit()

    for _ in range(5):
        _login(anon, "bea", MALA)
    assert 50 <= bloqueo_seg() <= 60  # primer bloqueo: 1 min
    vencer()
    for _ in range(5):
        _login(anon, "bea", MALA)
    assert 110 <= bloqueo_seg() <= 120  # segundo: 2 min (progresivo)
    vencer()
    assert _login(anon, "bea", CLAVE).status_code == 200  # pasado el retardo se entra
    with api.db() as db:
        assert db.get(IntentoLogin, "bea") is None  # y el contador se reinicia
    for _ in range(4):
        _login(anon, "bea", MALA)
    assert _login(anon, "bea", CLAVE).status_code == 200  # 4 fallos no bloquean


def test_tope_del_retardo(api, anon, monkeypatch):
    from app.db.modelos import IntentoLogin

    monkeypatch.setattr(settings, "bloqueo_max_min", 3)
    for _ in range(4):  # 1, 2, 3, 3 min
        for _ in range(5):
            _login(anon, "tope", MALA)
        with api.db() as db:
            fila = db.get(IntentoLogin, "tope")
            seg = (fila.bloqueado_hasta - ahora()).total_seconds()
            fila.bloqueado_hasta = ahora() - timedelta(seconds=1)
            db.commit()
    assert seg <= 180


def test_limite_por_ip(api, anon, monkeypatch):
    monkeypatch.setattr(settings, "ip_max_fallos", 3)
    api.crear_usuario("legit", "lector")
    for i in range(3):
        assert _login(anon, f"nombre{i}", MALA).status_code == 401
    r = _login(anon, "legit", CLAVE)  # la IP agotó su cupo: ni con la clave buena
    assert r.status_code == 429 and r.json()["error"]["codigo"] == "DEMASIADOS_INTENTOS"
    otra_ip = TestClient(api.app, client=("10.9.8.7", 5000))
    assert _login(otra_ip, "legit", CLAVE).status_code == 200  # otra IP sin fallos entra


def test_fallos_anonimos_viejos_se_limpian(api, anon):
    from app.db.modelos import IntentoLogin

    with api.db() as db:
        db.add(IntentoLogin(clave="viejo", fallos=2, nivel=0, ultimo=ahora() - timedelta(hours=3)))
        db.commit()
    _login(anon, "otro", MALA)
    with api.db() as db:
        assert db.get(IntentoLogin, "viejo") is None


# ---------------------------------------------------------------- 4 y 5. nombre del login y eventos
def test_login_valida_patron_y_no_guarda_texto_libre(api, anon, admin):
    tecleada = "Mi Clave Secreta 99"
    for u in (tecleada, "ab", "x" * 41, "ana;drop"):
        r = _login(anon, u, MALA)
        assert r.status_code == 422, u
    assert tecleada not in api.log() and tecleada not in admin.get("/api/eventos").text


def test_usuarios_inexistentes_no_llenan_eventos(api, anon, admin):
    for i in range(3):
        _login(anon, "fantasma", MALA)
    assert admin.get("/api/eventos", params={"accion": "login_fallido"}).json()["total"] == 0
    assert '"fantasma"' in api.log() or "fantasma" in api.log()  # sí queda en el log de archivo
    api.crear_usuario("bea", "lector")
    _login(anon, "bea", MALA)
    assert admin.get("/api/eventos", params={"accion": "login_fallido"}).json()["total"] == 1


# ---------------------------------------------------------------- 3. mayúsculas
def test_usuario_insensible_a_mayusculas(admin, anon):
    r = admin.post("/api/usuarios", json={"usuario": "Pepe", "nombre": "P", "rol": "lector", "clave": CLAVE})
    assert r.status_code == 201 and r.json()["usuario"] == "pepe"
    assert admin.post("/api/usuarios", json={"usuario": "PEPE", "nombre": "P", "rol": "lector",
                                             "clave": CLAVE}).status_code == 409
    for nombre in ("PEPE", "Pepe", "pepe"):
        assert _login(anon, nombre, CLAVE).status_code == 200


# ---------------------------------------------------------------- 2. valores extremos
GRANDE = "9" * 20


@pytest.mark.parametrize("metodo,ruta", [
    ("GET", f"/api/fincas/{GRANDE}"), ("PATCH", f"/api/fincas/{GRANDE}"), ("DELETE", f"/api/fincas/{GRANDE}"),
    ("GET", f"/api/corridas/{GRANDE}"), ("DELETE", f"/api/corridas/{GRANDE}"),
    ("GET", f"/api/usuarios/{GRANDE}"), ("PATCH", f"/api/usuarios/{GRANDE}"),
    ("GET", f"/api/personas?paradero_id={GRANDE}"), ("GET", f"/api/personas?finca_id={GRANDE}"),
    ("GET", f"/api/fincas?pagina={10 ** 18}"), ("GET", "/api/eventos?hasta=9999-12-31"),
    ("GET", "/api/eventos?desde=0001-01-01T00:00:00%2B14:00"), ("GET", "/api/eventos?hasta=9999-12-31T23:59:59-14:00"),
])
def test_ids_y_fechas_fuera_de_rango_no_dan_500(admin, metodo, ruta):
    r = admin.request(metodo, ruta, json={} if metodo == "PATCH" else None)
    assert r.status_code in (404, 422) or (r.status_code == 200 and "eventos" in ruta), r.text
    assert r.status_code != 500


def test_cuerpos_extremos_no_dan_500(admin):
    f = admin.post("/api/fincas", json={"nombre": "F", "lat": 1, "lon": 1}).json()["id"]
    casos = [
        ("/api/personas", {"identificacion": "1", "nombre": "x", "finca_id": 10 ** 30}),
        ("/api/personas", {"identificacion": "1", "nombre": "x", "finca_id": f, "paradero_id": 2 ** 63}),
        ("/api/fincas", {"nombre": "G", "lat": 1, "lon": 1, "cod_nivel2": 2 ** 63}),
        ("/api/tipos-bus", {"tipo": "T", "capacidad": 10 ** 30, "costo": 1}),
        ("/api/tipos-bus", {"tipo": "T", "capacidad": 1, "costo": 1e308}),
    ]
    for ruta, cuerpo in casos:
        assert admin.post(ruta, json=cuerpo).status_code == 422, (ruta, cuerpo)
    for crudo in (b'{"nombre":"a","lat":NaN,"lon":1}', b'{"nombre":"a","lat":1,"lon":1e999}'):
        r = admin.post("/api/fincas", content=crudo, headers={"Content-Type": "application/json"})
        assert r.status_code == 422


NUM = [10 ** 30, -(10 ** 30), 2 ** 63, 2 ** 63 - 1, -1, 0, 1e308]
TXT = ["9" * 30, "x" * 5000, "\x00", "0001-01-01T00:00:00+14:00", "9999-12-31", "-1", "ñ" * 300, "%"]
SALTAR = {"/api/importar/datos-locales", "/api/auth/logout"}


def _tipo(esquema, comps):
    esquema = esquema or {}
    if "$ref" in esquema:
        return _tipo(comps[esquema["$ref"].split("/")[-1]], comps)
    for variante in esquema.get("anyOf", []):
        if variante.get("type") != "null":
            return _tipo(variante, comps)
    return esquema


def _valor(esquema, comps, n, t):
    e = _tipo(esquema, comps)
    if e.get("type") in ("integer", "number"):
        return n
    if e.get("type") == "object" or "properties" in e:
        return {k: _valor(v, comps, n, t) for k, v in e.get("properties", {}).items()}
    if e.get("type") == "array":
        return [n]
    if e.get("type") == "boolean":
        return "x"
    return t


def test_ningun_endpoint_da_500_con_valores_extremos(api, admin):
    esquema = api.app.openapi()
    comps = esquema["components"]["schemas"]
    fallos = []
    for ruta, ops in esquema["paths"].items():
        if ruta in SALTAR or not ruta.startswith("/api/"):
            continue
        for metodo, op in ops.items():
            for n, t in zip(NUM + NUM[:1], TXT):
                url, params = ruta, {}
                for p in op.get("parameters", []):
                    v = _valor(p.get("schema"), comps, n, t)
                    if p["in"] == "path":
                        url = url.replace("{" + p["name"] + "}", str(v).replace("\x00", "%00").replace("/", "_"))
                    else:
                        params[p["name"]] = v
                cuerpo = None
                if "requestBody" in op:
                    cuerpo = _valor(op["requestBody"]["content"]["application/json"]["schema"], comps, n, t)
                r = admin.request(metodo.upper(), url, params=params, json=cuerpo)
                if r.status_code >= 500:
                    fallos.append((metodo, ruta, n, t, r.status_code))
    assert fallos == []


# ---------------------------------------------------------------- 6. Origin / Referer con cookie
def _sin_cabeceras(api, admin):
    c = TestClient(api.app, raise_server_exceptions=False)  # sin Origin por defecto
    c.cookies.set("sesion", admin.cookies["sesion"])
    return c


def test_escritura_con_cookie_exige_origin_o_referer(api, admin):
    c = _sin_cabeceras(api, admin)
    cuerpo = {"nombre": "F", "lat": 1, "lon": 1}
    assert c.post("/api/fincas", json=cuerpo).status_code == 403
    assert c.post("/api/fincas", json=cuerpo, headers={"Origin": ""}).status_code == 403
    assert c.post("/api/fincas", json=cuerpo, headers={"Origin": "null"}).status_code == 403
    assert c.post("/api/fincas", json=cuerpo, headers={"Referer": "http://evil.example/x"}).status_code == 403
    assert c.post("/api/fincas", json=cuerpo, headers={"Referer": "http://testserver/personas"}).status_code == 201
    cuerpo["nombre"] = "G"
    assert c.post("/api/fincas", json=cuerpo, headers={"Origin": "http://testserver"}).status_code == 201
    assert c.get("/api/fincas").status_code == 200  # lecturas no se afectan


def test_escritura_sin_cookie_no_exige_origin(api):
    c = TestClient(api.app, raise_server_exceptions=False)
    assert c.post("/api/auth/login", json={"usuario": "nadie", "clave": MALA}).status_code == 401  # no 403


# ---------------------------------------------------------------- 7, 8, 9. hosts, cabeceras, docs
@pytest.mark.parametrize("host", ["localhost", "localhost:8000", "127.0.0.1:8000", "[::1]:8000", "testserver"])
def test_hosts_permitidos(anon, host):
    assert anon.get("/api/salud", headers={"Host": host}).status_code == 200


@pytest.mark.parametrize("host", ["evil.example", "evil.example:8000", "127.0.0.1.evil.example"])
def test_host_ajeno_rechazado(anon, host):
    assert anon.get("/api/salud", headers={"Host": host}).status_code == 400


def test_cabeceras_de_seguridad(anon):
    h = anon.get("/api/salud").headers
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY"
    assert h["referrer-policy"] == "same-origin"
    csp = h["content-security-policy"]
    for parte in ("default-src 'self'", "img-src 'self' data:", "frame-ancestors 'none'", "script-src 'self'"):
        assert parte in csp
    assert "script-src 'self' 'unsafe-inline'" not in csp


def _hashes_inline(html: str) -> list[str]:
    return ["'sha256-" + __import__("base64").b64encode(hashlib.sha256(s.encode()).digest()).decode() + "'"
            for s in re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.DOTALL)]


def test_csp_autoriza_solo_los_scripts_inline_del_index(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    html = "<html><body><script>window.x = 1</script><script src='main.js'></script></body></html>"
    (dist / "index.html").write_text(html, encoding="utf-8")
    app = create_app(db_url=f"sqlite:///{(tmp_path / 'x.db').as_posix()}", logs_dir=tmp_path / "l",
                     frontend_dist=dist, hosts=["testserver"])
    with TestClient(app) as c:
        csp = c.get("/").headers["content-security-policy"]
    assert _hashes_inline(html)[0] in csp and "unsafe-inline" not in csp.split("style-src")[0]


def test_csp_no_rompe_el_build_real_de_angular(tmp_path):
    index = settings.frontend_dist / "index.html"
    if not index.is_file():
        pytest.skip("no hay build del frontend")
    app = create_app(db_url=f"sqlite:///{(tmp_path / 'x.db').as_posix()}", logs_dir=tmp_path / "l", hosts=["testserver"])
    with TestClient(app) as c:
        r = c.get("/")
    html = index.read_text(encoding="utf-8")
    assert not re.search(r"\son(load|click|error)=", html)  # sin manejadores inline
    assert all(h in r.headers["content-security-policy"] for h in _hashes_inline(html))


def test_docs_apagados_por_defecto_y_activables(tmp_path):
    kw = {"db_url": f"sqlite:///{(tmp_path / 'x.db').as_posix()}", "logs_dir": tmp_path / "l",
          "frontend_dist": tmp_path / "no", "hosts": ["testserver"]}
    with TestClient(create_app(docs=False, **kw)) as c:
        assert c.get("/api/docs").status_code == 404 and c.get("/api/openapi.json").status_code == 404
    with TestClient(create_app(docs=True, **kw)) as c:
        assert c.get("/api/openapi.json").status_code == 200 and c.get("/api/docs").status_code == 200
        assert "content-security-policy" not in c.get("/api/docs").headers  # Swagger necesita su CDN


# ---------------------------------------------------------------- 10. claves triviales
@pytest.mark.parametrize("clave", ["aaaaaaaaaaaa", "abababababab", "abcdefghijkl", "1234567890123", "0987654321",
                                   "qwertyuiopas", "zyxwvutsrqpo", "abcabcabcabc"])
def test_claves_triviales_rechazadas(admin, clave):
    r = admin.post("/api/usuarios", json={"usuario": "nuevo", "nombre": "N", "rol": "lector", "clave": clave})
    assert r.status_code == 422 and r.json()["error"]["detalle"][0]["campo"] == "clave"


def test_clave_razonable_aceptada(admin):
    assert admin.post("/api/usuarios", json={"usuario": "nuevo", "nombre": "N", "rol": "lector",
                                             "clave": "tres palabras al azar"}).status_code == 201

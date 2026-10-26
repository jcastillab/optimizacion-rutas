"""Login, sesión, bloqueo, último admin, usuarios."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from app.core.seguridad import hash_clave, hash_token, verificar_clave
from app.db.base import ahora
from app.db.modelos import IntentoLogin, Sesion
from tests.web.conftest import CLAVE


def test_hash_scrypt_con_sal():
    a, b = hash_clave("abc"), hash_clave("abc")
    assert a != b and a.startswith("scrypt$")
    assert verificar_clave("abc", a) and not verificar_clave("abd", a) and not verificar_clave("abc", "basura")


def test_login_cookie_y_sesion_solo_con_hash(api, anon):
    api.crear_usuario("ana", "admin")
    r = anon.post("/api/auth/login", json={"usuario": "ana", "clave": CLAVE})
    assert r.status_code == 200
    assert set(r.json()) >= {"id", "usuario", "nombre", "rol", "activo"} and "clave" not in r.text
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "path=/" in cookie
    token = anon.cookies["sesion"]
    with api.db() as db:
        hashes = [s.token_hash for s in db.scalars(select(Sesion))]
    assert hashes == [hash_token(token)] and token not in hashes
    assert anon.get("/api/auth/yo").json()["usuario"] == "ana"


def test_logout_revoca_la_sesion(api, admin):
    token = admin.cookies["sesion"]
    assert admin.post("/api/auth/logout").status_code == 204
    otro = api.cliente()
    otro.cookies.set("sesion", token)
    assert otro.get("/api/auth/yo").status_code == 401  # el token robado ya no sirve


def test_sesion_vencida(api, admin):
    with api.db() as db:
        for s in db.scalars(select(Sesion)):
            s.expira = ahora() - timedelta(seconds=1)
        db.commit()
    assert admin.get("/api/auth/yo").status_code == 401


def test_mismo_error_usuario_inexistente_o_clave_mala(api, anon):
    api.crear_usuario("ana", "admin")
    a = anon.post("/api/auth/login", json={"usuario": "ana", "clave": "incorrecta-xx"})
    b = anon.post("/api/auth/login", json={"usuario": "nadie", "clave": "incorrecta-xx"})
    assert a.status_code == b.status_code == 401
    ea, eb = a.json()["error"], b.json()["error"]
    assert ea["codigo"] == eb["codigo"] == "NO_AUTENTICADO" and ea["mensaje"] == eb["mensaje"]


def test_usuario_inactivo_no_entra(api, anon):
    api.crear_usuario("inac", "lector", activo=False)
    assert anon.post("/api/auth/login", json={"usuario": "inac", "clave": CLAVE}).status_code == 401


def test_bloqueo_por_intentos(api, anon, admin):
    api.crear_usuario("bea", "lector")
    codigos = [anon.post("/api/auth/login", json={"usuario": "bea", "clave": "mala-mala-1"}).status_code
               for _ in range(5)]
    assert codigos == [401, 401, 401, 401, 429]
    r = anon.post("/api/auth/login", json={"usuario": "bea", "clave": CLAVE})  # aun con la clave buena
    assert r.status_code == 429 and r.json()["error"]["codigo"] == "DEMASIADOS_INTENTOS"
    assert admin.get("/api/eventos", params={"accion": "login_fallido"}).json()["total"] == 5  # los intentos ya bloqueados no se auditan
    with api.db() as db:  # pasado el bloqueo se puede entrar
        db.get(IntentoLogin, "bea").bloqueado_hasta = ahora() - timedelta(seconds=1)
        db.commit()
    assert anon.post("/api/auth/login", json={"usuario": "bea", "clave": CLAVE}).status_code == 200


def test_ultimo_admin_no_se_desactiva_ni_degrada(api, admin):
    uid = admin.get("/api/auth/yo").json()["id"]
    for cuerpo in ({"activo": False}, {"rol": "lector"}):
        r = admin.patch(f"/api/usuarios/{uid}", json=cuerpo)
        assert r.status_code == 409 and r.json()["error"]["codigo"] == "CONFLICTO"
    api.crear_usuario("otro", "admin")  # con un segundo admin sí se puede
    assert admin.patch(f"/api/usuarios/{uid}", json={"rol": "lector"}).status_code == 200


def test_usuarios_crud_y_clave_minima(admin):
    r = admin.post("/api/usuarios", json={"usuario": "nuevo", "nombre": "Nuevo", "rol": "lector", "clave": "corta"})
    assert r.status_code == 422 and r.json()["error"]["detalle"][0]["campo"] == "clave"
    r = admin.post("/api/usuarios", json={"usuario": "nuevo", "nombre": "Nuevo", "rol": "jefe", "clave": CLAVE})
    assert r.status_code == 422
    ok = {"usuario": "nuevo", "nombre": "Nuevo", "rol": "lector", "clave": CLAVE}
    r = admin.post("/api/usuarios", json=ok)
    assert r.status_code == 201 and "clave" not in r.text and "scrypt" not in r.text
    assert admin.post("/api/usuarios", json=ok).status_code == 409
    assert admin.delete(f"/api/usuarios/{r.json()['id']}").status_code == 405  # sin DELETE


def test_cambiar_clave_cierra_sesiones_y_se_audita_sin_clave(api, admin):
    api.crear_usuario("tomas", "lector")
    c = api.cliente("tomas")
    uid = c.get("/api/auth/yo").json()["id"]
    nueva = "otra-clave-muy-larga-9"
    assert admin.patch(f"/api/usuarios/{uid}", json={"clave": nueva}).status_code == 200
    assert c.get("/api/auth/yo").status_code == 401
    assert api.cliente("tomas", nueva).get("/api/auth/yo").status_code == 200
    ev = admin.get("/api/eventos", params={"entidad": "usuario", "accion": "editar"}).text
    assert "cambiada" in ev and nueva not in ev

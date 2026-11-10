"""Tabla ruta × rol (anónimo / lector / admin) para TODAS las rutas de /api."""

from __future__ import annotations

import re

import pytest

from app.api.main import create_app

# (método, ruta, cuerpo, anónimo, lector, admin). Con cuerpo vacío/id inexistente, el admin que
# "pasa" la autorización recibe 422/404 (lo que prueba que llegó al endpoint); None = se prueba aparte.
RECURSOS = ["fincas", "paraderos", "personas", "tipos-bus"]
TABLA = [
    ("GET", "/api/salud", None, 200, 200, 200),
    ("POST", "/api/auth/login", {}, 422, 422, 422),
    ("GET", "/api/auth/yo", None, 401, 200, 200),
    ("GET", "/api/usuarios", None, 401, 403, 200),
    ("POST", "/api/usuarios", {}, 401, 403, 422),
    ("GET", "/api/usuarios/{id}", None, 401, 403, 404),
    ("PATCH", "/api/usuarios/{id}", {}, 401, 403, 404),
    ("POST", "/api/importar/datos-locales", None, 401, 403, None),
    ("POST", "/api/simulador/ejecutar", None, 401, 422, 422),
    ("GET", "/api/corridas", None, 401, 200, 200),
    ("GET", "/api/corridas/{id}", None, 401, 404, 404),
    ("DELETE", "/api/corridas/{id}", None, 401, 403, 404),
    ("GET", "/api/eventos", None, 401, 403, 200),
]
for r in RECURSOS:
    TABLA += [
        ("GET", f"/api/{r}", None, 401, 200, 200),
        ("POST", f"/api/{r}", {}, 401, 403, 422),
        ("GET", f"/api/{r}/{{id}}", None, 401, 404, 404),
        ("PATCH", f"/api/{r}/{{id}}", {}, 401, 403, 404),
        ("DELETE", f"/api/{r}/{{id}}", None, 401, 403, 404),
    ]
APARTE = {("POST", "/api/auth/logout")}  # cierra la sesión: se prueba en test_auth


def _caso(fila):
    metodo, ruta, cuerpo = fila[:3]
    return metodo, ruta.replace("{id}", "999999"), cuerpo


@pytest.mark.parametrize("fila", TABLA, ids=lambda f: f"{f[0]} {f[1]}")
def test_permisos_por_rol(fila, anon, lector, admin):
    esperados = dict(zip(("anon", "lector", "admin"), fila[3:]))
    metodo, ruta, cuerpo = _caso(fila)
    for nombre, cliente in (("anon", anon), ("lector", lector), ("admin", admin)):
        if esperados[nombre] is None:
            continue
        r = cliente.request(metodo, ruta, json=cuerpo)
        assert r.status_code == esperados[nombre], f"{nombre}: {r.status_code} {r.text}"


def test_la_tabla_cubre_todas_las_rutas(api, tmp_path):
    app = create_app(docs=True, db_url=f"sqlite:///{(tmp_path / 'docs.db').as_posix()}", hosts=["testserver"])
    plantillas = {(m.upper(), re.sub(r"\{[^}]+\}", "{id}", ruta))
                  for ruta, ops in app.openapi()["paths"].items() if ruta.startswith("/api/")
                  for m in ops}
    cubiertas = {(f[0], f[1]) for f in TABLA} | APARTE
    assert plantillas == cubiertas

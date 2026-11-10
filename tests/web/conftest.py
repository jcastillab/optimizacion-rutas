"""Fixtures de la app web: base SQLite temporal por prueba y TestClient real."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.core.config import settings
from app.core.seguridad import hash_clave
from app.db.modelos import Usuario

CLAVE = "clave-de-prueba-123"


@dataclass
class Api:
    app: object
    tmp: object
    clientes: list = field(default_factory=list)

    def db(self):
        return self.app.state.sessionmaker()

    def crear_usuario(self, usuario: str, rol: str = "lector", clave: str = CLAVE, activo: bool = True) -> int:
        with self.db() as db:
            u = Usuario(usuario=usuario, nombre=usuario.title(), rol=rol, activo=activo,
                        clave_hash=hash_clave(clave))
            db.add(u)
            db.commit()
            return u.id

    def cliente(self, usuario: str | None = None, clave: str = CLAVE) -> TestClient:
        """Cliente con su propia cookie; si hay ``usuario`` inicia sesión de verdad."""
        c = TestClient(self.app, raise_server_exceptions=False, headers={"Origin": "http://testserver"})  # como un navegador
        if usuario:
            r = c.post("/api/auth/login", json={"usuario": usuario, "clave": clave})
            assert r.status_code == 200, r.text
        self.clientes.append(c)
        return c

    def log(self) -> str:
        return (self.tmp / "logs" / "app.log").read_text(encoding="utf-8")


@pytest.fixture
def api(tmp_path):
    app = create_app(db_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}", logs_dir=tmp_path / "logs",
                     frontend_dist=tmp_path / "sin_frontend", hosts=["testserver"])
    with TestClient(app):  # ejecuta el lifespan (create_all + logging) durante la prueba
        yield Api(app, tmp_path)


@pytest.fixture
def anon(api):
    return api.cliente()


@pytest.fixture
def admin(api):
    api.crear_usuario("ana", "admin")
    return api.cliente("ana")


@pytest.fixture
def lector(api):
    api.crear_usuario("luis", "lector")
    return api.cliente("luis")


@pytest.fixture
def hay_datos_locales():
    faltan = [p for p in (settings.maestro_file, settings.posiciones_file, settings.datos_dir / "fincas_sunshine.kml")
              if not p.exists()]
    if faltan:
        pytest.skip("faltan los archivos fuente en datos/")

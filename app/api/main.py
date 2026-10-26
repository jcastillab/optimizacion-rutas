"""Aplicación FastAPI: ``app = create_app()`` (uvicorn app.api.main:app)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse

from app.api.deps import verificar_origen
from app.api.routers import (
    auth,
    eventos,
    importar,
    recursos,
    salud,
    simulador,
    usuarios,
)
from app.core.config import settings
from app.core.errores import NoEncontrado, registrar_handlers
from app.core.limitador import LimitadorIP
from app.core.logging_config import (
    MiddlewareRequest,
    cerrar_logging,
    configurar_logging,
)
from app.core.seguridad_http import (
    MiddlewareSeguridad,
    construir_csp,
    hashes_scripts_inline,
)
from app.db import modelos  # noqa: F401  (registra las tablas en Base.metadata)
from app.db.base import Base, crear_engine, crear_sessionmaker, preparar_directorio
from app.db.esquema import verificar_esquema


def _servir_frontend(app: FastAPI, dist: Path) -> None:
    raiz = dist.resolve()

    @app.get("/{ruta:path}", include_in_schema=False)
    def spa(ruta: str):
        if ruta == "api" or ruta.startswith("api/"):
            raise NoEncontrado("El recurso no existe.")
        archivo = (raiz / ruta).resolve()
        if ruta and archivo.is_relative_to(raiz) and archivo.is_file():
            return FileResponse(archivo)
        return FileResponse(raiz / "index.html")  # fallback SPA


def create_app(db_url: str | None = None, logs_dir: Path | None = None, frontend_dist: Path | None = None,
               docs: bool | None = None, hosts: list[str] | None = None) -> FastAPI:
    """``hosts``: hosts extra aceptados (además de ``settings.hosts_permitidos``); ``docs``: Swagger/OpenAPI."""
    docs = settings.docs if docs is None else docs
    url = db_url or settings.db_url
    engine = crear_engine(url)  # no toca el disco: importar este módulo no crea carpetas ni archivos

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        configurar_logging(logs_dir or settings.logs_dir)
        preparar_directorio(url)
        Base.metadata.create_all(engine)
        verificar_esquema(engine)  # falla al arrancar con un mensaje claro si la base es de otra versión
        yield
        engine.dispose()
        cerrar_logging()

    app = FastAPI(title="Transporte de personal", version=settings.version, lifespan=lifespan,
                  docs_url="/api/docs" if docs else None,
                  openapi_url="/api/openapi.json" if docs else None, redoc_url=None,
                  dependencies=[Depends(verificar_origen)])
    app.state.engine = engine
    app.state.sessionmaker = crear_sessionmaker(engine)
    app.state.limitador = LimitadorIP()
    registrar_handlers(app)
    app.add_middleware(MiddlewareRequest)

    for r in (auth.router, usuarios.router, recursos.fincas, recursos.paraderos, recursos.personas,
              recursos.tipos_bus, importar.router, simulador.simulador, simulador.corridas, eventos.router,
              salud.router):
        app.include_router(r, prefix="/api")

    dist = frontend_dist or settings.frontend_dist
    hashes: list[str] = []
    if (dist / "index.html").is_file():  # después de /api: así el comodín no lo tapa
        _servir_frontend(app, dist)
        hashes = hashes_scripts_inline((dist / "index.html").read_text(encoding="utf-8"))
    # Lo último que se añade es lo más externo: host y cabeceras cubren también las respuestas 500.
    app.add_middleware(MiddlewareSeguridad, hosts=[*settings.hosts_permitidos, *(hosts or [])],
                       csp=construir_csp(hashes))
    return app


app = create_app()

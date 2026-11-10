"""Excepciones de dominio y handlers globales con el formato del contrato."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("transporte")


class ErrorApi(Exception):
    status = 500
    codigo = "ERROR_INTERNO"

    def __init__(self, mensaje: str, detalle=None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.detalle = detalle


class NoAutenticado(ErrorApi):
    status, codigo = 401, "NO_AUTENTICADO"


class SinPermiso(ErrorApi):
    status, codigo = 403, "SIN_PERMISO"


class NoEncontrado(ErrorApi):
    status, codigo = 404, "NO_ENCONTRADO"


class Conflicto(ErrorApi):
    status, codigo = 409, "CONFLICTO"


class Validacion(ErrorApi):
    status, codigo = 422, "VALIDACION"


class DemasiadosIntentos(ErrorApi):
    status, codigo = 429, "DEMASIADOS_INTENTOS"


_POR_STATUS = {
    401: ("NO_AUTENTICADO", "Debes iniciar sesión."),
    403: ("SIN_PERMISO", "No tienes permiso para esto."),
    404: ("NO_ENCONTRADO", "El recurso no existe."),
    405: ("METODO_NO_PERMITIDO", "Método no permitido."),
}


def cuerpo_error(codigo: str, mensaje: str, detalle, request_id: str | None) -> dict:
    return {"error": {"codigo": codigo, "mensaje": mensaje, "detalle": detalle, "request_id": request_id}}


def _respuesta(request: Request, status: int, codigo: str, mensaje: str, detalle=None) -> JSONResponse:
    rid = request.scope.get("state", {}).get("request_id")
    return JSONResponse(cuerpo_error(codigo, mensaje, detalle, rid), status_code=status)


def respuesta_500(request_id: str) -> JSONResponse:
    return JSONResponse(
        cuerpo_error("ERROR_INTERNO", "Ocurrió un error interno. Si persiste, informa el código de solicitud.",
                     None, request_id),
        status_code=500,
    )


def _traducir(e: dict) -> str:
    tipo, ctx = e.get("type", ""), e.get("ctx", {})
    if tipo == "missing":
        return "Es obligatorio."
    comparadores = {"greater_than_equal": ("mayor o igual a", "ge"), "less_than_equal": ("menor o igual a", "le"),
                    "greater_than": ("mayor que", "gt"), "less_than": ("menor que", "lt")}
    if tipo in comparadores:
        texto, clave = comparadores[tipo]
        return f"Debe ser {texto} {ctx.get(clave)}."
    if tipo == "string_too_short":
        return f"Debe tener al menos {ctx.get('min_length')} caracteres."
    if tipo == "string_too_long":
        return f"Debe tener como máximo {ctx.get('max_length')} caracteres."
    if tipo in ("int_parsing", "float_parsing", "int_from_float"):
        return "Debe ser un número válido."
    if tipo == "bool_parsing":
        return "Debe ser verdadero o falso."
    if tipo == "literal_error":
        return f"Valor no permitido. Opciones: {ctx.get('expected')}."
    if tipo in ("string_type", "string_pattern_mismatch"):
        return "Formato no válido."
    if tipo in ("json_invalid", "model_attributes_type"):
        return "El cuerpo de la solicitud no es un JSON válido."
    msg = e.get("msg", "Valor no válido.")
    return msg.removeprefix("Value error, ")


def registrar_handlers(app: FastAPI) -> None:
    @app.exception_handler(ErrorApi)
    async def _dominio(request: Request, exc: ErrorApi):
        return _respuesta(request, exc.status, exc.codigo, exc.mensaje, exc.detalle)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        codigo, msg = _POR_STATUS.get(exc.status_code, ("ERROR_HTTP", "No se pudo completar la solicitud."))
        return _respuesta(request, exc.status_code, codigo, msg)

    @app.exception_handler(RequestValidationError)
    async def _validacion(request: Request, exc: RequestValidationError):
        detalle = [
            {"campo": "body" if e["type"] in ("json_invalid", "model_attributes_type")
             else ".".join(str(p) for p in e["loc"][1:]) or str(e["loc"][0]), "mensaje": _traducir(e)}
            for e in exc.errors()
        ]
        return _respuesta(request, 422, "VALIDACION", "Hay datos no válidos en la solicitud.", detalle)

    @app.exception_handler(IntegrityError)
    async def _integridad(request: Request, exc: IntegrityError):
        log.warning("IntegrityError no convertido: %s", exc.orig)
        return _respuesta(request, 409, "CONFLICTO", "El dato choca con otro existente o con datos relacionados.")

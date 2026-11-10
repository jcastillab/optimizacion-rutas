# ruff: noqa: B008  (idioma de FastAPI: Depends/Body en los valores por defecto)
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Request, Response
from sqlalchemy.orm import joinedload

from app.api.deps import (
    IdPath,
    PaginaQ,
    PorPaginaQ,
    get_db,
    requiere_admin,
    solo_lectura,
    usuario_actual,
)
from app.core.config import settings
from app.db.modelos import Corrida
from app.repository import corridas as repo
from app.repository.auditoria import registrar
from app.repository.base import listar, obtener
from app.schemas.comun import Pagina
from app.schemas.simulador import CorridaOut, CorridaResumenOut, ParametrosIn
from app.services import simulacion

simulador = APIRouter(prefix="/simulador", tags=["simulador"])
corridas = APIRouter(prefix="/corridas", tags=["corridas"])


@simulador.post("/ejecutar", response_model=CorridaOut)
@solo_lectura  # lee y calcula con BEGIN diferido; solo guardar la corrida toma el candado de escritura
def ejecutar(request: Request, params: ParametrosIn | None = Body(default=None), db=Depends(get_db),
             usuario=Depends(usuario_actual)):
    params = params or ParametrosIn()
    calculo = simulacion.calcular(db, params.velocidad_kmh, params.tiempo_max_min)
    with request.app.state.sessionmaker() as escritura:  # sesión corta, BEGIN IMMEDIATE
        c = simulacion.guardar(escritura, usuario.id, calculo)
        registrar(escritura, request, "simular", "corrida", c.id,
                  {"parametros": c.parametros, "resumen": c.resumen})
        escritura.commit()
        return repo.a_completa(escritura, c)


@corridas.get("", response_model=Pagina[CorridaResumenOut])
def lista(pagina: PaginaQ = 1, por_pagina: PorPaginaQ = settings.por_pagina_defecto, db=Depends(get_db),
          _=Depends(usuario_actual)):
    items, total = listar(db, Corrida, pagina, por_pagina, orden=Corrida.id.desc(),
                          opciones=(joinedload(Corrida.usuario),))
    return {"items": [repo.a_resumen(c) for c in items], "total": total, "pagina": pagina,
            "por_pagina": por_pagina}


@corridas.get("/{id_}", response_model=CorridaOut)
def una(id_: IdPath, db=Depends(get_db), _=Depends(usuario_actual)):
    return repo.a_completa(db, obtener(db, Corrida, id_, "La corrida"))


@corridas.delete("/{id_}", status_code=204)
def borrar(id_: IdPath, request: Request, db=Depends(get_db), _=Depends(requiere_admin)):
    c = obtener(db, Corrida, id_, "La corrida")
    resumen = c.resumen
    db.delete(c)
    registrar(db, request, "borrar", "corrida", id_, {"antes": {"resumen": resumen}})
    db.commit()
    return Response(status_code=204)

# ruff: noqa: B008  (idioma de FastAPI: Depends/Body en los valores por defecto)
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import PaginaQ, PorPaginaQ, get_db, requiere_admin
from app.core.config import settings
from app.core.errores import Validacion
from app.db.modelos import Evento
from app.repository.base import listar
from app.schemas.comun import Pagina
from app.schemas.eventos import EventoOut

router = APIRouter(prefix="/eventos", tags=["eventos"], dependencies=[Depends(requiere_admin)])


def _fecha(campo: str, texto: str, fin: bool) -> tuple[datetime, bool]:
    """(instante UTC, exclusivo). Un ``hasta`` sin fracción de segundo es inclusivo de ese segundo completo
    (los eventos se muestran truncados al segundo) y uno ``AAAA-MM-DD``, del día completo."""
    texto = texto.strip()
    try:
        d = datetime.fromisoformat(texto)
        d = d.astimezone(UTC).replace(tzinfo=None) if d.tzinfo else d
    except (ValueError, OverflowError):
        raise Validacion("Hay datos no válidos en la solicitud.",
                         [{"campo": campo, "mensaje": "Usa el formato AAAA-MM-DD o fecha y hora ISO-8601."}]
                         ) from None
    if not fin or "." in texto:
        return d, False
    try:
        return d + (timedelta(days=1) if len(texto) == 10 else timedelta(seconds=1)), True
    except OverflowError:  # 9999-12-31: no hay siguiente, todo lo anterior entra
        return datetime.max, False


@router.get("", response_model=Pagina[EventoOut])
def lista(pagina: PaginaQ = 1, por_pagina: PorPaginaQ = settings.por_pagina_defecto, accion: Annotated[str | None, Query(max_length=30)] = None,
          usuario: Annotated[str | None, Query(max_length=60)] = None,
          entidad: Annotated[str | None, Query(max_length=30)] = None,
          desde: Annotated[str | None, Query(max_length=40)] = None,
          hasta: Annotated[str | None, Query(max_length=40)] = None, db=Depends(get_db)):
    c = [col == v for col, v in ((Evento.accion, accion), (Evento.usuario, usuario and usuario.lower()),
                                 (Evento.entidad, entidad)) if v]
    if desde:
        c.append(Evento.fecha >= _fecha("desde", desde, False)[0])
    if hasta:
        limite, exclusivo = _fecha("hasta", hasta, True)
        c.append(Evento.fecha < limite if exclusivo else Evento.fecha <= limite)
    items, total = listar(db, Evento, pagina, por_pagina, condiciones=c, orden=Evento.id.desc())
    return {"items": items, "total": total, "pagina": pagina, "por_pagina": por_pagina}

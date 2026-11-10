# ruff: noqa: B008  (idioma de FastAPI: Depends/Body en los valores por defecto)
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.deps import get_db, requiere_admin
from app.repository.auditoria import registrar
from app.services.importar import importar_datos_locales

router = APIRouter(prefix="/importar", tags=["importar"])


@router.post("/datos-locales")
def datos_locales(request: Request, sobrescribir: bool = False, db=Depends(get_db), _=Depends(requiere_admin)):
    """Crea lo que falta; con ``sobrescribir=true`` también pisa los registros que difieren del Excel."""
    resultado = importar_datos_locales(db, sobrescribir)
    registrar(db, request, "importar", None, None,
              {**{k: v for k, v in resultado.items() if k != "avisos"}, "sobrescribir": sobrescribir})
    db.commit()
    return resultado

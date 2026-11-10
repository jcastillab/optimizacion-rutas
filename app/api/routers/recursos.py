"""Fincas, paraderos, personas y tipos de bus: una fábrica, cuatro routers."""

from __future__ import annotations

from app.api.crud import crear_router_crud
from app.db.modelos import Finca, Paradero, Persona, TipoBus
from app.schemas import recursos as s

fincas = crear_router_crud(
    prefijo="/fincas", tag="fincas", entidad="finca", modelo=Finca, entrada=s.FincaIn, edicion=s.FincaEdit,
    salida=s.FincaOut, buscar=("nombre",), articulo="La finca", que="una finca", filtros={"activo": "bool"})
paraderos = crear_router_crud(
    prefijo="/paraderos", tag="paraderos", entidad="paradero", modelo=Paradero, entrada=s.ParaderoIn,
    edicion=s.ParaderoEdit, salida=s.ParaderoOut, buscar=("nombre",), articulo="El paradero",
    que="un paradero", filtros={"activo": "bool"})
personas = crear_router_crud(
    prefijo="/personas", tag="personas", entidad="persona", modelo=Persona, entrada=s.PersonaIn,
    edicion=s.PersonaEdit, salida=s.PersonaOut, buscar=("nombre", "identificacion"), articulo="La persona",
    que="una persona", filtros={"paradero_id": "int", "finca_id": "int", "activo": "bool"},
    refs={"finca_id": Finca, "paradero_id": Paradero})
tipos_bus = crear_router_crud(
    prefijo="/tipos-bus", tag="tipos-bus", entidad="tipo_bus", modelo=TipoBus, entrada=s.TipoBusIn,
    edicion=s.TipoBusEdit, salida=s.TipoBusOut, buscar=("tipo",), articulo="El tipo de bus",
    que="un tipo de bus")

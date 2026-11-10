"""CLI: crea un usuario (por defecto administrador). No hay usuario por defecto.

Uso:
    python scripts/crear_admin.py <usuario> [--nombre "Nombre"] [--rol admin|lector]
    echo clave | python scripts/crear_admin.py <usuario> --clave-stdin   # automatizar

La clave se pide por getpass (no queda en el historial ni en los argumentos).
La base sale de TRANSPORTE_DB_URL (por defecto data/app.db).
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.core.seguridad import clave_trivial, hash_clave
from app.db.base import Base, crear_engine, crear_sessionmaker
from app.db.modelos import Usuario
from app.repository.auditoria import registrar_evento
from app.repository.usuarios import por_nombre
from app.schemas.usuarios import Login


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("usuario")
    ap.add_argument("--nombre")
    ap.add_argument("--rol", choices=["admin", "lector"], default="admin")
    ap.add_argument("--clave-stdin", action="store_true", help="leer la clave de la entrada estándar")
    args = ap.parse_args()

    from pydantic import TypeAdapter, ValidationError
    try:
        usuario = TypeAdapter(Login).validate_python(args.usuario)
    except ValidationError:
        print("Usuario no válido: 3 a 40 caracteres (letras, números, . _ -); se guarda en minúsculas.", file=sys.stderr)
        return 2

    nombre = args.nombre if args.nombre is None else args.nombre.strip()
    if nombre == "":
        print("El nombre no puede estar en blanco.", file=sys.stderr)
        return 2

    if args.clave_stdin:
        clave = sys.stdin.readline().rstrip("\r\n")
    else:
        clave = getpass.getpass("Clave: ")
        if clave != getpass.getpass("Repite la clave: "):
            print("Las claves no coinciden.", file=sys.stderr)
            return 2
    if not settings.clave_min_largo <= len(clave) <= 200:
        print(f"La clave debe tener entre {settings.clave_min_largo} y 200 caracteres.", file=sys.stderr)
        return 2

    if clave_trivial(clave):
        print("La clave es demasiado simple: mezcla más caracteres, sin secuencias ni repeticiones.", file=sys.stderr)
        return 2

    engine = crear_engine(settings.db_url)
    Base.metadata.create_all(engine)
    with crear_sessionmaker(engine)() as db:
        if por_nombre(db, usuario):
            print(f"Ya existe el usuario {usuario!r}.", file=sys.stderr)
            return 1
        u = Usuario(usuario=usuario, nombre=nombre or usuario, rol=args.rol, clave_hash=hash_clave(clave))
        db.add(u)
        db.flush()
        registrar_evento(db, "crear", usuario="(script)", entidad="usuario", entidad_id=u.id,
                         detalle={"despues": {"usuario": usuario, "rol": args.rol}})
        db.commit()
    print(f"Usuario {usuario!r} creado con rol {args.rol}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

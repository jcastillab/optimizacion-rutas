"""CLI: levanta la app web en http://127.0.0.1:8000 (no abre el navegador).

Uso:
    python scripts/iniciar_app.py [--puerto 8000]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import uvicorn

from app.core.config import settings


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--puerto", type=int, default=settings.puerto)
    args = ap.parse_args()
    # Solo 127.0.0.1: la app no se expone a la red.
    uvicorn.run("app.api.main:app", host="127.0.0.1", port=args.puerto)


if __name__ == "__main__":
    main()

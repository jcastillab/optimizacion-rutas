"""Normalización de nombres de ruta/parada para poder cruzar el maestro de
empleados (``info de rutas a 19-09-2026.xlsx``) con el archivo de
coordenadas (``rutas y paradas con posicion.xlsx``).

Los dos archivos no comparten una clave limpia: hay sufijos de fin de
semana/festivo (" FDS"), espacios extra, y algunos nombres en el archivo
fuente contienen el carácter de reemplazo U+FFFD ("�"), que es una pérdida
de datos real (no un problema de encoding recuperable) — ver investigación
en la sesión que originó este módulo. Para esos casos se recurre a
coincidencia aproximada (``difflib``) en vez de a una reconstrucción del
carácter, que no es posible.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

REPLACEMENT_CHAR = "�"

# Variantes conocidas de sufijo "fin de semana / festivo" encontradas en el
# archivo de posiciones. Se eliminan del nombre y marcan tipo_dia=FESTIVO.
_FDS_SUFFIX_RE = re.compile(r"\s*,?\s*(FDS|FESTIVOS?)\.?\s*$", re.IGNORECASE)

# Alias manuales para nombres de ruta que no cruzan ni siquiera tras
# normalizar (confirmados al revisar el reporte de reconciliación).
# Formato: nombre normalizado en el archivo de posiciones -> nombre
# normalizado equivalente en el maestro de rutas.
ALIAS_RUTAS: dict[str, str] = {
    "FUNZA, MSOQUERA(R1)": "FUNZA(R1)",
}


def colapsar_espacios(texto: str) -> str:
    return re.sub(r"\s+", " ", texto or "").strip()


def normalizar_clave(texto: str) -> str:
    """Clave de cruce: mayúsculas, sin espacios repetidos/extremos.

    No intenta "arreglar" el carácter de reemplazo U+FFFD porque no es
    recuperable; lo conserva para que el llamador decida si usa
    coincidencia exacta o aproximada.
    """

    return colapsar_espacios(texto).upper()


def separar_tipo_dia(nombre_ruta: str) -> tuple[str, str]:
    """Separa el nombre base de ruta del sufijo de fin de semana/festivo.

    Devuelve ``(nombre_base_normalizado, tipo_dia)`` con
    ``tipo_dia`` en ``{"LABORAL", "FESTIVO"}``.
    """

    clave = normalizar_clave(nombre_ruta)
    sin_sufijo = _FDS_SUFFIX_RE.sub("", clave).strip()
    if sin_sufijo != clave:
        return sin_sufijo, "FESTIVO"
    return clave, "LABORAL"


def resolver_alias(nombre_base_normalizado: str) -> str:
    return ALIAS_RUTAS.get(nombre_base_normalizado, nombre_base_normalizado)


@dataclass(frozen=True)
class ResultadoMatch:
    clave_encontrada: str | None
    tipo: str  # "EXACTO" | "APROXIMADO" | "SIN_COORDENADA"
    score: float = 1.0


def mejor_coincidencia(
    clave: str, candidatas: list[str], umbral: float = 0.82
) -> ResultadoMatch:
    """Busca ``clave`` dentro de ``candidatas``.

    1. Coincidencia exacta tras normalizar.
    2. Si la clave contiene el carácter de reemplazo (dato corrupto) o no
       hubo match exacto, intenta una coincidencia aproximada por similitud
       de texto (``difflib``), útil para el caso de nombres con "�".
    """

    if clave in candidatas:
        return ResultadoMatch(clave_encontrada=clave, tipo="EXACTO", score=1.0)

    cercanas = difflib.get_close_matches(clave, candidatas, n=1, cutoff=umbral)
    if cercanas:
        score = difflib.SequenceMatcher(None, clave, cercanas[0]).ratio()
        return ResultadoMatch(clave_encontrada=cercanas[0], tipo="APROXIMADO", score=score)

    return ResultadoMatch(clave_encontrada=None, tipo="SIN_COORDENADA", score=0.0)

"""Claves (scrypt + sal) y tokens de sesión. Solo stdlib."""

from __future__ import annotations

import base64
import functools
import hashlib
import hmac
import os
import secrets

_N, _R, _P = 2**14, 8, 1


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def hash_clave(clave: str) -> str:
    sal = os.urandom(16)
    h = hashlib.scrypt(clave.encode(), salt=sal, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${_b64(sal)}${_b64(h)}"


def verificar_clave(clave: str, almacenado: str) -> bool:
    """Comparación en tiempo constante; un hash mal formado da False."""
    try:
        _, n, r, p, sal, esperado = almacenado.split("$")
        h = hashlib.scrypt(clave.encode(), salt=base64.b64decode(sal), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(h, base64.b64decode(esperado))
    except (ValueError, TypeError):
        return False


@functools.cache
def hash_falso() -> str:
    """Hash para gastar el mismo tiempo cuando el usuario no existe."""
    return hash_clave(secrets.token_hex(8))


def nuevo_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


_SECUENCIAS = ("01234567890123456789", "abcdefghijklmnopqrstuvwxyz", "qwertyuiopasdfghjklzxcvbnm")


def clave_trivial(clave: str) -> bool:
    """Menos de 4 caracteres distintos o una secuencia obvia (123456..., abcdef..., qwerty..., al revés)."""
    c = clave.lower()
    return len(set(c)) < 4 or any(c in s or c in s[::-1] for s in _SECUENCIAS)

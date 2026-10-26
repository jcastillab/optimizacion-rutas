"""Límite de fallos de login por IP: en memoria, ventana deslizante.

shortcut: se reinicia con el proceso y no comparte estado entre procesos; basta para una app local de un
solo proceso. Si algún día hay varios procesos o un proxy inverso, pasar a una tabla o a Redis y leer la
IP real del proxy (hoy se usa la IP del socket).
"""

from __future__ import annotations

import time
from collections import deque
from threading import Lock

from app.core.config import settings


class LimitadorIP:
    def __init__(self):
        self._fallos: dict[str, deque[float]] = {}
        self._lock = Lock()

    def _podar(self, ip: str, ahora: float) -> deque[float]:
        q = self._fallos.setdefault(ip, deque())
        while q and q[0] < ahora - settings.ip_ventana_min * 60:
            q.popleft()
        return q

    def bloqueada(self, ip: str) -> bool:
        with self._lock:
            q = self._podar(ip, time.monotonic())
            if not q:
                self._fallos.pop(ip, None)
            return len(q) >= settings.ip_max_fallos

    def registrar_fallo(self, ip: str) -> None:
        with self._lock:
            ahora = time.monotonic()
            if len(self._fallos) > settings.ip_max_registradas:  # tope de memoria: olvida las IP sin fallos recientes
                for k in [k for k in self._fallos if not self._podar(k, ahora)]:
                    del self._fallos[k]
            self._podar(ip, ahora).append(ahora)

"""Historial de conversaciones (user + assistant por turno cerrado).

VERSIÓN PROVISIONAL EN MEMORIA: sirve para que la API, el front y el Docker arranquen desde el primer día.
El bloque B la sustituye por PostgreSQL con SQLModel **sin cambiar estas cuatro firmas**:

    ensure_schema() -> None
    save_turn(thread_id, pregunta, respuesta) -> None
    list_messages(thread_id) -> list[{role, content, created_at}]
    storage_mode() -> str

Se pierde al reiniciar el proceso: no vale para la entrega (el historial tiene que ir a Postgres).
"""

import threading
from datetime import datetime, timezone

_mensajes: dict[str, list[dict]] = {}
_lock = threading.Lock()


def ensure_schema() -> None:
    """Crea las tablas si no existen. En memoria no hay nada que crear."""


def save_turn(thread_id: str, pregunta: str, respuesta: str) -> None:
    """Guarda un turno cerrado: el mensaje del usuario y la respuesta del agente, en ese orden."""
    ahora = datetime.now(timezone.utc)
    with _lock:
        hilo = _mensajes.setdefault(thread_id, [])
        hilo.append({"role": "user", "content": pregunta, "created_at": ahora})
        hilo.append({"role": "assistant", "content": respuesta, "created_at": ahora})


def list_messages(thread_id: str) -> list[dict]:
    """Mensajes de un hilo en orden temporal. Hilo desconocido → lista vacía."""
    with _lock:
        return [dict(m) for m in _mensajes.get(thread_id, [])]


def storage_mode() -> str:
    """Lo que enseña /health en «storage»."""
    return "memoria"

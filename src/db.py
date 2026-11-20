"""Historial de conversaciones en PostgreSQL (SQLModel).

Sustituye a la versión provisional en memoria **sin cambiar las cuatro firmas**:

    ensure_schema() -> None
    save_turn(thread_id, pregunta, respuesta) -> None
    list_messages(thread_id) -> list[{role, content, created_at}]
    storage_mode() -> str

La conexión sale de config.DATABASE_URL (.env en local, panel de Render en la nube).
"""

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine, select

import config
from src.models import Conversation, Message

_engine: Engine | None = None

CONNECT_TIMEOUT_SEGUNDOS = 10  # si Postgres no responde en este tiempo, error claro en vez de quedarse colgado

def get_engine() -> Engine:
    """Crea la conexión la primera vez que hace falta (no al importar: así los tests usan otra)."""
    global _engine
    if _engine is None:
        if not config.DATABASE_URL:
            raise RuntimeError("Falta DATABASE_URL (PostgreSQL). Copia .env.example a .env y complétala.")
        # pool_pre_ping: comprueba la conexión antes de usarla (Render cierra las que llevan rato sin uso).
        _engine = create_engine(
            config.DATABASE_URL,
            pool_pre_ping=True,
            connect_args={"connect_timeout": CONNECT_TIMEOUT_SEGUNDOS},
        )
    return _engine


def ensure_schema() -> None:
    """Crea las tablas si no existen (se llama al arrancar la API)."""
    SQLModel.metadata.create_all(get_engine())


def save_turn(thread_id: str, pregunta: str, respuesta: str) -> None:
    """Guarda un turno cerrado: el mensaje del usuario y la respuesta del agente, en ese orden.

    Todo va en una sola transacción: o se guardan los dos mensajes, o ninguno.
    """
    with Session(get_engine()) as session:
        if session.get(Conversation, thread_id) is None:
            session.add(Conversation(id=thread_id))
            session.flush()  # la conversación existe antes de sus mensajes (clave foránea)
        session.add(Message(thread_id=thread_id, role="user", content=pregunta))
        session.add(Message(thread_id=thread_id, role="assistant", content=respuesta))
        session.commit()


def list_messages(thread_id: str) -> list[dict]:
    """Mensajes de un hilo en orden de inserción (por id). Hilo desconocido → lista vacía."""
    with Session(get_engine()) as session:
        filas = session.exec(
            select(Message).where(Message.thread_id == thread_id).order_by(Message.id)
        ).all()
        return [{"role": m.role, "content": m.content, "created_at": m.created_at} for m in filas]


def storage_mode() -> str:
    """Lo que enseña /health en «storage»: «postgres» si la conexión es a PostgreSQL."""
    dialecto = get_engine().dialect.name
    return "postgres" if dialecto == "postgresql" else dialecto

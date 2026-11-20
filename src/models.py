"""Modelos SQLModel del historial (PostgreSQL).

Dos tablas unidas por thread_id:
    Conversation  1 ── N  Message
Cada turno cerrado guarda dos Message: el del usuario y el del agente (ver src/db.py).
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel

THREAD_ID_MAX = 64  # mismo límite que AskIn.thread_id en schemas.py


def _ahora() -> datetime:
    """Fecha y hora actuales en UTC."""
    return datetime.now(timezone.utc)


class Conversation(SQLModel, table=True):
    """Una conversación: el thread_id que manda el cliente."""

    id: str = Field(primary_key=True, max_length=THREAD_ID_MAX)
    created_at: datetime = Field(default_factory=_ahora, sa_type=DateTime(timezone=True))


class Message(SQLModel, table=True):
    """Un mensaje del historial: la pregunta del usuario o la respuesta del agente."""

    id: int | None = Field(default=None, primary_key=True)  # autoincremental: da el orden real
    thread_id: str = Field(foreign_key="conversation.id", index=True, max_length=THREAD_ID_MAX)
    role: str = Field(max_length=20)  # "user" | "assistant"
    content: str
    created_at: datetime = Field(default_factory=_ahora, sa_type=DateTime(timezone=True))

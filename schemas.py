"""Contrato HTTP de la API (PB3).

Es un punto de contacto entre bloques: cualquier cambio se acuerda con el equipo y va en una PR propia.
La tabla de rutas y códigos está en el README («Contrato HTTP»).
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AskIn(BaseModel):
    """Un turno del agente."""

    pregunta: str = Field(..., min_length=1, max_length=2000,
                          examples=["¿Cuánto cuesta la entrada a la piscina de verano para adultos?"])
    thread_id: str = Field(..., min_length=1, max_length=64, examples=["demo-1"],
                           description="Identifica la conversación. Otro thread_id = conversación nueva.")
    auto_aprobar: bool = Field(True, description="true: si el grafo pide aprobación, la API aprueba sola "
                                                 "(cómodo en Swagger). false: devuelve pendiente_hitl=true "
                                                 "y se decide con POST /approve.")


class AskOut(BaseModel):
    """Resultado de un turno (también lo devuelve /approve)."""

    respuesta: str
    thread_id: str
    done: bool = Field(description="true si el turno se cerró con un plan aprobado.")
    pendiente_hitl: bool = Field(description="true si hay un plan esperando POST /approve.")
    plan: list[str] = Field(default_factory=list, description="Plan propuesto, para enseñarlo antes de aprobar.")
    error: str | None = None


class ApproveIn(BaseModel):
    """Decisión humana sobre el plan pendiente de un hilo."""

    thread_id: str = Field(..., min_length=1, max_length=64, examples=["demo-1"])
    aprobado: bool = Field(..., description="true aprueba, false rechaza.")


class MessageOut(BaseModel):
    """Un mensaje del historial, en orden temporal."""

    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class HealthOut(BaseModel):
    """Pulso del servicio."""

    status: Literal["ok"]
    storage: str = Field(description="Dónde vive el historial: «postgres» en local con Docker y en Render.")

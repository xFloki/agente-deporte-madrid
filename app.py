"""API del agente de Deporte Municipal (PB3).

  /ask → procesar_turno (y aprobar_plan si auto_aprobar) → historial en PostgreSQL (src/db.py)

  uvicorn app:app --reload        # http://127.0.0.1:8000/docs

Lo que falta del bloque A (ver README): /approve con el agente real, api_key (401/503),
rate limit (429), timeout (504), CORS y log por petición.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Query
from fastapi.responses import RedirectResponse

from schemas import AskIn, AskOut, ApproveIn, HealthOut, MessageOut
from src import db
from src.agent import aprobar_plan, procesar_turno

API_KEY_QUERY = Query(None, description="Clave de la API. Obligatoria en /ask, /approve y /threads/…/messages.")

# Pregunta de cada hilo con un plan pendiente: el turno se guarda cuando se decide en /approve.
_pendientes: dict[str, str] = {}


def _a_ask_out(resultado: dict) -> AskOut:
    """Del dict que devuelve src/agent.py al contrato AskOut."""
    return AskOut(
        respuesta=resultado["respuesta"],
        thread_id=resultado["thread_id"],
        done=resultado["done"],
        pendiente_hitl=resultado["pendiente_hitl"],
        plan=resultado["plan"],
        error=resultado["error"],
    )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.ensure_schema()
    yield


app = FastAPI(
    title="Agente de Deporte Municipal · API",
    version="0.1.0",
    description="El agente multiagente del PB2 (LangGraph + RAG) detrás de una API REST. "
                "/health y /docs son públicos; el resto pide api_key en la query.",
    lifespan=lifespan,
)


@app.get("/", include_in_schema=False)
def raiz() -> RedirectResponse:
    return RedirectResponse("/docs")


@app.get("/health", response_model=HealthOut, tags=["servicio"])
def health() -> HealthOut:
    """Pulso del servicio y dónde vive el historial."""
    return HealthOut(status="ok", storage=db.storage_mode())


@app.post("/ask", response_model=AskOut, tags=["agente"])
def ask(body: AskIn, api_key: str | None = API_KEY_QUERY) -> AskOut:
    """Un turno del agente. Con auto_aprobar=true, si queda un plan pendiente la API lo aprueba sola."""
    resultado = procesar_turno(body.pregunta, body.thread_id)
    if body.auto_aprobar and resultado["pendiente_hitl"]:
        resultado = aprobar_plan(body.thread_id, True)

    if resultado["error"]:  # el agente no ha completado el turno (plan pendiente, límite de turnos…): no se guarda
        return _a_ask_out(resultado)
    if resultado["pendiente_hitl"]:
        _pendientes[body.thread_id] = body.pregunta
    else:  # turno cerrado: aprobado o sin plan
        db.save_turn(body.thread_id, body.pregunta, resultado["respuesta"])
    return _a_ask_out(resultado)


@app.post("/approve", response_model=AskOut, tags=["agente"])
def approve(body: ApproveIn, api_key: str | None = API_KEY_QUERY) -> AskOut:
    """Aprueba o rechaza el plan pendiente. (Ejemplo: el bloque A lo conecta a aprobar_plan.)"""
    pregunta = _pendientes.pop(body.thread_id, "")
    respuesta = "(ejemplo) Plan aprobado." if body.aprobado else "(ejemplo) Plan rechazado."
    db.save_turn(body.thread_id, pregunta, respuesta)
    return AskOut(respuesta=respuesta, thread_id=body.thread_id, done=body.aprobado, pendiente_hitl=False)


@app.get("/threads/{thread_id}/messages", response_model=list[MessageOut], tags=["historial"])
def messages(thread_id: str, api_key: str | None = API_KEY_QUERY) -> list[MessageOut]:
    """Historial del hilo, en orden temporal."""
    return [MessageOut(**m) for m in db.list_messages(thread_id)]

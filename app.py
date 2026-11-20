"""API del agente de Deporte Municipal (PB3).

VERSIÓN MÍNIMA del punto de partida: las rutas del contrato ya existen y devuelven respuestas
de ejemplo con la forma de AskOut, para que el front y el Docker puedan arrancar desde el primer día.

  uvicorn app:app --reload        # http://127.0.0.1:8000/docs

Lo que falta, por bloques (ver README):
  A · llamar a procesar_turno / aprobar_plan de src/agent.py, api_key (401/503), rate limit (429),
      timeout (504), CORS y log por petición.
  B · historial real en PostgreSQL (src/db.py con las mismas firmas).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Query
from fastapi.responses import RedirectResponse

from schemas import AskIn, AskOut, ApproveIn, HealthOut, MessageOut
from src import db

API_KEY_QUERY = Query(None, description="Clave de la API. Obligatoria en /ask, /approve y /threads/…/messages.")

# Hilos con un plan pendiente (solo para que las respuestas de ejemplo sean coherentes).
_pendientes: dict[str, str] = {}


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
    """Un turno del agente. (Ejemplo: el bloque A lo conecta a procesar_turno.)"""
    respuesta = f"(respuesta de ejemplo) Has preguntado: «{body.pregunta}»"
    plan = ["(ejemplo) Consultar la tarifa en el documento oficial."]
    if body.auto_aprobar:
        db.save_turn(body.thread_id, body.pregunta, respuesta)
        return AskOut(respuesta=respuesta, thread_id=body.thread_id, done=True, pendiente_hitl=False, plan=plan)
    _pendientes[body.thread_id] = body.pregunta
    return AskOut(respuesta=respuesta, thread_id=body.thread_id, done=False, pendiente_hitl=True, plan=plan)


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

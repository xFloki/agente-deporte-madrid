"""Cliente HTTP de la API del agente. El front solo habla con la API a través de este módulo.

Lee API_BASE_URL y API_KEY del .env (el front no importa config.py ni nada de src/).
La clave nunca se enseña en pantalla ni en los mensajes de error.
"""

import os
import uuid
from urllib.parse import quote

import requests
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
API_KEY = os.getenv("API_KEY", "")

# En Render (free) el primer acceso despierta el servicio: puede tardar cerca de un minuto
TIMEOUT_HEALTH = 60
# Un poco más que ASK_TIMEOUT_SECONDS de la API (300): si el turno tarda, que conteste ella con 504
TIMEOUT_TURNO = 330

MENSAJES = {
    400: "No hay ningún plan pendiente en esta conversación.",
    401: "La API rechaza la clave: revisa API_KEY en el .env del front.",
    404: "La API no tiene esta conversación (¿se ha reiniciado el servicio?). Empieza una nueva.",
    422: "La API no acepta la petición (datos no válidos).",
    429: "Demasiadas peticiones en un minuto. Espera un poco y vuelve a intentarlo.",
    503: "La API no tiene API_KEY configurada.",
    504: "El agente ha tardado demasiado en responder (timeout).",
}


class ErrorAPI(Exception):
    """Error al hablar con la API, con un mensaje listo para enseñar."""

    def __init__(self, mensaje: str, status: int | None = None):
        super().__init__(mensaje)
        self.status = status


def _pedir(metodo: str, ruta: str, *, json: dict | None = None, protegida: bool = True, timeout: float) -> dict | list:
    params = {"api_key": API_KEY} if protegida else None
    try:
        r = requests.request(metodo, f"{API_BASE_URL}{ruta}", params=params, json=json, timeout=timeout)
    except requests.Timeout:
        raise ErrorAPI("La API no responde a tiempo. En Render, el primer acceso puede tardar cerca de un minuto.")
    except requests.RequestException:
        raise ErrorAPI(f"No se puede conectar con la API en {API_BASE_URL}.")
    if r.status_code >= 400:
        raise ErrorAPI(MENSAJES.get(r.status_code, f"La API ha devuelto un error {r.status_code}."), r.status_code)
    return r.json()


def nuevo_thread_id() -> str:
    """Identificador de una conversación nueva."""
    return uuid.uuid4().hex[:8]


def health() -> dict:
    """GET /health (público)."""
    return _pedir("GET", "/health", protegida=False, timeout=TIMEOUT_HEALTH)


def ask(pregunta: str, thread_id: str) -> dict:
    """POST /ask con auto_aprobar=false: si hay plan, la decisión la toma la persona en el front."""
    cuerpo = {"pregunta": pregunta, "thread_id": thread_id, "auto_aprobar": False}
    return _pedir("POST", "/ask", json=cuerpo, timeout=TIMEOUT_TURNO)


def approve(thread_id: str, aprobado: bool) -> dict:
    """POST /approve: aprueba o rechaza el plan pendiente."""
    return _pedir("POST", "/approve", json={"thread_id": thread_id, "aprobado": aprobado}, timeout=TIMEOUT_TURNO)


def messages(thread_id: str) -> list[dict]:
    """GET /threads/{thread_id}/messages: el historial guardado en la API."""
    return _pedir("GET", f"/threads/{quote(thread_id, safe='')}/messages", timeout=TIMEOUT_HEALTH)

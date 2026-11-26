"""Tests del contrato HTTP del PB3: rutas, schemas e historial.

Sin red, sin Gemini y sin Postgres: el agente es falso (siempre propone un plan) y el historial va a SQLite en memoria.
"""

from collections import defaultdict, deque

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

import app as api
import config
import rate_limit
from config import normalizar_database_url
from src import db


def _resultado_falso(thread_id: str, **cambios) -> dict:
    """Mismo formato que devuelve src/agent.py."""
    base = {"respuesta": "La entrada cuesta 4,50 €.", "plan": ["Consultar la tarifa oficial."],
            "pendiente_hitl": True, "done": False, "log": [], "traza_tools": [],
            "thread_id": thread_id, "error": None}
    return {**base, **cambios}


def _procesar_turno_falso(mensaje: str, thread_id: str) -> dict:
    return _resultado_falso(thread_id)


def _aprobar_plan_falso(thread_id: str, aprobado: bool) -> dict:
    return _resultado_falso(thread_id, pendiente_hitl=False, done=aprobado,
                            respuesta="Plan aprobado." if aprobado else "Plan rechazado.")


CLAVE = "clave-de-test"


@pytest.fixture
def client(monkeypatch):
    # Base de datos de prueba en memoria (SQLite), nueva en cada test: sin Postgres ni red.
    # El servicio usa PostgreSQL; los tests contra Postgres real van en tests/test_db_postgres.py.
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    monkeypatch.setattr(db, "_engine", engine)
    monkeypatch.setattr(api, "_pendientes", {})
    monkeypatch.setattr(api, "_hilos", set())
    monkeypatch.setattr(api, "procesar_turno", _procesar_turno_falso)
    monkeypatch.setattr(api, "aprobar_plan", _aprobar_plan_falso)
    monkeypatch.setattr(config, "API_KEY", CLAVE)
    monkeypatch.setattr(rate_limit, "_peticiones", defaultdict(deque))
    with TestClient(api.app) as c:
        c.params = {"api_key": CLAVE}
        yield c


def test_health_publico(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "storage": db.storage_mode()}


def test_raiz_redirige_a_docs(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert r.headers["location"] == "/docs"


def test_swagger_lista_rutas_y_schemas(client):
    spec = client.get("/openapi.json").json()
    assert {"/health", "/ask", "/approve", "/threads/{thread_id}/messages"} <= set(spec["paths"])
    assert {"AskIn", "AskOut", "ApproveIn", "MessageOut"} <= set(spec["components"]["schemas"])
    assert client.get("/docs").status_code == 200


def test_ask_auto_aprobar_cierra_y_guarda(client):
    r = client.post("/ask", json={"pregunta": "¿Precio piscina?", "thread_id": "t1"})
    assert r.status_code == 200
    cuerpo = r.json()
    assert set(cuerpo) == {"respuesta", "thread_id", "done", "pendiente_hitl", "plan", "error"}
    assert cuerpo["done"] and not cuerpo["pendiente_hitl"]
    msgs = client.get("/threads/t1/messages").json()
    assert [m["role"] for m in msgs] == ["user", "assistant"]


def test_ask_pendiente_no_se_guarda_hasta_approve(client):
    r = client.post("/ask", json={"pregunta": "¿Precio piscina?", "thread_id": "t2", "auto_aprobar": False})
    assert r.json()["pendiente_hitl"] and not r.json()["done"]
    assert client.get("/threads/t2/messages").json() == []

    r = client.post("/approve", json={"thread_id": "t2", "aprobado": True})
    assert r.status_code == 200
    assert r.json()["done"] and not r.json()["pendiente_hitl"]
    msgs = client.get("/threads/t2/messages").json()
    assert [(m["role"], m["content"]) for m in msgs] == [("user", "¿Precio piscina?"), ("assistant", "Plan aprobado.")]


def test_approve_rechazar_cierra_y_guarda(client):
    client.post("/ask", json={"pregunta": "¿Precio piscina?", "thread_id": "t3", "auto_aprobar": False})
    r = client.post("/approve", json={"thread_id": "t3", "aprobado": False})
    assert r.status_code == 200
    assert not r.json()["done"] and not r.json()["pendiente_hitl"]
    assert client.get("/threads/t3/messages").json()[-1]["content"] == "Plan rechazado."


def test_ask_sin_plan_se_guarda(client, monkeypatch):
    sin_plan = lambda mensaje, thread_id: _resultado_falso(
        thread_id, respuesta="No tengo información sobre eso.", plan=[], pendiente_hitl=False)
    monkeypatch.setattr(api, "procesar_turno", sin_plan)
    r = client.post("/ask", json={"pregunta": "¿Torneo de ajedrez?", "thread_id": "t4"})
    assert not r.json()["done"] and not r.json()["pendiente_hitl"]
    assert [m["role"] for m in client.get("/threads/t4/messages").json()] == ["user", "assistant"]


def test_ask_con_error_no_se_guarda(client, monkeypatch):
    con_error = lambda mensaje, thread_id: _resultado_falso(
        thread_id, respuesta="", pendiente_hitl=False, error="Límite de turnos alcanzado.")
    monkeypatch.setattr(api, "procesar_turno", con_error)
    r = client.post("/ask", json={"pregunta": "¿Precio piscina?", "thread_id": "t5"})
    assert r.status_code == 200
    assert r.json()["error"] == "Límite de turnos alcanzado."
    assert client.get("/threads/t5/messages").json() == []


def test_approve_sin_sesion_404(client):
    r = client.post("/approve", json={"thread_id": "nunca-visto", "aprobado": True})
    assert r.status_code == 404


def test_approve_sin_plan_pendiente_400(client):
    client.post("/ask", json={"pregunta": "¿Precio piscina?", "thread_id": "t6"})
    r = client.post("/approve", json={"thread_id": "t6", "aprobado": True})
    assert r.status_code == 400
    assert len(client.get("/threads/t6/messages").json()) == 2


def test_sin_clave_o_clave_incorrecta_401(client):
    with TestClient(api.app) as sin_clave:
        assert sin_clave.post("/ask", json={"pregunta": "Hola", "thread_id": "t8"}).status_code == 401
        assert sin_clave.post("/approve", json={"thread_id": "t8", "aprobado": True}).status_code == 401
        assert sin_clave.get("/threads/t8/messages").status_code == 401
    assert client.get("/threads/t8/messages", params={"api_key": "otra"}).status_code == 401


def test_servidor_sin_api_key_503(client, monkeypatch):
    monkeypatch.setattr(config, "API_KEY", "")
    assert client.get("/threads/t9/messages").status_code == 503


def test_rate_limit_429(client, monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MINUTE", 3)
    codigos = [client.get("/threads/t10/messages").status_code for _ in range(4)]
    assert codigos == [200, 200, 200, 429]


def test_rate_limit_no_cuenta_peticiones_sin_clave(client, monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MINUTE", 1)
    assert client.get("/threads/t11/messages", params={"api_key": "otra"}).status_code == 401
    assert client.get("/threads/t11/messages").status_code == 200


def test_health_y_docs_sin_clave(client):
    with TestClient(api.app) as sin_clave:
        assert sin_clave.get("/health").status_code == 200
        assert sin_clave.get("/docs").status_code == 200


def test_body_invalido_422(client):
    assert client.post("/ask", json={"thread_id": "t7"}).status_code == 422
    assert client.post("/approve", json={"thread_id": "t7"}).status_code == 422


def test_dos_hilos_no_se_mezclan(client):
    client.post("/ask", json={"pregunta": "A", "thread_id": "a"})
    client.post("/ask", json={"pregunta": "B", "thread_id": "b"})
    assert [m["content"] for m in client.get("/threads/a/messages").json()][0] == "A"
    assert [m["content"] for m in client.get("/threads/b/messages").json()][0] == "B"
    assert client.get("/threads/c/messages").json() == []


@pytest.mark.parametrize("entrada, salida", [
    ("postgres://u:p@h:5432/db", "postgresql+psycopg://u:p@h:5432/db"),
    ("postgresql://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
    ("postgresql+psycopg://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
    ("", ""),
])
def test_normalizar_database_url(entrada, salida):
    assert normalizar_database_url(entrada) == salida

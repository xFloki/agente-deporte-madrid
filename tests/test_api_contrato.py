"""Tests del contrato HTTP del PB3: rutas, schemas e historial.

Sin red, sin Gemini y sin Postgres: el agente es falso (siempre propone un plan) y el historial va a SQLite en memoria.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

import app as api
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
    with TestClient(api.app) as c:
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


def test_ask_sin_auto_aprobar_queda_pendiente_y_approve_decide(client):
    r = client.post("/ask", json={"pregunta": "¿Precio piscina?", "thread_id": "t2", "auto_aprobar": False})
    assert r.json()["pendiente_hitl"] and not r.json()["done"]
    r = client.post("/approve", json={"thread_id": "t2", "aprobado": False})
    assert r.status_code == 200
    assert not r.json()["pendiente_hitl"] and not r.json()["done"]


def test_body_invalido_422(client):
    assert client.post("/ask", json={"thread_id": "t3"}).status_code == 422
    assert client.post("/approve", json={"thread_id": "t3"}).status_code == 422


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

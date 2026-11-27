"""Tests del historial contra PostgreSQL de verdad (bloque B).

Necesitan el Postgres local en marcha (docker start pg-deporte) y DATABASE_URL en el .env.
Si no hay Postgres (por ejemplo, en el CI de GitHub), se saltan en lugar de fallar.
"""

import uuid

import pytest
from sqlalchemy import text
from sqlmodel import Session, select

import config
from src import db
from src.models import Conversation, Message


def _postgres_disponible() -> bool:
    """¿Hay un Postgres respondiendo? Como mucho espera 2 s (si no, el CI y Windows se quedan colgados)."""
    if not config.DATABASE_URL.startswith("postgresql"):
        return False
    from sqlalchemy import create_engine

    prueba = create_engine(config.DATABASE_URL, connect_args={"connect_timeout": 2})
    try:
        with prueba.connect() as conexion:
            conexion.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        return False
    finally:
        prueba.dispose()

pytestmark = pytest.mark.skipif(not _postgres_disponible(),
                                reason="sin PostgreSQL local (docker start pg-deporte)")


@pytest.fixture
def hilos():
    """Da thread_id únicos a cada test y, al acabar, borra sus filas (la base queda como estaba)."""
    db.ensure_schema()
    creados: list[str] = []

    def nuevo() -> str:
        thread_id = f"test-{uuid.uuid4().hex[:8]}"
        creados.append(thread_id)
        return thread_id

    yield nuevo

    with Session(db.get_engine()) as session:
        for thread_id in creados:
            for mensaje in session.exec(select(Message).where(Message.thread_id == thread_id)).all():
                session.delete(mensaje)
            session.flush()  # primero los mensajes: dependen de la conversación (clave foránea)
            conversacion = session.get(Conversation, thread_id)
            if conversacion:
                session.delete(conversacion)
        session.commit()


def test_storage_mode_es_postgres():
    assert db.storage_mode() == "postgres"


def test_turno_guarda_user_y_assistant_en_orden(hilos):
    thread_id = hilos()
    db.save_turn(thread_id, "¿Precio piscina?", "La entrada cuesta 4,50 €.")
    mensajes = db.list_messages(thread_id)
    assert [(m["role"], m["content"]) for m in mensajes] == [
        ("user", "¿Precio piscina?"),
        ("assistant", "La entrada cuesta 4,50 €."),
    ]
    assert all(m["created_at"].tzinfo is not None for m in mensajes)  # hora con zona (UTC)


def test_varios_turnos_del_mismo_hilo_en_orden(hilos):
    thread_id = hilos()
    db.save_turn(thread_id, "P1", "R1")
    db.save_turn(thread_id, "P2", "R2")
    assert [m["content"] for m in db.list_messages(thread_id)] == ["P1", "R1", "P2", "R2"]


def test_dos_hilos_no_se_mezclan(hilos):
    a, b = hilos(), hilos()
    db.save_turn(a, "pregunta A", "respuesta A")
    db.save_turn(b, "pregunta B", "respuesta B")
    assert [m["content"] for m in db.list_messages(a)] == ["pregunta A", "respuesta A"]
    assert [m["content"] for m in db.list_messages(b)] == ["pregunta B", "respuesta B"]


def test_hilo_desconocido_devuelve_lista_vacia(hilos):
    assert db.list_messages(hilos()) == []


def test_historial_sobrevive_a_un_reinicio(hilos, monkeypatch):
    thread_id = hilos()
    db.save_turn(thread_id, "antes", "del reinicio")
    db.get_engine().dispose()                  # cierra todas las conexiones
    monkeypatch.setattr(db, "_engine", None)   # como un proceso nuevo: conexión desde cero
    assert [m["content"] for m in db.list_messages(thread_id)] == ["antes", "del reinicio"]

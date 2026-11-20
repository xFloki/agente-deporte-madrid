"""Tests del front (front/streamlit_app.py): habla solo HTTP con la API.

Sin red y sin API: AppTest ejecuta el front y una API falsa sustituye a las funciones de front/api_cliente.py.
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

FRONT = Path(__file__).resolve().parents[1] / "front"
APP = str(FRONT / "streamlit_app.py")


class APIFalsa:
    """Imita el contrato: /ask deja el plan pendiente y /approve cierra el turno y lo guarda."""

    def __init__(self):
        self.historial: dict[str, list[dict]] = {}
        self.pendientes: dict[str, str] = {}
        self.llamadas: list[str] = []

    def health(self):
        self.llamadas.append("health")
        return {"status": "ok", "storage": "postgres"}

    def ask(self, pregunta, thread_id):
        self.llamadas.append("ask")
        self.pendientes[thread_id] = pregunta
        return {"respuesta": "La entrada cuesta 4,5 €.", "thread_id": thread_id, "done": False,
                "pendiente_hitl": True, "plan": ["Consultar la tarifa oficial."], "error": None}

    def approve(self, thread_id, aprobado):
        self.llamadas.append("approve")
        pregunta = self.pendientes.pop(thread_id)
        respuesta = "Plan aprobado." if aprobado else "Plan rechazado."
        ahora = datetime.now(timezone.utc).isoformat()
        self.historial.setdefault(thread_id, []).extend([
            {"role": "user", "content": pregunta, "created_at": ahora},
            {"role": "assistant", "content": respuesta, "created_at": ahora},
        ])
        return {"respuesta": respuesta, "thread_id": thread_id, "done": aprobado,
                "pendiente_hitl": False, "plan": [], "error": None}

    def messages(self, thread_id):
        self.llamadas.append("messages")
        return list(self.historial.get(thread_id, []))


@pytest.fixture
def api_falsa(monkeypatch):
    monkeypatch.syspath_prepend(str(FRONT))
    import api_cliente

    falsa = APIFalsa()
    for nombre in ("health", "ask", "approve", "messages"):
        monkeypatch.setattr(api_cliente, nombre, getattr(falsa, nombre))
    return falsa


def _botones(at: AppTest) -> list[str]:
    return [b.label for b in at.sidebar.button]


def _preguntar(texto: str) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.chat_input[0].set_value(texto).run()
    assert not at.exception
    return at


def test_health_en_la_barra_lateral(api_falsa):
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert "postgres" in at.sidebar.success[0].value
    assert at.session_state["thread_id"]


def test_aprobar_cierra_el_turno_y_el_historial_sale_de_la_api(api_falsa):
    at = _preguntar("¿Cuánto cuesta la piscina?")
    assert at.session_state["pendiente"]["plan"] == ["Consultar la tarifa oficial."]
    assert {"Aprobar", "Rechazar"} <= set(_botones(at))

    at.sidebar.button[_botones(at).index("Aprobar")].click().run()

    assert "Aprobar" not in _botones(at)
    assert [m["content"] for m in at.session_state["historial"]] == ["¿Cuánto cuesta la piscina?", "Plan aprobado."]
    assert api_falsa.llamadas[-2:] == ["approve", "messages"]


def test_rechazar_deja_seguir_en_el_mismo_hilo(api_falsa):
    at = _preguntar("¿Cuánto cuesta la piscina?")
    thread_id = at.session_state["thread_id"]

    at.sidebar.button[_botones(at).index("Rechazar")].click().run()

    assert at.session_state["pendiente"] is None
    assert at.session_state["historial"][-1]["content"] == "Plan rechazado."
    at.chat_input[0].set_value("¿Y para jubilados?").run()
    assert at.session_state["thread_id"] == thread_id


def test_nueva_conversacion_cambia_el_thread_id(api_falsa):
    at = _preguntar("¿Cuánto cuesta la piscina?")
    antes = at.session_state["thread_id"]

    at.sidebar.button[_botones(at).index("Nueva conversación")].click().run()

    assert at.session_state["thread_id"] != antes
    assert at.session_state["pendiente"] is None and at.session_state["historial"] == []


def test_error_de_la_api_se_ve_en_pantalla(api_falsa, monkeypatch):
    import api_cliente

    def ask_sin_clave(pregunta, thread_id):
        raise api_cliente.ErrorAPI(api_cliente.MENSAJES[401], 401)

    monkeypatch.setattr(api_cliente, "ask", ask_sin_clave)
    at = _preguntar("¿Cuánto cuesta la piscina?")
    assert any("API_KEY" in e.value for e in at.error)


def test_el_front_no_importa_el_agente():
    for fichero in FRONT.glob("*.py"):
        codigo = fichero.read_text(encoding="utf-8")
        assert "import src" not in codigo and "from src" not in codigo, fichero.name
        assert "import config" not in codigo and "from config" not in codigo, fichero.name


class _Respuesta:
    def __init__(self, status, datos=None):
        self.status_code = status
        self._datos = datos or {}

    def json(self):
        return self._datos


@pytest.mark.parametrize("status", [401, 429, 504])
def test_cliente_traduce_los_codigos_de_error(monkeypatch, status):
    monkeypatch.syspath_prepend(str(FRONT))
    import api_cliente

    monkeypatch.setattr(api_cliente.requests, "request", lambda *a, **k: _Respuesta(status))
    with pytest.raises(api_cliente.ErrorAPI) as e:
        api_cliente.ask("hola", "t1")
    assert e.value.status == status
    assert str(e.value) == api_cliente.MENSAJES[status]


def test_cliente_manda_la_clave_solo_en_rutas_protegidas(monkeypatch):
    monkeypatch.syspath_prepend(str(FRONT))
    import api_cliente

    vistas = []

    def request(metodo, url, params=None, json=None, timeout=None):
        vistas.append((url, params))
        return _Respuesta(200, {"status": "ok", "storage": "postgres"})

    monkeypatch.setattr(api_cliente.requests, "request", request)
    monkeypatch.setattr(api_cliente, "API_KEY", "clave-de-prueba")
    api_cliente.health()
    api_cliente.messages("t 1")
    assert vistas[0][1] is None
    assert vistas[1] == (f"{api_cliente.API_BASE_URL}/threads/t%201/messages", {"api_key": "clave-de-prueba"})

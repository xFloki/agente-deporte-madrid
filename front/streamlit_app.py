"""Front del agente (PB3): cliente HTTP de la API. No importa el grafo ni ejecuta tools.

  streamlit run front/streamlit_app.py

Lee API_BASE_URL y API_KEY del .env. En la demo final, API_BASE_URL es la URL de Render.
"""

import streamlit as st

import api_cliente as api

st.set_page_config(page_title="Agente · Deporte municipal", page_icon="🏊", layout="centered")

SALUDO = (
    "Hola. Soy un **agente multiagente** del deporte municipal de Madrid: "
    "tarifas, abonos, normas, instalaciones y actividades. "
    "Cuando prepare un plan, podrás aprobarlo o rechazarlo antes de cerrarlo."
)


def _recargar_historial() -> None:
    """Pide a la API el historial del hilo (sale de Postgres, no de una lista del front)."""
    try:
        st.session_state.historial = api.messages(st.session_state.thread_id)
    except api.ErrorAPI as e:
        st.session_state.error = str(e)


def _comprobar_servicio() -> None:
    try:
        st.session_state.salud = api.health()
    except api.ErrorAPI as e:
        st.session_state.salud = {"error": str(e)}


def _reset() -> None:
    """Conversación nueva: otro thread_id, sin plan pendiente y sin historial."""
    st.session_state.thread_id = api.nuevo_thread_id()
    st.session_state.historial = []
    st.session_state.pendiente = None   # turno esperando Aprobar / Rechazar
    st.session_state.ultimo = None      # último turno, para el panel de debug
    st.session_state.error = None


def _abrir(thread_id: str) -> None:
    """Retoma una conversación ya guardada (por ejemplo, después de recargar la página o un redeploy)."""
    _reset()
    st.session_state.thread_id = thread_id
    _recargar_historial()


def _texto(respuesta: str, plan: list[str], pendiente: bool) -> str:
    """Respuesta del agente + plan en viñetas (si lo hay)."""
    texto = respuesta or "(Sin respuesta)"
    if plan:
        etiqueta = "Plan (pendiente de aprobación)" if pendiente else "Plan"
        texto += f"\n\n**{etiqueta}:**\n" + "\n".join(f"- {p}" for p in plan)
    return texto


def _preguntar(pregunta: str) -> None:
    st.session_state.error = None
    try:
        resultado = api.ask(pregunta, st.session_state.thread_id)
    except api.ErrorAPI as e:
        st.session_state.error = str(e)
        return
    st.session_state.ultimo = {"pregunta": pregunta, **resultado}
    if resultado.get("pendiente_hitl"):
        st.session_state.pendiente = st.session_state.ultimo
    _recargar_historial()


def _decidir(aprobado: bool) -> None:
    """HITL: la persona aprueba o rechaza el plan; la API cierra el turno."""
    st.session_state.error = None
    pendiente = st.session_state.pendiente
    try:
        resultado = api.approve(st.session_state.thread_id, aprobado)
    except api.ErrorAPI as e:
        st.session_state.error = str(e)
        return
    st.session_state.pendiente = None
    st.session_state.ultimo = {"pregunta": pendiente["pregunta"] if pendiente else "", **resultado}
    _recargar_historial()


if "thread_id" not in st.session_state:
    _reset()
    _comprobar_servicio()

with st.sidebar:
    st.subheader("Servicio")
    salud = st.session_state.salud
    if "error" in salud:
        st.error(salud["error"])
    else:
        st.success(f"API activa · historial en **{salud.get('storage', '?')}**")
    st.caption(f"API: `{api.API_BASE_URL}`")
    if st.button("Comprobar servicio", use_container_width=True):
        _comprobar_servicio()
        st.rerun()

    st.divider()
    st.caption(f"thread_id: `{st.session_state.thread_id}`")
    if st.button("Recargar historial", use_container_width=True,
                 help="Vuelve a pedir el historial a la API (sale de PostgreSQL)."):
        st.session_state.error = None
        _recargar_historial()
        st.rerun()
    with st.expander("Abrir una conversación"):
        otro = st.text_input("thread_id", key="abrir_thread_id", placeholder="p. ej. prueba-davide-1")
        if st.button("Abrir", use_container_width=True) and otro.strip():
            _abrir(otro.strip())
            st.rerun()

    pendiente = st.session_state.pendiente
    if pendiente:
        st.divider()
        st.subheader("HITL — aprobar plan")
        for item in pendiente.get("plan") or []:
            st.markdown(f"- {item}")
        c1, c2 = st.columns(2)
        if c1.button("Aprobar", use_container_width=True, type="primary"):
            _decidir(True)
            st.rerun()
        if c2.button("Rechazar", use_container_width=True):
            _decidir(False)
            st.rerun()

    st.divider()
    if st.button("Nueva conversación", use_container_width=True):
        _reset()
        st.rerun()

st.title("Asistente de Deporte Municipal")
st.caption("Front Streamlit → API FastAPI (agente PB2 + RAG) → PostgreSQL")

with st.chat_message("assistant"):
    st.markdown(SALUDO)

# Historial guardado en la API (GET /threads/{thread_id}/messages)
for m in st.session_state.historial:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# Último turno que la API no ha guardado (p. ej. una abstención, que no cierra con plan)
ultimo = st.session_state.ultimo
guardadas = {m["content"] for m in st.session_state.historial}
if ultimo and not st.session_state.pendiente and ultimo.get("respuesta") not in guardadas and ultimo.get("pregunta"):
    with st.chat_message("user"):
        st.markdown(ultimo["pregunta"])
    with st.chat_message("assistant"):
        st.markdown(_texto(ultimo.get("respuesta", ""), ultimo.get("plan") or [], False))
        st.caption("Este turno no queda en el historial: la API solo guarda los turnos cerrados.")

# Turno con plan pendiente: aún no está en el historial
pendiente = st.session_state.pendiente
if pendiente:
    with st.chat_message("user"):
        st.markdown(pendiente["pregunta"])
    with st.chat_message("assistant"):
        st.markdown(_texto(pendiente.get("respuesta", ""), pendiente.get("plan") or [], True))
    st.warning("Plan pendiente de aprobación: usa los botones de la barra lateral.")

if st.session_state.error:
    st.error(st.session_state.error)

if prompt := st.chat_input("Tu pregunta sobre deporte municipal...", disabled=bool(pendiente)):
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Consultando a los especialistas..."):
            _preguntar(prompt)
    st.rerun()

with st.expander("Respuesta de la API (debug)"):
    st.json({"thread_id": st.session_state.thread_id, "health": st.session_state.salud, "ultimo": st.session_state.ultimo})

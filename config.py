"""Configuración central del agente (límites, modelo, rutas).

Las rutas se calculan desde este fichero, así el proyecto funciona
lo lances desde donde lo lances (python main.py, streamlit run app.py, tests).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# --- LLM ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-3.1-flash-lite")
TEMPERATURE = 0.0

# --- Límites duros (los aplica Python, nunca el LLM) ---
MAX_ITER = 6     # pasos máximos del supervisor por turno
MAX_STEPS = 3    # llamadas a tools máximas por especialista y turno
MAX_TURNS = 10   # turnos de usuario por conversación (thread_id)

# --- Mocks (USE_MOCKS=1 en .env → tools falsas, sin red ni Gemini en las tools) ---
USE_MOCKS = os.getenv("USE_MOCKS", "0") == "1"

# --- API (PB3). Las variables de entorno solo se leen en este fichero ---
def normalizar_database_url(url: str) -> str:
    """Render da «postgres://…»; SQLAlchemy con psycopg 3 quiere «postgresql+psycopg://…»."""
    for prefijo in ("postgres://", "postgresql://"):
        if url.startswith(prefijo):
            return "postgresql+psycopg://" + url[len(prefijo):]
    return url


DATABASE_URL = normalizar_database_url(os.getenv("DATABASE_URL", ""))
API_KEY = os.getenv("API_KEY", "")               # vacía → las rutas protegidas devuelven 503
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:8501").split(",") if o.strip()]
ASK_TIMEOUT_SECONDS = float(os.getenv("ASK_TIMEOUT_SECONDS", "300"))
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))

# --- Rutas ---
DATA_DIR = BASE_DIR / "data"
ASSETS_DIR = BASE_DIR / "assets"
SALIDAS_DIR = BASE_DIR / "salidas"          # fichas generadas al aprobar (no se versiona)
IMAGEN_DEMO = ASSETS_DIR / "imagen_demo.jpg"
FALLBACK_API = DATA_DIR / "fallback_api.json"

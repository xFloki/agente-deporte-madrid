# Imagen de la API del agente (FastAPI + agente del PB2 + RAG), la misma en local y en Render.
#   docker build -t agente-deporte .
#   docker run --rm -p 8000:8000 --env-file .env agente-deporte

FROM python:3.12-slim

# Logs sin búfer (se ven al momento en Render), sin ficheros .pyc y sin caché de pip (imagen más ligera)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 1) torch solo CPU: la versión por defecto trae CUDA y pesa varios GB que aquí no se usan
RUN pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu

# 2) Dependencias en una capa aparte: si requirements.txt no cambia, Docker la reutiliza y el build es rápido
COPY requirements.txt .
RUN pip install -r requirements.txt

# 3) Índice del RAG en su propia capa: solo se rehace si cambia rag/ (código o corpus).
#    Descarga el modelo de embeddings y construye Chroma. No llama a Gemini: no necesita claves.
COPY rag/ rag/
RUN python -m rag --index

# A partir de aquí el modelo ya está en la imagen: que no intente descargarlo al arrancar
ENV HF_HUB_OFFLINE=1

# 4) El resto del código (API, agente, tools, imagen demo). Cambiarlo ya no reconstruye el índice.
COPY . .

# A partir de aquí el modelo ya está en la imagen: que no intente descargarlo al arrancar
ENV HF_HUB_OFFLINE=1

EXPOSE 8000

# sh -c para que se expanda ${PORT} (Render lo inyecta; en local, 8000) y exec para que uvicorn
# reciba las señales de parada (redeploy). --no-access-log: la api_key va en la URL y el log de accesos la escribiría.
CMD ["sh", "-c", "exec uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000} --no-access-log"]

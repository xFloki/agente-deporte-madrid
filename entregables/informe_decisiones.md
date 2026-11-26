# Informe de decisiones — Project Break 3 (MLOps)

El agente del PB2 (multiagente LangGraph + RAG del PB1 sobre el deporte municipal de Madrid), publicado como servicio:
API FastAPI con Swagger, historial en PostgreSQL, una imagen Docker desplegada en Render y un front Streamlit que habla con la URL pública.

**URL del servicio:** _pendiente_

| Apartado | Responsable |
|---|---|
| 1. Sistema desplegado | Davide |
| 2. Contrato | Alex |
| 3. Datos | María |
| 4. Prueba de vida | Davide |
| 5. Arquitectura y coste | Entre todos |
| 6. CI/CD | Entre todos |
| 7. Tres fallos | Uno cada uno |

---

## 1. Sistema desplegado

<!-- Dibujo del sistema: front local, Web Service en Render (API + agente + RAG), PostgreSQL de Render y Gemini. -->

_Pendiente._

## 2. Contrato: qué es público y qué lleva `api_key`

<!-- Rutas públicas (/health, /docs) y protegidas (/ask, /approve, /threads/{id}/messages); 401, 422, 429, 503 y 504. -->

_Pendiente._

## 3. Datos: qué hay en Postgres y qué se pierde al reiniciar

### Qué guardamos en PostgreSQL

El historial de los turnos cerrados, con SQLModel (`src/models.py` y `src/db.py`). Las tablas se crean al arrancar la API.

| Tabla | Columnas | Contenido |
|---|---|---|
| `conversation` | `id` (= `thread_id`), `created_at` | Una fila por conversación |
| `message` | `id` autoincremental, `thread_id` → `conversation.id`, `role`, `content`, `created_at` (UTC) | Dos filas por turno: la pregunta (`user`) y la respuesta (`assistant`) |

- **Qué es un turno cerrado:** aprobado, rechazado o sin plan. Un turno con el plan pendiente se guarda cuando se decide en `/approve`; si el agente devuelve `error`, no se guarda nada.
- **Una transacción por turno:** se guardan los dos mensajes o ninguno.
- **Orden por `id`, no por fecha:** la pregunta y la respuesta se guardan a la vez y pueden tener el mismo `created_at`.
- **Conexión:** `DATABASE_URL` sale del entorno (`.env` en local y panel de Render en la nube). `config.py` convierte el `postgres://` que da Render en `postgresql+psycopg://`. En local usamos un contenedor `postgres:16` con volumen; en Render, el Postgres gestionado.

### Qué vive solo en la memoria del proceso

- **El estado del grafo** (`MemorySaver`, por `thread_id`) y **los planes pendientes de aprobar** que guarda la API. Si el servicio se reinicia o se redespliega con un plan pendiente, ese plan se pierde: `/approve` devuelve 404 y hay que repetir la pregunta. **El historial de los turnos cerrados no se pierde.** Llevar el checkpoint de LangGraph a Postgres queda fuera del alcance del enunciado.
- **El archivo del plan aprobado** (`salidas/plan_….md`) se escribe en el disco del contenedor. Lo comprobamos en local: se crea dentro del contenedor y desaparece al pararlo. En Render pasa lo mismo en cada redeploy (ver apartado 7).

### Cómo lo hemos comprobado

- **Tests contra Postgres real** (`tests/test_db_postgres.py`): orden de los mensajes, dos `thread_id` que no se mezclan, y el historial tras cerrar todas las conexiones y abrir una nueva (como un proceso recién arrancado). Se saltan si Postgres no responde en 2 s, para no bloquear el CI. Los tests de las rutas usan una base de prueba en memoria; el servicio usa siempre Postgres.
- **Reinicio de la API en local:** un turno guardado desde uvicorn sigue ahí después de reiniciarlo, y el contenedor Docker lee los mismos mensajes del mismo Postgres.
- **Desde el front:** turno, reinicio de la API, «Recargar historial» y «Abrir una conversación» → el turno reaparece.
- **En la URL pública:** ver apartado 4.

### Una decisión que salió de un fallo real

Sin límite de espera, con Postgres caído, la conexión se quedó colgada **3 min 26 s** sin dar error. Con `connect_timeout=10` falla en **unos 22 s** (un intento por IPv6 y otro por IPv4) con un error claro, en vez de dejar la API colgada.

## 4. Prueba de vida

<!-- Turno en la URL pública, redeploy, y GET …/messages sigue devolviéndolo. Pegar la URL que se envía al profesorado. -->

_Pendiente._

## 5. Conclusiones de arquitectura y coste

### Piezas y por qué la API va en un solo contenedor

_Pendiente._

### Un límite que hemos notado de verdad

_Pendiente._

### Escalado

<!-- Primer paso si hubiera más usuarios (subir plan) y qué no montamos (varias réplicas, colas). -->

_Pendiente._

### Dos facturas: infraestructura y tokens

<!-- Orden de magnitud: web + Postgres en Render, y tokens de un /ask. -->

_Pendiente._

## 6. Conclusiones de CI/CD

### Qué comprobaríamos antes de cada deploy

<!-- Un test que no llama al LLM y un docker build. -->

_Pendiente._

### Dónde están los secretos

_Pendiente._

### Cómo desplegamos y qué es un rollback

_Pendiente._

### Qué separa desarrollo de producción

_Pendiente._

## 7. Tres fallos y qué haríamos después

_Pendiente._

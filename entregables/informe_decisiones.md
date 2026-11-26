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

_Pendiente._

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

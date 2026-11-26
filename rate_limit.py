"""Rate limit en memoria: como mucho RATE_LIMIT_PER_MINUTE peticiones por api_key cada 60 segundos."""

import logging
import time
from collections import defaultdict, deque

from fastapi import HTTPException

import config

logger = logging.getLogger(__name__)

VENTANA_SEGUNDOS = 60.0
_peticiones: dict[str, deque[float]] = defaultdict(deque)


def check_rate_limit(api_key: str) -> None:
    """429 si esta clave ya ha hecho RATE_LIMIT_PER_MINUTE peticiones en los últimos 60 s."""
    ahora = time.monotonic()
    cola = _peticiones[api_key]
    while cola and ahora - cola[0] > VENTANA_SEGUNDOS:
        cola.popleft()

    if len(cola) >= config.RATE_LIMIT_PER_MINUTE:
        logger.warning("rate limit 429: más de %s peticiones en 60 s", config.RATE_LIMIT_PER_MINUTE)
        raise HTTPException(status_code=429, detail="Demasiadas peticiones; espera un minuto.")
    cola.append(ahora)

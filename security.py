"""Seguridad de la API: comprobar la api_key de la query y el rate limit antes de entrar en una ruta protegida.

Las rutas la usan con dependencies=[Depends(require_api_key)].
"""

import logging

from fastapi import HTTPException, Query

import config
from rate_limit import check_rate_limit

logger = logging.getLogger(__name__)


def require_api_key(
    api_key: str | None = Query(None, description="Clave de acceso a la API (la misma que API_KEY en el servidor)."),
) -> str:
    """503 si el servidor no tiene API_KEY; 401 si la clave falta o no coincide; 429 si pasa del rate limit."""
    if not config.API_KEY:
        logger.error("auth 503: API_KEY no configurada en el servidor")
        raise HTTPException(status_code=503, detail="API_KEY no configurada en el servidor.")
    if not api_key or api_key != config.API_KEY:
        logger.warning("auth 401: api_key ausente o inválida")
        raise HTTPException(status_code=401, detail="API key inválida o ausente.")
    check_rate_limit(api_key)
    return api_key

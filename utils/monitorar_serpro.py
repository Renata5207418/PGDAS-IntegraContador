from __future__ import annotations
import os
import time
import logging
import requests
from dotenv import load_dotenv
from typing import Dict, Any, Tuple
from utils.uploader_serpro import SerproClient

load_dotenv()

_URL_BASE = os.getenv("URL_BASE", "").rstrip("/")
_ENDPOINT = f"{_URL_BASE}/Monitorar"
_POLL_SEC = 4

client = SerproClient()


def _envelope(pedido_id: str) -> Dict[str, Any]:
    return {"idPedidoDados": pedido_id}


def monitorar_pedido(pedido_id: str, *, timeout: Tuple[int, int] = (10, 30), max_min: int = 3) -> Dict[str, Any]:
    """
    Faz polling em /Monitorar até o pedido sair de PROCESSANDO ou EM_FILA
    ou até max_min minutos.
    """
    deadline = time.time() + 60 * max_min

    while True:
        # monta headers (inclui Bearer, jwt e X-Api-Key)
        headers = client.build_headers("pgdas")

        # dispara /Monitorar
        r = requests.post(
            _ENDPOINT,
            headers=headers,
            json=_envelope(pedido_id),
            timeout=timeout
        )

        try:
            body = r.json()
        except ValueError:
            body = r.text

        logging.info("Monitorar %s → HTTP %s", pedido_id, r.status_code)

        # terminou?
        if r.status_code == 200 \
           and isinstance(body, dict) \
           and body.get("situacao") not in ("PROCESSANDO", "EM_FILA"):
            return body

        if time.time() >= deadline:
            raise RuntimeError("Monitorar: tempo máximo excedido")

        time.sleep(_POLL_SEC)

from __future__ import annotations
import os
import json
import time
import logging
import requests
from dotenv import load_dotenv
from typing import Dict, Any, Tuple
from auth.token_auth import TokenAutenticacao
from utils.uploader_serpro import _cabecalhos

load_dotenv()

_URL_BASE = os.getenv("URL_BASE", "").rstrip("/")
_API_KEY = os.getenv("API_KEY_SERPRO")
_ENDPOINT = f"{_URL_BASE}/Monitorar"
_POLL_SEC = 4


def _envelope(pedido_id: str) -> Dict[str, Any]:
    """
    Payload mínimo exigido pela rota /Monitorar do Integra-SN.
    """
    return {"idPedidoDados": pedido_id}


# --------------------------------------------------------------------------- #
def monitorar_pedido(pedido_id: str, tok: TokenAutenticacao, *, timeout: Tuple[int, int] = (10, 30), max_min: int = 3) -> Dict[str, Any]:
    """
    Faz **polling** em `/Monitorar` até o pedido sair de *PROCESSANDO* / *EM_FILA*
    ou até `max_min` minutos.
    """
    limite = time.time() + 60 * max_min

    while True:
        # 1) garante tokens válidos
        access, jwt = tok.obter_token()
        # 2) dispara /Monitorar
        r = requests.post(
                _ENDPOINT,
                headers=_cabecalhos(access, jwt) | {"X-Api-Key": _API_KEY},
                data=json.dumps(_envelope(pedido_id), ensure_ascii=False).encode(),
                timeout=timeout
            )

        try:
            body = r.json()
        except ValueError:
            body = r.text
        logging.info("Monitorar %s → HTTP %s", pedido_id, r.status_code)

        # 3) terminou?
        if r.status_code == 200 and body.get("situacao") not in ("PROCESSANDO", "EM_FILA"):
            return body

        if time.time() >= limite:
            raise RuntimeError("Monitorar: tempo máximo excedido")

        time.sleep(_POLL_SEC)

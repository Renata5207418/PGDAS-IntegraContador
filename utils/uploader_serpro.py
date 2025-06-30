from __future__ import annotations
import os
import json
import logging
import time
import requests
from typing import Dict, Any, Tuple

_URL_BASE = os.getenv("URL_BASE").rstrip("/")
_API_KEY = os.getenv("API_KEY_SERPRO")
_CNPJ_CONT = os.getenv("CNPJ_CONT")
_TIPO_DOC = 2
_ENDPOINT = f"{_URL_BASE}/Declarar"
_DEFAULT_TO = int(os.getenv("SERPRO_READ_TIMEOUT", 60))


# --------------------------------------------------------------------------
def _cabecalhos(access: str, jwt: str) -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Api-Key": _API_KEY,
        "Authorization": f"Bearer {access}",
        "jwt_token": jwt,
        "Role-Type": "TERCEIROS",
    }


def _envelope(dados: Dict[str, Any]) -> Dict[str, Any]:
    parte = {"numero": _CNPJ_CONT, "tipo": _TIPO_DOC}
    return {
        "contratante":      parte,
        "autorPedidoDados": parte,
        "contribuinte":     {"numero": dados["cnpjCompleto"], "tipo": _TIPO_DOC},
        "pedidoDados": {
            "idSistema": "PGDASD",
            "idServico": "TRANSDECLARACAO11",
            "versaoSistema": "1.0",
            "dados": json.dumps(dados, ensure_ascii=False),
        },
    }


# --------------------------------------------------------------------------
def enviar(payload_fiscal: Dict[str, Any], access_token: str, jwt_token: str, timeout: Tuple[int, int] | None = None, retries: int = 2) -> Dict[str, Any]:
    """
    POST /Declarar.  Devolve {"status": http, "body": json|texto}.
    * 2xx → sucesso imediato
    * 4xx → falha imediata (não reenvia)
    * 5xx ou erro de rede → faz até `retries` tentativas e,
      se esgotar, levanta RuntimeError("Falha persistente…", último_resp).
    """
    if timeout is None:
        timeout = (10, _DEFAULT_TO)

    data = json.dumps(_envelope(payload_fiscal), ensure_ascii=False).encode()
    ultimo_resp: Dict[str, Any] = {"status": None, "body": "nenhuma resposta"}

    for tent in range(1, retries + 2):
        try:
            r = requests.post(_ENDPOINT, headers=_cabecalhos(access_token, jwt_token),
                              data=data, timeout=timeout)
            try:
                body = r.json()
            except ValueError:
                body = r.text

            status = r.status_code
            resp = {"status": status, "body": body}

            if 200 <= status < 300 or 400 <= status < 500:
                return resp

            ultimo_resp = resp
            logging.warning("SERPRO %s (tent %s/%s) – body: %s",
                            status, tent, retries + 1, body)

        except requests.RequestException as exc:
            ultimo_resp = {"status": None, "body": str(exc)}
            logging.error("erro rede %s tent %s/%s", exc, tent, retries + 1)

        if tent <= retries:
            time.sleep(2 * tent)

    raise RuntimeError("Falha persistente ao chamar SERPRO", ultimo_resp)

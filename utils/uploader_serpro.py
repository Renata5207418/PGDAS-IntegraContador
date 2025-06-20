from __future__ import annotations
from typing import Dict, Any, Tuple
import os
import json
import logging
import time
import requests

_URL_BASE = os.getenv("URL_BASE").rstrip("/")
_API_KEY = os.getenv("API_KEY_SERPRO")
_CNPJ_CONT = os.getenv("CNPJ_CONT")
_TIPO_DOC = 2
_ENDPOINT = f"{_URL_BASE}/Declarar"


def _cabecalhos(access: str, jwt: str) -> Dict[str, str]:
    """Cabeçalhos HTTP exigidos pelo SERPRO (OAuth + mTLS + X-Api-Key)."""
    return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Api-Key": _API_KEY,
            "Authorization": f"Bearer {access}",
            "jwt_token": jwt,
            "Role-Type": "TERCEIROS",
        }


def _envelope(dados: Dict[str, Any]) -> Dict[str, Any]:
    """Monta o JSON externo (contratante + pedidoDados + etc.)."""
    parte = {"numero": _CNPJ_CONT, "tipo": _TIPO_DOC}
    return {
        "contratante":       parte,
        "autorPedidoDados":  parte,
        "contribuinte":     {"numero": dados["cnpjCompleto"], "tipo": _TIPO_DOC},
        "pedidoDados": {
            "idSistema":     "PGDASD",
            "idServico":     "TRANSDECLARACAO11",
            "versaoSistema": "1.0",
            "dados": json.dumps(dados, ensure_ascii=False)
        }
    }


def enviar(payload_fiscal: Dict[str, Any], access_token: str, jwt_token: str, timeout: Tuple[int, int] = (10, 30),
           retries: int = 2) -> Dict[str, Any]:
    """POST no endpoint /Declarar com envelope completo."""
    body_json = _envelope(payload_fiscal)
    data = json.dumps(body_json, ensure_ascii=False).encode()
    for tent in range(1, retries + 2):
        try:
            r = requests.post(_ENDPOINT, headers=_cabecalhos(access_token, jwt_token), data=data, timeout=timeout)
            try:
                body = r.json()
            except ValueError:
                body = r.text

            if r.status_code < 500:
                return {"status": r.status_code, "body": body}
            logging.warning("SERPRO 5xx (%s) tent %s/%s – body: %s", r.status_code, tent, retries + 1, body)

        except requests.RequestException as exc:
            logging.error("erro rede %s tent %s/%s", exc, tent, retries + 1)
        if tent <= retries:
            time.sleep(2 * tent)

    raise RuntimeError("Falha persistente ao chamar SERPRO")

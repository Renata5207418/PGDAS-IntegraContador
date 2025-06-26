import os
import logging
import requests
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()
_PARTNER_URL = os.getenv("PARTNER_URL")


def _total_valores(valores: List[Dict[str, float]]) -> float:
    return round(sum(float(v.get("valor", 0)) for v in valores), 2)


def enviar_para_parceiro(cnpj: str, pa: int, dados: Dict[str, Any], fallback_tipo: Optional[int] = None, fallback_pdf: Optional[str] = None) -> Dict[str, Any]:
    """
    Monta o payload e (caso PARTNER_URL) faz POST.
    Sempre devolve um dicionário:
      { "payload": ..., "http_status": <int|None>, "erro": <str|None> }
    """
    declaracao = dados.get("declaracao")

    guia_b64 = (
        fallback_pdf
        if fallback_pdf
        else declaracao if isinstance(declaracao, str)
        else None
    )

    tipo = (
        fallback_tipo
        if fallback_tipo is not None
        else declaracao.get("tipoDeclaracao") if isinstance(declaracao, dict)
        else None
    )

    valores = dados.get("valoresDevidos", [])
    total = _total_valores(valores)

    payload: Dict[str, Any] = {
        "cnpj": cnpj,
        "pa": pa,
        "tipoDeclaracao": tipo,
        "totalDevido": total,
        "valoresDevidos": valores,
        "pdfBase64": guia_b64,
        "recibo": dados.get("recibo"),
        "idDeclaracao": dados.get("idDeclaracao"),
    }

    result: Dict[str, Any] = {"payload": payload, "http_status": None, "erro": None}

    if _PARTNER_URL:
        try:
            r = requests.post(_PARTNER_URL, json=payload, timeout=30)
            result["http_status"] = r.status_code
            r.raise_for_status()
            logging.info("Retorno enviado ao parceiro (%s) → %s", cnpj, r.status_code)
        except Exception as exc:
            result["erro"] = str(exc)
            logging.exception("Falha ao enviar dados ao parceiro: %s", exc)
    else:
        logging.warning("PARTNER_URL não configurada; só gerando payload.")

    return result

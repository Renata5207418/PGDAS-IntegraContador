from typing import Dict, Any, List, Optional


def _total_valores(valores: List[Dict[str, float]]) -> float:
    return round(sum(float(v.get("valor", 0)) for v in valores), 2)


def montar_payload_parceiro(cnpj: str, pa: int, dados: Dict[str, Any], tipo_declaracao: Optional[int] = None, pdf_b64: Optional[str] = None) -> Dict[str, Any]:
    """
    Monta o payload e devolve para a solicitação.
    """
    declaracao = dados.get("declaracao")

    guia_b64 = (
        pdf_b64
        if pdf_b64
        else declaracao if isinstance(declaracao, str)
        else None
    )

    tipo = (
        tipo_declaracao
        if tipo_declaracao is not None
        else declaracao.get("tipoDeclaracao") if isinstance(declaracao, dict)
        else None
    )

    valores = dados.get("valoresDevidos", [])
    total = _total_valores(valores)

    return {
        "cnpj": cnpj,
        "pa": pa,
        "tipoDeclaracao": tipo,
        "totalDevido": total,
        "valoresDevidos": valores,
        "pdfBase64": guia_b64,
        "recibo": dados.get("recibo"),
        "idDeclaracao": dados.get("idDeclaracao"),
    }

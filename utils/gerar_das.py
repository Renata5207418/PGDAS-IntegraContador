import json
from datetime import date, timedelta
from typing import Any, Dict
from utils.uploader_serpro import SerproClient

_client = SerproClient()


def gerar_das_unico(cnpj: str, pa: int, data_consolidacao: str | None = None) -> Dict[str, Any]:
    """
       Emite um DAS para o CNPJ e PA informados.
       Se data_consolidacao não vier, usa hoje como AAAAMMDD.
       Se vier no formato 'YYYY-MM-DD', remove hífens.
       """
    # 1) corrige o default para AAAAMMDD
    if data_consolidacao is None:
        tomorrow = date.today() + timedelta(days=1)
        data_consolidacao = tomorrow.strftime("%Y%m%d")
    else:
        data_consolidacao = data_consolidacao.replace("-", "")

    payload = {
        "cnpj": cnpj,
        "pa": pa,
        "dataConsolidacao": data_consolidacao
    }

    # 2) chama o serviço
    resp = _client.enviar("das", payload)
    body = resp.get("body")

    # 3) se não for JSON, retorna erro bruto
    if not isinstance(body, dict):
        return {"status": "FALHA", "cnpj": cnpj, "erro": body}

    # 4) trata HTTP “não 2xx” como falha
    if not (200 <= resp["status"] < 300):
        return {"status": "FALHA", "cnpj": cnpj, "erro": body}

    # 5) a partir daqui, HTTP 2xx e body é dict
    raw_dados = body.get("dados")
    parsed = None

    # quando vem string, fazemos json.loads
    if isinstance(raw_dados, str) and raw_dados.strip():
        try:
            parsed = json.loads(raw_dados)
        except json.JSONDecodeError:
            # volta sucesso, mas sem PDF se não decodificar
            return {"status": "SUCESSO", "cnpj": cnpj, "das_pdf_b64": None, "detalhamento": None}
    elif isinstance(raw_dados, (list, dict)):
        parsed = raw_dados

    # 6) extrai o objeto DAS (lista ou dict)
    das_obj = None
    if isinstance(parsed, list) and parsed:
        das_obj = parsed[0]
    elif isinstance(parsed, dict):
        das_obj = parsed

    # 7) monta retorno
    if das_obj:
        return {
            "status": "SUCESSO",
            "cnpj": cnpj,
            "das_pdf_b64": das_obj.get("pdf"),
            "detalhamento": das_obj.get("detalhamento"),
        }
    else:
        # corpo vazio, sem PDF
        return {
            "status": "SUCESSO",
            "cnpj": cnpj,
            "das_pdf_b64": None,
            "detalhamento": None,
        }

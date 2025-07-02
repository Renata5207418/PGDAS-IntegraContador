import os
import json
import time
import logging
import requests
from typing import Any, Dict, Tuple
from auth.token_auth import TokenAutenticacao


class SerproClient:
    """
    Cliente genérico para chamar APIs SERPRO de PGDAS (Declarar) e DAS (Emitir).
    """

    _SERVICES = {
        "pgdas": {
            "path": "Declarar",
            "jwt_header": "jwt_token",
            "id_servico": "TRANSDECLARACAO11",
        },
        "das": {
            "path": "Emitir",
            "jwt_header": "jwt_token",
            "id_servico": "GERARDAS12",
        },
    }

    def __init__(self):
        self.url_base = os.getenv("URL_BASE", "").rstrip("/")
        self.api_key = os.getenv("API_KEY_SERPRO", "")
        self.cnpj_cont = os.getenv("CNPJ_CONT", "")
        self.tipo_doc = int(os.getenv("TIPO_DOC", "2"))
        # tempo padrão de leitura
        self._default_to = int(os.getenv("SERPRO_READ_TIMEOUT", "60"))
        self._auth = TokenAutenticacao()

    def _build_headers(self, service: str) -> Dict[str, str]:
        access, jwt = self._auth.obter_token()
        cfg = self._SERVICES[service]
        return {
            "Content-Type": "application/json",
            "Accept":        "application/json",
            "X-Api-Key":     self.api_key,
            "Authorization": f"Bearer {access}",
            cfg["jwt_header"]: jwt,
            "Role-Type":     "TERCEIROS",
        }

    def build_headers(self, service: str) -> Dict[str, str]:
        """
        Mesmo que _build_headers, mas sem usar membro protegido.
        """
        return self._build_headers(service)

    def _build_envelope(self, service: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Monta o corpo da requisição conforme serviço:
          - pgdas: data deve ser o payload fiscal retornado por json_builder.montar_json()
          - das:   data deve ter as chaves 'cnpj', 'pa' e opcional 'dataConsolidacao'
        """
        parte = {"numero": self.cnpj_cont, "tipo": self.tipo_doc}
        svc = self._SERVICES[service]

        if service == "pgdas":
            # já é um dict pronto para ser serializado
            dados_json = json.dumps(data, ensure_ascii=False)
            numero_contribuinte = data["cnpjCompleto"]
        else:  # das
            dados_internos = {"periodoApuracao": str(data["pa"]).zfill(6)}
            if data.get("dataConsolidacao"):
                dados_internos["dataConsolidacao"] = data["dataConsolidacao"]
            dados_json = json.dumps(dados_internos, ensure_ascii=False)
            numero_contribuinte = data["cnpj"]

        return {
            "contratante":      parte,
            "autorPedidoDados": parte,
            "contribuinte":     {"numero": numero_contribuinte, "tipo": self.tipo_doc},
            "pedidoDados": {
                "idSistema":     "PGDASD",
                "idServico":     svc["id_servico"],
                "versaoSistema": "1.0",
                "dados":         dados_json,
            },
        }

    def enviar(
        self,
        service: str,
        data: Dict[str, Any],
        timeout: Tuple[int, int] = None,
        retries: int = 2
    ) -> Dict[str, Any]:
        """
        Faz POST para /<path> passando envelope + headers adequados.
        Retorna {'status': HTTP, 'body': json|texto}.
        """
        if service not in self._SERVICES:
            raise ValueError(f"Serviço desconhecido: {service!r}")

        url = f"{self.url_base}/{self._SERVICES[service]['path']}"
        headers = self._build_headers(service)
        envelope = self._build_envelope(service, data)
        payload = json.dumps(envelope, ensure_ascii=False).encode()

        if timeout is None:
            timeout = (10, self._default_to)

        last_resp = {"status": None, "body": None}
        for attempt in range(retries + 1):
            try:
                r = requests.post(url, headers=headers, data=payload, timeout=timeout)
                try:
                    body = r.json()
                except ValueError:
                    body = r.text
                status = r.status_code
                resp = {"status": status, "body": body}

                # 2xx → sucesso imediato; 4xx → falha sem retry
                if 200 <= status < 300 or 400 <= status < 500:
                    return resp

                last_resp = resp
                logging.warning(
                    "SERPRO %s [%s] tent %s/%s → %s",
                    service, status, attempt + 1, retries + 1, body
                )
            except requests.RequestException as e:
                last_resp = {"status": None, "body": str(e)}
                logging.error(
                    "Erro rede %s tent %s/%s",
                    e, attempt + 1, retries + 1
                )

            time.sleep(2 * (attempt + 1))

        raise RuntimeError("Falha persistente ao chamar SERPRO", last_resp)

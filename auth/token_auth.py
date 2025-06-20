import os
import base64
import warnings
import tempfile
from pathlib import Path
from dotenv import load_dotenv
from requests_pkcs12 import post
from typing import Tuple, Optional
from datetime import datetime, timedelta, timezone
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12

load_dotenv()


warnings.filterwarnings(
    "ignore",
    message="PKCS#12 bundle could not be parsed as DER, falling back to parsing as BER",
)


def ensure_der_pfx(src_path: str, password: str) -> str:
    """
    Retorna um caminho para um PFX codificado em DER.
    - Se `src_path` já estiver OK, devolve o mesmo caminho.
    - Caso contrário, cria um DER temporário (em %TEMP%) e devolve o novo caminho.
    """
    data = Path(src_path).read_bytes()
    passwd_bytes = password.encode()

    try:
        # Tenta carregar assumindo DER estrito. Se der certo, nada a fazer.
        pkcs12.load_key_and_certificates(data, passwd_bytes)
        return src_path
    except ValueError:
        # Caiu aqui? O arquivo provavelmente está em BER; converte.
        key, cert, add_certs = pkcs12.load_key_and_certificates(data, passwd_bytes)

        der_data = pkcs12.serialize_key_and_certificates(
            b"friendly-name",
            key,
            cert,
            add_certs,
            serialization.BestAvailableEncryption(passwd_bytes),
        )

        tmp_file = Path(tempfile.gettempdir()) / f"{Path(src_path).stem}_der.pfx"
        tmp_file.write_bytes(der_data)
        return str(tmp_file)


class TokenAutenticacao:
    """Autenticação OAuth 2.0 + mTLS para qualquer API SERPRO."""
    def __init__(self) -> None:
        self.token_cache: dict[str, Optional[str | datetime]] = {
            "access_token": None,
            "jwt_token": None,
            "expires_at": None,
        }

        self.caminho_certificado = os.getenv("CAMINHO_CERTIFICADO")
        self.nome_certificado = os.getenv("NOME_CERTIFICADO")
        self.senha_certificado = os.getenv("SENHA_CERTIFICADO")
        self.consumer_key = os.getenv("CONSUMER_KEY")
        self.consumer_secret = os.getenv("CONSUMER_SECRET")
        self.url_autenticacao = os.getenv("URL_AUTENTICACAO", "https://gateway.apiserpro.gov.br/token")

        if not all(
            [
                self.caminho_certificado,
                self.nome_certificado,
                self.senha_certificado,
                self.consumer_key,
                self.consumer_secret,
                self.url_autenticacao,
            ]
        ):
            raise ValueError("Faltam variáveis de ambiente para autenticação SERPRO.")

        original = os.path.join(self.caminho_certificado, self.nome_certificado)
        self.certificado_pfx = ensure_der_pfx(original, self.senha_certificado)

    def _expirou(self) -> bool:
        """True se não existe token ou já passou do horário de expiração."""
        exp = self.token_cache["expires_at"]
        return exp is None or datetime.now(timezone.utc) >= exp

    def obter_token(self) -> Tuple[str, str]:
        """
        Retorna (access_token, jwt_token). Se o cache estiver válido,
        devolve direto; senão, renova com o endpoint /token.
        """

        if self.token_cache["access_token"] and self.token_cache["jwt_token"] and not self._expirou():
            return self.token_cache["access_token"], self.token_cache["jwt_token"]

        headers = {
            "Authorization": "Basic "
                             + base64.b64encode(f"{self.consumer_key}:{self.consumer_secret}".encode()).decode(),
            "Role-Type": "TERCEIROS",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        body = {"grant_type": "client_credentials"}

        try:
            response = post(
                self.url_autenticacao,
                data=body,
                headers=headers,
                verify=True,
                pkcs12_filename=self.certificado_pfx,
                pkcs12_password=self.senha_certificado,
            )
            response.raise_for_status()

            data = response.json()
            self.token_cache["access_token"] = data.get("access_token")
            self.token_cache["jwt_token"] = data.get("jwt_token")

            # grava o horário de expiração (renova 60 s antes, por garantia)
            ttl = int(data.get("expires_in", 3600))
            self.token_cache["expires_at"] = datetime.now(timezone.utc) + timedelta(seconds=max(ttl - 60, 0))

            return self.token_cache["access_token"], self.token_cache["jwt_token"]

        except Exception as e:
            raise Exception(f"Erro ao autenticar SERPRO: {e}") from e

from pymongo.errors import DuplicateKeyError
from pymongo import MongoClient, ASCENDING
from dotenv import load_dotenv
from typing import Any, Dict
from datetime import datetime
import os
import json


load_dotenv()


# ---------------------------------------------------------------------
# conexão / inicialização
# ---------------------------------------------------------------------
MONGODB_URI = os.environ["MONGODB_URI"]
MONGO_DB = os.environ.get("MONGO_DB", "pgdas")
COLLECTION = os.environ.get("COLLECTION", "transmissao_pgd")

_client = MongoClient(MONGODB_URI)
_db = _client[MONGO_DB]
_collection = _db[COLLECTION]


def init_db() -> None:
    """
    Garante a existência da coleção e índices básicos.
    """
    _collection.create_index([("cnpj", ASCENDING), ("pa", ASCENDING), ("tipoDeclaracao", ASCENDING)], unique=True)
    _collection.create_index("status")


# ---------------------------------------------------------------------
# helpers internos
# ---------------------------------------------------------------------
def _make_cnpj_pa_id(cnpj: str, pa: int, tipo: int) -> str:
    return f"{cnpj}_{pa}_{tipo}"


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------
# API pública — idêntica à versão SQLite
# ---------------------------------------------------------------------
def insert_transmission(cnpj: str, pa: int, tipo: int, payload: Dict[str, Any]) -> str:
    """
    Insere documento PENDENTE e devolve o _id como string.
    """
    _id = _make_cnpj_pa_id(cnpj, pa, tipo)
    doc = {
        "_id": _id,
        "cnpj": cnpj,
        "pa": pa,
        "tipoDeclaracao": tipo,
        "status": "PENDENTE",
        "criado_em": _now_iso(),
        "payload_json": payload,
    }

    if tipo == 1:
        # ---------- SOMENTE INSERE ----------
        # Se o _id já existir o DuplicateKeyError sobe para o chamador
        _collection.insert_one(doc)

    elif tipo == 2:
        # ---------- SUBSTITUI ----------
        _collection.replace_one({"_id": _id}, doc, upsert=True)

    else:
        raise ValueError(f"Tipo de declaração inesperado: {tipo}")

    return _id


def update_success(cnpj: str, pa: int, tipo: int, resp: Dict[str, Any]) -> None:
    """
    Marca SUCESSO, grava resposta, guia (PDF base64) e valoresDevidos.
    """
    _id = _make_cnpj_pa_id(cnpj, pa, tipo)
    # ------------ extrai partes internas iguais ao código SQLite ----------
    interno: Dict[str, Any] = {}
    raw = None

    if isinstance(resp.get("body"), dict):
        raw = resp["body"].get("dados")

    if raw is None and isinstance(resp.get("dados"), str):
        raw = resp["dados"]

    if isinstance(raw, str):
        try:
            interno = json.loads(raw)
        except json.JSONDecodeError:
            interno = {}

    valores = interno.get("valoresDevidos", [])
    guia_b64 = interno.get("declaracao") if isinstance(interno.get("declaracao"), str) else None
    # ----------------------------------------------------------------------

    _collection.update_one(
        {"_id": _id},
        {"$set": {
            "status": "SUCESSO",
            "response_json": resp,
            "guia_pdf_base64": guia_b64,
            "valores_devidos_json": valores
        }}
    )


def update_failure(cnpj: str, pa: int, tipo: int, resp: Dict[str, Any] | None = None, error: str | None = None) -> None:
    """
    Marca FALHA, salva resposta bruta (se houver) e msg de erro.
    """
    _id = _make_cnpj_pa_id(cnpj, pa, tipo)
    _collection.update_one(
        {"_id": _id},
        {"$set": {
            "status": "FALHA",
            "response_json": resp,
            "error_msg": error,
            "atualizado_em": _now_iso()
        }}
    )

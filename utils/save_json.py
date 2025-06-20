from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, Optional
from database.dominio_db import DatabaseConnection, DB_PARAMS


def _default_base_dir() -> Path:
    """Pasta “json/” na raiz do projeto (…/PgDas/json)."""
    return Path(__file__).resolve().parent.parent / "json"


def _buscar_codi_emp_por_cnpj(cnpj: str) -> Optional[int]:
    """
        Busca o *codi_emp* da empresa pelo CNPJ.
        Retorna None se não encontrar.
    """
    sql = "SELECT TOP 1 codi_emp FROM bethadba.geempre WHERE cgce_emp = ?"
    db = DatabaseConnection(**DB_PARAMS)
    db.connect()
    rows = db.execute_query(sql, (cnpj,))
    db.close()
    return rows[0][0] if rows else None


def salvar_payload(payload: Dict[str, Any], *, codi_emp: Optional[int | str] = None, base_dir: Path | str | None = None,
                   pretty: bool = False) -> Path:
    """
        Grava *payload* em disco:
        • Subpasta : json/AAAAMM/
        • Nome arquivo : <codi_emp> - PGDAS - AAAAMM.json
        • `pretty=True` gera JSON identado; caso contrário, compacto.
        Retorna o `Path` do arquivo salvo.
    """
    if base_dir is None:
        base_dir = _default_base_dir()
    base_dir = Path(base_dir)

    pa = int(payload["pa"])
    pa_str = f"{pa:06d}"

    if codi_emp is None:
        codi_emp = _buscar_codi_emp_por_cnpj(payload["cnpjCompleto"])
    codi_emp_str = str(codi_emp) if codi_emp is not None else "multi"

    pasta_mes = base_dir / pa_str
    pasta_mes.mkdir(parents=True, exist_ok=True)

    nome_arquivo = f"{codi_emp_str} - PGDAS - {pa_str}.json"
    caminho = pasta_mes / nome_arquivo

    opts = {"ensure_ascii": False, "indent": 2} if pretty else {
        "ensure_ascii": False, "separators": (",", ":")
    }
    caminho.write_text(json.dumps(payload, **opts), encoding="utf-8")
    return caminho

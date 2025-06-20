from datetime import date
from typing import Optional
from database.dominio_db import DatabaseConnection, DB_PARAMS
from dicionario_id.atividade_map import _normalize, _best_match_id
from dicionario_id.id_rules import id_by_anexo_desc
from functools import lru_cache


@lru_cache(maxsize=None)
def _descricao_por_tabela(anexo: int, secao: int, tabela: int, vigencia: date) -> Optional[str]:
    """
       Descrição oficial da combinação *(anexo, seção, tabela)* vigente.
       Consulta **bethadba.eftabela_simples_nacional_tabela** e devolve a
       última descrição ≤ `vigencia`.  Retorna *None* se não encontrada.
    """
    # normaliza – sempre 1º dia do mês
    vigencia = date(vigencia.year, vigencia.month, 1)

    sql = """
        SELECT TOP 1 descricao
          FROM bethadba.eftabela_simples_nacional_tabela
         WHERE anexo    = ?
           AND secao    = ?
           AND tabela   = ?
           AND vigencia <= ?
         ORDER BY vigencia DESC
    """
    db = DatabaseConnection(**DB_PARAMS)
    db.connect()
    rows = db.execute_query(sql, (anexo, secao, tabela, vigencia))
    db.close()
    return rows[0][0].strip() if rows else None


def id_atividade(anexo: int, secao: int, tabela: int, vigencia: date) -> Optional[int]:
    """
        Resolve para `idAtividade` (1-43) usado no PGDAS-D.

        Fluxo:
        1. Busca a descrição oficial da tabela no banco (`_descricao_por_tabela`).
        2. Aplica regras rápidas por anexo (`id_by_anexo_desc`).
        3. Se não casar, faz *fuzzy-matching* contra o dicionário completo
           (`_best_match_id`).

        Retorna `None` se nenhuma estratégia encontrar correspondência
        aceitável.
        """
    desc_banco = _descricao_por_tabela(anexo, secao, tabela, vigencia)
    if not desc_banco:
        return None

    desc_norm = _normalize(desc_banco)

    # Tenta regras específicas por anexo
    id_regra = id_by_anexo_desc(anexo, desc_norm)
    if id_regra is not None:
        return id_regra

    #  Fallback: fuzzy-matching com todo o dicionário
    id_fuzzy, score = _best_match_id(desc_norm)
    # (opcional) log para ver o quão confiante estava
    print(f"Fuzzy: {desc_norm} -> id {id_fuzzy}, score {score:.2f}")
    return id_fuzzy

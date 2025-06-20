from __future__ import annotations
from datetime import datetime, date
from typing import Dict, Any, Iterable, Tuple, Optional
from dicionario_id.id_atividade import id_atividade


# -----------------------------------------------------------------------------
# utilidades de data / PA
# ------------------------------------------------------------------------------
def _as_date(val) -> date:
    """Converte *val* (str|datetime|date) → date."""
    if isinstance(val, date):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        return datetime.strptime(val[:10], "%Y-%m-%d").date()
    raise TypeError(f"Não sei converter {val!r} para date")


def _pa_from_date(dt: date) -> int:
    """date → inteiro AAAAMM (período de apuração)."""
    return dt.year * 100 + dt.month


def _pa_anteriores(pa_atual: int, n: int) -> list[int]:
    """Retorna os *n* PAs imediatamente anteriores a *pa_atual*."""
    ano, mes = divmod(pa_atual, 100)
    res: list[int] = []
    for _ in range(n):
        mes -= 1
        if mes == 0:
            mes, ano = 12, ano - 1
        res.append(ano * 100 + mes)
    return res


# -----------------------------------------------------------------------------
#  FOLHA - IMPLEMENTAÇÃO FUTURA CASO NECESSÁRIO....
# -----------------------------------------------------------------------------
def buscar_folha(_cnpj: str, _pa: int) -> float | None:
    """Stub.  Quando tiver a consulta pronta, devolva o valor da folha."""
    return None


def _folhas_salario(cnpj: str, pa: int) -> list[dict[str, float]]:
    """
    Gera a lista de folhas de salário (12 PAs anteriores).
    • Se **todos** os valores forem zero/None → devolve lista vazia
      e o campo nem chega a ser enviado na API.
    """
    folhas: list[dict[str, float]] = []
    tem_valor = False

    for pa_ant in _pa_anteriores(pa, 12):
        valor = buscar_folha(cnpj, pa_ant) or 0.0
        if valor:
            tem_valor = True
        folhas.append({"pa": pa_ant, "valor": round(valor, 2)})

    return folhas if tem_valor else []


# -----------------------------------------------------------------------------
#  Mercado Interno × Externo
# -----------------------------------------------------------------------------
#  -- adicionar novos IDs de exportação quando surgir necessidade
_IDS_MERCADO_EXTERNO: set[int] = {29, 30, 31, 32, 33, 38, 39, 43}


def _linha_eh_externa(r: Dict[str, Any], cache_id: dict[Tuple[int, int, int], Optional[int]]) -> bool:
    """True se a linha pertence a atividade de exportação."""
    anexo, secao, tabela = r["anexo"], r["secao"], r["tabela"]
    chave = (anexo, secao, tabela)
    if chave not in cache_id:
        cache_id[chave] = id_atividade(
            anexo, secao, tabela, _as_date(r["data_sim"])
        )
    ida = cache_id[chave]
    return ida in _IDS_MERCADO_EXTERNO


def _totais_mi_mx(rows: Iterable[Dict[str, Any]]) -> tuple[float, float]:
    """Soma separada de receitas: (interno, externo)."""
    cache_id: dict[tuple[int, int, int], Optional[int]] = {}
    total_int = total_ext = 0.0

    for r in rows:
        basen = float(r["basen"] or 0)
        anexo, secao, tabela = r["anexo"], r["secao"], r["tabela"]
        chave = (anexo, secao, tabela)

        if chave not in cache_id:
            cache_id[chave] = id_atividade(
                anexo, secao, tabela, _as_date(r["data_sim"])
            )
        ida = cache_id[chave]
        if ida is None:
            continue
        if ida in _IDS_MERCADO_EXTERNO:
            total_ext += basen
        else:
            total_int += basen

    return round(total_int, 2), round(total_ext, 2)


# -----------------------------------------------------------------------------
# Montar o JSON e limpar campos não obrigátorios.
# -----------------------------------------------------------------------------
def _clean(obj: Any) -> Any:
    """Remove recursivamente valores None, [] ou {} do objeto."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            v_clean = _clean(v)
            if v_clean not in (None, [], {}):
                out[k] = v_clean
        return out
    if isinstance(obj, list):
        cleaned = [_clean(i) for i in obj]
        return [i for i in cleaned if i not in (None, [], {})]
    return obj


def montar_json(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Constrói o JSON de transmissão do PGDAS-D a partir das linhas
    retornadas por `buscar_simples()`.
    """
    rows = list(rows)
    if not rows:
        raise ValueError("Lista de registros vazia")

    pa = _pa_from_date(_as_date(rows[0]["data_sim"]))
    cnpj_matriz = rows[0]["cgce_emp"]

    receita_int, receita_ext = _totais_mi_mx(rows)

    declaracao = {
        "tipoDeclaracao": 1,
        "receitaPaCompetenciaInterno": receita_int,
        "receitaPaCompetenciaExterno": receita_ext,
        # todos abaixo são opcionais – só ficam se >0 / não vazio
        "receitaPaCaixaInterno": None,
        "receitaPaCaixaExterno": None,
        "valorFixoIcms": None,
        "valorFixoIss": None,
        "receitasBrutasAnteriores": [],
        "folhasSalario": _folhas_salario(cnpj_matriz, pa),
        "naoOptante": None,
        "estabelecimentos": []
    }

    payload = {
        "cnpjCompleto": cnpj_matriz,
        "pa": pa,
        "indicadorTransmissao": False,
        "indicadorComparacao": True,
        "declaracao": declaracao,
        "valoresParaComparacao": []
    }

    # ─────────────── mapeia atividades por estabelecimento ──────────────────
    mapa_estab: dict[int, dict[str, Any]] = {}
    cache_id: dict[Tuple[int, int, int], Optional[int]] = {}

    for r in rows:
        basen = float(r["basen"] or 0)
        chave = (r["anexo"], r["secao"], r["tabela"])

        if chave not in cache_id:
            anexo, secao, tabela = chave
            cache_id[chave] = id_atividade(
                anexo, secao, tabela, _as_date(r["data_sim"])
            )
        ida = cache_id[chave]
        if ida is None:
            continue

        est = mapa_estab.setdefault(
            r["codi_emp"],
            {"cnpjCompleto": r["cgce_emp"], "atividades": []}
        )

        for atv in est["atividades"]:
            if atv["idAtividade"] == ida:
                atv["valorAtividade"] += basen
                atv["receitasAtividade"][0]["valor"] += basen
                break
        else:
            est["atividades"].append({
                "idAtividade": ida,
                "valorAtividade": basen,
                "receitasAtividade": [{"valor": basen}]
            })

    declaracao["estabelecimentos"] = list(mapa_estab.values())

    # ───────────────────── limpeza final de campos vazios ───────────────────
    return _clean(payload)

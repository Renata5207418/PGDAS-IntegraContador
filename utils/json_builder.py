from __future__ import annotations
from datetime import datetime, date
from typing import Dict, Any, Iterable
from dicionario_id.segment_rules import SEGMENT_RULES
from database.dominio_db import buscar_folha as _buscar_folha_db


# ---------------------------------------------------------------------------
# utilidades de data / PA
# ---------------------------------------------------------------------------
def _as_date(val) -> date:
    if isinstance(val, date):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        return datetime.strptime(val[:10], "%Y-%m-%d").date()
    raise TypeError(f"Não sei converter {val!r} para date")


def _pa_from_date(dt: date) -> int:
    return dt.year * 100 + dt.month


def _pa_anteriores(pa_atual: int, n: int) -> list[int]:
    ano, mes = divmod(pa_atual, 100)
    res = []
    for _ in range(n):
        mes -= 1
        if mes == 0:
            mes, ano = 12, ano - 1
        res.append(ano * 100 + mes)
    return res


# ---------------------------------------------------------------------------
# folha
# ---------------------------------------------------------------------------
def buscar_folha(cnpj: str, pa: int) -> float | None:
    """Chama diretamente a função do domínio_db para trazer o valor."""
    return _buscar_folha_db(cnpj, pa)


def _folhas_salario(cnpj: str, pa: int) -> list[dict[str, float]]:
    meses = _pa_anteriores(pa, 12)
    folhas = []
    for m in meses:
        valor = buscar_folha(cnpj, m) or 0.0
        folhas.append({"pa": m, "valor": round(valor, 2)})
    # 2) filtra só se existir alguma folha com valor > 0
    if not any(f["valor"] > 0 for f in folhas):
        return []
    # 3) ordena por pa crescente e devolve
    return sorted(folhas, key=lambda f: f["pa"])


# IDs de atividade "sujeito ao fator r" do anexo 3
_IDS_FATOR_R_ANEXO_3 = {10, 11, 12}


def _precisa_folha(rows):
    # Se algum anexo 5, já precisa folha
    if any(r["anexo"] == 5 for r in rows):
        return True
    # Para Anexo 3, verifica se algum idAtividade é do fator R
    for r in rows:
        if r["anexo"] == 3:
            cfg = SEGMENT_RULES.get((r["anexo"], r["secao"], r["tabela"]))
            if cfg and cfg["id"] in _IDS_FATOR_R_ANEXO_3:
                return True
    return False


# ---------------------------------------------------------------------------
# mercado interno × externo
# ---------------------------------------------------------------------------
_IDS_MERCADO_EXTERNO = {29, 30, 31, 32, 33, 38, 39, 43}


def _totais_mi_mx(rows: Iterable[Dict[str, Any]]) -> tuple[float, float]:
    total_int = total_ext = 0.0
    for r in rows:
        anexo, secao, tabela = r["anexo"], r["secao"], r["tabela"]
        if (anexo, secao, tabela) == (0, 0, 0):           # ignora linhas “fantasma”
            continue
        basen = float(r["basen"] or 0)
        ida = SEGMENT_RULES[(anexo, secao, tabela)]["id"]
        if ida in _IDS_MERCADO_EXTERNO:
            total_ext += basen
        else:
            total_int += basen
    return round(total_int, 2), round(total_ext, 2)


# ---------------------------------------------------------------------------
# limpar campos vazios
# ---------------------------------------------------------------------------
def _clean(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items() if v not in (None, [], {})}
    if isinstance(obj, list):
        cleaned = [_clean(i) for i in obj]
        return [i for i in cleaned if i not in (None, [], {})]
    return obj


# ---------------------------------------------------------------------------
# montar JSON PGDAS-D
# ---------------------------------------------------------------------------
def montar_json(rows: Iterable[Dict[str, Any]], tipo_declaracao: int = 1) -> Dict[str, Any]:
    rows = list(rows)

    # SE NÃO EXISTIR MOVIMENTO
    movimento = any(
        float(r["basen"] or 0) > 0 and (r["anexo"], r["secao"], r["tabela"]) != (0, 0, 0)
        for r in rows
    )
    sem_mov = (not rows) or (not movimento)
    if sem_mov and not rows:
        raise ValueError("Sem movimento, mas rows vazio: precisa de pelo menos 1 registro para obter PA e CNPJ")

    pa = _pa_from_date(_as_date(rows[0]["data_sim"]))
    cnpj_matriz = next((r["cgce_emp"] for r in rows if r["cgce_emp"].endswith("0001")), rows[0]["cgce_emp"])

    if not movimento:
        # ===== SEM MOVIMENTO =====
        estabelecimentos = [
            {"cnpjCompleto": r["cgce_emp"]}
            for r in rows
            if (r["anexo"], r["secao"], r["tabela"]) == (0, 0, 0)
        ]

        # se não achar nenhuma linha “0,0,0”, inclui pelo menos a matriz
        if not estabelecimentos:
            estabelecimentos = [{"cnpjCompleto": cnpj_matriz}]
        declaracao = {
            "tipoDeclaracao": tipo_declaracao,
            "receitaPaCompetenciaInterno": 0.00,
            "receitaPaCompetenciaExterno": 0.00,
            "estabelecimentos": estabelecimentos
        }
        payload = {
            "cnpjCompleto": cnpj_matriz,
            "pa": pa,
            "indicadorTransmissao": False,     # APÓS TESTES ALTERAR PARA TRUE, QUANDO FOR TRANSMITIR DE VERDADE.
            "indicadorComparacao": False,
            "declaracao": declaracao
        }
        return _clean(payload)

    receita_int, receita_ext = _totais_mi_mx(rows)
    declaracao = {
        "tipoDeclaracao": tipo_declaracao,
        "receitaPaCompetenciaInterno": receita_int,
        "receitaPaCompetenciaExterno": receita_ext,
        "receitaPaCaixaInterno": None,
        "receitaPaCaixaExterno": None,
        "valorFixoIcms": None,
        "valorFixoIss": None,
        "receitasBrutasAnteriores": [],
        "naoOptante": None,
        "estabelecimentos": []
    }
    if _precisa_folha(rows):
        folhas = _folhas_salario(cnpj_matriz, pa)
        if folhas:
            print(f"Incluindo folhasSalario para {cnpj_matriz} PA {pa}: {folhas}")
            declaracao["folhasSalario"] = folhas

    payload = {
        "cnpjCompleto": cnpj_matriz,
        "pa": pa,
        "indicadorTransmissao": False,      # APÓS TESTES ALTERAR PARA TRUE, QUANDO FOR TRANSMITIR DE VERDADE.
        "indicadorComparacao": False,
        "declaracao": declaracao,
        "valoresParaComparacao": []
    }

    # ─── agrega receitas por estabelecimento / atividade ───────────────
    mapa_estab: dict[int, dict[str, Any]] = {}
    for r in rows:
        print(
            f"PROCESSANDO: codi_emp={r['codi_emp']} cnpj={r['cgce_emp']} anexo={r['anexo']} secao={r['secao']} tabela={r['tabela']} basen={r['basen']}")
        anexo, secao, tabela = r["anexo"], r["secao"], r["tabela"]
        if (anexo, secao, tabela) == (0, 0, 0):
            continue
        basen = float(r["basen"] or 0)
        if basen <= 0.0:
            continue

        cfg = SEGMENT_RULES[(anexo, secao, tabela)]
        ida, quali = cfg["id"], cfg["quali"]

        est = mapa_estab.setdefault(
            r["codi_emp"],
            {"cnpjCompleto": r["cgce_emp"], "atividades": []}
        )
        print(set((r['codi_emp'], r['cgce_emp']) for r in rows))

        for atv in est["atividades"]:
            if atv["idAtividade"] == ida:
                # Cria uma nova receita para cada linha do banco
                receita = {"valor": basen}
                if quali:
                    receita["qualificacoesTributarias"] = [
                        {"codigoTributo": k, "id": v} for k, v in quali.items()
                    ]
                atv["receitasAtividade"].append(receita)
                # Atualiza o valor total da atividade
                atv["valorAtividade"] += basen
                break
        else:
            nova = {
                "idAtividade": ida,
                "valorAtividade": basen,
                "receitasAtividade": [{
                    "valor": basen,
                    **({"qualificacoesTributarias": [
                        {"codigoTributo": k, "id": v} for k, v in quali.items()
                    ]} if quali else {})
                }]
            }
            est["atividades"].append(nova)

    declaracao["estabelecimentos"] = list(mapa_estab.values())
    print("mapa_estab final:", mapa_estab)
    return _clean(payload)

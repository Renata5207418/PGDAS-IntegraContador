from __future__ import annotations
from difflib import SequenceMatcher
from typing import Optional, Dict, Tuple
import unicodedata
import re

# ------------- DICIONÁRIO MESTRE id da SERPRO -> descrição -----------------
ID_ATIVIDADE_DESC = {
    1: "Sem substituição tributária/tributação monofásica/antecipação com encerramento de tributação (o substituto tributário do ICMS deve utilizar essa opção)",
    2: "Com substituição tributária/tributação monofásica/antecipação com encerramento de tributação (o substituído tributário do ICMS deve utilizar essa opção)",
    3: "Revenda de mercadorias para o exterior",

    4: "Sem substituição tributária/tributação monofásica/antecipação com encerramento de tributação (o substituto tributário do ICMS deve utilizar essa opção)",
    5: "Com substituição tributária/tributação monofásica/antecipação com encerramento de tributação (o substituído tributário do ICMS deve utilizar essa opção)",
    6: "Venda de mercadorias industrializadas pelo contribuinte para o exterior",

    7: "Locação de bens móveis, exceto para o exterior",
    8: "Locação de bens móveis para o exterior",

    9:  "Escritórios de serviços contábeis autorizados pela legislação municipal a pagar o ISS em valor fixo em guia do Município",

    10: "Sujeitos ao fator “r”, sem retenção/substituição tributária de ISS, com ISS devido a outro(s) Município(s)",
    11: "Sujeitos ao fator “r”, sem retenção/substituição tributária de ISS, com ISS devido ao próprio Município do estabelecimento",
    12: "Sujeitos ao fator “r”, com retenção/substituição tributária de ISS",

    13: "Não sujeitos ao fator “r” e tributados pelo Anexo III, sem retenção/substituição tributária de ISS, com ISS devido a outro(s) Município(s)",
    14: "Não sujeitos ao fator “r” e tributados pelo Anexo III, sem retenção/substituição tributária de ISS, com ISS devido ao próprio Município do estabelecimento",
    15: "Não sujeitos ao fator “r” e tributados pelo Anexo III, com retenção/substituição tributária de ISS",

    16: "Sujeitos ao Anexo IV, sem retenção/substituição tributária de ISS, com ISS devido a outro(s) Município(s)",
    17: "Sujeitos ao Anexo IV, sem retenção/substituição tributária de ISS, com ISS devido ao próprio Município do estabelecimento",
    18: "Sujeitos ao Anexo IV, com retenção/substituição tributária de ISS",

    19: "Serviços da área da construção civil relacionados nos subitens 7.02 e 7.05 da LC 116/2003, Anexo III, sem retenção, ISS devido a outro(s) Município(s)",
    20: "Serviços da área da construção civil relacionados nos subitens 7.02 e 7.05 da LC 116/2003, Anexo III, sem retenção, ISS devido ao próprio Município",
    21: "Serviços da área da construção civil relacionados nos subitens 7.02 e 7.05 da LC 116/2003, Anexo III, com retenção",

    22: "Serviços da área da construção civil relacionados nos subitens 7.02 e 7.05 da LC 116/2003, Anexo IV, sem retenção, ISS devido a outro(s) Município(s)",
    23: "Serviços da área da construção civil relacionados nos subitens 7.02 e 7.05 da LC 116/2003, Anexo IV, sem retenção, ISS devido ao próprio Município",
    24: "Serviços da área da construção civil relacionados nos subitens 7.02 e 7.05 da LC 116/2003, Anexo IV, com retenção",

    25: "Serviços de transporte coletivo municipal rodoviário, metroviário, ferroviário e aquaviário de passageiros, sem retenção/substituição tributária de ISS, com ISS devido a outro(s) Município(s)",
    26: "Serviços de transporte coletivo municipal rodoviário, metroviário, ferroviário e aquaviário de passageiros, sem retenção/substituição tributária de ISS, com ISS devido ao próprio Município do estabelecimento",
    27: "Serviços de transporte coletivo municipal rodoviário, metroviário, ferroviário e aquaviário de passageiros, com retenção/substituição tributária de ISS",

    28: "Escritórios de serviços contábeis autorizados pela legislação municipal a pagar o ISS em valor fixo em guia do Município",
    29: "Sujeitos ao fator “r”",
    30: "Não sujeitos ao fator “r” e tributados pelo Anexo III",
    31: "Sujeitos ao Anexo IV",

    32: "Serviços da área da construção civil relacionados nos subitens 7.02 e 7.05 da lista anexa à LC 116/2003 e tributados pelo Anexo III",
    33: "Serviços da área da construção civil relacionados nos subitens 7.02 e 7.05 da lista anexa à LC 116/2003 e tributados pelo Anexo IV",

    34: "Transporte sem substituição tributária de ICMS (o substituto tributário deve utilizar essa opção)",
    35: "Transporte com substituição tributária de ICMS (o substituído tributário deve utilizar essa opção)",
    36: "Comunicação sem substituição tributária de ICMS (o substituto tributário deve utilizar essa opção)",
    37: "Comunicação com substituição tributária de ICMS (o substituído tributário deve utilizar essa opção)",

    38: "Transporte para o exterior",
    39: "Comunicação para o exterior",

    40: "Sem retenção/substituição tributária de ISS, com ISS devido a outro(s) Município(s)",
    41: "Sem retenção/substituição tributária de ISS, com ISS devido ao próprio Município do estabelecimento",
    42: "Com retenção/substituição tributária de ISS",
    43: "Atividades com incidência simultânea de IPI e de ISS para o exterior",
}

# ------------------------------------------------------------
# Mapa de substituições: regex  ➜ texto que já existe no dicionário
_SUBSTS = {
    r'^tabela\s+\d+\s*-': '',             # já existia
    r'^receitas?\s+decorrentes?\s+': '',  # aparecem no anexo 2 e 5
    r'^serviços?\s+da?\s+': '',           # “Serviços da área da construção…”
    r'^serviços?\s+de\s+': '',            # “Serviços de transporte…”
    r'^serviços?\s+': '',                 # fallback
    r'^sujeitos?\s+ao?\s+': '',           # “Sujeitos ao fator ‘r’…”
    r'"': '',                             # colapsar espaços (feito no fim)
}


def _normalize(texto: str) -> str:
    """Normaliza texto (sem acento, minúsculo, remove prefixos genéricos)."""
    texto = unicodedata.normalize("NFKD", texto).encode("ASCII", "ignore").decode()
    for pat, repl in _SUBSTS.items():
        texto = re.sub(pat, repl, texto, flags=re.I)
    return re.sub(r"\s+", " ", texto).lower().strip(" -")


# ————————————————— lookup & fuzzy —————————————————
NORM_DESC_TO_ID: Dict[str, int] = {
    _normalize(desc): _id for _id, desc in ID_ATIVIDADE_DESC.items()
}


def id_por_descricao(desc: str) -> Optional[int]:
    """Retorna idAtividade exato ou None se não houver correspondência."""
    return NORM_DESC_TO_ID.get(_normalize(desc))


def _best_match_id(desc_norm: str, thr: float = 0.55) -> Tuple[Optional[int], float]:
    """
    Retorna (id, score) da melhor correspondência fuzzy ≥ *thr*.
    Se nenhuma atingiu o limiar, devolve (None, score_máx).
    """
    best_id, best_score = None, 0.0
    for _id, txt in ID_ATIVIDADE_DESC.items():
        score = SequenceMatcher(None, desc_norm, _normalize(txt)).ratio()
        if score > best_score:
            best_id, best_score = _id, score
    return (best_id, best_score) if best_score >= thr else (None, best_score)

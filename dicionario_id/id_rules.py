"""
Mapeia (anexo, seção, tabela, descrição) ➜ idAtividade (1‒43) do PGDAS-D.

• Base de referência .....................................................
  - Tabela oficial de 43 atividades publicada pelo SERPRO;
  - Descrições reais que vêm do banco BETHA (coluna `descricao`
    de bethadba.eftabela_simples_nacional_tabela).

• Estratégia .............................................................
  1. Para cada anexo conhecido (1-6, 105) aplicamos regras simples
     baseadas em palavras-chave:
       – “exterior / exporta” ................. receitas de exportação;
       – “fator r” ............................. serviços X mercadorias;
       – “sem retenção / sem ST” .............. variantes sem ST/retido;
       – “outro município” .................... ISS devido fora do domicílio.
  2. Se nenhuma regra casar, devolvemos None e o chamador cai no
     fuzzy-matching (SequenceMatcher) contra as 43 descrições oficiais.

• Utilidades .............................................................
  _tem(txt,*subs)          → contém qualquer substring da lista?
  _tem_st(txt)             → menciona “ST” sem estar precedido de “sem ST”?
  _tem_retencao(txt)       → menciona retenção/ST e NÃO “sem reten…”?

• Extensão futura .........................................................
  - Se surgir novo anexo ou texto diferente, basta:
      a) adicionar um bloco `if anexo == N:` com lógica semelhante; ou
      b) ampliar as palavras-chave dos blocos existentes.
  - Evite overfitting: use expressões genéricas (“transport”, “comunic”)
    em vez de frases inteiras.

Retorna: idAtividade (int) ou None (deixa para fuzzy).
"""
from __future__ import annotations
from typing import Optional


def _tem(txt: str, *subs: str) -> bool:
    """True se `txt` contém qualquer uma das substrings de `subs`."""
    return any(s in txt for s in subs)


# ───────── utilidades específicas ─────────
def _tem_st(txt: str) -> bool:
    """Menciona ST e NÃO começa com “sem st”."""
    return "st" in txt and "sem st" not in txt


def _tem_retencao(txt: str) -> bool:
    """Menciona retenção/ST e NÃO “sem reten…/sem st”."""
    return (_tem(txt, "retencao", "retencao/", "retido", "st")
            and not _tem(txt, "sem retencao", "sem st"))


# ───────── regras principais ─────────
def id_by_anexo_desc(anexo: int, desc: str) -> Optional[int]:
    """
    Resolve por regras (palavras-chave) para idAtividade (1-43).
    Se não casar, devolve *None* e o chamador usa fuzzy-match.
    """
    # — ANEXO I —
    if anexo == 1:
        if "exterior" in desc:
            return 3
        if "sem st" in desc or "sem substituicao" in desc:
            return 1
        if _tem_st(desc):
            return 2
        return 1

    # — ANEXO II —
    if anexo == 2:
        if "exterior" in desc:
            return 6
        if _tem_st(desc):
            return 5
        return 4

    # — ANEXO III —
    if anexo == 3:
        export = "exporta" in desc or "exterior" in desc
        fator_r = "nao sujeitos" not in desc
        retencao = _tem_retencao(desc)

        if export:                          # 29 / 30
            return 29 if fator_r else 30

        if fator_r:                         # mercado interno
            if retencao:
                return 12
            if "outro municipio" in desc:
                return 10
            return 11
        else:
            if retencao:
                return 15
            if "outro municipio" in desc:
                return 13
            return 14

    # — ANEXO IV —
    if anexo == 4:
        export = "exporta" in desc or "exterior" in desc
        retencao = _tem_retencao(desc)

        if export:                          # 31
            return 31
        if retencao:
            return 18
        if "outro municipio" in desc:
            return 16
        return 17

    # — ANEXOS 5 e 105 —
    if anexo in (5, 105):
        export = "exporta" in desc or "exterior" in desc
        fator_r = "fator r" in desc and "nao" not in desc
        retencao = _tem_retencao(desc)
        outro_mun = "outro municipio" in desc

        if export:
            return 32 if "construcao" in desc else 30

        if fator_r:
            if retencao:
                return 12
            return 10 if outro_mun else 11
        else:
            if retencao:
                return 15
            return 13 if outro_mun else 14

    # — ANEXO 6 (transporte/comunicação ICMS) —
    if anexo == 6:
        export = "exporta" in desc or "exterior" in desc
        is_transp = "transport" in desc  # pega transporte / transportes

        if export:
            return 38 if is_transp else 39  # transporte ou comunicação p/ exterior

        # identificar “SEM ST”
        sem_st = ("sem st" in desc
                  or "sem retencao" in desc
                  or "sem reten" in desc
                  or "sem substituicao" in desc)

        if sem_st:
            return 34 if is_transp else 36  # sem ST

        # com ST / retenção
        if _tem_st(desc) or _tem_retencao(desc):
            return 35 if is_transp else 37  # com ST

        # fallback – assume sem ST
        return 34 if is_transp else 36

    # — outros anexos: deixa para o fuzzy —
    return None

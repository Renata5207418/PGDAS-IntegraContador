# scripts/make_segment_rules.py
from pathlib import Path
from datetime import datetime, date
from database.dominio_db import DatabaseConnection, DB_PARAMS

SQL = """
SELECT  t.anexo,
        t.secao,
        t.tabela,
        t.vigencia,
        t.descricao
FROM bethadba.eftabela_simples_nacional_tabela t
JOIN (
        SELECT  anexo, secao, tabela, MAX(vigencia) AS vigencia
        FROM bethadba.eftabela_simples_nacional_tabela
        GROUP BY anexo, secao, tabela
) ult
  ON  ult.anexo    = t.anexo
  AND ult.secao    = t.secao
  AND ult.tabela   = t.tabela
  AND ult.vigencia = t.vigencia
ORDER BY t.anexo, t.secao, t.tabela
"""

# ─── consulta ───────────────────────────────────────────────
db = DatabaseConnection(**DB_PARAMS)
db.connect()
rows = db.execute_query(SQL)
db.close()

# ─── escreve o módulo ───────────────────────────────────────
out_lines = [
    '"""',
    'segment_rules.py  –  GERADO AUTOMATICAMENTE; preencha id/quali nas linhas desejadas.',
    '"""',
    '',
    'from types import MappingProxyType',
    '',
    '_SEGMENT_RULES = {'
]

for a, s, t, vig_raw, desc in rows:
    # normaliza data (string ou datetime → YYYY-MM-DD)
    if isinstance(vig_raw, str):
        vig = datetime.strptime(vig_raw.split()[0], "%Y-%m-%d").date()
    elif isinstance(vig_raw, datetime):
        vig = vig_raw.date()
    else:
        vig = vig_raw  # já é date

    # entrada com id=None para ser preenchida depois
    out_lines.append(
        f'    ({a}, {s}, {t}): {{"id": None, "quali": {{}}}},   # vig {vig}, {desc.strip()}'
    )

out_lines += [
    '}',
    '',
    'SEGMENT_RULES = MappingProxyType(_SEGMENT_RULES)',
    "__all__ = ['SEGMENT_RULES']",
]

PROJECT_ROOT = Path(__file__).resolve().parents[1]   # PgDas/
OUT_FILE = PROJECT_ROOT / "dicionario_id" / "segment_rules.py"
OUT_FILE.parent.mkdir(parents=True, exist_ok=True)   # garante que existe
OUT_FILE.write_text("\n".join(out_lines), encoding="utf-8")
print("segment_rules.py criado em", OUT_FILE.relative_to(PROJECT_ROOT))

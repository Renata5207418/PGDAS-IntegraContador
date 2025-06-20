from database.dominio_db import DatabaseConnection, DB_PARAMS
from datetime import datetime


sql = """
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

db = DatabaseConnection(**DB_PARAMS)
db.connect()
rows = db.execute_query(sql)
db.close()

for a, s, ta, vig, desc in rows:
    # caso vig já seja date/datetime, deixa como está
    if isinstance(vig, str):
        # banco costuma entregar '2025-01-01 00:00:00.000'
        vig = datetime.strptime(vig.split()[0], "%Y-%m-%d").date()
    elif isinstance(vig, datetime):
        vig = vig.date()

    print(f"{a}-{s}-{ta} ({vig:%Y-%m-%d}) → {desc}")

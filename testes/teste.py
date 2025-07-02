from database.dominio_db import buscar_simples
from utils.json_builder import montar_json
from utils.save_json import salvar_payload
import json

# 1) defina as variáveis de entrada
cnpj = "11371445000102"
pa = 202505

# 2) busque e monte o JSON
rows = list(buscar_simples(cnpj, pa=pa))
payload = montar_json(rows)

# 3) salve em arquivo
caminho_gravado = salvar_payload(payload, pretty=True)

# 4) imprima o CNPJ correto
print(json.dumps(
    payload["declaracao"].get("folhasSalario", []),
    indent=2, ensure_ascii=False
))
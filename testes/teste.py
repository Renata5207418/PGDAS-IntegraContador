from database.dominio_db import buscar_simples
from utils.json_builder import montar_json
from utils.save_json import salvar_payload


rows = list(buscar_simples("00000000", pa="202505"))
payload = montar_json(rows)
caminho_gravado = salvar_payload(payload, pretty=True)
print(f"CNPJ {buscar_simples} - Arquivo salvo em: {caminho_gravado}")


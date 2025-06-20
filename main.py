from dotenv import load_dotenv
from database.dominio_db import buscar_simples
from utils.json_builder import montar_json
from auth.token_auth import TokenAutenticacao
from utils.monitorar_serpro import monitorar_pedido
from utils.uploader_serpro import enviar

load_dotenv()

rows = buscar_simples("00000000000000", pa="202505")

payload_fiscal = montar_json(rows)
tok = TokenAutenticacao()
access, jwt = tok.obter_token()

resp = enviar(payload_fiscal, access, jwt)
print("Resposta imediata:", resp)

# ------------------------------------------------------------
# só monitora se o SERPRO disse que o pedido ainda está em fila
# ------------------------------------------------------------
if resp["status"] == 202:
    pedido_id = resp["body"]["responseId"]
    resp_final = monitorar_pedido(pedido_id, tok)
    print(resp_final)
else:
    print(resp)

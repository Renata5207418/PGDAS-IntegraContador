from dotenv import load_dotenv
from database.dominio_db import buscar_simples
from utils.json_builder import montar_json
from auth.token_auth import TokenAutenticacao
from utils.monitorar_serpro import monitorar_pedido
from utils.uploader_serpro import enviar

load_dotenv()

rows = buscar_simples("18277532000136", pa="202505")

payload_fiscal = montar_json(rows)
tok = TokenAutenticacao()
access, jwt = tok.obter_token()

resp = enviar(payload_fiscal, access, jwt)
pedido_id = resp["body"]["responseId"]

resp_final = monitorar_pedido(pedido_id, tok)
print(resp_final)

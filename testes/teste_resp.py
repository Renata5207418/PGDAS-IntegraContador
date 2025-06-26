from pymongo import MongoClient
import json
import requests
from utils.resp_controle import enviar_para_parceiro
from dotenv import load_dotenv

load_dotenv()

client = MongoClient("mongodb://localhost:27017")
coll = client["pgdas"]["transmissao_pgd"]

# 1) pega o último SUCESSO gravado
doc = coll.find_one(
    {"status": "SUCESSO"},
    sort=[("criado_em", -1)],
)

if not doc:
    raise SystemExit("Nenhum documento com status=SUCESSO encontrado.")

# 2) bloco interno do SERPRO
try:
    dados = json.loads(doc["response_json"]["body"]["dados"])
except (KeyError, json.JSONDecodeError):
    raise SystemExit("Campo body.dados ausente ou inválido.")

# 3) fallbacks vindos do que você mesmo salvou
fallback_tipo = doc["payload_json"]["declaracao"]["tipoDeclaracao"]
fallback_pdf = doc.get("guia_pdf_base64")          # pode ser None

# 4) gera o payload definitivo (e posta se PARTNER_URL estiver setado)
payload = enviar_para_parceiro(
    cnpj=doc["cnpj"],
    pa=doc["pa"],
    dados=dados,
    fallback_tipo=fallback_tipo,
    fallback_pdf=fallback_pdf,
)

print(json.dumps(payload, indent=2, ensure_ascii=False))
r = requests.post("https://httpbin.org/post", json=payload, timeout=30)
print("====== resposta httpbin ======")
print(r.text)

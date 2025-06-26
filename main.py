import os
import json
import logging
from typing import Any, Dict, List
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from database.db_schema import (
    init_db,
    insert_transmission,
    update_success,
    update_failure,
)
from pymongo.errors import DuplicateKeyError
from database.dominio_db import buscar_simples
from utils.json_builder import montar_json
from utils.save_json import salvar_payload
from utils.uploader_serpro import enviar
from utils.monitorar_serpro import monitorar_pedido
from utils.resp_controle import enviar_para_parceiro
from auth.token_auth import TokenAutenticacao

# ---------------------------------------------------------------------- setup
load_dotenv()
init_db()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

app = Flask(__name__)
app.json.ensure_ascii = False


# ---------------------------------------------------------------------- rota
@app.route("/transmitir-pgdas", methods=["POST"])
def transmitir_pgdas():
    data = request.get_json(force=True)
    pa = data.get("pa")
    cnpjs = data.get("cnpjs")
    tipo = data.get("tipoDeclaracao", 1)   # 1-original · 2-retificadora

    # ----- validação
    if not pa or not isinstance(cnpjs, list) or not cnpjs:
        return jsonify(error="JSON deve conter 'pa' e lista não vazia 'cnpjs'"), 400
    if tipo not in (1, 2):
        return jsonify(error="'tipoDeclaracao' deve ser 1 ou 2"), 400

    # ----- autenticação SERPRO
    tok = TokenAutenticacao()
    access, jwt = tok.obter_token()

    resultados: List[Dict[str, Any]] = []

    # ================================================================== loop
    for cnpj in cnpjs:
        resp: Dict[str, Any] | None = None
        try:
            # 1) monta payload local
            rows = buscar_simples(cnpj, pa=pa)
            payload = montar_json(rows, tipo)
            salvar_payload(payload, pretty=True)

            # 2) grava como PENDENTE  ---------------------------
            try:
                insert_transmission(cnpj, pa, tipo, payload)
            except DuplicateKeyError:
                msg = ("Declaração ORIGINAL já transmitida para este CNPJ/PA. "
                       "Envie como tipoDeclaracao=2 para retificar.") if tipo == 1 else "Declaração RETIFICADORA já existe para este CNPJ/PA."
                resultados.append({
                    "cnpj": cnpj,
                    "status": "JA_TRANSMITIDA",
                    "mensagem": msg
                })
                continue  # pula para o próximo CNPJ
            # ----------------------------------------------------

            # 3) envia ao SERPRO
            resp = enviar(payload, access, jwt)
            if resp.get("status") == 202:
                resp = monitorar_pedido(resp["body"]["responseId"], tok)

            # 4) marca SUCESSO no banco
            update_success(cnpj, pa, tipo, resp)

            # 5) extrai dados para retorno e parceiro
            interno: Dict[str, Any] = {}
            raw = resp.get("body", {}).get("dados") if isinstance(resp.get("body"), dict) else resp.get("dados")
            if isinstance(raw, str):
                interno = json.loads(raw)

            guia_b64 = interno.get("declaracao") if isinstance(interno.get("declaracao"), str) else None

            # 6) envia para parceiro
            parceiro_info = enviar_para_parceiro(
                cnpj, pa, interno,
                fallback_tipo=tipo,
                fallback_pdf=guia_b64,
            )

            # 7) adiciona no resultado final
            resultados.append({
                "cnpj": cnpj,
                "status": "SUCESSO",
                "statusParceiro": parceiro_info.get("http_status"),
                "totalDevido": sum(v["valor"] for v in interno.get("valoresDevidos", [])),
                "valoresDevidos": interno.get("valoresDevidos", []),
            })

        except Exception as e:
            logging.exception("Erro no PGDAS %s", cnpj)
            update_failure(cnpj, pa, tipo, resp, str(e))
            resultados.append({
                "cnpj": cnpj,
                "status": "FALHA",
                "erro": str(e),
            })

    return jsonify(pa=pa, tipoDeclaracao=tipo, resultados=resultados), 200


# ----------------------------------------------------------------- execução
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 6200)))

#  para testar a rota, abra o prompt de comando e cole ->  curl -X POST http://127.0.0.1:6200/transmitir-pgdas ^
#      -H "Content-Type: application/json" ^
#      -d "{\"pa\":202505,\"tipoDeclaracao\":1,\"cnpjs\":[\"0000000000100\"]}"

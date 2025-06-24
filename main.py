import os
import json
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from database.db_schema import init_db, insert_transmission, update_success, update_failure
from database.dominio_db import buscar_simples
from utils.json_builder import montar_json
from utils.save_json import salvar_payload
from auth.token_auth import TokenAutenticacao
from utils.monitorar_serpro import monitorar_pedido
from utils.uploader_serpro import enviar

load_dotenv()
init_db()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
app = Flask(__name__)


@app.route("/transmitir-pgdas", methods=["POST"])
def transmitir_pgdas():
    data = request.get_json(force=True)
    pa = data.get("pa")
    cnpjs = data.get("cnpjs")
    if not pa or not isinstance(cnpjs, list) or not cnpjs:
        return jsonify(error="JSON deve conter 'pa' e lista não vazia 'cnpjs'"), 400

    tok = TokenAutenticacao()
    access, jwt = tok.obter_token()

    resultados = []
    for cnpj in cnpjs:
        idx = None
        resp = None
        try:
            # 1) busca no domínio e monta payload
            rows = buscar_simples(cnpj, pa=pa)
            payload = montar_json(rows)

            # 1.1) salva o JSON em arquivo para auditoria/depuração
            caminho = salvar_payload(payload, pretty=True)
            logging.info("Payload salvo em: %s", caminho)

            # 2) insere como PENDENTE
            idx = insert_transmission(cnpj, pa, payload)

            # 3) envia ao SERPRO
            resp = enviar(payload, access, jwt)
            if resp.get("status") == 202:
                pedido_id = resp["body"]["responseId"]
                resp = monitorar_pedido(pedido_id, tok)

            # 4) sucesso
            update_success(idx, resp)

            # 5) extrai valoresDevidos p/ retorno
            interno = {}
            raw = resp.get("dados")
            if isinstance(raw, str):
                interno = json.loads(raw)
            resultados.append({
                "cnpj": cnpj,
                "status": "SUCESSO",
                "valoresDevidos": interno.get("valoresDevidos", [])
            })

        except Exception as e:
            logging.exception("Erro no PGDAS %s", cnpj)
            update_failure(idx, resp if 'resp' in locals() else None, str(e))
            resultados.append({
                "cnpj": cnpj,
                "status": "FALHA",
                "erro": str(e)
            })

    return jsonify(pa=pa, resultados=resultados), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))


import os
import json
import logging
from typing import Any, Dict, List
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from database.db_schema import init_db, insert_transmission, update_success, update_failure
from pymongo.errors import DuplicateKeyError
from database.dominio_db import buscar_simples
from utils.json_builder import montar_json
from utils.save_json import salvar_payload
from utils.uploader_serpro import enviar
from utils.monitorar_serpro import monitorar_pedido
from utils.resp_controle import montar_payload_parceiro
from auth.token_auth import TokenAutenticacao

# ----------------------------------------------------------------------
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
    """
    Recebe um JSON no formato::

        {
          "pa": 202505,
          "tipoDeclaracao": 1,      # 1 = Original | 2 = Retificadora
          "cnpjs": ["14993727000121", "..." ]
        }

    • Para cada CNPJ, tenta transmitir a declaração do PA
      informado.
    • Devolve **uma lista de resultados**, cada item com:
        - status: SUCESSO | JA_TRANSMITIDA | FALHA
        - recibo / pdf_b64 (quando vier da SERPRO)
        - serpro_body (cópia literal da resposta em caso de FALHA)

    Qualquer erro controlado é capturado e transformado em FALHA,
    preservando o corpo original devolvido pelo SERPRO.
    """
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
            # 1) monta payload local (mantém igual)
            rows = buscar_simples(cnpj, pa=pa)
            if not rows:
                resultados.append({
                    "cnpj": cnpj,
                    "status": "FALHA",
                    "erro": f"Nenhum dado do PGDAS-D encontrado no Domínio para PA  {pa}",
                })
                update_failure(cnpj, pa, tipo, None, "rows vazio")
                continue
            payload = montar_json(rows, tipo)
            salvar_payload(payload, pretty=True)

            # 2) Envia ao SERPRO
            resp = enviar(payload, access, jwt)
            if resp.get("status") == 202:
                resp = monitorar_pedido(resp["body"]["responseId"], tok)

            # ─── novo bloco: se não for 2xx, trate como erro ──────────────────────
            if not (200 <= resp.get("status", 0) < 300):
                resultados.append({
                    "cnpj": cnpj,
                    "status": "FALHA",
                    "erro": "SERPRO devolveu HTTP %s" % resp["status"],
                    "serpro_body": resp["body"],
                })
                update_failure(cnpj, pa, tipo, resp, "HTTP %s" % resp["status"])
                continue

            # 2.5) Verifica se a ORIGINAL já estava concluída
            if (tipo == 1 and
                    resp.get("status") == 200 and
                    isinstance(resp.get("body"), dict) and
                    resp["body"].get("codigoStatus") == "CONCLUIDO" and
                    isinstance(resp["body"].get("dados"), dict) and
                    resp["body"]["dados"].get("reciboDeclaracao")):
                resultados.append({
                    "cnpj": cnpj,
                    "status": "JA_TRANSMITIDA",
                    "mensagem": "Declaração ORIGINAL já estava transmitida no PGDAS-D",
                    "recibo": resp["body"]["dados"]["reciboDeclaracao"],
                    "pdf_b64": resp["body"]["dados"].get("declaracao")
                })
                continue
            # 3) Grava no Mongo
            try:
                insert_transmission(cnpj, pa, tipo, payload)
            except DuplicateKeyError:
                resultado = {
                    "cnpj": cnpj,
                    "status": "JA_TRANSMITIDA",
                    "mensagem": (
                        "Declaração ORIGINAL já transmitida..."
                        if tipo == 1
                        else "Declaração RETIFICADORA já existe..."
                    ),
                }
                if resp and isinstance(resp.get("body"), dict):
                    dados = resp["body"].get("dados") or {}
                    resultado["recibo"] = dados.get("reciboDeclaracao")
                    resultado["pdf_b64"] = dados.get("declaracao")
                resultados.append(resultado)
                continue

            # 4) marca SUCESSO no banco
            update_success(cnpj, pa, tipo, resp)

            # 5) extrai dados para retorno e parceiro
            interno: Dict[str, Any] = {}

            raw = (resp.get("body", {}).get("dados")
                   if isinstance(resp.get("body"), dict)
                   else resp.get("dados"))

            if isinstance(raw, str) and raw.strip():
                try:
                    interno = json.loads(raw)
                except json.JSONDecodeError:
                    logging.warning("Campo 'dados' não é JSON válido; ignorando parse")

            guia_b64 = interno.get("declaracao") if isinstance(interno.get("declaracao"), str) else None

            # 6) envia para parceiro
            payload_parceiro = montar_payload_parceiro(
                cnpj, pa, interno,
                tipo_declaracao=tipo,
                pdf_b64=guia_b64
            )

            # 7) adiciona no resultado final
            resultados.append({
                "status": "SUCESSO",
                **payload_parceiro
            })

        # ------------- time-out / 5xx persistente --------------------- #
        except RuntimeError as e:
            msg, extra = e.args if len(e.args) == 2 else (str(e), None)
            resultados.append({
                "cnpj": cnpj,
                "status": "FALHA",
                "erro": msg,
                "serpro_body": extra,
            })
            update_failure(cnpj, pa, tipo, extra, msg)

        # ------------- falhas inesperadas ----------------------------- #
        except Exception as e:
            logging.exception("Erro no PGDAS %s", cnpj)
            update_failure(cnpj, pa, tipo, resp, str(e))
            resultados.append({
                "cnpj": cnpj,
                "status": "FALHA",
                "erro": str(e),
            })

    # ---------- resposta final --------------------------------------- #
    return jsonify(pa=pa, tipoDeclaracao=tipo, resultados=resultados), 200


# ----------------------------------------------------------------- execução
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 6200)))

#  para testar a rota, abra o prompt de comando e cole ->  curl -X POST http://127.0.0.1:6200/transmitir-pgdas ^
#      -H "Content-Type: application/json" ^
#      -d "{\"pa\":202505,\"tipoDeclaracao\":1,\"cnpjs\":[\"0000000000100\"]}"

import sqlite3
import json

DB_PATH = "pgdas.db"


def init_db(path: str = DB_PATH):
    """Cria a tabela única se não existir."""
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = ON;")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS transmissao_pgd (
      id                   INTEGER PRIMARY KEY AUTOINCREMENT,
      cnpj                 TEXT    NOT NULL,
      pa                   INTEGER NOT NULL,
      status               TEXT    NOT NULL,            -- PENDENTE, SUCESSO, FALHA
      criado_em            TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
      payload_json         TEXT    NOT NULL,            -- JSON enviado
      response_json        TEXT,                       -- JSON recebido completo
      guia_pdf_base64      TEXT,                       -- base64 do PDF, se houver
      valores_devidos_json TEXT,                       -- JSON array de valoresDevidos
      error_msg            TEXT                        -- msg de erro, se falha
    );
    """)
    conn.commit()
    conn.close()


def insert_transmission(cnpj: str, pa: int, payload: dict) -> int:
    """Insere uma linha PENDENTE e retorna o ID."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
      INSERT INTO transmissao_pgd
        (cnpj, pa, status, payload_json)
      VALUES (?, ?, 'PENDENTE', ?)
    """, (cnpj, pa, json.dumps(payload, ensure_ascii=False)))
    idx = cur.lastrowid
    conn.commit()
    conn.close()
    return idx


def update_success(idx: int, resp: dict):
    """Marca SUCESSO, salva JSON bruto, guia e valoresDevidos."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 1) string completa da resposta
    resp_json_str = json.dumps(resp, ensure_ascii=False)

    # 2) extrai onde o SERPRO coloca os valoresDevidos:
    interno = {}
    raw = None

    # cenário A: envelope de enviar() → resp["body"]["dados"]
    if isinstance(resp.get("body"), dict):
        raw = resp["body"].get("dados")

    # cenário B: monitorar_pedido já retorna o JSON puro → resp["dados"]
    if raw is None and isinstance(resp.get("dados"), str):
        raw = resp["dados"]

    # parseia o JSON interno, se existir
    if isinstance(raw, str):
        try:
            interno = json.loads(raw)
        except json.JSONDecodeError:
            interno = {}

    # 3) pega o array de valoresDevidos (ou lista vazia)
    valores = interno.get("valoresDevidos", [])

    # 4) pega o PDF em Base64 (ou None)
    guia = interno.get("declaracao")
    guia_b64 = guia if isinstance(guia, str) else None

    # 5) grava no SQLite
    cur.execute("""
      UPDATE transmissao_pgd
      SET status               = 'SUCESSO',
          response_json        = ?,
          guia_pdf_base64      = ?,
          valores_devidos_json = ?
      WHERE id = ?
    """, (
      resp_json_str,
      guia_b64,
      json.dumps(valores, ensure_ascii=False),
      idx
    ))

    conn.commit()
    conn.close()


def update_failure(idx: int, resp: dict | None = None, error: str | None = None):
    """Marca FALHA, salva JSON bruto (se houver) e a mensagem de erro."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    resp_json = json.dumps(resp, ensure_ascii=False) if resp is not None else None
    cur.execute("""
      UPDATE transmissao_pgd
      SET status        = 'FALHA',
          response_json = ?,
          error_msg     = ?
      WHERE id = ?
    """, (resp_json, error, idx))
    conn.commit()
    conn.close()

import os
import re
import logging
import sqlanydb
from datetime import date
from dotenv import load_dotenv
from typing import Iterable, Optional, Tuple, List, Dict

logging.basicConfig(level=logging.INFO)
load_dotenv()


class DatabaseConnection:
    """
        Conexão simples com o banco **SQL Anywhere** usado pelo Domínio.
        * `connect()`  – abre a conexão e faz log.
        * `execute_query()` – executa SQL parametrizado; devolve lista de tuplas
          ou [] se houver erro.
        * `close()` – fecha a conexão se existir.
    """
    def __init__(self, host: str, port: int, dbname: str, user: str, password: str) -> None:
        self.conn_str = {
            "servername": host,
            "dbn": dbname,
            "userid": user,
            "password": password,
            "LINKS": f"tcpip(host={host};port={port})"
        }
        self.conn: Optional[sqlanydb.Connection] = None

    # ------------------------------------------------------------------ #
    def connect(self) -> None:
        """Abre a conexão; loga falha e mantém `self.conn=None` se der erro."""
        try:
            logging.info(
                f"Conectando em {self.conn_str['servername']} "
                f"DB {self.conn_str['dbn']} ({self.conn_str['LINKS']})"
            )
            self.conn = sqlanydb.connect(**self.conn_str)
        except sqlanydb.Error as e:
            logging.error(f"Erro ao conectar: {e}")
            self.conn = None

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()

    # ------------------------------------------------------------------ #
    def execute_query(self, query: str, params: Tuple | None = None) -> List[Tuple]:
        """
           Executa SQL + parâmetros e devolve `fetchall()`.
           Retorna [] se não houver conexão ou se ocorrer exceção.
        """
        if self.conn is None:
            logging.error("Conexão não estabelecida.")
            return []
        cur = self.conn.cursor()
        try:
            cur.execute(query, params or ())
            return cur.fetchall()
        except sqlanydb.Error as e:
            logging.error(f"Erro na consulta: {e}\nSQL: {query}\nparams: {params}")
            return []
        finally:
            cur.close()


# ---------------------------------------------------------------------------
DB_PARAMS = {
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT")),
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASS"),
}


def buscar_simples(cnpj_raiz: str, anexo: Optional[int] = None, secao: Optional[int] = None, pa: Optional[str] = None, data_ini: Optional[date] = None, data_fim: Optional[date] = None) -> Iterable[Dict]:
    """
    Lê bethadba.efsdoimp_simples_nacional (alias sn) unida à geempre (ge).
    • Passe `pa="AAAAMM"` para um único período.
    • Ou use `data_ini`/`data_fim` para intervalo.
    """
    clean = re.sub(r"\D", "", cnpj_raiz)[:8]
    raiz = clean[:8] if len(clean) >= 8 else clean
    filtros = ["ge.cgce_emp LIKE ?"]
    params: List = [f"{raiz}%"]

    # ----- PA único ------------------------------------------------------
    if pa:
        filtros.append("( YEAR(sn.data_sim)*100 + MONTH(sn.data_sim) ) = ?")
        params.append(int(pa))

    # ----- intervalo opcional -------------------------------------------
    else:
        if data_ini:
            filtros.append("sn.data_sim >= ?")
            params.append(data_ini)
        if data_fim:
            filtros.append("sn.data_sim <= ?")
            params.append(data_fim)

    if anexo is not None:
        filtros.append("sn.anexo = ?")
        params.append(anexo)
    if secao is not None:
        filtros.append("sn.secao = ?")
        params.append(secao)

    sql = f"""
        SELECT ge.codi_emp,
           ge.cgce_emp AS cgce_emp,
           sn.filial,
           sn.anexo,
           sn.secao,
           sn.tabela,
           sn.basen,
           sn.data_sim
         FROM bethadba.efsdoimp_simples_nacional sn
         JOIN bethadba.geempre ge ON ge.codi_emp = sn.filial
        WHERE {" AND ".join(filtros)}
    """

    db = DatabaseConnection(**DB_PARAMS)
    db.connect()
    rows = db.execute_query(sql, tuple(params))
    db.close()

    return [
        {"codi_emp": r[0],
         "cgce_emp": r[1],
         "filial": r[2],
         "anexo": r[3],
         "secao": r[4],
         "tabela": r[5],
         "basen": r[6],
         "data_sim": r[7]}
        for r in rows
    ]


def buscar_folha(cnpj_raiz: str, pa: int) -> Optional[float]:
    """
    Lê bethadba.efsimples_nacional_folha_anterior (alias fa).
    Retorna o total de 'valor' **exatamente** no mês pa (AAAAMM).
    """
    clean = re.sub(r"\D", "", cnpj_raiz)[:8]
    raiz = clean if len(clean) >= 8 else clean

    ano = pa // 100
    mes = pa % 100

    sql = """
        SELECT
          SUM(fa.valor)          AS soma_valor,
          SUM(fa.VALOR_INSS_CPP) AS soma_inss
        FROM bethadba.efsimples_nacional_folha_anterior fa
        JOIN bethadba.geempre ge
          ON ge.codi_emp = fa.codi_emp
       WHERE ge.cgce_emp LIKE ?
         AND YEAR(fa.periodo)  = ?
         AND MONTH(fa.periodo) = ?
    """
    params = (f"{raiz}%", ano, mes)

    db = DatabaseConnection(**DB_PARAMS)
    db.connect()
    rows = db.execute_query(sql, params)
    db.close()

    if not rows:
        return None

    soma_valor, soma_inss = rows[0]

    # converte cada um pra float, tratando None como 0.0
    v = float(soma_valor) if soma_valor is not None else 0.0
    i = float(soma_inss) if soma_inss is not None else 0.0

    total = v + i
    return total if total != 0 else 0.0

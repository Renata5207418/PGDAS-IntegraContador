import os
import sys
import json
from datetime import datetime
from pathlib import Path
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from pymongo import MongoClient

# ---------------------------- CONFIG -----------------------------------
URI = os.getenv("PGDAS_BACKUP_URI", "mongodb://localhost:27017/pgdas")
DEST_DIR = Path(os.getenv("PGDAS_BACKUP_DIR", r"S:\SETOR FISCAL\PASTAS FUNCIONARIOS\RENATA\BACKUP BANCO PGDAS"))
TIMEZONE = "America/Sao_Paulo"
RUN_AT_HH = 17
RUN_AT_MM = 58
COLLECTION = "transmissao_pgd"
# -----------------------------------------------------------------------


def run_backup():
    client = MongoClient(URI)
    db = client.get_default_database()
    collection = db[COLLECTION]

    count = 0
    for doc in collection.find():
        # Pega data de criação para pasta (ou usa hoje)
        criado_em = doc.get("criado_em")
        if not criado_em:
            criado_em = datetime.now().isoformat()
        if isinstance(criado_em, str):
            pasta_mes = criado_em[:7]
        else:
            pasta_mes = criado_em.strftime("%Y-%m")

        pasta_destino = DEST_DIR / pasta_mes
        pasta_destino.mkdir(parents=True, exist_ok=True)

        nome_arquivo = f"{doc['_id']}.json"
        caminho_arquivo = pasta_destino / nome_arquivo

        with open(caminho_arquivo, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
        count += 1

    print(f"[BACKUP] {count} documentos salvos em pastas por mês. Backup finalizado ✓")


# -----------------------------------------------------------------------
if __name__ == "__main__":
    if "--run-now" in sys.argv:
        run_backup()
        sys.exit(0)

    # Scheduler bloqueante
    scheduler = BlockingScheduler(timezone=pytz.timezone(TIMEZONE))

    trigger = CronTrigger(hour=RUN_AT_HH, minute=RUN_AT_MM)
    scheduler.add_job(run_backup,
                      id="dump_diario",
                      trigger=trigger,
                      max_instances=1,
                      misfire_grace_time=3600)

    print(f"Scheduler ativo – backup diário às {RUN_AT_HH:02d}:{RUN_AT_MM:02d} "
          f"({TIMEZONE}).  Ctrl+C para sair.")
    scheduler.start()

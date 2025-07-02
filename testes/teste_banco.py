from database.dominio_db import buscar_folha

cnpj = "04691199000100"
for mes in [202401, 202402, 202403, 202404, 202405]:
    print(mes, buscar_folha(cnpj, mes))

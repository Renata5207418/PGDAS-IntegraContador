from pprint import pprint
from database.dominio_db import buscar_simples


resultados = buscar_simples('12345678', pa='202505')

pprint(resultados)

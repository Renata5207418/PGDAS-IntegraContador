# PgDas

Automatiza a geração e transmissão de declarações **PGDAS-D** ao SERPRO,
com suporte a OAuth2 + mTLS, persistência em **MongoDB** e monitoramento
assíncrono de pedidos.

---

## Índice
- [Descrição](#descrição)
- [Funcionalidades](#funcionalidades)
- [Tecnologias](#tecnologias)
- [Pré-requisitos](#pré-requisitos)
- [Instalação](#instalação)
- [Configuração](#configuração)
- [Uso](#uso)
- [Estrutura de Diretórios](#estrutura-de-diretórios)
- [Testes](#testes)
- [Contribuição](#contribuição)
- [Licença](#licença)
- [Autor](#autor)

---

## Descrição

O **PgDas** faz:

1. Conecta ao **Domínio/SQL Anywhere** para extrair dados de receita.  
2. Constrói o JSON conforme especificação PGDAS-D.  
3. Salva o payload em `json/AAAAMM/` para auditoria.  
4. Transmite ao SERPRO via **OAuth 2 + mTLS + API-Key**.  
5. Monitora o pedido até `codigoStatus = CONCLUIDO`.  
6. Persiste histórico (sucesso/falha) em **MongoDB**.

---

## Funcionalidades

- 🔐 **Autenticação**: cache de `access_token` e `jwt_token`.
- 🏗️ **Builder**: agrupa receitas, calcula MI × MX, remove campos vazios.
- 💾 **Persistência**: payload + resposta (incluindo PDF Base-64) em Mongo.
- 📡 **Transmissão**: re-tentativa automática para 5xx, polling de monitoramento.
- 🛠️ **API Flask** `POST /transmitir-pgdas` pronta para integração.

---

## Tecnologias

| Camada  | Stack                                         |
|---------|-----------------------------------------------|
| Core    | Python 3.10+, `typing`, `logging`             |
| Web     | Flask                                         |
| SERPRO  | `requests`, `requests-pkcs12`, `cryptography` |
| Banco   | **MongoDB** (`pymongo`)                       |
| Domínio | `sqlanydb`                                    |
| Outros  | `python-dotenv`, `pathlib`                    |

---

## Pré-requisitos

* Python 3.10+  
* MongoDB em execução (local ou Atlas)  
* Acesso ao banco Domínio (SQL Anywhere)  
* Certificado PFX + credenciais da Loja SERPRO

---

## Instalação

```bash
git clone https://…/PgDas.git
cd PgDas
python -m venv .venv && source .venv/bin/activate   # Linux/mac
# .venv\Scripts\activate  (Windows)
pip install -r requirements.txt
Nenhum passo extra de banco é necessário — as coleções Mongo são criadas
automaticamente na primeira execução.

Configuração
Copie .env.example → .env e preencha:

dotenv
Copiar
Editar
# === Certificado mTLS ===
CAMINHO_CERTIFICADO=/caminho/para/cert
NOME_CERTIFICADO=meu_cert.pfx
SENHA_CERTIFICADO=senha_do_pfx

# === OAuth2 Loja SERPRO ===
CONSUMER_KEY=ck_xxx
CONSUMER_SECRET=cs_xxx
URL_AUTENTICACAO=https://gateway.apiserpro.gov.br/token

# === Endpoint Integra Contador ===
URL_BASE=https://gateway.apiserpro.gov.br/integra-sn
API_KEY_SERPRO=api_key_xxx
CNPJ_CONT=00000000000191
SERPRO_READ_TIMEOUT=60   # opcional

# === MongoDB ===
MONGO_URI=mongodb://localhost:27017/pgdas

# === Domínio SQLAnywhere ===
DB_HOST=...
DB_PORT=2638
DB_NAME=...
DB_USER=...
DB_PASS=...

# === Flask ===
PORT=6200
Dica: ao ir para produção, troque indicadorTransmissao para
True em json_builder.py ou envie esse flag pelo front-end.

Uso
Via API REST
bash
Copiar
Editar
curl -X POST http://localhost:6200/transmitir-pgdas \
  -H "Content-Type: application/json" \
  -d '{
        "pa": 202505,
        "tipoDeclaracao": 1,
        "cnpjs": ["11111111000191"]
      }'
Resposta:

json
Copiar
Editar
{
  "pa": 202505,
  "resultados": [
    {
      "cnpj": "11111111000191",
      "status": "SUCESSO",
      "recibo": "123.456.789.000001",
      "pdf_b64": "JVBERi0xLjQKJ...."
    }
  ],
  "tipoDeclaracao": 1
}
Execução direta
bash
Copiar
Editar
python main.py        # sobe o servidor Flask em 0.0.0.0:6200
Estrutura de Diretórios
bash
Copiar
Editar
PgDas/
├── auth/                  # OAuth2 + mTLS
├── database/              # Mongo + Domínio
├── utils/                 # builder, uploader, monitor etc.
├── json/AAAAMM/           # payloads salvos
├── testes/                # scripts de teste
├── main.py                # API Flask
└── .env / README.md
Testes
bash
Copiar
Editar
python testes/teste_banco.py     # conexão Domínio
python testes/teste.py           # builder + validação
python testes/consulta_vigencia.py
Contribuição
Fork

git checkout -b feature/sua-feature

Commits claros

Pull Request descrevendo a mudança

Autor
Renata Boppre Scharf
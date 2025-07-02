---
<!-- Badges -->
[![Python](https://img.shields.io/badge/python-3.10+-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Build](https://img.shields.io/github/actions/workflow/status/seu-usuario/PgDas/ci.yml?branch=main)](https://github.com/seu-usuario/PgDas/actions)

# PgDas

Automatiza a geração e transmissão de declarações **PGDAS-D** ao SERPRO, com:
- Autenticação OAuth2 + mTLS  
- Persistência em **MongoDB**  
- Monitoramento assíncrono de pedidos  

---

## 📑 Índice

- [Descrição](#descrição)  
- [Funcionalidades](#funcionalidades)  
- [Tecnologias](#tecnologias)  
- [Pré-requisitos](#pré-requisitos)  
- [Quick Start](#quick-start)  
- [Configuração](#configuração)  
- [Uso](#uso)  
  - [Via API REST](#via-api-rest)  
  - [Execução Direta](#execução-direta)  
- [Estrutura de Diretórios](#estrutura-de-diretórios)  
- [Testes](#testes)  
- [Contribuição](#contribuição)  
- [Licença](#licença)  
- [Autor](#autor)  

---

## 📝 Descrição

O **PgDas** realiza todo o fluxo de entrega das obrigações do Simples Nacional:

1. Conexão ao banco **Domínio/SQL Anywhere** para extração de dados de receita.  
2. Geração do JSON no formato exigido pela especificação **PGDAS-D**.  
3. Geração de guia **DAS** em PDF (Base64).  
4. Armazenamento dos payloads em `json/AAAAMM/` para auditoria.  
5. Transmissão ao SERPRO via OAuth2 + mTLS + API Key.  
6. Polling até `codigoStatus = CONCLUIDO`.  
7. Persiste histórico de respostas (sucesso/falha) em **MongoDB**.

---

## 🚀 Funcionalidades

- 🔐 **Autenticação**  
  - Cache de `access_token` e `jwt_token`  
  - Renovação automática antes do vencimento  

- 🏗️ **Builder de JSON**  
  - Agrupa receitas, calcula MI × MX  
  - Remove campos vazios  

- 💾 **Persistência**  
  - Armazena payload + respostas (incluindo PDF em Base64)  
  - Histórico completo no MongoDB  

- 📡 **Transmissão**  
  - Retry automático em HTTP 5xx  
  - Polling assíncrono para status do pedido  

- 🛠️ **API REST**  
  - Endpoint `POST /transmitir-pgdas` pronto para integração  

- 📊 **DAS**:  
  - Geração de guias de recolhimento (DAS) a partir dos dados de receita.
  - Salva o PDF em Base64 junto com o histórico.


---

## 🛠️ Tecnologias

| Camada     | Stack                                          |
|------------|------------------------------------------------|
| **Core**   | Python 3.10+, `typing`, `logging`              |
| **Web**    | Flask                                          |
| **SERPRO** | `requests`, `requests-pkcs12`, `cryptography`  |
| **Banco**  | MongoDB (`pymongo`)                            |
| **Domínio**| `sqlanydb`                                     |
| **Utilitários** | `python-dotenv`, `pathlib`               |

---

## 📋 Pré-requisitos

- Python 3.10 ou superior  
- MongoDB em execução (local ou Atlas)  
- Acesso ao banco Domínio (SQL Anywhere)  
- Certificado PFX + credenciais da Loja SERPRO  

---

## ⚡ Quick Start

```bash
# 1. Clone o repositório
git clone https://github.com/seu-usuario/PgDas.git
cd PgDas

# 2. Crie e ative o virtualenv
python -m venv .venv
# Linux/Mac
source .venv/bin/activate
# Windows
# .venv\Scripts\activate

# 3. Instale dependências
pip install -r requirements.txt

# 4. Copie e configure variáveis de ambiente
cp .env.example .env
# Edite o .env conforme o próximo tópico

# 5. Inicie o servidor Flask
python main.py
````

---

## ⚙️ Configuração

Preencha o arquivo `.env` com suas credenciais:

```dotenv
# === Certificado mTLS ===
CAMINHO_CERTIFICADO=/caminho/para/meu_cert.pfx
NOME_CERTIFICADO=meu_cert.pfx
SENHA_CERTIFICADO=minha_senha

# === OAuth2 SERPRO ===
CONSUMER_KEY=ck_xxx
CONSUMER_SECRET=cs_xxx
URL_AUTENTICACAO=https://gateway.apiserpro.gov.br/token

# === Integra Contador ===
URL_BASE=https://gateway.apiserpro.gov.br/integra-sn
API_KEY_SERPRO=api_key_xxx
CNPJ_CONT=00000000000100
SERPRO_READ_TIMEOUT=60

# === MongoDB ===
MONGO_URI=mongodb://localhost:27000/pgdas

# === Domínio SQLAnywhere ===
DB_HOST=...
DB_PORT=...
DB_NAME=...
DB_USER=...
DB_PASS=...

# === Flask ===
PORT=6200
```

> **Dica:** para enviar o indicadorTransmissao, você pode alterar o valor em `json_builder.py` ou passar esse flag pela API.

---

## 📦 Uso

### Via API REST

```bash
curl -X POST http://localhost:6200/transmitir-pgdas \
  -H "Content-Type: application/json" \
  -d '{
        "pa": 202505,
        "tipoDeclaracao": 1,
        "cnpjs": ["11111111000191"]
      }'
```

**Resposta de exemplo:**

```json
{
  "pa": 202505,
  "tipoDeclaracao": 1,
  "resultados": [
    {
      "cnpj": "11111111000191",
      "status": "SUCESSO",
      "recibo": "123.456.789.000001",
      "pdf_b64": "JVBERi0xLjQKJ...."
    }
  ]
}
```

### Execução Direta

```bash
python main.py
# Servidor rodando em http://0.0.0.0:6200
```

---

## 🗂️ Estrutura de Diretórios

```
PgDas/
├── auth/                  # OAuth2 + mTLS
├── database/              # MongoDB + Domínio
├── utils/                 # Builder, uploader, monitor etc.
├── json/AAAAMM/           # Payloads salvos para auditoria
├── testes/                # Scripts de teste
├── main.py                # Ponto de entrada Flask
├── .env.example           # Exemplo de variáveis de ambiente
└── README.md              # Documentação
```

---

## ✅ Testes

```bash
python testes/teste_banco.py       # Conexão com Domínio
python testes/teste.py             # Builder + Validação de JSON
python testes/consulta_vigencia.py # Validação de vigência
```

---

## 🤝 Contribuição

1. Faça um **fork**
2. Crie uma branch `feature/sua-feature`
3. Commit com mensagens claras
4. Abra um **Pull Request** detalhando a mudança

---

## 📝 Licença

Este projeto está sob a licença [MIT](LICENSE).

---

## 👤 Autor

**Renata Boppre Scharf**

---
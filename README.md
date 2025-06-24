# PgDas

Automatiza a geração e transmissão de declarações PGDAS-D ao SERPRO, com suporte a OAuth2 + mTLS, persistência em
SQLite e monitoramento de pedidos.

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

O **PgDas** é um utilitário em Python que:

1. Conecta ao banco Domínio (SQL Anywhere) para extrair dados de receita do Simples Nacional.  
2. Constrói o JSON de declaração conforme especificação PGDAS-D.  
3. Salva localmente o payload em `json/AAAAMM/` para auditoria.  
4. Transmite ao SERPRO via OAuth 2.0 + mTLS e API key.  
5. Monitora o pedido de transmissão até conclusão.  
6. Persiste histórico e resultados (sucesso/falha) em banco SQLite (`pgdas.db`).  

---

## Funcionalidades

- 💼 **Autenticação**: OAuth2 + mTLS (PKCS#12) com cache de token.  
- 📊 **Construção de Payload**: agrupa receitas por estabelecimento e atividade, calcula internos × externos.  
- 📁 **Salvar JSON**: gera arquivos em `json/AAAAMM/`, com opção “pretty” para debug.  
- 📡 **Transmissão**: envia e monitora via endpoints `/Declarar` e `/Monitorar`.  
- 🗄️ **Banco Local**: SQLite para rastrear status, payload e resposta (incluindo PDF base64).  
- 🔄 **API REST**: rota Flask `/transmitir-pgdas` para integração com outros sistemas.  

---

## Tecnologias

- Python 3.10+  
- Flask  
- sqlite3  
- requests, requests-pkcs12  
- python-dotenv  
- cryptography  
- sqlanydb  
- typing, pathlib, logging  

---

## Pré-requisitos

- Python 3.10 ou superior  
- `pip`  
- (Opcional) Virtualenv  

---

## Instalação

1. Clone o repositório:  
   ```bash
   git clone https://…/PgDas.git
   cd PgDas
````

2. Crie e ative um virtualenv (opcional):

   ```bash
   python -m venv .venv
   source .venv/bin/activate    # Linux/macOS
   .venv\Scripts\activate       # Windows
   ```
3. Instale dependências:

   ```bash
   pip install -r requirements.txt
   ```
4. Inicialize o banco SQLite:

   ```bash
   # Será executado automaticamente ao iniciar o app
   python main.py
   ```

---

## Configuração

Copie o arquivo de exemplo `.env.example` para `.env` e preencha:

```dotenv
# Certificado PKCS#12 (mTLS)
CAMINHO_CERTIFICADO=/caminho/para/cert
NOME_CERTIFICADO=meu_cert.pfx
SENHA_CERTIFICADO=senha_do_pfx

# OAuth2
CONSUMER_KEY=seu_consumer_key
CONSUMER_SECRET=seu_consumer_secret
URL_AUTENTICACAO=https://gateway.apiserpro.gov.br/token

# Endpoints SERPRO
URL_BASE=https://gateway.apiserpro.gov.br/integra-sn
API_KEY_SERPRO=sua_api_key
CNPJ_CONT=00000000000191

# Domínio (SQL Anywhere)
DB_HOST=...
DB_PORT=2638
DB_NAME=...
DB_USER=...
DB_PASS=...

# Flask
PORT=5000
```

> **Observação:** reveja `indicadorTransmissao` e `indicadorComparacao` em `utils/json_builder.py` antes de ir para produção.

---

## Uso

### Via API REST

Faça um **POST** para `/transmitir-pgdas`:

```bash
curl -X POST http://localhost:5000/transmitir-pgdas \
  -H "Content-Type: application/json" \
  -d '{
        "pa": 202505,
        "cnpjs": ["11111111000191","22222222000199"]
      }'
```

**Resposta JSON**:

```json
{
  "pa": 202505,
  "resultados": [
    {
      "cnpj": "11111111000191",
      "status": "SUCESSO",
      "valoresDevidos": [ ... ]
    },
    {
      "cnpj": "22222222000199",
      "status": "FALHA",
      "erro": "mensagem de erro…"
    }
  ]
}
```

### Script direto

```bash
python main.py
```

A aplicação roda em `http://0.0.0.0:<PORT>`.

---

## Estrutura de Diretórios

```
PgDas/
├── .venv/                      # Virtualenv (opcional)
├── auth/
│   └── token_auth.py           # OAuth2 + mTLS (PKCS#12)
├── database/
│   ├── db_schema.py            # Criação e atualização do SQLite
│   └── dominio_db.py           # Conexão e query ao Domínio (SQL Anywhere)
├── dicionario_id/
│   └── segment_rules.py        # Mapas de segmentação de atividade
├── json/
│   ├── 202504/                 # Payloads salvos por competência
│   ├── 202505/
│   └── exemplos/
├── testes/
│   ├── consulta_vigencia.py    # Scripts de teste (vigência, DB, payload)
│   ├── teste.py
│   └── teste_banco.py
├── utils/
│   ├── json_builder.py         # Montagem do JSON PGDAS-D
│   ├── monitorar_serpro.py     # Polling do endpoint /Monitorar
│   ├── save_json.py            # Salva payload em disco
│   └── uploader_serpro.py      # Envio ao SERPRO (/Declarar)
├── .env                        # Variáveis de ambiente
├── main.py                     # API Flask principal
├── pgdas.db                    # Banco SQLite local
└── README.md                   # Este arquivo
```

---

## Testes

Os scripts em `testes/` cobrem:

* **Conexão e consulta** ao banco Domínio (`teste_banco.py`).
* **Geração de payload** e verificação de campos (`teste.py`).
* **Validação de vigência** (`consulta_vigencia.py`).

Execute diretamente:

```bash
python testes/teste.py
python testes/teste_banco.py
python testes/consulta_vigencia.py
```

---

## Contribuição

1. Fork este repositório.
2. Crie uma branch feature/xyz.
3. Faça commits claros.
4. Abra um Pull Request descrevendo suas alterações.

---

## Autor

**Renata Boppre Scharf**

```


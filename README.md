# Almoxarifado da Cantina-Escola (Desafio 02 — Nível A)

## 1. Problema e Usuário
A cantina-escola controla o estoque em planilhas compartilhadas que qualquer pessoa edita, fazendo com que o saldo fique negativo, o histórico de retiradas se perca e as compras sejam feitas tarde demais. O produto é usado pelo **responsável pelo almoxarifado** para registrar compras (entradas), retiradas para a cozinha (saídas), consultar o histórico de cada item e identificar rapidamente o que precisa ser comprado.

---

## 2. Requisitos da Ficha e Status

| Código | Requisito | Status | Endpoint |
| :--- | :--- | :--- | :--- |
| **RF1** | Cadastrar produto (`nome` único, `unidade` em `un`/`kg`/`L`, `estoque_minimo >= 0`, `saldo = 0`) | Implementado | `POST /produtos` |
| **RF2** | Registrar movimentação de `entrada` ou `saida` (`quantidade > 0` e `motivo`) | Implementado | `POST /produtos/<id>/movimentacoes` |
| **RF3** | **Regra Central:** Recusar saída maior que o saldo (`409`), sem registrar nada | Implementado | `POST /produtos/<id>/movimentacoes` |
| **RF4** | Consultar produto com saldo atual e histórico de movimentações | Implementado | `GET /produtos/<id>` |
| **RF5** | Listar produtos abaixo do estoque mínimo (`saldo < estoque_minimo`) | Implementado | `GET /produtos/abaixo-minimo` |
| **Extra** | Verificação de saúde da aplicação e banco (`iniciado_em` + `SELECT 1`) | Implementado | `GET /health` |

---

## 3. Arquitetura e Decisões Técnicas (Nível A)

```text
[Cliente / VS Code REST Client / Navegador]
                    │
                    ▼  HTTPS
     [Azure App Service (Linux / Python)]
        Flask + Gunicorn (app:app)
                    │
                    ▼  TCP/5432 + TLS (sslmode=require)
  [Azure Database for PostgreSQL - Servidor Flexível]
        Tabelas: produtos, movimentacoes
```

### Decisões Justificadas

1. **Saldo armazenado na tabela `produtos` + atualização atômica em transação**
   - **O que se ganha:** Leitura imediata do saldo (`O(1)`) e proteção real contra concorrência. A saída executa `UPDATE produtos SET saldo = saldo - %s WHERE id = %s AND saldo >= %s` e o `INSERT INTO movimentacoes` dentro da **mesma transação**. Se duas requisições chegarem ao mesmo tempo para retirar o último saldo, apenas uma afeta a linha e a outra recebe `409` sem deixar saldo negativo. Além disso, `CHECK (saldo >= 0)` no PostgreSQL atua como última linha de defesa.
   - **O que se perde:** Exige disciplina para nunca alterar `saldo` fora da transação de movimentação (não existem rotas de edição direta de saldo).

2. **Quantidade decimal (`NUMERIC(10, 3)`) em vez de `INTEGER` ou `FLOAT`**
   - **O que se ganha:** Suporta tanto itens contados por unidade (`un`) quanto itens fracionados em `kg` e `L` (ex.: `2.5 kg` de arroz) sem erros de arredondamento binário de ponto flutuante (`FLOAT`).
   - **O que se perde:** Ocupa ligeiramente mais espaço que `INTEGER` e exige conversão explícita ao serializar JSON.

3. **Banco gerenciado na nuvem (Azure Database for PostgreSQL) em vez de arquivo local ou VM**
   - **O que se ganha:** Persistência real independente do ciclo de vida do App Service (sobrevive a reinícios e novos deploys), backups automáticos e firewall gerenciado.
   - **O que se perde:** Necessidade de gerenciar regras de firewall/SSL (`sslmode=require`) e lembrar de parar o servidor após a aula para evitar consumo de créditos.

---

## 4. Modelo de Dados e Restrições

Arquivo completo em `banco/schema.sql`:

- **`produtos`**
  - `id` (`SERIAL PRIMARY KEY`)
  - `nome` (`VARCHAR(120) NOT NULL UNIQUE`) — impede duplicidade (CA5 → `409`)
  - `unidade` (`VARCHAR(10) NOT NULL CHECK (unidade IN ('un', 'kg', 'L'))`)
  - `estoque_minimo` (`NUMERIC(10, 3) NOT NULL DEFAULT 0 CHECK (estoque_minimo >= 0)`)
  - `saldo` (`NUMERIC(10, 3) NOT NULL DEFAULT 0 CHECK (saldo >= 0)`) — garantia de integridade no banco
  - `criado_em` (`TIMESTAMPTZ NOT NULL DEFAULT NOW()`)

- **`movimentacoes`**
  - `id` (`SERIAL PRIMARY KEY`)
  - `produto_id` (`INTEGER NOT NULL REFERENCES produtos(id)`) — chave estrangeira
  - `tipo` (`VARCHAR(10) NOT NULL CHECK (tipo IN ('entrada', 'saida'))`)
  - `quantidade` (`NUMERIC(10, 3) NOT NULL CHECK (quantidade > 0)`) — impede zero ou negativo (CA3 → `400`)
  - `motivo` (`VARCHAR(255) NOT NULL`)
  - `criada_em` (`TIMESTAMPTZ NOT NULL DEFAULT NOW()`)

---

## 5. Como Executar no VS Code (Local)

1. Abra a pasta do projeto no **VS Code**.
2. Crie e ative um ambiente virtual Python:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   ```
3. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
4. Copie `.env.example` para `.env` e preencha a variável `DATABASE_URL`:
   ```bash
   cp .env.example .env
   ```
5. Crie as tabelas no banco PostgreSQL executando `banco/schema.sql` (ou rodando `python init_db.py`).
6. Inicie a API:
   ```bash
   python app.py
   ```
7. Abra o arquivo `requisicoes.http` no VS Code (com a extensão **REST Client**) para testar todas as rotas.

---

## 6. Implantação na Azure (Nível A)

1. **Criar Grupo de Recursos e PostgreSQL Flexível (B1ms / 32 GiB)** no Portal Azure (`rg-cloud-gXX`), liberando acesso aos serviços do Azure e o IP da máquina para aplicar `banco/schema.sql`.
2. **Criar App Service (Linux, Python 3.11/3.12, Plano F1)** com nome único `app-cloud-gXX-iniciais`.
3. **Configurar Variáveis de Ambiente** no App Service (*Configurações > Variáveis de ambiente*):
   - `DATABASE_URL` = `postgresql://USUARIO:SENHA@SERVIDOR.postgres.database.azure.com:5432/BANCO?sslmode=require`
   - `SCM_DO_BUILD_DURING_DEPLOYMENT` = `true`
4. **Comando de inicialização** (*Configurações > Configurações gerais*):
   ```bash
   gunicorn --bind=0.0.0.0 --timeout 600 app:app
   ```
5. **Publicar pelo terminal (Azure CLI)** ou pela extensão Azure App Service do VS Code:
   ```bash
   az webapp up --name app-cloud-gXX-iniciais --resource-group rg-cloud-gXX --plan plan-cloud-gXX --sku F1 --runtime "PYTHON:3.11" --location brazilsouth
   az webapp restart --name app-cloud-gXX-iniciais --resource-group rg-cloud-gXX
   ```

---

## 7. Tabela de Casos de Teste

| Caso | Cenário | Entrada | Resultado Esperado | Resultado Obtido |
| :--- | :--- | :--- | :--- | :--- |
| **CA1** | Entrada de 10 e saída de 4 | `POST /produtos/1/movimentacoes` (`entrada`: 10, depois `saida`: 4) | `201` em ambas; `saldo = 6` e 2 linhas no histórico | *(Preencher após teste)* |
| **CA2 (Negativo)** | Saída maior que o saldo | Com `saldo = 6`, `POST /produtos/1/movimentacoes` (`saida`: 7) | `409 Conflict`; saldo permanece `6` e histórico mantém 2 linhas | *(Preencher após teste)* |
| **CA3 (Negativo)** | Quantidade zero ou negativa | `POST /produtos/1/movimentacoes` (`quantidade`: `0` ou `-2`) | `400 Bad Request` | *(Preencher após teste)* |
| **CA4** | Alerta de estoque mínimo | Produto A (`saldo=3, min=5`) e Produto B (`saldo=5, min=5`) | `GET /produtos/abaixo-minimo` lista apenas Produto A | *(Preencher após teste)* |
| **CA5 (Negativo)** | Produto com nome duplicado | `POST /produtos` com `nome` já cadastrado | `409 Conflict` | *(Preencher após teste)* |
| **Extra (Negativo)** | Produto inexistente | `GET /produtos/9999` ou `POST /produtos/9999/movimentacoes` | `404 Not Found` | *(Preencher após teste)* |
| **Persistência** | Reinício do App Service | Cadastrar `GXX-PALAVRA`, reiniciar App Service e consultar `/health` e `/produtos` | `iniciado_em` atualizado e registro `GXX-PALAVRA` preservado | *(Preencher após teste)* |

---

## 8. Evidências Obrigatórias (Pasta `evidencias/`)

- **E1:** URL pública do App Service em execução (`https://app-cloud-gXX-iniciais.azurewebsites.net`).
- **E2:** 4 prints com data e hora visíveis da prova de persistência (`GXX-PALAVRA` listado, `iniciado_em` antes do reinício, `iniciado_em` alterado após reinício com dado preservado, e consulta direta no PostgreSQL).
- **E3:** Execução dos casos de teste acima (positivos e negativos).
- **E4:** Diagrama de arquitetura (seção 3).
- **E5:** Print das variáveis de ambiente na Azure com valores ocultos e `.gitignore` contendo `.env`.
- **E6:** Este `README.md` completo e link do pitch de 90 segundos.

---

## 9. Dificuldade Superada, Limitações e Próximos Passos

- **Dificuldade superada (exemplo técnico):** *Problema:* Falha de conexão ao PostgreSQL da Azure por exigência de criptografia TLS (`no pg_hba.conf entry ... no encryption`). *Diagnóstico e Causa:* O servidor gerenciado da Azure recusa conexões sem SSL por padrão. *Solução:* Configuração de `sslmode=require` na `DATABASE_URL` e fallback automático no `db.py` para conexões com `azure.com`.
- **Limitações conhecidas:** Não há autenticação de usuários (o responsável é informado no campo `motivo`) e não há rota de exclusão de produtos ou estorno automático.
- **Próximos passos:** Implementar estorno por lançamento contrário (sem apagar histórico), filtro de movimentações por período e exportação de relatório CSV para o Azure Blob Storage.

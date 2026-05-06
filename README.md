# Detection as Code — Splunk

Repositório para gerenciar detecções Splunk como código com CI/CD automatizado via GitHub Actions.

## Como funciona

```
Analista cria/edita detection YAML
        ↓
  git push → abre PR
        ↓
GitHub Actions (self-hosted runner)
  ├── Valida sintaxe YAML
  ├── Valida schema (campos obrigatórios, enums, etc.)
  ├── Valida sintaxe SPL via Splunk REST API
  └── Bloqueia merge se houver erro
        ↓
  Code review + aprovação
        ↓
  Merge para main
        ↓
GitHub Actions deploy
  ├── Dry-run (preview do que vai mudar)
  └── Deploy via Splunk REST API (create/update)
```

## Estrutura do repositório

```
.
├── detections/
│   ├── endpoint/          # Detecções de endpoint (Windows, Linux)
│   ├── network/           # Detecções de rede
│   └── identity/          # Detecções de identidade/acesso
├── scripts/
│   ├── validate.py        # Validação de schema + SPL
│   ├── deploy.py          # Deploy via REST API
│   └── splunk_client.py   # Cliente Splunk REST
├── schemas/
│   └── detection.schema.json  # JSON Schema para as detecções
├── .github/workflows/
│   ├── validate-pr.yml    # Roda em todo PR
│   └── deploy.yml         # Roda no merge para main
└── .pre-commit-config.yaml
```

## Formato de uma detecção

```yaml
name: "Nome legível da detecção"
id: "uuid-v4-unico"          # gere com: python -c "import uuid; print(uuid.uuid4())"
version: 1                    # incremente a cada mudança
status: draft                 # draft | testing | production | deprecated
author: "seu-nome"
date: "2026-05-06"
modified: "2026-05-06"
description: "O que detecta e por quê (mínimo 10 chars)"
type: alert                   # alert | report | scheduled_report

search: |
  index=windows EventCode=4732
  | where Group_Name="Administrators"
  | table _time, ComputerName, Member_Name

schedule:
  cron: "*/15 * * * *"
  earliest: "-15m"
  latest: "now"

alert:
  condition: "search count > 0"
  severity: high              # informational | low | medium | high | critical
  suppress: false

tags:
  mitre_attack:
    - T1098                   # formato obrigatório: T####(.###)
  platform:
    - Windows                 # Windows | Linux | macOS | AWS | Azure | GCP | Network
  category: identity          # endpoint | network | identity | cloud | application

splunk_app: "search"
```

## Setup local

### 1. Instalar dependências

```bash
make setup
```

### 2. Configurar variáveis de ambiente

```bash
export SPLUNK_URL="https://localhost:8089"
export SPLUNK_TOKEN="<your-token>"
# ou autenticação por usuário/senha:
export SPLUNK_USERNAME="admin"
export SPLUNK_PASSWORD="<your-password>"
```

Para obter um token no Splunk:
**Settings → Tokens → New Token**

### 3. Validar detecções localmente

```bash
# Sem conectar ao Splunk (só schema)
make validate

# Com validação de SPL via API
make validate-splunk

# Arquivo específico
python scripts/validate.py detections/endpoint/detect_powershell_encoded_command.yml
```

### 4. Deploy manual

```bash
# Preview sem alterar nada
make deploy-dry

# Deploy de todas as detecções
make deploy

# Deploy de arquivo específico
python scripts/deploy.py detections/endpoint/detect_new_local_admin.yml
```

## Configurar o self-hosted runner

Os workflows usam `runs-on: self-hosted` porque o Splunk está rodando localmente no Orbstack e os runners do GitHub não têm acesso a `localhost`.

### Instalar o runner na sua máquina

1. No GitHub: **Settings → Actions → Runners → New self-hosted runner**
2. Selecione **macOS** e siga as instruções
3. No diretório do runner, configure e inicie:

```bash
./config.sh --url https://github.com/SEU_USER/SEU_REPO --token TOKEN_GERADO
./run.sh
```

Para rodar como serviço em background:
```bash
./svc.sh install
./svc.sh start
```

### Variáveis e secrets no GitHub

Vá em **Settings → Secrets and variables → Actions** e adicione:

| Tipo | Nome | Valor |
|------|------|-------|
| Secret | `SPLUNK_URL` | `https://localhost:8089` |
| Secret | `SPLUNK_TOKEN` | token gerado no Splunk |
| Variable | `SPLUNK_APP` | `search` (ou seu app customizado) |

> O Orbstack expõe as portas dos containers diretamente em `localhost` na máquina host.
> Se usar VM em vez de container, use o IP da VM: `https://splunk.orb.local:8089`

## Fluxo do analista

```bash
# 1. Criar branch para a nova detecção
git checkout -b detection/detect-brute-force-login

# 2. Criar o arquivo de detecção
# (use um UUID novo: python -c "import uuid; print(uuid.uuid4())")
vim detections/identity/detect_brute_force_login.yml

# 3. Validar localmente antes de commitar
python scripts/validate.py --no-splunk detections/identity/detect_brute_force_login.yml

# 4. Commitar e abrir PR
git add detections/identity/detect_brute_force_login.yml
git commit -m "feat: add brute force login detection"
git push origin detection/detect-brute-force-login
# → GitHub Actions roda a validação automaticamente no PR

# 5. Após aprovação e merge → deploy automático
```

## Campos obrigatórios e validações

| Campo | Obrigatório | Validação |
|-------|-------------|-----------|
| `name` | Sim | min 5 chars |
| `id` | Sim | UUID v4 |
| `version` | Sim | inteiro >= 1 |
| `status` | Sim | enum: draft/testing/production/deprecated |
| `author` | Sim | string |
| `description` | Sim | min 10 chars |
| `type` | Sim | enum: alert/report/scheduled_report |
| `search` | Sim | string SPL + sintaxe válida (via Splunk API) |
| `tags.category` | Sim | enum: endpoint/network/identity/cloud/application |
| `tags.mitre_attack` | Não | formato T####(.###) |

> Detecções com `status: draft` ou sem tags MITRE geram **warnings** (não bloqueiam o PR).
> Detecções com `status: production` são habilitadas automaticamente no Splunk.
> Detecções com outros status são criadas como **disabled** no Splunk.

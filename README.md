# Nexus

CLI para centralizar o catálogo, status e acesso a projetos gerenciados por agentes IA.

Registra projetos, escaneia dados (git/filesystem/health checks), oferece TUI para lançar Claude Code, e publica um dashboard web estático.

## Instalação

**Dependências:** Python 3.10+, Git, pipx.

### macOS

```bash
brew install pipx
pipx ensurepath
pipx install --editable . --force
```

### Linux (Ubuntu/Debian)

```bash
sudo apt-get install -y pipx
pipx ensurepath
pipx install --editable . --force
```

Depois disso, `nexus` estará disponível globalmente.

## Comandos

| Comando      | Descrição                                      |
|--------------|-------------------------------------------------|
| *(nenhum)*   | Abre TUI — lista, filtra, lança Claude Code     |
| `add`        | Registrar projeto (interativo)                   |
| `remove`     | Remover projeto do registry                      |
| `list`       | Listar projetos (`--all` inclui arquivados)      |
| `scan`       | Scan completo (`--project` para um só, `--sync-project-config` para nexus.yaml) |
| `status`     | Detalhes de um projeto                           |
| `edit`       | Editar campos interativamente (inclui web config)|
| `note`       | Atualizar nota rápida                            |
| `discover`   | Descobrir projetos em diretório (até 3 níveis)   |
| `push`       | Scan + build + publicar portal web               |
| `web-init`   | Gerar/atualizar prompt web de um projeto         |

### Exemplos

```bash
nexus                              # abre TUI
nexus add                          # registra projeto atual
nexus add /caminho/do/projeto      # registra outro projeto
nexus list                         # lista ativos
nexus list --all                   # lista todos (inclui arquivados)
nexus scan                         # scan completo
nexus scan --project nexus         # scan de um só
nexus scan --sync-project-config   # cria/sincroniza nexus.yaml e escaneia
nexus status nexus                 # detalhes
nexus note nexus "trabalhando"     # nota rápida
nexus edit nexus                   # editar campos + web config
nexus discover ~/projetos          # descobrir projetos
nexus push                         # publicar portal
nexus web-init                     # menu interativo para gerar prompt web
nexus web-init "Dragon Heir"       # gerar prompt web para projeto específico
```

## Resolução de projetos

Os comandos `status`, `edit`, `note`, `remove`, `web-init` aceitam uma query para identificar o projeto:

1. Match exato por path absoluto
2. Match exato por nome (case-insensitive)
3. Match parcial por nome ou path

Se ambíguo, lista opções. Não precisa ser o nome exato — "dragon" encontra "Dragon Heir".

## Arquivos de dados

Os dados ficam em um diretório separado (configurável via `NEXUS_DATA_DIR` ou `~/.config/nexus/local.yml`). Por padrão: `~/.nexus/data/`.

| Arquivo | Descrição |
|---------|-----------|
| `<data_dir>/projects.yml` | Registry — fonte de verdade, curada manualmente ou via CLI |
| `<data_dir>/data.json` | Dados de scan — auto-gerado, consumido pelo dashboard/TUI |
| `<projeto>/nexus.yaml` | Override local por projeto (schema completo com campos vazios) |
| `~/.config/nexus/local.yml` | Config local — define `data_dir` e overrides de path por máquina |

### `projects.yml`

```yaml
projects:
- path: /caminho/do/nexus
  name: nexus
  description: CLI para centralizar o status de projetos
  icon: 🐍
  category: ferramentas
  repo: henryavila/nexus
  added: '2026-02-20'
  web:
    route: /dh
    static_dir: app
    build_cmd: npm run build  # opcional
```

**Campos:** `path` (obrigatório), `name` (obrigatório), `description`, `icon`, `category`, `url`, `repo`, `status`, `note`, `added`, `web`.

### `nexus.yaml`

Arquivo local em cada projeto, criado automaticamente no `nexus add`.

Para garantir que todos os projetos tenham o schema completo, use:

```bash
nexus scan --sync-project-config
```

`--sync-project-config`:
- cria `nexus.yaml` se faltar
- mantém valores já preenchidos
- adiciona campos novos faltantes com `null`
- não copia o arquivo para o repositório Nexus nem para o portal web

Exemplo mínimo:

```yaml
schema_version: 1
project:
  path: null
  name: null
  description: null
  icon: null
  category: null
  url: null
  repo: null
  status: null
  note: null
  added: null
web:
  route: null
  static_dir: null
  build_cmd: null
local:
  path_override: null
```

### `local.yml` (fallback legado)

Para compatibilidade com setups antigos, ainda pode mapear paths entre máquinas:

```yaml
path_overrides:
  /mnt/e/OneDrive/Projeto: /home/user/Projeto
```

## Classes de projeto

Detectadas automaticamente no scan:

- **git** — Tem `.git/`. Fornece: branch, último commit, dirty status
- **filesystem** — Sem git (ex: pastas OneDrive). Fornece: último arquivo modificado

A **última atividade** usa o mais recente entre data do commit e data de modificação no filesystem.

## Status

- **active** — Padrão. Aparece na TUI e dashboard
- **archived** — Oculto na TUI/dashboard. Alterado via `nexus edit`

Staleness é mostrada pela data de última atividade, não pelo status.

## Health checks

| Check | Significado |
|-------|-------------|
| `path_exists` | Path acessível nesta máquina |
| `claude_memory_portable` | `true` = memória dentro do projeto (portável), `false` = só em ~/.claude (local) |
| `web_compliant` | Projeto tem output web gerado na pasta configurada |

Alertas aparecem na TUI e no dashboard quando algum check falha.

## Categorias

Padrão: `pessoal`, `trabalho`, `igreja`, `games`, `ferramentas`, `estudo`.

Novas categorias podem ser criadas no `add`/`edit`.

## TUI

Bare `nexus` abre o TUI (textual). Projetos são listados agrupados por categoria, com barra de alertas e filtro em tempo real.

Na abertura, carrega dados existentes imediatamente e roda scan em background com progresso no subtítulo.

### Keybindings

| Tecla  | Ação                          |
|--------|-------------------------------|
| Enter  | Lançar Claude Code no projeto |
| `e`    | Editar projeto                |
| `n`    | Adicionar nota                |
| `r`    | Remover projeto               |
| `/`    | Focar no filtro               |
| `q`    | Sair                          |

### Badges

- 🌐 — Projeto tem URL publicada
- 📡 — Projeto tem página web configurada no portal

### Símbolos de status

- `●` — Ativo, limpo
- `◐` — Git dirty (mudanças não commitadas)
- `◇` — Arquivado

Todas as ações interativas (edit, note, remove) suportam Ctrl+C para cancelar.

## Dashboard Web

Dashboard estático em `frontend/` (HTML/CSS/JS vanilla). Mobile-first, dark theme, responsivo.

- Busca/filtro em tempo real
- Cards agrupados por categoria
- Links para URL e GitHub
- Alertas de health checks
- Badge de web compliance

O dashboard lê `data.json` via fetch — requer servidor HTTP (não funciona via `file://`).

## Páginas web de projetos

Projetos podem ter páginas web individuais no portal. A config `web` no `projects.yml` define:

- **route** — Rota no portal (ex: `/dh`)
- **static_dir** — Pasta com o output estático (ex: `app`, `dist`)
- **build_cmd** — Comando de build opcional (ex: `npm run build`)

### Workflow

1. `nexus edit <projeto>` → habilitar web config
2. `nexus web-init <projeto>` → gerar o prompt `docs/nexus-web-prompt.md` no projeto
3. Usar o prompt com Claude para gerar a página web
4. `nexus push` → roda build + copia output para o portal

O `web-init` sem parâmetro lista projetos com web e permite escolher.

### Requisitos do output

- **Site 100% estático** — Sem dependência de runtime (PHP, Node, etc.)
- CDNs são permitidos
- Frameworks frontend são permitidos se o output for estático
- O `nexus push` executa o `build_cmd` automaticamente

## Portal (`web/`)

Repositório git separado em `web/` (no .gitignore do nexus). Hospedado no DigitalOcean Apps.

O `nexus push`:

1. Escaneia todos os projetos
2. Distribui template web para projetos que não o têm
3. Roda `build_cmd` dos projetos web
4. Copia `frontend/` → portal (dashboard)
5. Copia `data.json` → portal
6. Copia `static_dir/` → `portal/route/` (páginas de projeto)
7. Commit `[nexus-auto] update portal` + push

## Automação

### Git hook (instalado pelo `add`)

Após cada commit em um projeto registrado, roda scan em background:

```bash
python3 -m nexus scan --project "$(git rev-parse --show-toplevel)" 2>/dev/null &
```

O hook é idempotente — `nexus add` pode ser chamado várias vezes sem duplicar.

### Claude Code hook

Ver `AGENTS.md` para configuração.

### Cron (opcional)

```bash
*/30 * * * * cd /caminho/do/nexus && nexus push >> /tmp/nexus-push.log 2>&1
```

## Discover

`nexus discover <diretório>` busca projetos até 3 níveis de profundidade.

**Indicadores reconhecidos:** `.git`, `.claude`, `CLAUDE.md`, `AGENTS.md`, `CODEX.md`, `package.json`, `pyproject.toml`, `Cargo.toml`, `TODO.md`, `README.md`.

**Diretórios ignorados:** `node_modules`, `.git`, `venv`, `.venv`, `__pycache__`, `.next`, `dist`, `build`, `.cache`, `target`, `.tox`.

Para cada candidato, pergunta se deseja adicionar (interativo) ou pular.

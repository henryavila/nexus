# Nexus — Instruções para IA

## Básico

- **O que é**: CLI + TUI para catalogar, escanear e lançar projetos gerenciados por agentes IA
- **Stack**: Python 3.10+, typer (CLI), textual (TUI), PyYAML, dataclasses
- **Idioma**: pt-BR para UI/mensagens, inglês para código e nomes de variáveis
- **Dados**: `~/.nexus/data/` por padrão (configurável via `NEXUS_DATA_DIR` ou `~/.config/nexus/local.yml`)

## Arquitetura (v0.2)

```
nexus/
├── config.py              # NexusConfig — resolução de data_dir
├── constants.py            # domínios, naturezas, kinds
├── models/                 # dataclasses: Project, App, Idea, CodexEntry, Skill, Environment
├── repositories/           # YamlRepository, MarkdownRepository + concretas
├── services/               # ServiceContainer + serviços por entidade
├── infra/                  # file_lock, path_resolver, git_sync
├── cli/                    # typer CLI (entry point: nexus.cli:main)
├── tui/                    # Textual TUI (screens/, widgets/, app.py)
├── _legacy_main.py         # CLI antigo (features não portadas ainda)
├── codex_reader.py         # parsing de markdown (mantido)
├── slug.py                 # slugify / make_short_slug (mantido)
├── scanner.py              # scan_all, scan_one (não portado)
└── ...
```

## Comandos essenciais

```bash
# Instalar (editable, rodar na raiz do repo)
pipx install --editable . --force

# Primeira vez: inicializar dados
nexus init

# Migrar dados de diretório antigo
nexus migrate --from data

# Rodar testes (~991 testes)
python -m pytest tests/ -v

# Rodar só testes novos (unit)
python -m pytest tests/unit/ -v

# Rodar TUI
nexus tui

# CLI help
nexus --help
```

## Regras de código

- **Dispatch explícito**: action handlers usam `elif` por tab — **NUNCA else fallthrough**. Tab desconhecida → `self.notify("Ação não disponível", severity="warning")`
- **Safety-first**: confirmar ações destrutivas, sem silent fallthrough
- **Path sanitization**: `.strip("\"'")` em todos os inputs de path
- **Enter key**: NÃO usar `priority=True` no binding — quebra ModalScreen
- **TUI mutating actions**: chamam funções de comando diretamente (NÃO `main()`)
- **Background scan**: usa `threading.Thread(daemon=True)` (NÃO `run_worker`) para não bloquear `asyncio.run()` no exit
- **Sync no TUI**: ações usam `_tui_sync_background()` (daemon thread); apenas `_background_scan` usa `_tui_sync()` direto
- **scan_all**: aceita `cancelled` callback; verificar entre cada projeto
- **Novo código**: usar `ServiceContainer` para dados, NÃO acessar YAML/JSON diretamente
- **Novos comandos CLI**: adicionar em `nexus/cli/` usando typer
- **Modelos**: sempre usar dataclasses de `nexus/models/`, nunca dicts raw para dados novos

## Features não portadas (em _legacy_main.py)

- `cmd_discover` (recursive project finder)
- `cmd_push` / `cmd_web_init` (web portal)
- `cmd_open` (launch project in editor)
- `cmd_move` (project relocation)
- `cmd_project_replace`, `cmd_project_absorb`, `cmd_project_split`
- `cmd_project_convert_to_app`, `cmd_app_convert_to_project`
- `cmd_idea_promote` (idea → project/app)
- `cmd_codex_editor_*` (editor management)
- `cmd_skill_gaps` (skill coverage analysis)
- `_auto_update()` (update checker)
- `_cmd_add_interactive` (guided project creation)
- Full `scanner.py` logic (scan_project, scan_all, git/filesystem analysis)

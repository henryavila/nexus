from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from .cli_registry import detect_clis
from .environment import (
    find_environment, get_current_hostname, migrate_paths_from_registry,
    register_environment, register_environment_non_interactive, resolve_path_for_entry,
    set_environment_path,
)
from .hooks import install_claude_hook, install_git_hook, remove_claude_hook, remove_git_hook
from .project_config import apply_project_overrides, ensure_project_config, resolve_project_path
from .registry import (
    ProjectEntry, add_project, backfill_slugs, load_registry, move_project,
    remove_project, resolve_project, update_project, normalize_path,
)
from .ideas import (
    IdeaEntry, add_idea, load_ideas, remove_idea, resolve_idea,
    update_idea, _update_ideas_in_data_json,
)
from .codex import (
    CodexEntry, load_codex, save_codex_entry, remove_codex_entry,
    resolve_codex, sort_codex, _update_codex_in_data_json,
)
from .editors import (
    add_editor as editor_add, get_default_editor, load_editors,
    open_in_editor, pick_editor, save_editors,
)
from .scanner import read_data, scan_all, scan_one
from .sync import auto_sync_registry, quick_sync
from . import DEFAULT_DOMAINS, PROJECT_NATURES, CODEX_KINDS

_MUTATING_COMMANDS = {
    "add", "remove", "move", "edit", "note", "discover", "scan",
    "idea",  # covers idea add/edit/remove/promote
    "codex",  # covers codex add/edit/remove
    "env",  # covers env setup
    "app",  # covers app add/edit/remove
    "project",  # covers project replace/absorb/split
}

_COMMAND_SYNC_FILES = {
    "add":      ["data/projects.yml"],
    "remove":   ["data/projects.yml"],
    "move":     ["data/projects.yml"],
    "edit":     ["data/projects.yml"],
    "note":     ["data/projects.yml"],
    "discover": ["data/projects.yml", "data/apps.yml"],
    "idea":     ["data/ideas.yml", "data/projects.yml", "data/apps.yml"],
    "app":      ["data/apps.yml", "data/projects.yml"],
    "codex":    ["data/codex/"],
    "env":      ["data/environments.yml"],
    "project":  ["data/projects.yml", "data/apps.yml"],
    "scan":     None,  # full sync
}

def _safe_path_exists(path: str | Path) -> bool:
    try:
        return Path(path).exists()
    except OSError:
        return False


WEB_TEMPLATE = Path(__file__).resolve().parent.parent / "docs" / "nexus-web-prompt.md"
PORTAL_REPO_URL = ""  # configure via environment or local.yml


def _distribute_web_template(project_path: str, *, name: str = "", description: str = "",
                              domain: str = "", repo: str | None = None,
                              web: dict | None = None, force: bool = False) -> None:
    """Copy nexus-web-prompt.md to a project's docs/, filling in project context."""
    if not WEB_TEMPLATE.exists() or not web:
        return
    dest = Path(project_path) / "docs" / "nexus-web-prompt.md"
    if (force or not _safe_path_exists(dest)) and _safe_path_exists(project_path):
        route = web.get("route", "")
        static_dir = web.get("static_dir", "dist")
        build_cmd = web.get("build_cmd")

        content = WEB_TEMPLATE.read_text(encoding="utf-8")
        content = content.replace("{{name}}", name or Path(project_path).name)
        content = content.replace("{{description}}", description or "")
        content = content.replace("{{domain}}", domain or "")
        content = content.replace("{{route}}", route)
        content = content.replace("{{static_dir}}", static_dir)

        # Conditional lines
        content = content.replace("{{repo_line}}",
                                  f"| **Repo** | `{repo}` |\n" if repo else "")
        content = content.replace("{{build_line}}",
                                  f"| **Comando de build** | `{build_cmd}` |\n" if build_cmd else "")
        content = content.replace("{{build_section}}",
                                  f"- O build é executado com `{build_cmd}` (o `nexus push` roda automaticamente)\n"
                                  if build_cmd else "")

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        print(f"  Template web copiado para {dest}")

DISCOVERY_INDICATORS = [
    ".git", ".claude", "CLAUDE.md", "AGENTS.md", "CODEX.md",
    "package.json", "pyproject.toml", "Cargo.toml",
    "TODO.md", "README.md",
]


def _format_rel_date(iso_date: str | None) -> str:
    if not iso_date:
        return "n/a"
    try:
        d = datetime.fromisoformat(iso_date).date()
        days = (datetime.now().date() - d).days
        if days <= 0:
            return "today"
        if days == 1:
            return "1d ago"
        return f"{days}d ago"
    except ValueError:
        return iso_date


def _prompt_choice(prompt: str, options: list[str], allow_new: bool = False) -> str:
    print(prompt)
    for i, opt in enumerate(options, 1):
        print(f"  {i}) {opt}")
    if allow_new:
        print(f"  {len(options) + 1}) (criar nova)")
    while True:
        raw = input("> ").strip()
        if not raw:
            return options[0]
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(options):
                return options[idx - 1]
            if allow_new and idx == len(options) + 1:
                return input("Nova categoria: ").strip()
        elif raw in options:
            return raw
        print("Opção inválida. Tente novamente.")


def _detect_repo(path: str) -> str | None:
    """Auto-detect GitHub repo from git remote."""
    import re as _re
    if _safe_path_exists(Path(path) / ".git"):
        remote = subprocess.run(
            ["git", "remote", "get-url", "origin"], cwd=path,
            capture_output=True, text=True
        ).stdout.strip()
        if "github.com" in remote:
            m = _re.search(r"github\.com[:/]([^/]+/[^/.]+)", remote)
            if m:
                return m.group(1)
    return None


def _match_known_entry_for_path(path: str) -> tuple[str | None, object | None]:
    """Infer a known project or app from a local path."""
    from .apps import load_apps

    norm = normalize_path(path)
    repo = _detect_repo(norm)
    basename = Path(norm).name.lower()

    for entry in load_registry():
        if entry.path and normalize_path(entry.path) == norm:
            return "project", entry
        if repo and entry.repo == repo:
            return "project", entry
        if entry.slug and entry.slug.lower() == basename:
            return "project", entry
        if entry.name.lower() == basename:
            return "project", entry

    for entry in load_apps():
        if repo and entry.github == repo:
            return "app", entry
        if entry.slug and entry.slug.lower() == basename:
            return "app", entry
        if entry.name.lower() == basename:
            return "app", entry

    return None, None


def _launch_cli_in_path(path: str, *, name: str, icon: str | None, shell: bool = False) -> int:
    """Launch shell or AI CLI in a resolved local directory."""
    clis = detect_clis()
    if not clis:
        print("Nenhum AI CLI encontrado no PATH (claude, codex, opencode).")
        return 1

    if shell:
        shell_cmd = os.environ.get("SHELL", "/bin/bash")
        os.chdir(path)
        os.execvp(shell_cmd, [shell_cmd])
        return 0  # unreachable

    print(f"Abrindo: {icon or ''} {name} ({path})\n")
    print("CLIs disponíveis:")
    for i, c in enumerate(clis, 1):
        default_marker = " (padrão)" if i == 1 else ""
        print(f"  {i}) {c.label}{default_marker}")
    print("  0) Shell (abrir na pasta)")
    try:
        choice = input("\nEscolha [1]: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelado.")
        return 0
    if not choice:
        choice = "1"
    if choice == "0":
        shell_cmd = os.environ.get("SHELL", "/bin/bash")
        os.chdir(path)
        os.execvp(shell_cmd, [shell_cmd])
        return 0  # unreachable
    if not choice.isdigit() or not (1 <= int(choice) <= len(clis)):
        print("Opção inválida.")
        return 1

    cli = clis[int(choice) - 1]
    os.chdir(path)
    os.execvp(cli.cmd, [cli.cmd])
    return 0  # unreachable


def _quick_add_project(norm: str, *, name: str | None = None, description: str = "",
                       domain: str = "pessoal", nature: str = "contexto",
                       private: bool = False, icon: str | None = None,
                       url: str | None = None, repo: str | None = None,
                       silent: bool = False) -> tuple[bool, ProjectEntry]:
    """Quick add a project with zero prompts. Returns (created, entry)."""
    if not name:
        name = Path(norm).name
    if not repo:
        repo = _detect_repo(norm)
        if repo and not silent:
            print(f"  Repo detectado: {repo}")

    entry = ProjectEntry(
        path=norm,
        name=name,
        description=description,
        icon=icon,
        domain=domain,
        nature=nature,
        private=private,
        url=url,
        repo=repo,
    )

    created, entry = add_project(entry)
    if not silent:
        if created:
            print(f"Adicionado: {entry.name} ({entry.path})")
        else:
            print(f"Projeto já registrado: {entry.path}")

    add_resolved = resolve_path_for_entry(entry.slug, entry.path)
    if add_resolved:
        resolved = resolve_project_path(add_resolved)
        cfg_created, cfg_updated = ensure_project_config(resolved)
        if not silent:
            if cfg_created:
                print("  Arquivo nexus.yaml criado.")
            elif cfg_updated:
                print("  Arquivo nexus.yaml sincronizado.")

        hook_path = resolved
        if install_git_hook(hook_path):
            if not silent:
                print("  Git post-commit hook instalado.")
        if install_claude_hook(hook_path):
            if not silent:
                print("  Claude Code hook instalado.")

    return created, entry


def cmd_add(args: argparse.Namespace) -> int:
    interactive = getattr(args, "interactive", False)
    target_path = getattr(args, "path", None)

    # Determine mode: flags present without -i = inline; no path no flags = interactive
    has_inline_flags = any(getattr(args, f, None) is not None for f in
                          ["name", "description", "domain", "nature", "icon", "repo", "url"])
    has_private_flag = getattr(args, "private", False)
    has_inline_flags = has_inline_flags or has_private_flag

    if has_inline_flags and not target_path:
        print("Erro: path é obrigatório no modo inline.")
        return 1

    if interactive or (not target_path and not has_inline_flags):
        # Interactive mode (legacy)
        return _cmd_add_interactive(args)

    # Quick add mode (path provided)
    target_path = target_path.strip("\"'")
    norm = str(Path(target_path).expanduser().resolve())
    if not _safe_path_exists(norm):
        print(f"Path não existe: {norm}")
        return 1

    created, entry = _quick_add_project(
        norm,
        name=getattr(args, "name", None),
        description=getattr(args, "description", None) or "",
        domain=getattr(args, "domain", None) or "pessoal",
        nature=getattr(args, "nature", None) or "contexto",
        private=getattr(args, "private", False),
        icon=getattr(args, "icon", None),
        url=getattr(args, "url", None),
        repo=getattr(args, "repo", None),
    )
    return 0


def _cmd_add_interactive(args: argparse.Namespace) -> int:
    """Legacy interactive add mode."""
    target_path = getattr(args, "path", None) or "."
    norm = str(Path(target_path).expanduser().resolve())

    if not _safe_path_exists(norm):
        print(f"Path não existe: {norm}")
        return 1

    try:
        default_name = Path(norm).name
        name = input(f"Nome [{default_name}]: ").strip() or default_name
        description = input("Descrição: ").strip()

        existing_domains = list(set(DEFAULT_DOMAINS + [e.domain for e in load_registry() if e.domain]))
        domain = _prompt_choice("Domínio:", sorted(existing_domains))

        nature = _prompt_choice("Natureza:", PROJECT_NATURES)

        icon = input("Ícone (emoji, Enter para pular): ").strip() or None
        url = input("URL publicada (Enter para pular): ").strip() or None

        repo = _detect_repo(norm)
        if repo:
            print(f"  Repo detectado: {repo}")
        if not repo:
            repo = input("Repo (namespace git, Enter para pular): ").strip() or None

        has_web = input("Configurar página web no portal? (não precisa de URL) [s/N]: ").strip().lower() == "s"
        web = None
        if has_web:
            route = input("Rota (ex: /dh): ").strip()
            static_dir = input("Pasta do build estático (ex: dist): ").strip() or "dist"
            build_cmd = input("Comando de build (Enter para pular): ").strip() or None
            web = {"route": route, "static_dir": static_dir}
            if build_cmd:
                web["build_cmd"] = build_cmd
            _distribute_web_template(norm, name=name, description=description,
                                      domain=domain, repo=repo, web=web)
    except (KeyboardInterrupt, EOFError):
        print("\nCancelado.")
        return 0

    entry = ProjectEntry(
        path=norm,
        name=name,
        description=description,
        icon=icon,
        domain=domain,
        nature=nature,
        url=url,
        repo=repo,
        web=web,
    )

    created, entry = add_project(entry)
    if created:
        print(f"Adicionado: {entry.name} ({entry.path})")
    else:
        print(f"Projeto já registrado: {entry.path}")

    add_resolved = resolve_path_for_entry(entry.slug, entry.path)
    if add_resolved:
        resolved = resolve_project_path(add_resolved)
        cfg_created, cfg_updated = ensure_project_config(resolved)
        if cfg_created:
            print("  Arquivo nexus.yaml criado.")
        elif cfg_updated:
            print("  Arquivo nexus.yaml sincronizado.")

        hook_path = resolved
        if install_git_hook(hook_path):
            print("  Git post-commit hook instalado.")
        if install_claude_hook(hook_path):
            print("  Claude Code hook instalado.")

    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    matched, ambiguous = resolve_project(args.query)
    if ambiguous:
        print("Projeto ambíguo. Matches:")
        for e in ambiguous:
            print(f"  - {e.name}: {e.path}")
        return 1
    if not matched:
        print("Projeto não encontrado.")
        return 1

    resolved = resolve_path_for_entry(matched.slug, matched.path)
    if resolved:
        hook_path = resolve_project_path(resolved)
        remove_git_hook(hook_path)
        remove_claude_hook(hook_path)
    ok = remove_project(matched.name if not matched.path else matched.path)
    if not ok:
        print("Projeto não encontrado.")
        return 1

    print(f"Removido: {matched.name} ({resolved or matched.path})")
    return 0


def cmd_move(args: argparse.Namespace) -> int:
    matched, ambiguous = resolve_project(args.query)
    if ambiguous:
        print("Projeto ambíguo. Matches:")
        for e in ambiguous:
            print(f"  - {e.name}: {e.path}")
        return 1
    if not matched:
        print("Projeto não encontrado.")
        return 1

    new_path = args.new_path

    if not new_path:
        # Auto-discover
        from .relocate import find_moved_project
        old_path = resolve_path_for_entry(matched.slug, matched.path)
        if not old_path:
            print(f"Erro: {matched.name} não tem path neste environment.")
            try:
                new_path = input("Informe o novo path (Enter para cancelar): ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nCancelado.")
                return 0
            if not new_path:
                return 0
        else:
            print(f"Procurando {matched.name} nas proximidades de {old_path}...")
            candidates = find_moved_project(old_path)
            if not candidates:
                print("Não encontrado automaticamente.")
                try:
                    new_path = input("Informe o novo path (Enter para cancelar): ").strip()
                except (KeyboardInterrupt, EOFError):
                    print("\nCancelado.")
                    return 0
                if not new_path:
                    return 0
            elif len(candidates) == 1:
                print(f"🔍 Encontrado: {candidates[0]}")
                try:
                    confirm = input("Usar este path? [S/n]: ").strip().lower()
                except (KeyboardInterrupt, EOFError):
                    print("\nCancelado.")
                    return 0
                if confirm == "n":
                    return 0
                new_path = candidates[0]
            else:
                print("🔍 Vários candidatos:")
                for i, c in enumerate(candidates, 1):
                    print(f"  {i}) {c}")
                try:
                    choice = input("> ").strip()
                except (KeyboardInterrupt, EOFError):
                    print("\nCancelado.")
                    return 0
                if choice.isdigit() and 1 <= int(choice) <= len(candidates):
                    new_path = candidates[int(choice) - 1]
                else:
                    print("Opção inválida.")
                    return 1

    new_path = str(Path(new_path).expanduser().resolve())
    if not _safe_path_exists(new_path):
        print(f"Novo path não existe: {new_path}")
        return 1

    result = move_project(matched.path, new_path)
    if not result:
        print("Erro ao atualizar registro (path já registrado ou projeto não encontrado).")
        return 1

    print(f"Path atualizado: {result.name}")
    print(f"  {matched.path} → {new_path}")

    # Ensure nexus.yaml and hooks at new location
    resolved = resolve_project_path(new_path)
    cfg_created, cfg_updated = ensure_project_config(resolved)
    if cfg_created:
        print("  Arquivo nexus.yaml criado.")
    elif cfg_updated:
        print("  Arquivo nexus.yaml sincronizado.")

    if install_git_hook(resolved):
        print("  Git post-commit hook instalado.")
    if install_claude_hook(resolved):
        print("  Claude Code hook instalado.")

    # Rescan the project at new location
    scan_result = scan_one(new_path)
    if scan_result:
        print("  Rescan OK.")
    else:
        print("  ⚠ Rescan falhou (o projeto será escaneado no próximo 'nexus scan').")

    return 0


def cmd_list(args: argparse.Namespace) -> int:
    entries = [apply_project_overrides(e) for e in load_registry()]
    show_all = getattr(args, "all", False)
    if not show_all:
        entries = [e for e in entries if e.status not in ("archived", "replaced")]
    entries.sort(key=lambda e: e.added or "", reverse=True)

    if not entries:
        print("Nenhum projeto registrado.")
        return 0

    # Build rows and calculate column widths
    headers = ("SLUG", "NOME", "DOMÍNIO", "NATUREZA", "ADDED")
    rows = []
    for e in entries:
        icon = e.icon or ""
        private_badge = " \U0001F512" if e.private and e.nature == "ferramenta" else ""
        rows.append((
            e.slug or "-",
            f"{icon} {e.name}{private_badge}" if icon else f"{e.name}{private_badge}",
            e.domain,
            e.nature,
            e.added or "-",
        ))

    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    print(fmt.format(*headers))
    print("  ".join("─" * w for w in widths))
    for e, row in zip(entries, rows):
        print(fmt.format(*row))
    print(f"\n{len(entries)} projeto(s)")
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    def _sync_entry_config(entry: ProjectEntry) -> None:
        resolved = resolve_path_for_entry(entry.slug, entry.path)
        if not resolved:
            return
        target = resolve_project_path(resolved)
        created, updated = ensure_project_config(target)
        if created:
            print(f"  {entry.name}: nexus.yaml criado.")
        elif updated:
            print(f"  {entry.name}: nexus.yaml sincronizado.")

    # Environment onboarding check
    env = find_environment()
    if env is None:
        hostname = get_current_hostname()
        if sys.stdin.isatty():
            print("Novo ambiente detectado!")
            print(f"Hostname: {hostname}")
            name = input("Nome para este ambiente: ").strip() or hostname
            location = input("Localização (casa/trabalho/outro): ").strip() or "unknown"
            migrate_paths_from_registry(name, location)
            print(f"  Ambiente '{name}' registrado com paths migrados do registry.")
        else:
            register_environment_non_interactive()

    if args.project:
        matched, ambiguous = resolve_project(args.project)
        if ambiguous:
            print("Projeto ambíguo. Matches:")
            for e in ambiguous:
                print(f"  - {e.name}: {e.path}")
            return 1

        target = args.project
        if matched:
            target = resolve_path_for_entry(matched.slug, matched.path) or matched.path
            if args.sync_project_config:
                _sync_entry_config(matched)
        elif _safe_path_exists(args.project):
            inferred_kind, inferred_entry = _match_known_entry_for_path(args.project)
            if inferred_entry and inferred_entry.slug:
                norm_target = normalize_path(args.project)
                set_environment_path(get_current_hostname(), inferred_entry.slug, norm_target)
                if inferred_kind == "project":
                    matched = inferred_entry
                    target = resolve_path_for_entry(matched.slug, matched.path) or matched.path
                    if args.sync_project_config:
                        _sync_entry_config(matched)
                else:
                    print(f"Path registrado para app '{inferred_entry.name}' neste environment.")
                    return 0
        elif args.sync_project_config and _safe_path_exists(args.project):
            created, updated = ensure_project_config(resolve_project_path(args.project))
            if created:
                print("  nexus.yaml criado.")
            elif updated:
                print("  nexus.yaml sincronizado.")

        if not target:
            print("Skipped: projeto sem path neste environment.")
            return 0
        result = scan_one(target)
        if result is None:
            print("Skipped: projeto não registrado ou inacessível.")
            return 0
        print(f"Scanned: {result['name']}")
        return 0

    # Ensure hooks are installed on all projects
    hooks_installed = 0
    for entry in load_registry():
        if args.sync_project_config:
            _sync_entry_config(entry)
        resolved = resolve_path_for_entry(entry.slug, entry.path)
        if not resolved:
            continue
        hook_path = resolve_project_path(resolved)
        if install_git_hook(hook_path):
            hooks_installed += 1
        if install_claude_hook(hook_path):
            hooks_installed += 1
    if hooks_installed:
        print(f"  {hooks_installed} hook(s) instalado(s).")

    backfilled = backfill_slugs()
    if backfilled:
        print(f"  {backfilled} slug(s) gerados.")

    def _progress(i, total, name):
        print(f"  [{i}/{total}] {name}...", flush=True)

    data = scan_all(on_progress=_progress)
    print(f"Scanned {len(data.get('projects', []))} projeto(s).")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    matched, ambiguous = resolve_project(args.query)
    if ambiguous:
        print("Projeto ambíguo. Matches:")
        for e in ambiguous:
            print(f"  - {e.name}: {e.path}")
        return 1
    if not matched:
        print("Projeto não encontrado.")
        return 1

    effective = apply_project_overrides(matched)
    env_path = resolve_path_for_entry(matched.slug, matched.path)
    resolved_path = resolve_project_path(env_path) if env_path else None

    print(f"Nome: {effective.name}")
    print(f"Path: {resolved_path or '(sem path neste environment)'}")
    if matched.path and resolved_path and normalize_path(resolved_path) != normalize_path(matched.path):
        print(f"Path registry: {matched.path}")
    print(f"Descrição: {effective.description}")
    print(f"Domínio: {effective.domain}")
    print(f"Natureza: {effective.nature}")
    if effective.private and effective.nature == "ferramenta":
        print("Privado: sim")
    if effective.icon:
        print(f"Ícone: {effective.icon}")
    if effective.url:
        print(f"URL: {effective.url}")
    if effective.repo:
        print(f"Repo: {effective.repo}")
    if effective.note:
        print(f"Nota: {effective.note}")
    print(f"Status: {effective.status or 'active'}")

    data = read_data()
    target_registry = normalize_path(matched.path) if matched.path else ""
    target_resolved = normalize_path(resolved_path) if resolved_path else ""
    proj = None
    for p in data.get("projects", []):
        if normalize_path(p.get("path", "")) in {target_registry, target_resolved}:
            proj = p
            break

    if proj:
        print(f"Classe: {proj.get('class')}")
        print(f"Última atividade: {_format_rel_date(proj.get('last_activity'))}")
        git = proj.get("git") or {}
        if git:
            print(f"Branch: {git.get('branch')}  Dirty: {git.get('dirty')}")
            print(f"Último commit: {git.get('last_commit_date')} — {git.get('last_commit_message')}")
        health = proj.get("health") or {}
        from .scanner import get_health_value
        if get_health_value(health, "claude_memory_portable") is False:
            print("⚠  Memória do Claude está LOCAL (não portável)")
        if get_health_value(health, "path_exists") is False:
            print("⚠  Path não existe nesta máquina")
    else:
        print("(sem dados de scan — execute: nexus scan)")

    return 0


def cmd_edit(args: argparse.Namespace) -> int:
    matched, ambiguous = resolve_project(args.query)
    if ambiguous:
        print("Projeto ambíguo. Matches:")
        for e in ambiguous:
            print(f"  - {e.name}: {e.path}")
        return 1
    if not matched:
        print("Projeto não encontrado.")
        return 1

    # Check for inline flags
    inline_fields = {}
    for field in ["name", "slug", "description", "domain", "nature", "icon", "url", "repo", "status", "note"]:
        val = getattr(args, field, None)
        if val is not None:
            inline_fields[field] = val
    if getattr(args, "private", False):
        inline_fields["private"] = True
    if getattr(args, "no_private", False):
        inline_fields["private"] = False

    if inline_fields:
        # Inline edit mode — apply directly
        result = update_project(matched.path or matched.name, **inline_fields)
        if result:
            print(f"Atualizado: {result.name}")
        return 0

    # Interactive edit mode (legacy)
    print(f"Editando: {matched.name}")
    print("(Enter para manter valor atual, Ctrl+C para cancelar)\n")

    try:
        name = input(f"Nome [{matched.name}]: ").strip() or matched.name
        slug = input(f"Slug [{matched.slug}]: ").strip() or matched.slug
        description = input(f"Descrição [{matched.description}]: ").strip() or matched.description
        icon = input(f"Ícone [{matched.icon or ''}]: ").strip() or matched.icon
        url = input(f"URL [{matched.url or ''}]: ").strip() or matched.url
        repo = input(f"Repo [{matched.repo or ''}]: ").strip() or matched.repo

        existing_domains = list(set(DEFAULT_DOMAINS + [e.domain for e in load_registry() if e.domain]))
        sorted_domains = sorted(existing_domains)
        if matched.domain in sorted_domains:
            sorted_domains.remove(matched.domain)
        sorted_domains.insert(0, matched.domain)
        print(f"\nDomínio atual: {matched.domain}")
        domain = _prompt_choice("Domínio (Enter=manter):", sorted_domains)

        sorted_natures = list(PROJECT_NATURES)
        if matched.nature in sorted_natures:
            sorted_natures.remove(matched.nature)
        sorted_natures.insert(0, matched.nature)
        print(f"\nNatureza atual: {matched.nature}")
        nature = _prompt_choice("Natureza (Enter=manter):", sorted_natures)

        status_input = input(f"Status [{matched.status or 'active'}] (active/archived/replaced): ").strip()
        status = status_input if status_input in ("active", "archived", "replaced") else matched.status

        # Web config
        web = matched.web
        if web:
            print(f"\nWeb atual: rota={web.get('route')}, dir={web.get('static_dir')}, build={web.get('build_cmd', 'n/a')}")
            edit_web = input("Editar config web? [s/N]: ").strip().lower() == "s"
            if edit_web:
                remove_web = input("Remover config web? [s/N]: ").strip().lower() == "s"
                if remove_web:
                    web = None
                else:
                    route = input(f"Rota [{web.get('route', '')}]: ").strip() or web.get('route', '')
                    static_dir = input(f"Dir estático [{web.get('static_dir', 'dist')}]: ").strip() or web.get('static_dir', 'dist')
                    build_cmd = input(f"Comando build [{web.get('build_cmd', '')}]: ").strip() or web.get('build_cmd')
                    web = {"route": route, "static_dir": static_dir}
                    if build_cmd:
                        web["build_cmd"] = build_cmd
        else:
            has_web = input("\nConfigurar página web no portal? [s/N]: ").strip().lower() == "s"
            if has_web:
                route = input("Rota (ex: /dh): ").strip()
                static_dir = input("Pasta do build estático (ex: dist): ").strip() or "dist"
                build_cmd = input("Comando de build (Enter para pular): ").strip() or None
                web = {"route": route, "static_dir": static_dir}
                if build_cmd:
                    web["build_cmd"] = build_cmd
                edit_resolved = resolve_path_for_entry(matched.slug, matched.path)
                if edit_resolved:
                    _distribute_web_template(resolve_project_path(edit_resolved), name=name, description=description,
                                              domain=domain, repo=repo, web=web)
    except (KeyboardInterrupt, EOFError):
        print("\nCancelado.")
        return 0

    result = update_project(
        matched.path or matched.name,
        name=name,
        slug=slug,
        description=description,
        icon=icon,
        url=url,
        repo=repo,
        domain=domain,
        nature=nature,
        status=status if status != "active" else None,
        web=web,
    )

    if result:
        print(f"Atualizado: {result.name}")
        edit_resolved = resolve_path_for_entry(result.slug, result.path)
        if edit_resolved:
            resolved = resolve_project_path(edit_resolved)
            cfg_created, cfg_updated = ensure_project_config(resolved)
            if cfg_created:
                print("  Arquivo nexus.yaml criado.")
            elif cfg_updated:
                print("  Arquivo nexus.yaml sincronizado.")
    return 0


def cmd_note(args: argparse.Namespace) -> int:
    matched, ambiguous = resolve_project(args.query)
    if ambiguous:
        print("Projeto ambíguo. Matches:")
        for e in ambiguous:
            print(f"  - {e.name}: {e.path}")
        return 1
    if not matched:
        print("Projeto não encontrado.")
        return 1

    result = update_project(matched.path or matched.name, note=args.text)
    if result:
        print(f"Nota atualizada: {result.name} → \"{args.text}\"")
    return 0


def cmd_discover(args: argparse.Namespace) -> int:
    root = Path(args.path).expanduser().resolve()
    if not _safe_path_exists(root):
        print(f"Path não existe: {root}")
        return 1

    registered_paths = {
        normalize_path(e.path) for e in load_registry() if e.path
    }

    from . import EXCLUDED_DIRS
    skip_dirs = EXCLUDED_DIRS
    max_depth = 3
    candidates = []

    def _walk(directory: Path, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            children = sorted(directory.iterdir())
        except PermissionError:
            return
        for child in children:
            if not child.is_dir() or child.name in skip_dirs or child.name.startswith("."):
                continue
            indicators = [ind for ind in DISCOVERY_INDICATORS if _safe_path_exists(child / ind)]
            if indicators:
                candidates.append((child, indicators))
            else:
                _walk(child, depth + 1)

    _walk(root, 1)

    if not candidates:
        print("Nenhum projeto encontrado.")
        return 0

    print(f"Encontrados {len(candidates)} candidato(s):\n")
    added_projects = 0
    added_apps = 0
    for path, indicators in candidates:
        if normalize_path(str(path)) in registered_paths:
            print(f"  [já registrado] {path.name} ({path})")
            continue

        print(f"  {path.name} ({path})")
        print(f"    Indicadores: {', '.join(indicators)}")
        choice = input("    Adicionar como [p]rojeto, [a]pp ou [N]ão? (q=sair): ").strip().lower()
        if choice == "q":
            break
        if choice == "p":
            print(f"\n--- Registrando {path.name} ---")
            ns = argparse.Namespace(path=str(path))
            cmd_add(ns)
            added_projects += 1
            print()
        elif choice == "a":
            print(f"\n--- Registrando app {path.name} ---")
            cmd_app_add(default_name=path.name)
            added_apps += 1
            print()

    print(f"\n{added_projects} projeto(s) e {added_apps} app(s) adicionado(s).")
    return 0


def cmd_push(args: argparse.Namespace) -> int:
    from . import NEXUS_ROOT
    from .sync import pull_rebase

    # Sync nexus repo (get latest projects.yml)
    print("Sincronizando nexus repo...")
    ok, msg = pull_rebase(str(NEXUS_ROOT))
    if not ok:
        print(f"  ⚠  Sync nexus falhou: {msg}")
        print("  Resolva o conflito manualmente e tente novamente.")
        return 1
    print(f"  {msg}")

    def _progress(i, total, name):
        print(f"  [{i}/{total}] {name}...", flush=True)

    print("Scanning...")
    data = scan_all(on_progress=_progress)
    print(f"  {len(data.get('projects', []))} projeto(s) escaneados.")

    entries = [apply_project_overrides(e) for e in load_registry()]
    web_entries = [e for e in entries if e.web]

    # Distribute web template to web-enabled projects
    for entry in web_entries:
        push_resolved = resolve_path_for_entry(entry.slug, entry.path)
        if push_resolved:
            _distribute_web_template(resolve_project_path(push_resolved), name=entry.name, description=entry.description,
                                      domain=entry.domain, repo=entry.repo, web=entry.web)

    for entry in web_entries:
        web = entry.web
        push_resolved = resolve_path_for_entry(entry.slug, entry.path)
        if not push_resolved:
            continue
        project_path = Path(resolve_project_path(push_resolved))
        build_cmd = web.get("build_cmd")
        if build_cmd and _safe_path_exists(project_path):
            print(f"  Building {entry.name}...")
            result = subprocess.run(build_cmd, shell=True, cwd=str(project_path), capture_output=True, text=True)
            if result.returncode != 0:
                print(f"  ⚠  Build falhou para {entry.name}: {result.stderr[:200]}")

    portal = NEXUS_ROOT / "web"

    if not portal.exists():
        print("  Clonando portal repo...")
        subprocess.run(["git", "clone", PORTAL_REPO_URL, str(portal)], capture_output=True)

    if not portal.exists():
        print("Erro: portal repo não disponível.")
        return 1

    # Sync portal before committing
    print("Sincronizando portal...")
    ok, msg = pull_rebase(str(portal))
    if not ok:
        print(f"  ⚠  Sync portal falhou: {msg}")
        return 1

    import shutil
    from . import DATA_JSON

    frontend_src = NEXUS_ROOT / "frontend"
    if frontend_src.exists():
        for item in frontend_src.iterdir():
            dest = portal / item.name
            if item.is_dir():
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)

    shutil.copy2(str(DATA_JSON), str(portal / "data.json"))

    # Cache-busting: append content hash to CSS/JS references in index.html
    import hashlib, re
    portal_index = portal / "index.html"
    if portal_index.exists():
        html_text = portal_index.read_text()
        def _add_hash(m):
            attr, path = m.group(1), m.group(2)
            asset = portal / path
            if asset.exists():
                h = hashlib.md5(asset.read_bytes()).hexdigest()[:8]
                return f'{attr}="{path}?v={h}"'
            return m.group(0)
        html_text = re.sub(r'(href|src)="((?:css|js)/[^"]+)"', _add_hash, html_text)
        portal_index.write_text(html_text)

    for entry in web_entries:
        web = entry.web
        route = web.get("route", "").lstrip("/")
        push_resolved = resolve_path_for_entry(entry.slug, entry.path)
        if not push_resolved:
            continue
        static_dir = Path(resolve_project_path(push_resolved)) / web.get("static_dir", "dist")
        dest = portal / route
        if _safe_path_exists(static_dir):
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(str(static_dir), str(dest))
            print(f"  Copiado {entry.name} → {route}/")

    subprocess.run(["git", "add", "-A"], cwd=str(portal), capture_output=True)
    diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=str(portal), capture_output=True)
    if diff.returncode == 0:
        print("Nenhuma mudança no portal.")
        return 0

    subprocess.run(
        ["git", "commit", "-m", "[nexus-auto] update portal"],
        cwd=str(portal), capture_output=True
    )

    remote = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=str(portal), capture_output=True, text=True
    )
    if remote.returncode == 0:
        result = subprocess.run(["git", "push"], cwd=str(portal), capture_output=True, text=True)
        if result.returncode != 0:
            # Retry: pull --rebase then push again
            print("  Push falhou, tentando sync...")
            ok, msg = pull_rebase(str(portal))
            if ok:
                result = subprocess.run(["git", "push"], cwd=str(portal), capture_output=True, text=True)
            if result.returncode != 0:
                print(f"  Push falhou após retry: {result.stderr[:200]}")
                return 1
        print("Portal publicado com sucesso.")
    else:
        print("Portal commitado localmente (sem remote configurado).")

    return 0


def cmd_web_init(args: argparse.Namespace) -> int:
    """Generate or regenerate the web prompt template for a project."""
    query = getattr(args, "query", None)

    if query:
        matched, ambiguous = resolve_project(query)
        if ambiguous:
            print("Projeto ambíguo. Matches:")
            for e in ambiguous:
                print(f"  - {e.name}: {e.path}")
            return 1
        if not matched:
            print("Projeto não encontrado.")
            return 1
        entries = [matched]
    else:
        all_entries = load_registry()
        web_entries = [e for e in all_entries if e.web]
        if not web_entries:
            print("Nenhum projeto com config web. Use 'nexus edit <projeto>' para configurar.")
            return 0
        print("Projetos com web configurado:\n")
        for i, e in enumerate(web_entries, 1):
            route = e.web.get("route", "?")
            print(f"  {i}) {e.name}  ({route})")
        print(f"  a) Todos")
        try:
            choice = input("\nEscolha (número ou 'a'): ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nCancelado.")
            return 0
        if choice == "a":
            entries = web_entries
        elif choice.isdigit() and 1 <= int(choice) <= len(web_entries):
            entries = [web_entries[int(choice) - 1]]
        else:
            print("Opção inválida.")
            return 1

    for entry in entries:
        if not entry.web:
            print(f"  {entry.name}: sem config web. Use 'nexus edit {entry.name}' para configurar.")
            continue
        wi_resolved = resolve_path_for_entry(entry.slug, entry.path)
        if not wi_resolved:
            print(f"  {entry.name}: sem path neste environment.")
            continue
        _distribute_web_template(resolve_project_path(wi_resolved), name=entry.name, description=entry.description,
                                  domain=entry.domain, repo=entry.repo,
                                  web=entry.web, force=True)
    return 0


def cmd_idea(args: argparse.Namespace) -> int:
    if not hasattr(args, "idea_command") or args.idea_command is None:
        print("Uso: nexus idea {add,edit,remove,promote}")
        return 1
    return args.idea_func(args)


def cmd_idea_add(args: argparse.Namespace) -> int:
    from . import IDEA_PRIORITIES

    interactive = getattr(args, "interactive", False)

    # Check for inline flags
    has_inline = getattr(args, "title", None) is not None

    if has_inline and not interactive:
        # Inline mode
        title = args.title
        if not title:
            print("Título é obrigatório.")
            return 1
        entry = IdeaEntry(
            title=title,
            description=getattr(args, "description", None) or "",
            domain=getattr(args, "domain", None) or "pessoal",
            priority=getattr(args, "priority", None) or "medium",
            notes=getattr(args, "note", None),
        )
        result = add_idea(entry)
        _update_ideas_in_data_json()
        print(f"Ideia adicionada: {result.title} (id: {result.id})")
        return 0

    # Interactive mode (legacy)
    try:
        title = input("Título: ").strip()
        if not title:
            print("Título é obrigatório.")
            return 1
        description = input("Descrição: ").strip()
        existing_domains = list(set(DEFAULT_DOMAINS + [e.domain for e in load_ideas() if e.domain]))
        domain = _prompt_choice("Domínio:", sorted(existing_domains))
        priority = _prompt_choice("Prioridade:", IDEA_PRIORITIES)
        refs_raw = input("Referências (separadas por vírgula, Enter para pular): ").strip()
        references = [r.strip() for r in refs_raw.split(",") if r.strip()] if refs_raw else None
        notes = input("Notas (Enter para pular): ").strip() or None
    except (KeyboardInterrupt, EOFError):
        print("\nCancelado.")
        return 0

    entry = IdeaEntry(
        title=title,
        description=description,
        domain=domain,
        priority=priority,
        references=references,
        notes=notes,
    )
    result = add_idea(entry)
    _update_ideas_in_data_json()
    print(f"Ideia adicionada: {result.title} (id: {result.id})")
    return 0


def cmd_idea_edit(args: argparse.Namespace) -> int:
    from . import IDEA_PRIORITIES

    matched, ambiguous = resolve_idea(args.query)
    if ambiguous:
        print("Ideia ambígua. Matches:")
        for e in ambiguous:
            print(f"  - [{e.id}] {e.title}")
        return 1
    if not matched:
        print("Ideia não encontrada.")
        return 1

    # Check for inline flags
    inline_fields = {}
    for field in ["title", "description", "domain", "priority", "note"]:
        val = getattr(args, field, None)
        if val is not None:
            if field == "note":
                inline_fields["notes"] = val
            else:
                inline_fields[field] = val

    if inline_fields:
        update_idea(matched.id, **inline_fields)
        _update_ideas_in_data_json()
        print(f"Ideia atualizada: {matched.title}")
        return 0

    # Interactive edit mode (legacy)
    print(f"Editando: {matched.title} (id: {matched.id})")
    print("(Enter para manter valor atual, Ctrl+C para cancelar)\n")

    try:
        title = input(f"Título [{matched.title}]: ").strip() or matched.title
        description = input(f"Descrição [{matched.description}]: ").strip() or matched.description

        existing_domains = list(set(DEFAULT_DOMAINS + [e.domain for e in load_ideas() if e.domain]))
        sorted_domains = sorted(existing_domains)
        if matched.domain in sorted_domains:
            sorted_domains.remove(matched.domain)
        sorted_domains.insert(0, matched.domain)
        print(f"\nDomínio atual: {matched.domain}")
        domain = _prompt_choice("Domínio (Enter=manter):", sorted_domains)

        sorted_pris = list(IDEA_PRIORITIES)
        if matched.priority in sorted_pris:
            sorted_pris.remove(matched.priority)
        sorted_pris.insert(0, matched.priority)
        print(f"\nPrioridade atual: {matched.priority}")
        priority = _prompt_choice("Prioridade (Enter=manter):", sorted_pris)

        current_refs = ", ".join(matched.references) if matched.references else ""
        refs_raw = input(f"Referências [{current_refs}]: ").strip()
        if refs_raw:
            references = [r.strip() for r in refs_raw.split(",") if r.strip()]
        else:
            references = matched.references

        notes = input(f"Notas [{matched.notes or ''}]: ").strip() or matched.notes
    except (KeyboardInterrupt, EOFError):
        print("\nCancelado.")
        return 0

    update_idea(matched.id, title=title, description=description, domain=domain,
                priority=priority, references=references, notes=notes)
    _update_ideas_in_data_json()
    print(f"Ideia atualizada: {title}")
    return 0


def cmd_idea_remove(args: argparse.Namespace) -> int:
    matched, ambiguous = resolve_idea(args.query)
    if ambiguous:
        print("Ideia ambígua. Matches:")
        for e in ambiguous:
            print(f"  - [{e.id}] {e.title}")
        return 1
    if not matched:
        print("Ideia não encontrada.")
        return 1

    try:
        confirm = input(f"Remover '{matched.title}'? [s/N]: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelado.")
        return 0

    if confirm != "s":
        print("Cancelado.")
        return 0

    remove_idea(matched.id)
    _update_ideas_in_data_json()
    print(f"Ideia removida: {matched.title}")
    return 0


def cmd_idea_promote(args: argparse.Namespace) -> int:
    matched, ambiguous = resolve_idea(args.query)
    if ambiguous:
        print("Ideia ambígua. Matches:")
        for e in ambiguous:
            print(f"  - [{e.id}] {e.title}")
        return 1
    if not matched:
        print("Ideia não encontrada.")
        return 1

    # --app flag: promote idea directly to app
    if getattr(args, "app", False):
        return _cmd_idea_promote_to_app(args, matched)

    print(f"\nPromovendo ideia: {matched.title}")
    print(f"  Domínio: {matched.domain}")
    if matched.description:
        print(f"  Descrição: {matched.description}")

    try:
        confirm = input("Continuar? [S/n]: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelado.")
        return 0

    if confirm == "n":
        print("Cancelado.")
        return 0

    # Build note from idea context
    note_parts = []
    if matched.references:
        note_parts.append(f"Refs: {', '.join(matched.references)}")
    if matched.notes:
        note_parts.append(f"Notas: {matched.notes}")
    project_note = " | ".join(note_parts) if note_parts else None

    print(f"\n--- Registrando projeto {matched.title} ---")
    print(f"Nome pre-preenchido: {matched.title}")
    print(f"Descrição pre-preenchida: {matched.description}")
    print(f"Domínio: {matched.domain}")
    if project_note:
        print(f"Nota: {project_note}")
    print()

    # Run interactive cmd_add, but user can change values
    try:
        path = input("Path do projeto (Enter para '.'): ").strip().strip("\"'") or "."
    except (KeyboardInterrupt, EOFError):
        print("\nCancelado.")
        return 0

    norm = str(Path(path).expanduser().resolve())
    if not _safe_path_exists(norm):
        print(f"Path não existe: {norm}")
        return 1

    try:
        name = input(f"Nome [{matched.title}]: ").strip() or matched.title
        description = input(f"Descrição [{matched.description}]: ").strip() or matched.description

        existing_domains = list(set(DEFAULT_DOMAINS + [e.domain for e in load_registry() if e.domain]))
        sorted_domains = sorted(existing_domains)
        if matched.domain in sorted_domains:
            sorted_domains.remove(matched.domain)
        sorted_domains.insert(0, matched.domain)
        domain = _prompt_choice("Domínio (Enter=manter):", sorted_domains)

        nature = _prompt_choice("Natureza:", PROJECT_NATURES)

        icon = input("Ícone (emoji, Enter para pular): ").strip() or None
        url = input("URL publicada (Enter para pular): ").strip() or None

        repo = _detect_repo(norm)
        if repo:
            print(f"  Repo detectado: {repo}")
        if not repo:
            repo = input("Repo (namespace git, Enter para pular): ").strip() or None
    except (KeyboardInterrupt, EOFError):
        print("\nCancelado.")
        return 0

    entry = ProjectEntry(
        path=norm,
        name=name,
        description=description,
        icon=icon,
        domain=domain,
        nature=nature,
        url=url,
        repo=repo,
        note=project_note,
    )

    created, entry = add_project(entry)
    if created:
        # Only remove idea AFTER project is successfully registered
        remove_idea(matched.id)
        _update_ideas_in_data_json()
        print(f"\nIdeia promovida para projeto!")
        print(f"Adicionado: {entry.name} ({entry.path})")
    else:
        print(f"Projeto já registrado: {entry.path}")

    promote_resolved = resolve_path_for_entry(entry.slug, entry.path)
    if promote_resolved:
        resolved = resolve_project_path(promote_resolved)
        cfg_created, cfg_updated = ensure_project_config(resolved)
        if cfg_created:
            print("  Arquivo nexus.yaml criado.")
        elif cfg_updated:
            print("  Arquivo nexus.yaml sincronizado.")

        hook_path = resolved
        if install_git_hook(hook_path):
            print("  Git post-commit hook instalado.")
        if install_claude_hook(hook_path):
            print("  Claude Code hook instalado.")

    return 0


def _cmd_idea_promote_to_app(args: argparse.Namespace, matched: IdeaEntry) -> int:
    """Promote idea directly to app."""
    from .apps import AppEntry, add_app

    name = getattr(args, "name", None) or matched.title
    domain = getattr(args, "domain", None) or matched.domain
    github = getattr(args, "github", None)
    url = getattr(args, "url", None)

    try:
        confirm = input(f"Promover ideia '{matched.title}' para app '{name}'? (s/N) ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelado.")
        return 0

    if confirm != "s":
        print("Cancelado.")
        return 0

    app = AppEntry(
        name=name,
        description=matched.description,
        domain=domain,
        github=github,
        url=url,
    )
    try:
        result = add_app(app)
    except Exception:
        print("Erro ao criar app.")
        return 1
    remove_idea(matched.id)
    _update_ideas_in_data_json()
    print(f"Ideia '{matched.title}' promovida para app '{result.name}'.")
    return 0


# -- Codex commands --

def cmd_codex(args: argparse.Namespace) -> int:
    if not hasattr(args, "codex_command") or args.codex_command is None:
        print("Uso: nexus codex {add,edit,list,remove,editor}")
        return 1
    return args.codex_func(args)


def cmd_codex_add(args: argparse.Namespace) -> int:
    from datetime import date as _date
    from .slug import slugify

    try:
        title = input("Título: ").strip()
        if not title:
            print("Título é obrigatório.")
            return 1

        existing_kinds = list(set(CODEX_KINDS + [e.kind for e in load_codex() if e.kind]))
        kind = _prompt_choice("Tipo:", sorted(existing_kinds))

        existing_domains = list(set(DEFAULT_DOMAINS + [e.domain for e in load_codex() if e.domain]))
        domain = _prompt_choice("Domínio:", sorted(existing_domains))

        order_raw = input("Ordem (número, Enter para pular): ").strip()
        order = int(order_raw) if order_raw.isdigit() else None
    except (KeyboardInterrupt, EOFError):
        print("\nCancelado.")
        return 0

    today = str(_date.today())
    entry = CodexEntry(
        slug=slugify(title),
        title=title,
        kind=kind,
        domain=domain,
        order=order,
        created=today,
        updated=today,
    )
    save_codex_entry(entry)
    _update_codex_in_data_json()
    print(f"Codex criado: {entry.title} ({entry.slug}.md)")

    # Open in editor
    editor = get_default_editor()
    if not editor:
        print("Nenhum editor configurado. Configure com: nexus codex editor add")
        editor = editor_add()
    if editor:
        from .codex import CODEX_DIR
        file_path = str(CODEX_DIR / f"{entry.slug}.md")
        open_in_editor(editor, file_path)

        if editor.type != "terminal":
            input("Pressione Enter quando terminar de editar...")

        # Re-read content and update entry
        from datetime import date as _date2
        from .codex import _parse_frontmatter
        entry.updated = str(_date2.today())
        text = (CODEX_DIR / f"{entry.slug}.md").read_text(encoding="utf-8")
        _, content = _parse_frontmatter(text)
        entry.content = content
        save_codex_entry(entry)
        _update_codex_in_data_json()

    return 0


def cmd_codex_edit(args: argparse.Namespace) -> int:
    from datetime import date as _date

    matched, ambiguous = resolve_codex(args.query)
    if ambiguous:
        print("Entrada ambígua. Matches:")
        for e in ambiguous:
            print(f"  - {e.slug}: {e.title}")
        return 1
    if not matched:
        print("Entrada não encontrada.")
        return 1

    # Pick editor
    if getattr(args, "pick", False):
        editor = pick_editor()
    else:
        editor = get_default_editor()
        if not editor:
            print("Nenhum editor configurado.")
            editor = editor_add()

    if not editor:
        print("Nenhum editor disponível.")
        return 1

    from .codex import CODEX_DIR
    file_path = str(CODEX_DIR / f"{matched.slug}.md")
    open_in_editor(editor, file_path)

    if editor.type != "terminal":
        # GUI editors are non-blocking — wait for user to finish
        input("Pressione Enter quando terminar de editar...")

    # Re-read entire file (user may have changed frontmatter fields)
    from .codex import _parse_frontmatter
    text = (CODEX_DIR / f"{matched.slug}.md").read_text(encoding="utf-8")
    meta, content = _parse_frontmatter(text)
    matched.title = meta.get("title", matched.title)
    matched.kind = meta.get("kind", meta.get("category", matched.kind))
    matched.domain = meta.get("domain", matched.domain)
    matched.order = meta.get("order")
    matched.content = content
    matched.updated = str(_date.today())
    save_codex_entry(matched)
    _update_codex_in_data_json()
    print(f"Atualizado: {matched.title}")

    return 0


def cmd_codex_list(_args: argparse.Namespace) -> int:
    entries = sort_codex(load_codex())
    if not entries:
        print("Nenhuma entrada no Codex.")
        return 0

    for e in entries:
        order_str = f"[{e.order}] " if e.order is not None else ""
        print(f"  {order_str}{e.title}  [{e.kind}] [{e.domain}]  ({e.slug})")
    print(f"\n{len(entries)} entrada(s).")
    return 0


def cmd_codex_remove(args: argparse.Namespace) -> int:
    matched, ambiguous = resolve_codex(args.query)
    if ambiguous:
        print("Entrada ambígua. Matches:")
        for e in ambiguous:
            print(f"  - {e.slug}: {e.title}")
        return 1
    if not matched:
        print("Entrada não encontrada.")
        return 1

    try:
        confirm = input(f"Remover '{matched.title}'? [s/N]: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelado.")
        return 0

    if confirm != "s":
        print("Cancelado.")
        return 0

    remove_codex_entry(matched.slug)
    _update_codex_in_data_json()
    print(f"Removido: {matched.title}")
    return 0


def cmd_codex_editor(args: argparse.Namespace) -> int:
    if not hasattr(args, "editor_command") or args.editor_command is None:
        print("Uso: nexus codex editor {add,list,default,remove}")
        return 1
    return args.editor_func(args)


def cmd_codex_editor_add(_args: argparse.Namespace) -> int:
    editor_add()
    return 0


def cmd_codex_editor_list(_args: argparse.Namespace) -> int:
    editors, default = load_editors()
    if not editors:
        print("Nenhum editor configurado.")
        return 0
    for e in editors:
        marker = " (padrão)" if e.name == default else ""
        print(f"  {e.name} [{e.type}] — {e.command}{marker}")
    return 0


def cmd_codex_editor_default(_args: argparse.Namespace) -> int:
    editors, default = load_editors()
    if not editors:
        print("Nenhum editor configurado. Use: nexus codex editor add")
        return 1

    print("Selecione o editor padrão:")
    for i, e in enumerate(editors, 1):
        marker = " (atual)" if e.name == default else ""
        print(f"  {i}) {e.name}{marker}")
    try:
        choice = input("> ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelado.")
        return 0

    if choice.isdigit() and 1 <= int(choice) <= len(editors):
        new_default = editors[int(choice) - 1].name
        save_editors(editors, new_default)
        print(f"Editor padrão: {new_default}")
        return 0

    print("Opção inválida.")
    return 1


def cmd_codex_editor_remove(_args: argparse.Namespace) -> int:
    editors, default = load_editors()
    if not editors:
        print("Nenhum editor configurado.")
        return 0

    print("Remover qual editor?")
    for i, e in enumerate(editors, 1):
        print(f"  {i}) {e.name}")
    try:
        choice = input("> ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelado.")
        return 0

    if choice.isdigit() and 1 <= int(choice) <= len(editors):
        removed = editors.pop(int(choice) - 1)
        if default == removed.name and editors:
            default = editors[0].name
        elif not editors:
            default = ""
        save_editors(editors, default)
        print(f"Removido: {removed.name}")
        return 0

    print("Opção inválida.")
    return 1



def cmd_open(args: argparse.Namespace) -> int:
    """Resolve project by slug/name and launch a CLI in its directory.

    Falls back to apps: if no project matches, checks apps registry and
    opens the app URL in the browser.
    """
    import webbrowser
    from .apps import resolve_app

    matched, ambiguous = resolve_project(args.query)
    if ambiguous:
        print("Projeto ambíguo. Matches:")
        for e in ambiguous:
            slug_info = f" (slug: {e.slug})" if e.slug else ""
            print(f"  - {e.name}{slug_info}: {e.path}")
        return 1
    if not matched:
        # Try apps as fallback
        app_entry, app_candidates = resolve_app(args.query)
        if app_entry:
            env_path = resolve_path_for_entry(app_entry.slug, None)
            if env_path:
                path = resolve_project_path(env_path)
                if not path or not _safe_path_exists(path):
                    print(f"Path não existe: {path or env_path}")
                    return 1
                return _launch_cli_in_path(
                    path,
                    name=app_entry.name,
                    icon=app_entry.icon,
                    shell=getattr(args, "shell", False),
                )
            if app_entry.url:
                webbrowser.open(app_entry.url)
                print(f"Abrindo app '{app_entry.name}': {app_entry.url}")
                return 0
            else:
                print(f"App '{app_entry.name}' encontrado mas sem path neste environment e sem URL configurada.")
                return 1
        if app_candidates:
            print("Múltiplos resultados encontrados:")
            for c in app_candidates:
                print(f"  {c.name} [{c.slug}]")
            return 1
        print(f"Projeto não encontrado: {args.query}")
        return 1

    env_path = resolve_path_for_entry(matched.slug, matched.path)
    if not env_path:
        print(f"Erro: {matched.name} não tem path neste environment.")
        return 1
    path = resolve_project_path(env_path)
    if not path or not _safe_path_exists(path):
        print(f"Path não existe: {path or matched.path}")
        return 1
    return _launch_cli_in_path(
        path,
        name=matched.name,
        icon=matched.icon,
        shell=getattr(args, "shell", False),
    )


def cmd_tui(_args: argparse.Namespace) -> int:
    """Launch TUI — implemented in Task 5."""
    from . import DATA_JSON

    if not DATA_JSON.exists():
        print("Primeira execução — escaneando projetos...")
        def _progress(i, total, name):
            print(f"  [{i}/{total}] {name}...")
        scan_all(on_progress=_progress)
        _update_ideas_in_data_json()
        print("Pronto.\n")

    try:
        import importlib

        tui_mod = importlib.import_module(".tui", package=__package__)
        has_textual = getattr(tui_mod, "HAS_TEXTUAL", True)
        if isinstance(has_textual, bool) and not has_textual:
            print("TUI não disponível. Instale textual: pip install textual")
            return 1
        return tui_mod.run_tui()
    except ImportError:
        print("TUI não disponível. Instale textual: pip install textual")
        return 1


def cmd_env_list() -> None:
    """List all registered environments."""
    from .environment import load_environments, get_current_hostname
    envs = load_environments()
    if not envs:
        print("Nenhum ambiente registrado.")
        return
    hostname = get_current_hostname()
    for e in envs:
        current = " ← atual" if e.hostname == hostname else ""
        print(f"  {e.name} ({e.location}) [{e.hostname}]{current}")
        if e.last_seen:
            print(f"    Último acesso: {e.last_seen}")
        if e.paths:
            print(f"    Projetos: {len(e.paths)}")
        if e.absent:
            print(f"    Ausentes: {', '.join(e.absent)}")


def cmd_env_info(args: argparse.Namespace) -> None:
    """Show details for a specific environment."""
    from .environment import load_environments
    envs = load_environments()
    query = args.name.lower() if hasattr(args, "name") and args.name else None
    if not query:
        env = find_environment()
        if not env:
            print("Nenhum ambiente detectado. Use 'nexus env setup' para registrar.")
            return
        _print_env_detail(env)
        return
    for e in envs:
        if query in e.name.lower() or query in e.hostname.lower():
            _print_env_detail(e)
            return
    print(f"Ambiente não encontrado: {args.name}")


def _print_env_detail(env: "EnvironmentEntry") -> None:
    current = " (atual)" if env.hostname == get_current_hostname() else ""
    print(f"\n{env.name}{current}")
    print(f"  Hostname: {env.hostname}")
    print(f"  Localização: {env.location}")
    if env.last_seen:
        print(f"  Último acesso: {env.last_seen}")
    if env.paths:
        print(f"\n  Paths ({len(env.paths)}):")
        for slug, path in sorted(env.paths.items()):
            print(f"    {slug}: {path}")
    if env.absent:
        print(f"\n  Ausentes: {', '.join(env.absent)}")


def cmd_env_setup(args: argparse.Namespace) -> None:
    """Register the current machine as an environment."""
    env = find_environment()
    if env:
        print(f"Ambiente já registrado: {env.name} ({env.hostname})")
        return
    hostname = get_current_hostname()
    print(f"Hostname detectado: {hostname}")
    try:
        name = input("Nome para este ambiente: ").strip() or hostname
        location = input("Localização (casa/trabalho/outro): ").strip() or "unknown"
    except KeyboardInterrupt:
        print("\nCancelado.")
        return
    register_environment(name, location)
    print(f"Ambiente '{name}' registrado com sucesso!")


def cmd_env(args: argparse.Namespace) -> int:
    subcmd = getattr(args, "env_cmd", None) or "list"
    if subcmd == "list":
        cmd_env_list()
    elif subcmd == "info":
        cmd_env_info(args)
    elif subcmd == "setup":
        cmd_env_setup(args)
    else:
        print(f"Subcomando desconhecido: {subcmd}")
        return 1
    return 0


# -- App commands --

def cmd_app_list():
    """List all registered apps."""
    from .apps import load_apps
    apps = load_apps()
    if not apps:
        print("Nenhum app registrado.")
        return
    for a in apps:
        icon = f"{a.icon} " if a.icon else ""
        print(f"  {icon}{a.name} [{a.slug}] ({a.domain})")
        if a.description:
            print(f"    {a.description}")
        if a.url:
            print(f"    🌐 {a.url}")
        if a.github:
            print(f"    📦 {a.github}")


def cmd_app_add(args=None, *, default_name: str | None = None):
    """Add a new app, inline or interactively."""
    from .apps import AppEntry, add_app, load_apps

    interactive = getattr(args, "interactive", False) if args else False
    has_inline = args and getattr(args, "name", None) is not None

    if has_inline and not interactive:
        # Inline mode
        name = args.name
        if not name:
            print("Nome é obrigatório.")
            return
        entry = AppEntry(
            name=name,
            description=getattr(args, "description", None) or "",
            domain=getattr(args, "domain", None) or "pessoal",
            icon=getattr(args, "icon", None),
            github=getattr(args, "github", None),
            url=getattr(args, "url", None),
        )
        result = add_app(entry)
        print(f"App '{result.name}' adicionado com slug '{result.slug}'.")
        return

    # Interactive mode (legacy)
    try:
        if default_name:
            name = input(f"Nome [{default_name}]: ").strip() or default_name
        else:
            name = input("Nome do app: ").strip()
        if not name:
            print("Nome é obrigatório.")
            return
        description = input("Descrição: ").strip()
        existing_domains = list(set(DEFAULT_DOMAINS + [a.domain for a in load_apps() if a.domain]))
        domain = _prompt_choice("Domínio:", sorted(existing_domains))
        icon = input("Ícone (emoji): ").strip() or None
        github = input("GitHub (user/repo): ").strip() or None
        url = input("URL: ").strip() or None
    except KeyboardInterrupt:
        print("\nCancelado.")
        return

    entry = AppEntry(
        name=name,
        description=description,
        domain=domain,
        icon=icon,
        github=github,
        url=url,
    )
    result = add_app(entry)
    print(f"App '{result.name}' adicionado com slug '{result.slug}'.")


def cmd_app_remove(query):
    """Remove an app."""
    from .apps import resolve_app, remove_app
    entry, candidates = resolve_app(query)
    if entry is None:
        if candidates:
            print("Múltiplos apps encontrados:")
            for c in candidates:
                print(f"  {c.name} [{c.slug}]")
        else:
            print(f"App não encontrado: {query}")
        return
    try:
        confirm = input(f"Remover '{entry.name}'? (s/N) ").strip().lower()
    except KeyboardInterrupt:
        print("\nCancelado.")
        return
    if confirm != "s":
        print("Cancelado.")
        return
    remove_app(entry.slug)
    print(f"App '{entry.name}' removido.")


def cmd_app_edit(query, args=None):
    """Edit an app's fields, inline or interactively."""
    from .apps import resolve_app, load_apps, save_apps
    entry, candidates = resolve_app(query)
    if entry is None:
        if candidates:
            print("Múltiplos apps encontrados:")
            for c in candidates:
                print(f"  {c.name} [{c.slug}]")
        else:
            print(f"App não encontrado: {query}")
        return

    # Check for inline flags
    if args:
        inline_fields = {}
        for field in ["name", "slug", "description", "domain", "icon", "url", "github", "note"]:
            val = getattr(args, field, None)
            if val is not None:
                inline_fields[field] = val
        if inline_fields:
            for k, v in inline_fields.items():
                if hasattr(entry, k):
                    setattr(entry, k, v)
            apps = load_apps()
            for i, a in enumerate(apps):
                if a.slug == entry.slug:
                    apps[i] = entry
                    break
            save_apps(apps)
            from .apps import _update_apps_in_data_json
            _update_apps_in_data_json()
            print(f"App '{entry.name}' atualizado.")
            return

    # Interactive edit mode (legacy)
    print(f"\nEditando: {entry.name} [{entry.slug}]")
    print("(Enter para manter o valor atual)\n")
    try:
        name = input(f"Nome [{entry.name}]: ").strip() or entry.name
        desc = input(f"Descrição [{entry.description}]: ").strip() or entry.description
        domain = input(f"Domínio [{entry.domain}]: ").strip() or entry.domain
        icon = input(f"Ícone [{entry.icon or ''}]: ").strip() or entry.icon
        github = input(f"GitHub [{entry.github or ''}]: ").strip() or entry.github
        url = input(f"URL [{entry.url or ''}]: ").strip() or entry.url
    except KeyboardInterrupt:
        print("\nCancelado.")
        return
    entry.name = name
    entry.description = desc
    entry.domain = domain
    entry.icon = icon
    entry.github = github
    entry.url = url
    apps = load_apps()
    for i, a in enumerate(apps):
        if a.slug == entry.slug:
            apps[i] = entry
            break
    save_apps(apps)
    from .apps import _update_apps_in_data_json
    _update_apps_in_data_json()
    print(f"App '{entry.name}' atualizado.")


def cmd_app_note(query):
    """Add a note to an app."""
    from .apps import load_apps, resolve_app, save_apps
    entry, candidates = resolve_app(query)
    if entry is None:
        if candidates:
            print("Múltiplos apps encontrados:")
            for c in candidates:
                print(f"  {c.name} [{c.slug}]")
        else:
            print(f"App não encontrado: {query}")
        return
    try:
        raw_note = input(f"Nota para '{entry.name}': ").strip()
    except KeyboardInterrupt:
        print("\nCancelado.")
        return
    if not raw_note:
        print("Nota vazia, ignorando.")
        return
    env = find_environment()
    prefix = f"[{env.name}] " if env else ""
    entry.note = f"{prefix}{raw_note}"
    # Persist: update the entry in the apps list
    apps = load_apps()
    for i, a in enumerate(apps):
        if a.slug == entry.slug:
            apps[i] = entry
            break
    save_apps(apps)
    from .apps import _update_apps_in_data_json
    _update_apps_in_data_json()
    print(f"Nota registrada: {entry.note}")


def cmd_app(args: argparse.Namespace) -> int:
    subcmd = getattr(args, "app_cmd", None) or "list"
    if subcmd == "list":
        cmd_app_list()
    elif subcmd == "add":
        cmd_app_add(args)
    elif subcmd == "remove":
        query = getattr(args, "query", None)
        if not query:
            print("Uso: nexus app remove <query>")
            return 1
        cmd_app_remove(query)
    elif subcmd == "edit":
        query = getattr(args, "query", None)
        if not query:
            print("Uso: nexus app edit <query>")
            return 1
        cmd_app_edit(query, args)
    elif subcmd == "note":
        query = getattr(args, "query", None)
        if not query:
            print("Uso: nexus app note <query>")
            return 1
        cmd_app_note(query)
    elif subcmd == "convert-to-project":
        query = getattr(args, "query", None)
        if not query:
            print("Uso: nexus app convert-to-project <query>")
            return 1
        return cmd_app_convert_to_project(args)
    else:
        print(f"Subcomando desconhecido: {subcmd}")
        return 1
    return 0


# -- Evolution commands --

def cmd_project_replace(args: argparse.Namespace) -> int:
    """Replace an old project with a new one."""
    from datetime import date as _date

    old_query = args.old
    new_query = args.new

    old_entry, old_ambiguous = resolve_project(old_query)
    if old_ambiguous:
        print("Projeto antigo ambíguo. Matches:")
        for e in old_ambiguous:
            print(f"  - {e.name}: {e.path}")
        return 1
    if not old_entry:
        print(f"Projeto antigo não encontrado: {old_query}")
        return 1

    # Try to resolve new as existing project
    new_entry, new_ambiguous = resolve_project(new_query)
    if new_ambiguous:
        print("Projeto novo ambíguo. Matches:")
        for e in new_ambiguous:
            print(f"  - {e.name}: {e.path}")
        return 1

    if new_entry and new_entry.slug == old_entry.slug:
        print("Erro: projeto antigo e novo são o mesmo.")
        return 1

    if not new_entry:
        # Try as path
        new_path = new_query.strip("\"'")
        norm = str(Path(new_path).expanduser().resolve())
        if not _safe_path_exists(norm):
            print(f"Novo projeto não encontrado como slug/nome e path não existe: {norm}")
            return 1

        try:
            confirm = input(f"Substituir '{old_entry.name}' por '{Path(norm).name}'? (s/N) ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nCancelado.")
            return 0
        if confirm != "s":
            print("Cancelado.")
            return 0

        # Quick add inheriting domain and nature
        created, new_entry = _quick_add_project(
            norm,
            domain=old_entry.domain,
            nature=old_entry.nature,
            silent=True,
        )
        if not created:
            print(f"⚠ '{new_entry.name}' já está registrado. Nota de origem adicionada.")
    else:
        try:
            confirm = input(f"Substituir '{old_entry.name}' por '{new_entry.name}'? (s/N) ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nCancelado.")
            return 0
        if confirm != "s":
            print("Cancelado.")
            return 0

    today = str(_date.today())
    # Mark old as replaced
    update_project(
        old_entry.path or old_entry.name,
        status="replaced",
        note=f"Substituído por {new_entry.slug} em {today}",
    )
    # Add origin note to new
    update_project(
        new_entry.path or new_entry.name,
        note=f"Origem: {old_entry.slug} (replaced {today})",
    )

    print(f"'{old_entry.name}' substituído por '{new_entry.name}'. Nota de origem adicionada.")
    return 0


def cmd_project_absorb(args: argparse.Namespace) -> int:
    """Absorb a smaller project into a larger one."""
    from datetime import date as _date

    minor_query = args.minor
    major_query = args.major

    minor_entry, minor_amb = resolve_project(minor_query)
    if minor_amb:
        print("Projeto menor ambíguo. Matches:")
        for e in minor_amb:
            print(f"  - {e.name}: {e.path}")
        return 1
    if not minor_entry:
        print(f"Projeto menor não encontrado: {minor_query}")
        return 1

    major_entry, major_amb = resolve_project(major_query)
    if major_amb:
        print("Projeto maior ambíguo. Matches:")
        for e in major_amb:
            print(f"  - {e.name}: {e.path}")
        return 1
    if not major_entry:
        print(f"Projeto maior não encontrado: {major_query}")
        return 1

    if minor_entry.slug == major_entry.slug:
        print("Erro: projeto menor e maior são o mesmo.")
        return 1

    try:
        confirm = input(f"Absorver '{minor_entry.name}' em '{major_entry.name}'? (s/N) ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelado.")
        return 0
    if confirm != "s":
        print("Cancelado.")
        return 0

    today = str(_date.today())
    # Add note to major
    existing_note = major_entry.note or ""
    absorb_note = f"Absorveu: {minor_entry.slug} em {today}"
    new_note = f"{existing_note} | {absorb_note}" if existing_note else absorb_note
    update_project(major_entry.path or major_entry.name, note=new_note)

    # Remove minor
    remove_project(minor_entry.path or minor_entry.name)

    print(f"'{minor_entry.name}' absorvido por '{major_entry.name}' e removido.")
    return 0


def cmd_project_split(args: argparse.Namespace) -> int:
    """Split a project into multiple new ones."""
    from datetime import date as _date

    old_query = args.old
    paths = args.paths

    old_entry, old_amb = resolve_project(old_query)
    if old_amb:
        print("Projeto ambíguo. Matches:")
        for e in old_amb:
            print(f"  - {e.name}: {e.path}")
        return 1
    if not old_entry:
        print(f"Projeto não encontrado: {old_query}")
        return 1

    # Validate paths
    norm_paths = []
    for p in paths:
        norm = str(Path(p.strip("\"'")).expanduser().resolve())
        if not _safe_path_exists(norm):
            print(f"Path não existe: {norm}")
            return 1
        norm_paths.append(norm)

    try:
        confirm = input(f"Dividir '{old_entry.name}' em {len(norm_paths)} projetos? (s/N) ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelado.")
        return 0
    if confirm != "s":
        print("Cancelado.")
        return 0

    today = str(_date.today())
    new_slugs = []
    for norm in norm_paths:
        created, new_entry = _quick_add_project(
            norm,
            domain=old_entry.domain,
            nature=old_entry.nature,
            silent=True,
        )
        new_slugs.append(new_entry.slug)
        update_project(
            new_entry.path or new_entry.name,
            note=f"Origem: split de {old_entry.slug} em {today}",
        )
        if not created:
            print(f"  ⚠ '{new_entry.name}' já está registrado. Nota de origem adicionada.")
        else:
            print(f"  Adicionado: {new_entry.name} ({new_entry.slug})")

    # Mark old as replaced
    update_project(
        old_entry.path or old_entry.name,
        status="replaced",
        note=f"Dividido em {', '.join(new_slugs)} em {today}",
    )

    print(f"'{old_entry.name}' dividido em {len(new_slugs)} projetos. Original marcado como replaced.")
    return 0


def cmd_project_convert_to_app(args: argparse.Namespace) -> int:
    """Convert a project to an app."""
    from .apps import AppEntry, add_app, load_apps

    matched, ambiguous = resolve_project(args.query)
    if ambiguous:
        print("Projeto ambíguo. Matches:")
        for e in ambiguous:
            print(f"  - {e.name}: {e.path}")
        return 1
    if not matched:
        print("Projeto não encontrado.")
        return 1

    # Check duplicate slug
    existing_slugs = {a.slug for a in load_apps()}
    if matched.slug in existing_slugs:
        print(f"App com slug '{matched.slug}' já existe.")
        return 1

    # Show summary
    print(f"\nConverter projeto → app: {matched.name}")
    print(f"  Slug: {matched.slug}")
    if matched.description:
        print(f"  Descrição: {matched.description}")
    print(f"  Domínio: {matched.domain}")

    discarded = []
    if matched.path:
        discarded.append(f"path={matched.path}")
    if matched.nature != "contexto":
        discarded.append(f"nature={matched.nature}")
    if matched.private:
        discarded.append("private=True")
    if matched.status:
        discarded.append(f"status={matched.status}")
    if matched.web:
        discarded.append(f"web={matched.web}")
    if discarded:
        print(f"  Descartados: {', '.join(discarded)}")

    try:
        confirm = input(f"Converter '{matched.name}' para app? (s/N) ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelado.")
        return 0

    if confirm != "s":
        print("Cancelado.")
        return 0

    app = AppEntry(
        name=matched.name,
        slug=matched.slug,
        description=matched.description,
        icon=matched.icon,
        domain=matched.domain,
        github=matched.repo,
        url=matched.url,
        note=matched.note,
        added=matched.added,
    )
    try:
        add_app(app)
    except Exception:
        print("Erro ao criar app.")
        return 1
    remove_project(matched.name if not matched.path else matched.path)
    print(f"Convertido: '{matched.name}' agora é um app.")
    return 0


def cmd_app_convert_to_project(args: argparse.Namespace) -> int:
    """Convert an app to a project."""
    from .apps import resolve_app, remove_app

    matched, candidates = resolve_app(args.query)
    if candidates:
        print("App ambíguo. Matches:")
        for a in candidates:
            print(f"  - {a.name} [{a.slug}]")
        return 1
    if not matched:
        print("App não encontrado.")
        return 1

    # Check duplicate slug in projects
    existing_slugs = {p.slug for p in load_registry()}
    if matched.slug in existing_slugs:
        print(f"Projeto com slug '{matched.slug}' já existe.")
        return 1

    # Show summary
    print(f"\nConverter app → projeto: {matched.name}")
    print(f"  Slug: {matched.slug}")
    if matched.description:
        print(f"  Descrição: {matched.description}")
    print(f"  Domínio: {matched.domain}")

    try:
        path_input = input("Path do projeto (Enter para pular): ").strip().strip("\"'")
        if path_input:
            norm = str(Path(path_input).expanduser().resolve())
            if not _safe_path_exists(norm):
                print(f"Path não existe: {norm}")
                return 1
        else:
            norm = None

        print(f"\nNatureza atual: nenhuma (apps não têm natureza)")
        nature = _prompt_choice("Natureza:", list(PROJECT_NATURES))

        confirm = input(f"Converter '{matched.name}' para projeto? (s/N) ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelado.")
        return 0

    if confirm != "s":
        print("Cancelado.")
        return 0

    entry = ProjectEntry(
        name=matched.name,
        slug=matched.slug,
        description=matched.description,
        icon=matched.icon,
        domain=matched.domain,
        nature=nature,
        repo=matched.github,
        url=matched.url,
        note=matched.note,
        added=matched.added,
        path=norm,
    )
    created, result = add_project(entry)
    if not created:
        print(f"Erro: projeto já existe com path '{norm}'.")
        return 1

    if norm:
        add_resolved = resolve_path_for_entry(entry.slug, norm)
        if add_resolved:
            resolved = resolve_project_path(add_resolved)
            cfg_created, cfg_updated = ensure_project_config(resolved)
            if cfg_created:
                print("  Arquivo nexus.yaml criado.")
            elif cfg_updated:
                print("  Arquivo nexus.yaml sincronizado.")
            if install_git_hook(resolved):
                print("  Git post-commit hook instalado.")
            if install_claude_hook(resolved):
                print("  Claude Code hook instalado.")

    remove_app(matched.slug)
    print(f"Convertido: '{matched.name}' agora é um projeto ({nature}).")
    return 0


def cmd_project(args: argparse.Namespace) -> int:
    """Dispatch project subcommands."""
    subcmd = getattr(args, "project_cmd", None)
    if subcmd == "replace":
        return cmd_project_replace(args)
    elif subcmd == "absorb":
        return cmd_project_absorb(args)
    elif subcmd == "split":
        return cmd_project_split(args)
    elif subcmd == "convert-to-app":
        return cmd_project_convert_to_app(args)
    elif subcmd == "add":
        return cmd_add(args)
    elif subcmd == "remove":
        return cmd_remove(args)
    elif subcmd == "edit":
        return cmd_edit(args)
    elif subcmd == "list":
        return cmd_list(args)
    elif subcmd == "status":
        return cmd_status(args)
    elif subcmd is None:
        print("Uso: nexus project {add,edit,list,status,remove,replace,absorb,split,convert-to-app}")
        return 1
    else:
        print(f"Subcomando desconhecido: {subcmd}")
        return 1


def _add_project_inline_flags(parser: argparse.ArgumentParser) -> None:
    """Add inline flags for project add/edit."""
    parser.add_argument("--name", default=None)
    parser.add_argument("--description", default=None)
    parser.add_argument("--domain", default=None, choices=DEFAULT_DOMAINS)
    parser.add_argument("--nature", default=None, choices=PROJECT_NATURES)
    parser.add_argument("--icon", default=None)
    parser.add_argument("--repo", default=None)
    parser.add_argument("--url", default=None)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nexus", description="Nexus CLI")
    sub = parser.add_subparsers(dest="command")

    # -- Legacy top-level shortcuts (backwards compatible) --
    p_add = sub.add_parser("add", help="Registrar projeto")
    p_add.add_argument("path", nargs="?", default=None)
    p_add.add_argument("-i", "--interactive", action="store_true", help="Modo interativo")
    p_add.add_argument("--private", action="store_true", default=False)
    _add_project_inline_flags(p_add)
    p_add.set_defaults(func=cmd_add)

    p_remove = sub.add_parser("remove", help="Remover projeto")
    p_remove.add_argument("query")
    p_remove.set_defaults(func=cmd_remove)

    p_list = sub.add_parser("list", help="Listar projetos")
    p_list.add_argument("--all", action="store_true", help="Incluir arquivados e substituídos")
    p_list.set_defaults(func=cmd_list)

    p_scan = sub.add_parser("scan", help="Escanear projetos")
    p_scan.add_argument("--project", default=None)
    p_scan.add_argument(
        "--sync-project-config",
        action="store_true",
        help="Criar/sincronizar nexus.yaml nos projetos antes do scan",
    )
    p_scan.set_defaults(func=cmd_scan)

    p_status = sub.add_parser("status", help="Detalhes de um projeto")
    p_status.add_argument("query")
    p_status.set_defaults(func=cmd_status)

    p_edit = sub.add_parser("edit", help="Editar campos de um projeto")
    p_edit.add_argument("query")
    p_edit.add_argument("--name", default=None)
    p_edit.add_argument("--slug", default=None)
    p_edit.add_argument("--description", default=None)
    p_edit.add_argument("--domain", default=None, choices=DEFAULT_DOMAINS)
    p_edit.add_argument("--nature", default=None, choices=PROJECT_NATURES)
    p_edit.add_argument("--icon", default=None)
    p_edit.add_argument("--url", default=None)
    p_edit.add_argument("--repo", default=None)
    p_edit.add_argument("--status", default=None, choices=["active", "archived", "replaced"])
    p_edit.add_argument("--note", default=None)
    p_edit.add_argument("--private", action="store_true", default=False)
    p_edit.add_argument("--no-private", action="store_true", default=False)
    p_edit.set_defaults(func=cmd_edit)

    p_note = sub.add_parser("note", help="Atualizar nota rápida")
    p_note.add_argument("query")
    p_note.add_argument("text")
    p_note.set_defaults(func=cmd_note)

    p_discover = sub.add_parser("discover", help="Descobrir projetos em um diretório")
    p_discover.add_argument("path")
    p_discover.set_defaults(func=cmd_discover)

    p_push = sub.add_parser("push", help="Scan + build + publicar portal")
    p_push.set_defaults(func=cmd_push)

    p_web_init = sub.add_parser("web-init", help="Gerar/atualizar prompt web de um projeto")
    p_web_init.add_argument("query", nargs="?", default=None)
    p_web_init.set_defaults(func=cmd_web_init)

    # -- Project subcommand --
    p_project = sub.add_parser("project", help="Gerenciar projetos")
    p_project.set_defaults(func=cmd_project)
    project_sub = p_project.add_subparsers(dest="project_cmd")

    pp_add = project_sub.add_parser("add", help="Registrar projeto")
    pp_add.add_argument("path", nargs="?", default=None)
    pp_add.add_argument("-i", "--interactive", action="store_true")
    pp_add.add_argument("--private", action="store_true", default=False)
    _add_project_inline_flags(pp_add)

    pp_remove = project_sub.add_parser("remove", help="Remover projeto")
    pp_remove.add_argument("query")

    pp_edit = project_sub.add_parser("edit", help="Editar projeto")
    pp_edit.add_argument("query")
    pp_edit.add_argument("--name", default=None)
    pp_edit.add_argument("--slug", default=None)
    pp_edit.add_argument("--description", default=None)
    pp_edit.add_argument("--domain", default=None, choices=DEFAULT_DOMAINS)
    pp_edit.add_argument("--nature", default=None, choices=PROJECT_NATURES)
    pp_edit.add_argument("--icon", default=None)
    pp_edit.add_argument("--url", default=None)
    pp_edit.add_argument("--repo", default=None)
    pp_edit.add_argument("--status", default=None, choices=["active", "archived", "replaced"])
    pp_edit.add_argument("--note", default=None)
    pp_edit.add_argument("--private", action="store_true", default=False)
    pp_edit.add_argument("--no-private", action="store_true", default=False)

    pp_list = project_sub.add_parser("list", help="Listar projetos")
    pp_list.add_argument("--all", action="store_true")

    pp_status = project_sub.add_parser("status", help="Detalhes de um projeto")
    pp_status.add_argument("query")

    pp_replace = project_sub.add_parser("replace", help="Substituir projeto por outro")
    pp_replace.add_argument("old", help="Slug/nome do projeto antigo")
    pp_replace.add_argument("new", help="Slug/nome ou path do novo projeto")

    pp_absorb = project_sub.add_parser("absorb", help="Absorver projeto em outro")
    pp_absorb.add_argument("minor", help="Slug/nome do projeto menor")
    pp_absorb.add_argument("major", help="Slug/nome do projeto maior")

    pp_split = project_sub.add_parser("split", help="Dividir projeto em múltiplos")
    pp_split.add_argument("old", help="Slug/nome do projeto a dividir")
    pp_split.add_argument("paths", nargs="+", help="Paths dos novos projetos")

    pp_convert = project_sub.add_parser("convert-to-app", help="Converter projeto para app")
    pp_convert.add_argument("query")

    # -- Idea subcommand --
    p_idea = sub.add_parser("idea", help="Gerenciar ideias")
    p_idea.set_defaults(func=cmd_idea)
    idea_sub = p_idea.add_subparsers(dest="idea_command")

    p_idea_add = idea_sub.add_parser("add", help="Adicionar ideia")
    p_idea_add.add_argument("-i", "--interactive", action="store_true")
    p_idea_add.add_argument("--title", default=None)
    p_idea_add.add_argument("--description", default=None)
    p_idea_add.add_argument("--domain", default=None, choices=DEFAULT_DOMAINS)
    p_idea_add.add_argument("--priority", default=None, choices=["high", "medium", "low"])
    p_idea_add.add_argument("--note", default=None)
    p_idea_add.set_defaults(idea_func=cmd_idea_add)

    p_idea_edit = idea_sub.add_parser("edit", help="Editar ideia")
    p_idea_edit.add_argument("query", help="ID ou título da ideia")
    p_idea_edit.add_argument("--title", default=None)
    p_idea_edit.add_argument("--description", default=None)
    p_idea_edit.add_argument("--domain", default=None, choices=DEFAULT_DOMAINS)
    p_idea_edit.add_argument("--priority", default=None, choices=["high", "medium", "low"])
    p_idea_edit.add_argument("--note", default=None)
    p_idea_edit.set_defaults(idea_func=cmd_idea_edit)

    p_idea_remove = idea_sub.add_parser("remove", help="Remover ideia")
    p_idea_remove.add_argument("query", help="ID ou título da ideia")
    p_idea_remove.set_defaults(idea_func=cmd_idea_remove)

    p_idea_promote = idea_sub.add_parser("promote", help="Promover ideia para projeto ou app")
    p_idea_promote.add_argument("query", help="ID ou título da ideia")
    p_idea_promote.add_argument("--app", action="store_true", help="Promover para app ao invés de projeto")
    p_idea_promote.add_argument("--name", default=None)
    p_idea_promote.add_argument("--domain", default=None, choices=DEFAULT_DOMAINS)
    p_idea_promote.add_argument("--github", default=None)
    p_idea_promote.add_argument("--url", default=None)
    p_idea_promote.set_defaults(idea_func=cmd_idea_promote)

    # -- Codex subcommand --
    p_codex = sub.add_parser("codex", help="Gerenciar Codex (referências em markdown)")
    p_codex.set_defaults(func=cmd_codex)
    codex_sub = p_codex.add_subparsers(dest="codex_command")

    p_codex_add = codex_sub.add_parser("add", help="Adicionar entrada")
    p_codex_add.set_defaults(codex_func=cmd_codex_add)

    p_codex_edit = codex_sub.add_parser("edit", help="Editar entrada")
    p_codex_edit.add_argument("query", help="Slug ou título da entrada")
    p_codex_edit.add_argument("--pick", action="store_true", help="Escolher editor")
    p_codex_edit.set_defaults(codex_func=cmd_codex_edit)

    p_codex_list = codex_sub.add_parser("list", help="Listar entradas")
    p_codex_list.set_defaults(codex_func=cmd_codex_list)

    p_codex_remove = codex_sub.add_parser("remove", help="Remover entrada")
    p_codex_remove.add_argument("query", help="Slug ou título da entrada")
    p_codex_remove.set_defaults(codex_func=cmd_codex_remove)

    p_codex_editor = codex_sub.add_parser("editor", help="Gerenciar editores")
    p_codex_editor.set_defaults(codex_func=cmd_codex_editor)
    editor_sub = p_codex_editor.add_subparsers(dest="editor_command")

    p_editor_add = editor_sub.add_parser("add", help="Adicionar editor")
    p_editor_add.set_defaults(editor_func=cmd_codex_editor_add)

    p_editor_list = editor_sub.add_parser("list", help="Listar editores")
    p_editor_list.set_defaults(editor_func=cmd_codex_editor_list)

    p_editor_default = editor_sub.add_parser("default", help="Definir editor padrão")
    p_editor_default.set_defaults(editor_func=cmd_codex_editor_default)

    p_editor_remove = editor_sub.add_parser("remove", help="Remover editor")
    p_editor_remove.set_defaults(editor_func=cmd_codex_editor_remove)

    p_open = sub.add_parser("open", help="Abrir projeto em AI CLI")
    p_open.add_argument("query", help="Slug, nome ou path do projeto")
    p_open.add_argument("--shell", "-s", action="store_true",
                        help="Abrir shell direto na pasta do projeto")
    p_open.set_defaults(func=cmd_open)

    p_move = sub.add_parser("move", help="Atualizar path de um projeto que mudou de local")
    p_move.add_argument("query", help="Nome do projeto")
    p_move.add_argument("new_path", nargs="?", default=None, help="Novo path (auto-detecta se omitido)")
    p_move.set_defaults(func=cmd_move)

    p_env = sub.add_parser("env", help="Gerenciar ambientes")
    p_env.set_defaults(func=cmd_env)
    env_sub = p_env.add_subparsers(dest="env_cmd")
    env_sub.add_parser("list", help="Listar ambientes")
    env_info = env_sub.add_parser("info", help="Detalhes de um ambiente")
    env_info.add_argument("name", nargs="?", default=None)
    env_sub.add_parser("setup", help="Registrar este ambiente")

    # -- App subcommand --
    p_app = sub.add_parser("app", help="Gerenciar apps")
    p_app.set_defaults(func=cmd_app)
    app_sub = p_app.add_subparsers(dest="app_cmd")
    app_sub.add_parser("list", help="Listar apps")

    app_add = app_sub.add_parser("add", help="Adicionar app")
    app_add.add_argument("-i", "--interactive", action="store_true")
    app_add.add_argument("--name", default=None)
    app_add.add_argument("--description", default=None)
    app_add.add_argument("--domain", default=None, choices=DEFAULT_DOMAINS)
    app_add.add_argument("--icon", default=None)
    app_add.add_argument("--github", default=None)
    app_add.add_argument("--url", default=None)

    app_edit = app_sub.add_parser("edit", help="Editar app")
    app_edit.add_argument("query", nargs="?")
    app_edit.add_argument("--name", default=None)
    app_edit.add_argument("--slug", default=None)
    app_edit.add_argument("--description", default=None)
    app_edit.add_argument("--domain", default=None, choices=DEFAULT_DOMAINS)
    app_edit.add_argument("--icon", default=None)
    app_edit.add_argument("--github", default=None)
    app_edit.add_argument("--url", default=None)
    app_edit.add_argument("--note", default=None)

    app_remove = app_sub.add_parser("remove", help="Remover app")
    app_remove.add_argument("query", nargs="?")
    app_note = app_sub.add_parser("note", help="Adicionar nota")
    app_note.add_argument("query", nargs="?")
    app_convert = app_sub.add_parser("convert-to-project", help="Converter app para projeto")
    app_convert.add_argument("query")

    return parser


def _auto_update() -> None:
    """Pull latest nexus code and re-exec if updated."""
    if os.environ.get("_NEXUS_UPDATED"):
        return

    nexus_root = str(Path(__file__).resolve().parent.parent)

    # Get current HEAD
    head_before = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=nexus_root, capture_output=True, text=True,
    )
    if head_before.returncode != 0:
        return

    # Check for remote
    remote = subprocess.run(
        ["git", "remote"],
        cwd=nexus_root, capture_output=True, text=True,
    )
    if remote.returncode != 0 or not remote.stdout.strip():
        return

    # Pull --rebase (timeout prevents hang when network is unreachable)
    try:
        pull = subprocess.run(
            ["git", "pull", "--rebase", "--autostash"],
            cwd=nexus_root, capture_output=True, text=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        subprocess.run(
            ["git", "rebase", "--abort"],
            cwd=nexus_root, capture_output=True, text=True,
        )
        return
    if pull.returncode != 0:
        subprocess.run(
            ["git", "rebase", "--abort"],
            cwd=nexus_root, capture_output=True, text=True,
        )
        from .sync import _warn_sync_failure
        _warn_sync_failure("pull --rebase falhou. Pode haver commits locais não sincronizados.")
        return

    # Check if HEAD changed
    head_after = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=nexus_root, capture_output=True, text=True,
    )

    if head_before.stdout.strip() != head_after.stdout.strip():
        print("↻ Nexus atualizado, reiniciando...")
        os.environ["_NEXUS_UPDATED"] = "1"
        os.execv(sys.executable, [sys.executable, "-m", "nexus"] + sys.argv[1:])


def main() -> None:
    _auto_update()
    from nexus import APPS_YML
    if APPS_YML.exists():
        from nexus.integrity import check_registry_integrity
        check_registry_integrity()
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        raise SystemExit(cmd_tui(args))

    code = args.func(args)

    # Auto-sync after successful mutating commands
    if code == 0 and args.command in _MUTATING_COMMANDS:
        from . import NEXUS_ROOT
        sync_files = _COMMAND_SYNC_FILES.get(args.command)
        if sync_files is None:
            auto_sync_registry(str(NEXUS_ROOT), args.command)
        else:
            quick_sync(str(NEXUS_ROOT), sync_files, args.command)

    raise SystemExit(code)


if __name__ == "__main__":  # pragma: no cover
    main()

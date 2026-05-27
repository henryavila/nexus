from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import yaml

from .local_config import get_resolved_path
from .registry import ProjectEntry, normalize_path

PROJECT_CONFIG_FILENAME = "nexus.yaml"

_DEFAULT_CONFIG = {
    "schema_version": 1,
    "project": {
        "path": None,
        "name": None,
        "slug": None,
        "description": None,
        "icon": None,
        "domain": None,
        "nature": None,
        "url": None,
        "repo": None,
        "status": None,
        "note": None,
        "added": None,
    },
    "web": {
        "route": None,
        "static_dir": None,
        "build_cmd": None,
    },
    "local": {
        "path_override": None,
    },
}


def _is_non_empty(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _merge_with_defaults(raw: dict) -> dict:
    def _merge(defaults: dict, current: dict) -> dict:
        merged = deepcopy(defaults)
        for key, value in (current or {}).items():
            if key in merged and isinstance(merged[key], dict):
                if isinstance(value, dict):
                    merged[key] = _merge(merged[key], value)
                else:
                    # Keep default shape when file has invalid type.
                    continue
            else:
                merged[key] = value
        return merged

    return _merge(_DEFAULT_CONFIG, raw)


def _config_path(project_path: str) -> Path:
    return Path(project_path) / PROJECT_CONFIG_FILENAME


def _safe_exists(p: Path) -> bool:
    try:
        return p.exists()
    except OSError:
        return False


def _find_config_host_path(project_path: str) -> str:
    base = normalize_path(project_path)
    legacy = normalize_path(get_resolved_path(base))
    candidates = []
    if _safe_exists(Path(base)):
        candidates.append(base)
    if legacy != base and _safe_exists(Path(legacy)):
        candidates.append(legacy)

    for candidate in candidates:
        if _safe_exists(_config_path(candidate)):
            return candidate
    if candidates:
        return candidates[0]
    return base


def _render_with_comments(config: dict) -> str:
    text = yaml.dump(config, default_flow_style=False, allow_unicode=True, sort_keys=False)

    text = text.replace(
        "project:\n  path:",
        (
            "project:\n"
            "  # Caminho canônico do projeto no registry compartilhado.\n"
            "  # Normalmente não precisa alterar aqui; prefira local.path_override.\n"
            "  path:"
        ),
        1,
    )
    text = text.replace(
        "\n  slug:",
        "\n  # Identificador curto (ex.: dh, crcmg). Usado no 'nexus open'.\n  slug:",
        1,
    )
    text = text.replace(
        "\n  status:",
        '\n  # "archived" oculta o projeto no TUI/dashboard; null mantém padrão.\n  status:',
        1,
    )
    text = text.replace(
        "\n  added:",
        "\n  # Data de cadastro no formato YYYY-MM-DD.\n  added:",
        1,
    )
    text = text.replace(
        "web:\n  route:",
        (
            "web:\n"
            "  # Rota no portal (ex.: /dh). Deve começar com '/'.\n"
            "  route:"
        ),
        1,
    )
    text = text.replace(
        "\n  static_dir:",
        "\n  # Pasta estática relativa à raiz do projeto (ex.: dist, app).\n  static_dir:",
        1,
    )
    text = text.replace(
        "\n  build_cmd:",
        "\n  # Comando executado no `nexus push` antes de copiar arquivos web.\n  build_cmd:",
        1,
    )
    text = text.replace(
        "local:\n  path_override:",
        (
            "local:\n"
            "  # Override de caminho apenas para esta máquina.\n"
            "  path_override:"
        ),
        1,
    )
    return text


def _write_config(project_path: str, config: dict) -> None:
    path = _config_path(project_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render_with_comments(config), encoding="utf-8")


def load_project_config(project_path: str) -> dict:
    host = _find_config_host_path(project_path)
    path = _config_path(host)
    if not _safe_exists(path):
        return {}
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {}
    if not isinstance(raw, dict):
        return {}
    return _merge_with_defaults(raw)


def ensure_project_config(project_path: str) -> tuple[bool, bool]:
    target = Path(project_path)
    if not _safe_exists(target) or not target.is_dir():
        return False, False

    cfg_path = _config_path(project_path)
    created = not _safe_exists(cfg_path)

    if created:
        existing = {}
        existing_text = ""
    else:
        try:
            existing_text = cfg_path.read_text(encoding="utf-8")
            existing = yaml.safe_load(existing_text) or {}
        except yaml.YAMLError:
            existing_text = ""
            existing = {}
        if not isinstance(existing, dict):
            existing = {}

    merged = _merge_with_defaults(existing)
    has_template_comments = "Override de caminho apenas para esta máquina" in existing_text
    updated = (not created) and (merged != existing or not has_template_comments)

    if created or updated:
        _write_config(project_path, merged)

    return created, updated


def resolve_project_path(project_path: str) -> str:
    host = _find_config_host_path(project_path)
    config = load_project_config(host)

    local_override = (config.get("local") or {}).get("path_override")
    if _is_non_empty(local_override):
        return normalize_path(str(local_override))

    project_override = (config.get("project") or {}).get("path")
    if _is_non_empty(project_override):
        return normalize_path(str(project_override))

    return normalize_path(host)


def set_project_path_override(project_path: str, local_path: str) -> bool:
    host = _find_config_host_path(project_path)
    # Prefer existing host; fall back to local_path (the actual project dir on this machine)
    if _safe_exists(Path(host)) and Path(host).is_dir():
        target = host
    elif _safe_exists(Path(local_path)) and Path(local_path).is_dir():
        target = local_path
    else:
        return False

    ensure_project_config(target)
    config = load_project_config(target)
    merged = _merge_with_defaults(config)
    merged.setdefault("local", {})
    merged["local"]["path_override"] = normalize_path(local_path)
    _write_config(target, merged)
    return True


def apply_project_overrides(entry: ProjectEntry) -> ProjectEntry:
    if not entry.path:
        return entry
    config = load_project_config(entry.path)
    if not config:
        return entry

    project_cfg = config.get("project") or {}
    web_cfg = config.get("web") or {}

    overridden = replace(entry)
    for field in ("name", "slug", "description", "icon", "domain", "nature", "url", "repo", "status", "note", "added"):
        value = project_cfg.get(field)
        if _is_non_empty(value):
            setattr(overridden, field, value)

    merged_web = dict(entry.web or {})
    for field in ("route", "static_dir", "build_cmd"):
        value = web_cfg.get(field)
        if _is_non_empty(value):
            merged_web[field] = value
    overridden.web = merged_web or None

    return overridden

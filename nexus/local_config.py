from __future__ import annotations

from pathlib import Path

import yaml

LOCAL_CONFIG_PATH = Path.home() / ".config" / "nexus" / "local.yml"


def load_local_config() -> dict:
    if not LOCAL_CONFIG_PATH.exists():
        return {}
    return yaml.safe_load(LOCAL_CONFIG_PATH.read_text(encoding="utf-8")) or {}


def save_local_config(config: dict) -> None:
    LOCAL_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_CONFIG_PATH.write_text(
        yaml.dump(config, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )


def get_resolved_path(original_path: str) -> str:
    config = load_local_config()
    overrides = config.get("path_overrides", {})
    return overrides.get(original_path, original_path)


def set_path_override(original_path: str, local_path: str) -> None:
    config = load_local_config()
    overrides = config.setdefault("path_overrides", {})
    overrides[original_path] = local_path
    save_local_config(config)

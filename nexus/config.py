from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

_DEFAULT_DATA_DIR = Path.home() / ".nexus" / "data"
_DEFAULT_CONFIG_PATH = Path.home() / ".config" / "nexus" / "local.yml"


@dataclass
class NexusConfig:
    data_dir: Path

    @classmethod
    def load(cls, config_path: Path | None = None) -> NexusConfig:
        config_path = config_path or _DEFAULT_CONFIG_PATH
        env_dir = os.environ.get("NEXUS_DATA_DIR")
        if env_dir:
            return cls(data_dir=Path(env_dir))
        if config_path.exists():
            raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            if "data_dir" in raw:
                return cls(data_dir=Path(raw["data_dir"]))
        return cls(data_dir=_DEFAULT_DATA_DIR)

    def save(self, config_path: Path | None = None) -> None:
        config_path = config_path or _DEFAULT_CONFIG_PATH
        config_path.parent.mkdir(parents=True, exist_ok=True)
        existing = {}
        if config_path.exists():
            existing = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        existing["data_dir"] = str(self.data_dir)
        config_path.write_text(
            yaml.dump(existing, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )

    @property
    def projects_yml(self) -> Path:
        return self.data_dir / "projects.yml"

    @property
    def apps_yml(self) -> Path:
        return self.data_dir / "apps.yml"

    @property
    def ideas_yml(self) -> Path:
        return self.data_dir / "ideas.yml"

    @property
    def environments_yml(self) -> Path:
        return self.data_dir / "environments.yml"

    @property
    def codex_dir(self) -> Path:
        return self.data_dir / "codex"

    @property
    def data_json(self) -> Path:
        return self.data_dir / "data.json"

    @property
    def lock_file(self) -> Path:
        return self.data_dir / ".nexus.lock"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.codex_dir.mkdir(parents=True, exist_ok=True)

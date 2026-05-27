from __future__ import annotations
import copy
import json
from nexus.config import NexusConfig
from nexus.infra.file_lock import file_lock


_EMPTY_DATA = {
    "version": "3.0",
    "last_full_scan": None,
    "current_environment": None,
    "projects": [],
    "apps": [],
    "environments": [],
    "skills": {},
    "ideas": [],
    "codex": [],
}


class ScanRepository:
    def __init__(self, config: NexusConfig):
        self._path = config.data_json
        self._lock_path = config.lock_file

    def read(self) -> dict:
        if not self._path.exists():
            return copy.deepcopy(_EMPTY_DATA)
        with file_lock(self._lock_path):
            text = self._path.read_text(encoding="utf-8")
        data = json.loads(text) if text.strip() else {}
        for key, default in _EMPTY_DATA.items():
            data.setdefault(key, default if not isinstance(default, (list, dict)) else type(default)())
        return data

    def write(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with file_lock(self._lock_path):
            self._path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

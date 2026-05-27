from __future__ import annotations
from nexus.config import NexusConfig
from nexus.infra import git_sync


class SyncService:
    def __init__(self, config: NexusConfig, data_repo_path: str | None = None):
        self._config = config
        self._repo_path = data_repo_path

    def quick_sync(self, files: list[str], command: str) -> bool:
        if not self._repo_path:
            return True
        return git_sync.commit_and_push(self._repo_path, files, command)

    def full_sync(self, command: str) -> bool:
        if not self._repo_path:
            return True
        data_files = [
            "projects.yml", "ideas.yml", "apps.yml", "environments.yml",
        ]
        codex_dir = self._config.codex_dir
        if codex_dir.exists():
            data_files.append("codex/")
        return git_sync.commit_and_push(self._repo_path, data_files, command)

    def pull(self) -> tuple[bool, str]:
        if not self._repo_path:
            return True, "sem repo de dados configurado"
        return git_sync.pull_rebase(self._repo_path)

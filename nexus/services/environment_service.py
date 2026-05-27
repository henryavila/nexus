from __future__ import annotations
import socket
from datetime import date
from nexus.config import NexusConfig
from nexus.models import Environment
from nexus.repositories.environment_repo import EnvironmentRepository
from nexus.services.sync_service import SyncService


class EnvironmentService:
    def __init__(self, config: NexusConfig, sync: SyncService):
        self._repo = EnvironmentRepository(config)
        self._sync = sync

    def register(self, hostname: str, name: str, location: str = "") -> Environment:
        existing = self._repo.find_by_hostname(hostname)
        if existing:
            self._repo.update(hostname, name=name, location=location, last_seen=str(date.today()))
            return self._repo.find_by_hostname(hostname)
        env = Environment(
            hostname=hostname, name=name, location=location,
            last_seen=str(date.today()),
        )
        self._repo.add(env)
        self._sync.quick_sync(["environments.yml"], "env-setup")
        return env

    def get_current(self) -> Environment | None:
        hostname = socket.gethostname()
        return self._repo.find_by_hostname(hostname)

    def list_all(self) -> list[Environment]:
        return self._repo.load_all()

    def set_path(self, hostname: str, slug: str, path: str) -> None:
        env = self._repo.find_by_hostname(hostname)
        if env is None:
            return
        env.paths[slug] = path
        self._repo.update(hostname, paths=env.paths)
        self._sync.quick_sync(["environments.yml"], "env-path")

    def mark_absent(self, hostname: str, slug: str) -> None:
        env = self._repo.find_by_hostname(hostname)
        if env is None:
            return
        if slug not in env.absent:
            env.absent.append(slug)
        env.paths.pop(slug, None)
        self._repo.update(hostname, paths=env.paths, absent=env.absent)
        self._sync.quick_sync(["environments.yml"], "env-absent")

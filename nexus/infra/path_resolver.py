from __future__ import annotations
from nexus.models import Project, Environment


class PathResolver:
    def __init__(self, environments: list[Environment], hostname: str):
        self._env_map = {e.hostname: e for e in environments}
        self._hostname = hostname

    def resolve(self, project: Project) -> str | None:
        if project.path is None:
            return None
        env = self._env_map.get(self._hostname)
        if env:
            if project.slug in env.absent:
                return None
            override = env.paths.get(project.slug)
            if override:
                return override
        return project.path

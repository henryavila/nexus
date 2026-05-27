__version__ = "0.2.0"

from contextlib import contextmanager
from pathlib import Path
import fcntl

NEXUS_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = NEXUS_ROOT / "data"
DATA_JSON = DATA_DIR / "data.json"
LOCK_FILE = DATA_DIR / ".nexus.lock"
PROJECTS_YML = DATA_DIR / "projects.yml"
IDEAS_YML = DATA_DIR / "ideas.yml"
APPS_YML = DATA_DIR / "apps.yml"
ENVIRONMENTS_YML = DATA_DIR / "environments.yml"
IDEA_PRIORITIES = ["high", "medium", "low"]

DEFAULT_DOMAINS = ["trabalho", "pessoal", "igreja", "lazer", "empreendimentos", "estudo", "tech"]

PROJECT_NATURES = ["contexto", "ferramenta", "companion"]

CODEX_KINDS = ["referência", "guia", "workflow", "configuração", "tutorial", "anotação"]


@contextmanager
def file_lock(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as fd:
        fcntl.flock(fd.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fd.fileno(), fcntl.LOCK_UN)


EXCLUDED_DIRS = {
    "node_modules", ".git", ".claude", "vendor", "venv", ".venv",
    "__pycache__", ".next", "dist", "build", ".cache", "target", ".tox",
    "coverage",
}

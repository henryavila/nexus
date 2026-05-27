import json
import pytest
from pathlib import Path
from nexus.config import NexusConfig
from nexus.repositories.project_repo import ProjectRepository
from nexus.repositories.app_repo import AppRepository
from nexus.repositories.idea_repo import IdeaRepository
from nexus.repositories.codex_repo import CodexRepository
from nexus.repositories.skill_repo import SkillRepository
from nexus.repositories.environment_repo import EnvironmentRepository
from nexus.repositories.scan_repo import ScanRepository
from nexus.models import Project, App, Idea, CodexEntry, Skill, Environment


@pytest.fixture
def cfg(tmp_path):
    return NexusConfig(data_dir=tmp_path)


def test_project_repo_slug_generation(cfg):
    repo = ProjectRepository(cfg)
    repo.add(Project(name="My Cool Project", path="/tmp/mcp"))
    loaded = repo.load_all()
    assert loaded[0].slug != ""


def test_project_repo_unique_slug(cfg):
    repo = ProjectRepository(cfg)
    repo.add(Project(name="Alpha", path="/a"))
    repo.add(Project(name="Alpha", path="/b"))
    slugs = [p.slug for p in repo.load_all()]
    assert len(set(slugs)) == 2


def test_project_repo_resolve_by_path(cfg):
    repo = ProjectRepository(cfg)
    repo.add(Project(name="Test", slug="test", path="/tmp/test"))
    found = repo.resolve_by_path("/tmp/test")
    assert found is not None
    assert found.name == "Test"


def test_app_repo_slug_generation(cfg):
    repo = AppRepository(cfg)
    repo.add(App(name="My App"))
    loaded = repo.load_all()
    assert loaded[0].slug != ""


def test_idea_repo_id_generation(cfg):
    repo = IdeaRepository(cfg)
    repo.add(Idea(title="Cool Idea"))
    loaded = repo.load_all()
    assert loaded[0].id != ""
    assert len(loaded[0].id) == 8


def test_codex_repo_crud(cfg):
    cfg.codex_dir.mkdir(parents=True, exist_ok=True)
    repo = CodexRepository(cfg)
    repo.save(CodexEntry(slug="guide", title="Guide", content="# Hi"))
    assert repo.get("guide").title == "Guide"
    repo.remove("guide")
    assert repo.get("guide") is None


def test_skill_repo_crud(cfg):
    cfg.skills_dir.mkdir(parents=True, exist_ok=True)
    repo = SkillRepository(cfg)
    repo.save(Skill(slug="tdd", title="TDD", content="Test first"))
    assert repo.get("tdd").title == "TDD"


def test_environment_repo_crud(cfg):
    repo = EnvironmentRepository(cfg)
    repo.add(Environment(hostname="mac-1", name="Mac Studio"))
    loaded = repo.load_all()
    assert len(loaded) == 1
    assert loaded[0].hostname == "mac-1"


def test_environment_repo_find_by_hostname(cfg):
    repo = EnvironmentRepository(cfg)
    repo.add(Environment(hostname="mac-1", name="Mac"))
    repo.add(Environment(hostname="win-1", name="Windows"))
    found = repo.find_by_hostname("win-1")
    assert found is not None
    assert found.name == "Windows"


def test_scan_repo_read_empty(cfg):
    repo = ScanRepository(cfg)
    data = repo.read()
    assert data["version"] == "3.0"
    assert data["projects"] == []


def test_scan_repo_write_and_read(cfg):
    repo = ScanRepository(cfg)
    data = repo.read()
    data["projects"].append({"name": "Test", "slug": "test"})
    repo.write(data)
    reloaded = repo.read()
    assert len(reloaded["projects"]) == 1

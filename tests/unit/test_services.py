import pytest
from datetime import date
from nexus.config import NexusConfig
from nexus.services.project_service import ProjectService
from nexus.services.app_service import AppService
from nexus.services.idea_service import IdeaService
from nexus.services.codex_service import CodexService
from nexus.services.skill_service import SkillService
from nexus.services.environment_service import EnvironmentService
from nexus.services.sync_service import SyncService
from nexus.models import Project, App, Idea, CodexEntry, Skill, Environment


@pytest.fixture
def cfg(tmp_path):
    c = NexusConfig(data_dir=tmp_path)
    c.ensure_dirs()
    return c


@pytest.fixture
def sync(cfg):
    return SyncService(cfg, data_repo_path=None)


# --- ProjectService ---

def test_add_project(cfg, sync):
    svc = ProjectService(cfg, sync)
    p = svc.add("My Project", path="/tmp/mp")
    assert p.slug != ""
    assert p.added == str(date.today())
    assert svc.list_all()[0].name == "My Project"


def test_add_project_duplicate_name(cfg, sync):
    svc = ProjectService(cfg, sync)
    svc.add("Alpha", path="/a")
    svc.add("Alpha", path="/b")
    assert len(svc.list_all()) == 2


def test_remove_project(cfg, sync):
    svc = ProjectService(cfg, sync)
    svc.add("X", path="/x")
    removed = svc.remove("x")
    assert removed is not None
    assert svc.list_all() == []


def test_edit_project(cfg, sync):
    svc = ProjectService(cfg, sync)
    svc.add("X", path="/x")
    updated = svc.edit("x", description="new desc")
    assert updated.description == "new desc"


def test_resolve_project(cfg, sync):
    svc = ProjectService(cfg, sync)
    svc.add("My Project", path="/tmp/mp")
    assert svc.resolve("my").name == "My Project"


# --- AppService ---

def test_add_app(cfg, sync):
    svc = AppService(cfg, sync)
    a = svc.add("My App")
    assert a.slug != ""
    assert a.added == str(date.today())


def test_remove_app(cfg, sync):
    svc = AppService(cfg, sync)
    svc.add("X")
    assert svc.remove("x") is not None
    assert svc.list_all() == []


# --- IdeaService ---

def test_add_idea(cfg, sync):
    svc = IdeaService(cfg, sync)
    i = svc.add("Cool idea")
    assert len(i.id) == 8
    assert i.created == str(date.today())


def test_edit_idea(cfg, sync):
    svc = IdeaService(cfg, sync)
    i = svc.add("X")
    updated = svc.edit(i.id, priority="high")
    assert updated.priority == "high"


# --- CodexService ---

def test_add_codex(cfg, sync):
    svc = CodexService(cfg, sync)
    c = svc.add("My Guide", kind="guia", content="# Hello")
    assert c.slug == "my-guide"
    assert c.created == str(date.today())


def test_remove_codex(cfg, sync):
    svc = CodexService(cfg, sync)
    svc.add("X", content="hi")
    assert svc.remove("x") is not None
    assert svc.list_all() == []


# --- SkillService ---

def test_add_skill(cfg, sync):
    svc = SkillService(cfg, sync)
    s = svc.add("TDD Skill", scope="global")
    assert s.slug == "tdd-skill"


# --- EnvironmentService ---

def test_register_environment(cfg, sync):
    svc = EnvironmentService(cfg, sync)
    e = svc.register("mac-1", "Mac Studio", "Office")
    assert e.hostname == "mac-1"
    assert e.last_seen == str(date.today())


def test_get_current(cfg, sync):
    svc = EnvironmentService(cfg, sync)
    svc.register("mac-1", "Mac Studio", "Office")
    import socket
    with pytest.MonkeyPatch.context() as m:
        m.setattr(socket, "gethostname", lambda: "mac-1")
        env = svc.get_current()
    assert env is not None
    assert env.name == "Mac Studio"

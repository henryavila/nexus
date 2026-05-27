from pathlib import Path
from unittest.mock import patch
from nexus.infra.path_resolver import PathResolver
from nexus.models import Project, Environment


def test_resolve_direct_path_exists(tmp_path):
    project_dir = tmp_path / "my-project"
    project_dir.mkdir()
    project = Project(name="Test", path=str(project_dir), slug="test")
    resolver = PathResolver(environments=[], hostname="mac-1")
    assert resolver.resolve(project) == str(project_dir)


def test_resolve_env_override():
    project = Project(name="Test", path="/original/path", slug="test")
    env = Environment(
        hostname="mac-1", name="Mac",
        paths={"test": "/override/path"},
    )
    resolver = PathResolver(environments=[env], hostname="mac-1")
    with patch("pathlib.Path.exists", return_value=True):
        assert resolver.resolve(project) == "/override/path"


def test_resolve_returns_original_if_no_override():
    project = Project(name="Test", path="/original/path", slug="test")
    env = Environment(hostname="mac-1", name="Mac", paths={})
    resolver = PathResolver(environments=[env], hostname="mac-1")
    assert resolver.resolve(project) == "/original/path"


def test_resolve_none_path():
    project = Project(name="Test", path=None, slug="test")
    resolver = PathResolver(environments=[], hostname="mac-1")
    assert resolver.resolve(project) is None


def test_resolve_marks_absent():
    project = Project(name="Test", path="/gone", slug="test")
    env = Environment(hostname="mac-1", name="Mac", absent=["test"])
    resolver = PathResolver(environments=[env], hostname="mac-1")
    assert resolver.resolve(project) is None

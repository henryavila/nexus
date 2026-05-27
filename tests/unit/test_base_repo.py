import pytest
from pathlib import Path
from nexus.repositories.base import YamlRepository, MarkdownRepository
from nexus.models import Project, CodexEntry


@pytest.fixture
def repo(tmp_path):
    yml = tmp_path / "projects.yml"
    return YamlRepository(
        path=yml,
        model=Project,
        collection_key="projects",
        id_field="slug",
    )


def test_load_empty(repo):
    assert repo.load_all() == []


def test_add_and_load(repo):
    p = Project(name="Alpha", slug="alpha", path="/tmp/alpha")
    repo.add(p)
    loaded = repo.load_all()
    assert len(loaded) == 1
    assert loaded[0].name == "Alpha"
    assert loaded[0].slug == "alpha"


def test_get_by_id(repo):
    repo.add(Project(name="A", slug="a"))
    repo.add(Project(name="B", slug="b"))
    found = repo.get("b")
    assert found is not None
    assert found.name == "B"


def test_get_missing(repo):
    assert repo.get("nope") is None


def test_update(repo):
    repo.add(Project(name="A", slug="a"))
    updated = repo.update("a", description="new desc")
    assert updated is not None
    assert updated.description == "new desc"
    reloaded = repo.get("a")
    assert reloaded.description == "new desc"


def test_update_missing(repo):
    assert repo.update("nope", description="x") is None


def test_remove(repo):
    repo.add(Project(name="A", slug="a"))
    removed = repo.remove("a")
    assert removed is not None
    assert removed.name == "A"
    assert repo.load_all() == []


def test_remove_missing(repo):
    assert repo.remove("nope") is None


def test_resolve_exact_slug(repo):
    repo.add(Project(name="Alpha Project", slug="alpha"))
    assert repo.resolve("alpha").name == "Alpha Project"


def test_resolve_by_name(repo):
    repo.add(Project(name="Alpha Project", slug="alpha"))
    assert repo.resolve("Alpha Project").name == "Alpha Project"


def test_resolve_partial(repo):
    repo.add(Project(name="Alpha Project", slug="alpha-project"))
    assert repo.resolve("alpha").name == "Alpha Project"


def test_resolve_no_match(repo):
    repo.add(Project(name="Alpha", slug="alpha"))
    assert repo.resolve("beta") is None


def test_resolve_all_duplicate_name(repo):
    repo.add(Project(name="codeguard", slug="codeguard", domain="tech", nature="ferramenta"))
    repo.add(Project(name="codeguard", slug="codeguard-2", domain="pessoal", nature="contexto"))
    results = repo.resolve_all("codeguard")
    slugs = {r.slug for r in results}
    assert slugs == {"codeguard", "codeguard-2"}


def test_resolve_all_exact_slug_returns_one(repo):
    repo.add(Project(name="codeguard", slug="codeguard", domain="tech"))
    repo.add(Project(name="codeguard", slug="codeguard-2", domain="pessoal"))
    results = repo.resolve_all("codeguard-2")
    assert len(results) == 1
    assert results[0].slug == "codeguard-2"


def test_resolve_all_unique_name(repo):
    repo.add(Project(name="alpha", slug="alpha"))
    results = repo.resolve_all("alpha")
    assert len(results) == 1
    assert results[0].slug == "alpha"


def test_resolve_all_no_match(repo):
    repo.add(Project(name="alpha", slug="alpha"))
    assert repo.resolve_all("nonexistent") == []


# --- MarkdownRepository ---

@pytest.fixture
def md_repo(tmp_path):
    codex_dir = tmp_path / "codex"
    codex_dir.mkdir()
    return MarkdownRepository(directory=codex_dir, model=CodexEntry)


def test_md_load_empty(md_repo):
    assert md_repo.load_all() == []


def test_md_save_and_load(md_repo):
    entry = CodexEntry(slug="guide", title="My Guide", kind="guia", content="# Hello")
    md_repo.save(entry)
    loaded = md_repo.load_all()
    assert len(loaded) == 1
    assert loaded[0].title == "My Guide"
    assert loaded[0].content == "# Hello"


def test_md_get_by_slug(md_repo):
    md_repo.save(CodexEntry(slug="a", title="A"))
    md_repo.save(CodexEntry(slug="b", title="B"))
    assert md_repo.get("b").title == "B"


def test_md_remove(md_repo):
    md_repo.save(CodexEntry(slug="x", title="X"))
    removed = md_repo.remove("x")
    assert removed.title == "X"
    assert md_repo.load_all() == []


def test_md_path_traversal_rejected(md_repo):
    with pytest.raises(ValueError, match="Invalid slug"):
        md_repo.get("../../../etc/passwd")


def test_md_save_traversal_rejected(md_repo):
    entry = CodexEntry(slug="../../escape", title="Evil")
    with pytest.raises(ValueError, match="Invalid slug"):
        md_repo.save(entry)

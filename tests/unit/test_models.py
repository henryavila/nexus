from nexus.models import Project, App, Idea, CodexEntry, Skill, Environment


def test_project_defaults():
    p = Project(name="Test")
    assert p.name == "Test"
    assert p.slug == ""
    assert p.domain == "pessoal"
    assert p.nature == "contexto"
    assert p.private is False
    assert p.path is None
    assert p.status is None


def test_project_to_dict_omits_none():
    p = Project(name="Test", slug="test", path="/tmp/test")
    d = p.to_dict()
    assert d["name"] == "Test"
    assert d["path"] == "/tmp/test"
    assert "icon" not in d
    assert "url" not in d


def test_project_from_dict_with_legacy_category():
    d = {"name": "Old", "category": "trabalho", "slug": "old"}
    p = Project.from_dict(d)
    assert p.domain == "trabalho"


def test_app_defaults():
    a = App(name="MyApp")
    assert a.slug == ""
    assert a.domain == "pessoal"


def test_app_to_dict():
    a = App(name="X", slug="x", url="https://x.com")
    d = a.to_dict()
    assert d["url"] == "https://x.com"
    assert "github" not in d


def test_idea_defaults():
    i = Idea(title="Cool idea")
    assert i.priority == "medium"
    assert i.id == ""
    assert i.references is None


def test_idea_to_dict_preserves_empty_list():
    i = Idea(title="X", id="abc", references=[])
    d = i.to_dict()
    assert d["references"] == []


def test_codex_entry_defaults():
    c = CodexEntry(title="Guide")
    assert c.kind == "referência"
    assert c.order is None
    assert c.content == ""


def test_skill_defaults():
    s = Skill(title="My Skill")
    assert s.scope == "global"
    assert s.slug == ""


def test_environment_defaults():
    e = Environment(hostname="mac-1", name="Mac Studio")
    assert e.location == ""
    assert e.paths == {}
    assert e.absent == []


def test_environment_to_dict():
    e = Environment(hostname="h", name="n", location="l", paths={"a": "/b"}, absent=["c"])
    d = e.to_dict()
    assert d["paths"] == {"a": "/b"}
    assert d["absent"] == ["c"]

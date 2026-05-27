from __future__ import annotations

import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any


def _safe_path_exists(path: str | Path) -> bool:
    try:
        return Path(path).exists()
    except OSError:
        return False

HAS_TEXTUAL = True

try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Vertical
    from textual.reactive import reactive
    from textual.screen import ModalScreen, Screen
    from textual.suggester import Suggester
    from textual.widgets import DataTable, Footer, Header, Input, Markdown, OptionList, Static, TabbedContent, TabPane
    from textual.widgets.data_table import RowKey
except ModuleNotFoundError:
    HAS_TEXTUAL = False
    ComposeResult = Any

    class _TextualStub:
        def __init__(self, *args, **kwargs):
            self.renderable = args[0] if args else None

        @classmethod
        def __class_getitem__(cls, _item):
            return cls

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class Binding:
        def __init__(self, key: str, action: str, description: str = "",
                     show: bool = True, priority: bool = False):
            self.key = key
            self.action = action
            self.description = description
            self.show = show
            self.priority = priority

    class Suggester:
        def __init__(self, *args, **kwargs):
            pass

    def reactive(default):
        return default

    class App(_TextualStub):
        pass

    class Screen(_TextualStub):
        BINDINGS = []

        def dismiss(self, result=None):
            return result

    class ModalScreen(Screen):
        pass

    class Vertical(_TextualStub):
        pass

    class DataTable(_TextualStub):
        class RowSelected:
            row_key = None

        class RowHighlighted:
            row_key = None
            cursor_row = 0
            data_table = None

    class Footer(_TextualStub):
        pass

    class Header(_TextualStub):
        pass

    class Input(_TextualStub):
        class Changed:
            input = None
            value = ""

        class Submitted:
            input = None

    class Markdown(_TextualStub):
        pass

    class OptionList(_TextualStub):
        class OptionSelected:
            option_index = 0

    class Static(_TextualStub):
        pass

    class TabbedContent(_TextualStub):
        class TabActivated:
            pane = None

    class TabPane(_TextualStub):
        pass

    class RowKey(str):
        @property
        def value(self) -> str:
            return str(self)

from rich.text import Text
from rich.markdown import Markdown as RichMarkdown

from nexus.cli_registry import CliEntry, detect_clis
from nexus.cli import get_container
from nexus.config import NexusConfig
from nexus.repositories.scan_repo import ScanRepository
from nexus.services import ServiceContainer

from nexus.tui.screens import (
    IdeaDetailScreen,
    CodexDetailScreen,
    CodexOrderScreen,
    SkillDetailScreen,
    EnvDetailScreen,
    CliSelectScreen,
)
from nexus.tui.widgets.filter_suggester import FilterSuggester, _parse_filter

try:
    from nexus.scanner import get_health_value, scan_all, scan_one, read_data
except ImportError:
    def get_health_value(health, key):
        return health.get(key)

    def scan_all(**kwargs):
        pass

    def scan_one(path):
        pass

    def read_data():
        return {}

# Imports needed by run_tui_loop for legacy cmd_* functions
try:
    from nexus.codex import _codex_to_dict, _update_codex_in_data_json, load_codex, resolve_codex, save_codex_entry, sort_codex
except ImportError:
    def _codex_to_dict(e):
        return {}
    def _update_codex_in_data_json():
        pass
    def load_codex():
        return []
    def resolve_codex(slug):
        return None, None
    def save_codex_entry(entry):
        pass
    def sort_codex(entries):
        return entries

try:
    from nexus.ideas import _update_ideas_in_data_json
except ImportError:
    def _update_ideas_in_data_json():
        pass

try:
    from nexus.environment import resolve_path_for_entry
except ImportError:
    def resolve_path_for_entry(slug, path):
        return path

try:
    from nexus.project_config import resolve_project_path, set_project_path_override
except ImportError:
    def resolve_project_path(path):
        return path
    def set_project_path_override(old_path, new_path):
        return False

try:
    from nexus.local_config import set_path_override
except ImportError:
    def set_path_override(old_path, new_path):
        pass

try:
    from nexus.registry import load_registry, resolve_project, update_project
except ImportError:
    def load_registry():
        return []
    def resolve_project(query):
        return None, None
    def update_project(*args, **kwargs):
        pass

try:
    from nexus.sync import auto_sync_registry, quick_sync
except ImportError:
    def auto_sync_registry(*args, **kwargs):
        pass
    def quick_sync(*args, **kwargs):
        pass


def _nature_tag(nature: str, private: bool) -> Text:
    """Return a Rich Text tag for the nature field."""
    colors = {
        "contexto":   ("on #2d4a3e", "#73daca"),
        "ferramenta": ("on #3b2d4a", "#bb9af7"),
        "companion":  ("on #2d3a4a", "#7dcfff"),
    }
    label = nature
    bg, fg = colors.get(nature, ("", ""))
    prefix = "\U0001F512" if private else ""
    return Text(f"{prefix}{label}", style=f"{fg} {bg}")


# Mapping: TUI action prefix -> files to sync (None = full sync)
_TUI_SYNC_FILES = {
    "add":     ["data/projects.yml"],
    "edit":    ["data/projects.yml"],
    "note":    ["data/projects.yml"],
    "move":    ["data/projects.yml"],
    "remove":  ["data/projects.yml"],
    "idea":    ["data/ideas.yml", "data/projects.yml"],
    "codex":   ["data/codex/"],
    "app":     ["data/apps.yml"],
    "skill":   ["data/skills/*.md"],
    "env":     ["data/environments.yml"],
    "idea-promote": ["data/ideas.yml", "data/projects.yml", "data/apps.yml"],
    "scan":    None,  # full sync
}

_sync_thread: threading.Thread | None = None


def _set_sync_thread(thread: threading.Thread | None) -> None:
    """Set the current sync thread (for testing)."""
    global _sync_thread
    _sync_thread = thread


def _tui_sync_background(action: str) -> None:
    """Run _tui_sync in a daemon thread so it doesn't block the TUI loop."""
    global _sync_thread
    if _sync_thread is not None and _sync_thread.is_alive():
        _sync_thread.join(timeout=5)
    _sync_thread = threading.Thread(target=_tui_sync, args=(action,), daemon=True)
    _sync_thread.start()


def _tui_sync(action: str) -> None:
    from nexus import NEXUS_ROOT
    # Extract resource prefix: "codex-edit" -> "codex", "add" -> "add"
    prefix = action.split("-")[0]
    sync_files = _TUI_SYNC_FILES.get(prefix)
    if sync_files is None:
        auto_sync_registry(str(NEXUS_ROOT), f"tui-{action}")
    else:
        quick_sync(str(NEXUS_ROOT), sync_files, f"tui-{action}")


class NexusApp(App):
    """Nexus TUI Launcher."""

    TITLE = "Nexus"
    CSS = """
    Screen {
        background: $surface;
    }
    #alerts {
        height: auto;
        max-height: 4;
        background: $warning-darken-2;
        color: $text;
        padding: 0 1;
    }
    #detail-bar {
        height: auto;
        max-height: 3;
        color: $text-muted;
        padding: 0 1;
        border-top: solid $primary-darken-2;
    }
    #filter-input {
        dock: top;
        margin: 0 1;
    }
    DataTable {
        height: 1fr;
    }
    TabPane {
        padding: 0;
    }
    .tab-hint {
        height: 1;
        color: $text-disabled;
        padding: 0 1;
    }
    """

    # Ordered list of (pane_id, label) -- index determines the number key (1-based)
    TAB_ORDER = [
        ("ideas", "Ideias"),
        ("projects", "Projetos"),
        ("apps", "Apps"),
        ("skills", "Skills"),
        ("environments", "Environments"),
        ("codex", "Codex"),
    ]

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("slash", "focus_filter", "Search"),
        Binding("e", "edit_item", "Edit"),
        Binding("r", "remove_item", "Remove"),
        Binding("n", "add_note", "Note"),
        Binding("w", "open_web", "Web"),
        Binding("a", "add_idea", "Adicionar"),
        Binding("p", "promote_idea", "Promote"),
        Binding("enter", "launch_project", "Abrir"),
        Binding("o", "set_codex_order", "Ordem"),
        Binding("i", "toggle_detail_bar", "Detalhes"),
    ]

    # Append digit bindings based on TAB_ORDER
    for _i, (_tab_id, _label) in enumerate(TAB_ORDER):
        BINDINGS.append(Binding(str(_i + 1), f"switch_tab({_i})", f"Tab {_i + 1}", show=False))
    del _i, _tab_id, _label

    filter_text = reactive("")

    def __init__(self, initial_tab: str = "ideas", **kwargs):
        super().__init__(**kwargs)
        self.initial_tab = initial_tab
        self._container = get_container()
        self._scan_repo = ScanRepository(self._container.config)
        self._available_clis = detect_clis()
        self._cli_modal_open = False
        self._is_mounted = False
        self._scan_cancelled = threading.Event()
        self._project_row_data: dict[RowKey, dict] = {}
        self._idea_row_data: dict[RowKey, dict] = {}
        self._app_row_data: dict[RowKey, dict] = {}
        self._codex_row_data: dict[RowKey, dict] = {}
        self._skill_row_data: dict[RowKey, dict] = {}
        self._env_row_data: dict[RowKey, dict] = {}
        self._group_keys: set[RowKey] = set()
        self._last_cursor_row: int = -1
        self._detail_bar_visible = False

    def exit(self, *args, **kwargs) -> None:
        self._scan_cancelled.set()
        super().exit(*args, **kwargs)

    def compose(self) -> ComposeResult:
        yield Header()
        yield Input(placeholder="Filtrar... (d:domínio  n:natureza)", id="filter-input", suggester=FilterSuggester(use_cache=False))
        yield Static("", id="alerts")
        tab_labels = [f"{i+1} {label}" for i, (_id, label) in enumerate(self.TAB_ORDER)]
        with TabbedContent(*tab_labels, id="tabs"):
            with TabPane(tab_labels[0], id="ideas"):
                yield DataTable(id="idea-table", cursor_type="row")
            with TabPane(tab_labels[1], id="projects"):
                yield DataTable(id="project-table", cursor_type="row")
                yield Static("Projeto: KB, contexto, módulo ou lib (depende de outro para funcionar)", classes="tab-hint")
            with TabPane(tab_labels[2], id="apps"):
                yield DataTable(id="apps-table", cursor_type="row")
                yield Static("App: software independente que roda sozinho", classes="tab-hint")
            with TabPane(tab_labels[3], id="skills"):
                yield DataTable(id="skills-table", cursor_type="row")
            with TabPane(tab_labels[4], id="environments"):
                yield DataTable(id="environments-table", cursor_type="row")
            with TabPane(tab_labels[5], id="codex"):
                yield DataTable(id="codex-table", cursor_type="row")
        detail = Static("", id="detail-bar")
        detail.display = False
        yield detail
        yield Footer()

    def on_mount(self) -> None:
        self._load_projects()
        self._load_ideas()
        self._load_apps()
        self._load_skills()
        self._load_environments()
        self._load_codex()
        tabs = self.query_one("#tabs", TabbedContent)
        tabs.active = self.initial_tab
        # Focus the correct table
        focus_map = {
            "ideas": "#idea-table",
            "projects": "#project-table",
            "apps": "#apps-table",
            "skills": "#skills-table",
            "environments": "#environments-table",
            "codex": "#codex-table",
        }
        widget_id = focus_map.get(self.initial_tab, "#idea-table")
        self.query_one(widget_id, DataTable).focus()
        self._is_mounted = True
        threading.Thread(target=self._background_scan, daemon=True).start()

    def _background_scan(self) -> None:
        """Run scan in a daemon thread with progress updates.

        Uses a daemon thread (not run_worker) so that asyncio.run()'s
        shutdown_default_executor() does not block waiting for this thread
        when the user exits the TUI.
        """
        if self._scan_cancelled.is_set():
            return

        def _progress(i, total, name):
            try:
                self.call_from_thread(self._set_subtitle, f"[{i}/{total}] {name}...")
            except Exception:
                pass  # App already exited

        scan_all(on_progress=_progress, cancelled=self._scan_cancelled.is_set)
        if self._scan_cancelled.is_set():
            return
        _update_ideas_in_data_json()
        if self._scan_cancelled.is_set():
            return
        _update_codex_in_data_json()
        if self._scan_cancelled.is_set():
            return
        _tui_sync("scan")
        if self._scan_cancelled.is_set():
            return
        try:
            self.call_from_thread(self._set_subtitle, "")
            self.call_from_thread(self._reload_active_tab)
        except Exception:
            pass  # App already exited

    def _reload_active_tab(self) -> None:
        """Reload data for whichever tab is currently active."""
        load_map = {
            "ideas": self._load_ideas,
            "projects": self._load_projects,
            "apps": self._load_apps,
            "skills": self._load_skills,
            "environments": self._load_environments,
            "codex": self._load_codex,
        }
        loader = load_map.get(self._active_tab(), self._load_ideas)
        loader()

    def _set_subtitle(self, text: str) -> None:
        self.sub_title = text

    def _active_tab(self) -> str:
        return self.query_one("#tabs", TabbedContent).active

    def check_action(self, action: str, parameters: tuple) -> bool | None:
        """Hide bindings that don't apply to the active tab."""
        active = self._active_tab()
        all_tabs = {"projects", "ideas", "apps", "codex", "skills", "environments"}
        rules = {
            "add_note":          {"projects", "apps"},
            "open_web":          {"projects", "apps"},
            "add_idea":          {"projects", "ideas", "codex", "apps", "skills"},
            "promote_idea":      {"ideas"},
            "toggle_detail_bar": all_tabs,
            "remove_item":       {"projects", "ideas", "apps", "codex"},
            "edit_item":         {"projects", "ideas", "apps", "codex"},
            "set_codex_order":   {"codex"},
        }
        allowed = rules.get(action)
        if allowed is not None and active not in allowed:
            return False
        return True

    def action_switch_tab(self, index: int) -> None:
        """Switch to tab by index (0-based, matches TAB_ORDER)."""
        if index < 0 or index >= len(self.TAB_ORDER):
            return
        tab_id = self.TAB_ORDER[index][0]
        tabs = self.query_one("#tabs", TabbedContent)
        if tabs.active != tab_id:
            tabs.active = tab_id

    def _load_projects(self) -> None:
        # Load projects from ServiceContainer
        project_models = self._container.projects.list_all()
        registry_names = {p.name for p in project_models}

        # Merge with scan data for activity/health/git/status
        scan_data = self._scan_repo.read()
        scan_projects = {p.get("slug") or p.get("name"): p for p in scan_data.get("projects", [])}

        projects = []
        for proj in project_models:
            d = proj.to_dict()
            scan_info = scan_projects.get(d.get("slug") or d.get("name"), {})
            d.update({k: scan_info[k] for k in ("last_activity", "health", "git", "status") if k in scan_info})
            projects.append(d)

        # Parse filter
        filt = _parse_filter(self.filter_text) if self.filter_text else None

        active_projects = []
        archived_projects = []
        for p in projects:
            if p.get("status") in ("archived", "replaced"):
                archived_projects.append(p)
            else:
                if filt:
                    if filt["d"] and (p.get("domain") or "").lower() != filt["d"].lower():
                        continue
                    if filt["n"] and (p.get("nature") or "").lower() != filt["n"].lower():
                        continue
                    if filt["text"]:
                        q = filt["text"].lower()
                        if not (q in (p.get("name") or "").lower()
                                or q in (p.get("description") or "").lower()
                                or q in (p.get("note") or "").lower()):
                            continue
                active_projects.append(p)

        # Alerts
        alerts = []
        for p in projects:
            health = p.get("health") or {}
            if get_health_value(health, "claude_memory_portable") is False:
                alerts.append(f"⚠ {p.get('name')}: memória Claude local (não portável)")
            if get_health_value(health, "path_exists") is False:
                alerts.append(f"⚠ {p.get('name')}: path não existe")
        alert_widget = self.query_one("#alerts", Static)
        if alerts:
            alert_widget.update("\n".join(alerts))
            alert_widget.display = True
        else:
            alert_widget.display = False

        # Group by domain
        from collections import defaultdict
        groups = defaultdict(list)
        for p in active_projects:
            groups[p.get("domain") or "pessoal"].append(p)

        # Sort within groups by last_activity desc
        for domain in groups:
            groups[domain].sort(key=lambda p: p.get("last_activity") or "", reverse=True)

        # Sort domains by most recent activity
        sorted_domains = sorted(
            groups.keys(),
            key=lambda d: max((p.get("last_activity") or "" for p in groups[d]), default=""),
            reverse=True,
        )

        # Build table
        table = self.query_one("#project-table", DataTable)
        table.clear(columns=True)
        self._project_row_data.clear()
        # Remove old project group keys
        self._group_keys = {k for k in self._group_keys if not k.value.startswith("_group:proj:")}

        table.add_column("", width=2, key="col_icon")
        table.add_column("Nome", width=30, key="col_name")
        table.add_column("Natureza", width=14, key="col_tipo")
        table.add_column("Status", width=2, key="col_st")
        table.add_column("Atividade", width=10, key="col_ativ")
        table.add_column("Saúde", width=2, key="col_saude")
        table.add_column("Descrição / Nota", width=40, key="col_desc")

        for domain in sorted_domains:
            header_text = Text(f"── {domain} {'─' * 40}", style="bold #7aa2f7")
            gk = table.add_row(Text(""), header_text, Text(""), Text(""), Text(""), Text(""), Text(""), key=f"_group:proj:{domain}")
            self._group_keys.add(gk)

            for p in groups[domain]:
                icon = p.get("icon") or "\U0001F4C1"
                name = p.get("name", "???")
                nature = p.get("nature") or "contexto"
                private = p.get("private", False)
                status = p.get("status", "active")
                git = p.get("git") or {}

                if status == "archived":
                    sym = "◇"
                elif isinstance(git, dict) and git.get("dirty"):
                    sym = "◐"
                else:
                    sym = "●"

                last = p.get("last_activity")
                if last:
                    try:
                        days = (datetime.now().date() - datetime.fromisoformat(last).date()).days
                        rel = "today" if days <= 0 else f"{days}d"
                    except ValueError:
                        rel = last
                else:
                    rel = "n/a"

                mem = get_health_value(p.get("health") or {}, "claude_memory_portable")
                saude = "\U0001F9E0" if mem is True else ("⚠" if mem is False else "")

                note = p.get("note")
                if note:
                    desc_text = Text(f'"{note}"', style="#e0af68")
                else:
                    desc_text = Text((p.get("description") or "")[:80], style="dim")

                slug = p.get("slug", "")
                row_key = slug or name.lower().replace(" ", "-")
                rk = table.add_row(
                    icon, name, _nature_tag(nature, private), sym, rel, saude, desc_text,
                    key=row_key,
                )
                self._project_row_data[rk] = p

        # Archive section (also filtered)
        if filt:
            filtered_archived = []
            for p in archived_projects:
                if filt["d"] and (p.get("domain") or "").lower() != filt["d"].lower():
                    continue
                if filt["n"] and (p.get("nature") or "").lower() != filt["n"].lower():
                    continue
                if filt["text"]:
                    q = filt["text"].lower()
                    if not (q in (p.get("name") or "").lower()
                            or q in (p.get("description") or "").lower()):
                        continue
                filtered_archived.append(p)
            archived_projects = filtered_archived

        if archived_projects:
            gk = table.add_row(
                Text(""), Text("── arquivo " + "─" * 40, style="dim #565f89"),
                Text(""), Text(""), Text(""), Text(""), Text(""),
                key="_group:proj:arquivo",
            )
            self._group_keys.add(gk)
            for p in archived_projects:
                icon = p.get("icon") or "\U0001F4C1"
                name = Text(p.get("name", "???"), style="dim")
                nature = p.get("nature") or "contexto"
                tag = _nature_tag(nature, p.get("private", False))
                tag.stylize("dim")
                slug = p.get("slug", "")
                row_key = f"archived:{slug or name}"
                rk = table.add_row(
                    icon, name, tag, "◇", Text("", style="dim"), "", Text("", style="dim"),
                    key=row_key,
                )
                self._project_row_data[rk] = p

        self._calc_column_widths("project-table")
        self._update_detail_bar()

    def _load_ideas(self) -> None:
        idea_models = self._container.ideas.list_all()
        ideas = [i.to_dict() for i in idea_models]

        filt = _parse_filter(self.filter_text) if self.filter_text else None
        if filt:
            filtered = []
            for idea in ideas:
                if filt["d"] and (idea.get("domain") or "").lower() != filt["d"].lower():
                    continue
                if filt["text"]:
                    q = filt["text"].lower()
                    if not (q in (idea.get("title") or "").lower()
                            or q in (idea.get("description") or "").lower()):
                        continue
                filtered.append(idea)
            ideas = filtered

        # Sort: priority desc (high first), then created desc (newest first)
        # Stable sort: first by created desc, then by priority asc
        ideas.sort(key=lambda i: i.get("created") or "", reverse=True)
        priority_order = {"high": 0, "medium": 1, "low": 2}
        ideas.sort(key=lambda i: priority_order.get(i.get("priority", "medium"), 1))

        # Group by domain
        from collections import defaultdict
        groups = defaultdict(list)
        for idea in ideas:
            groups[idea.get("domain") or "pessoal"].append(idea)

        # Sort domains alphabetically
        sorted_domains = sorted(groups.keys())

        table = self.query_one("#idea-table", DataTable)
        table.clear(columns=True)
        self._idea_row_data.clear()
        self._group_keys = {k for k in self._group_keys if not k.value.startswith("_group:idea:")}

        table.add_column("", width=2, key="col_badge")
        table.add_column("Título", width=30, key="col_title")
        table.add_column("ID", width=10, key="col_id")
        table.add_column("Descrição", width=40, key="col_desc")

        priority_badges = {"high": "\U0001F534", "medium": "\U0001F7E1", "low": "\U0001F7E2"}
        for domain in sorted_domains:
            header_text = Text(f"── {domain} {'─' * 40}", style="bold #7aa2f7")
            gk = table.add_row(Text(""), header_text, Text(""), Text(""), key=f"_group:idea:{domain}")
            self._group_keys.add(gk)

            for idea in groups[domain]:
                badge = priority_badges.get(idea.get("priority", "medium"), "\U0001F7E1")
                idea_id = idea.get("id", "")
                rk = table.add_row(
                    badge,
                    idea.get("title", "???"),
                    idea_id,
                    Text((idea.get("description") or "")[:80], style="dim"),
                    key=f"idea:{idea_id}",
                )
                self._idea_row_data[rk] = idea

        self._calc_column_widths("idea-table")
        self._update_detail_bar()

    def _load_codex(self) -> None:
        codex_models = self._container.codex.list_all()
        # Sort: entries with order first (by order asc), then by title
        codex_models.sort(key=lambda e: (e.order is None, e.order or 0, e.title.lower()))
        entries = []
        for e in codex_models:
            d = {
                "slug": e.slug,
                "title": e.title,
                "kind": e.kind,
                "domain": e.domain,
                "order": e.order,
                "created": e.created,
                "updated": e.updated,
                "content": e.content,
            }
            entries.append(d)

        filt = _parse_filter(self.filter_text) if self.filter_text else None
        if filt:
            filtered = []
            for e in entries:
                if filt["d"] and (e.get("domain") or "").lower() != filt["d"].lower():
                    continue
                if filt["k"] and (e.get("kind") or "").lower() != filt["k"].lower():
                    continue
                if filt["text"]:
                    q = filt["text"].lower()
                    if not (q in (e.get("title") or "").lower()
                            or q in (e.get("slug") or "").lower()):
                        continue
                filtered.append(e)
            entries = filtered

        table = self.query_one("#codex-table", DataTable)
        table.clear(columns=True)
        self._codex_row_data.clear()

        table.add_column("Ordem", width=6, key="col_order")
        table.add_column("Título", width=30, key="col_title")
        table.add_column("Tipo", width=14, key="col_kind")
        table.add_column("Domínio", width=14, key="col_domain")
        table.add_column("Slug", width=16, key="col_slug")

        for e in entries:
            order = e.get("order")
            order_str = str(order) if order is not None else ""
            slug = e.get("slug", "")
            rk = table.add_row(
                order_str,
                e.get("title", "???"),
                e.get("kind", ""),
                e.get("domain", ""),
                slug,
                key=f"codex:{slug}",
            )
            self._codex_row_data[rk] = e

        self._calc_column_widths("codex-table")
        self._update_detail_bar()

    def _load_apps(self) -> None:
        app_models = self._container.apps.list_all()
        apps = [a.to_dict() for a in app_models]

        filt = _parse_filter(self.filter_text) if self.filter_text else None
        if filt:
            filtered = []
            for a in apps:
                if filt["d"] and (a.get("domain") or "").lower() != filt["d"].lower():
                    continue
                if filt["text"]:
                    q = filt["text"].lower()
                    if not (q in (a.get("name") or "").lower()
                            or q in (a.get("description") or "").lower()):
                        continue
                filtered.append(a)
            apps = filtered

        from collections import defaultdict
        groups = defaultdict(list)
        for a in apps:
            groups[a.get("domain") or "pessoal"].append(a)
        for domain in groups:
            groups[domain].sort(key=lambda a: (a.get("name") or "").lower())
        sorted_domains = sorted(groups.keys())

        table = self.query_one("#apps-table", DataTable)
        table.clear(columns=True)
        self._app_row_data.clear()
        self._group_keys = {k for k in self._group_keys if not k.value.startswith("_group:app:")}

        table.add_column("", width=2, key="col_icon")
        table.add_column("Nome", width=30, key="col_name")
        table.add_column("Domínio", width=16, key="col_domain")
        table.add_column("Descrição", width=40, key="col_desc")

        for domain in sorted_domains:
            header_text = Text(f"── {domain} {'─' * 40}", style="bold #7aa2f7")
            gk = table.add_row(Text(""), header_text, Text(""), Text(""), key=f"_group:app:{domain}")
            self._group_keys.add(gk)
            for a in groups[domain]:
                icon = a.get("icon") or "\U0001F4F1"
                slug = a.get("slug", "")
                rk = table.add_row(
                    icon,
                    a.get("name", "???"),
                    a.get("domain", ""),
                    Text((a.get("description") or "")[:80], style="dim"),
                    key=f"app:{slug}",
                )
                self._app_row_data[rk] = a

        self._calc_column_widths("apps-table")
        self._update_detail_bar()

    def _load_skills(self) -> None:
        scan_data = self._scan_repo.read()
        skills_data = scan_data.get("skills", {})

        items = []
        for slug, info in skills_data.items():
            entry = dict(info)
            entry["slug"] = slug
            items.append(entry)

        if self.filter_text:
            q = self.filter_text.lower()
            items = [
                s for s in items
                if q in (s.get("slug") or "").lower()
                or q in (s.get("title") or "").lower()
                or any(q in h.lower() for h in s.get("presence", {}))
                or any(
                    q in r.lower()
                    for v in s.get("presence", {}).values()
                    for r in v.get("repos", [])
                )
            ]

        table = self.query_one("#skills-table", DataTable)
        table.clear(columns=True)
        self._skill_row_data.clear()

        table.add_column("Escopo", width=3, key="col_scope")
        table.add_column("Nome", width=30, key="col_name")
        table.add_column("Slug", width=20, key="col_slug")
        table.add_column("Presença", width=40, key="col_presence")

        for s in items:
            presence = s.get("presence", {})
            if not presence:
                badge = "❓"  # ?
            elif any(v.get("global") for v in presence.values()):
                badge = "\U0001F310"  # globe
            else:
                badge = "\U0001F4E6"  # package

            parts = []
            for hostname, info in presence.items():
                if info.get("global"):
                    parts.append(f"{hostname} (global)")
                else:
                    repos = info.get("repos", [])
                    parts.append(f"{hostname} ({', '.join(repos)})")
            presence_str = " · ".join(parts)

            slug = s.get("slug", "???")
            rk = table.add_row(
                badge,
                s.get("title", slug),
                slug,
                Text(presence_str, style="dim") if presence_str else Text("", style="dim"),
                key=f"skill:{slug}",
            )
            self._skill_row_data[rk] = s

        self._calc_column_widths("skills-table")
        self._update_detail_bar()

    def _load_environments(self) -> None:
        env_models = self._container.environments.list_all()
        envs_data = [e.to_dict() for e in env_models]

        if self.filter_text:
            q = self.filter_text.lower()
            envs_data = [
                e for e in envs_data
                if q in (e.get("name") or "").lower()
                or q in (e.get("hostname") or "").lower()
                or q in (e.get("location") or "").lower()
            ]

        table = self.query_one("#environments-table", DataTable)
        table.clear(columns=True)
        self._env_row_data.clear()

        table.add_column("", width=2, key="col_icon")
        table.add_column("Nome", width=20, key="col_name")
        table.add_column("Localização", width=20, key="col_location")
        table.add_column("Hostname", width=20, key="col_hostname")
        table.add_column("Último Acesso", width=14, key="col_last_seen")

        for env in envs_data:
            hostname = env.get("hostname", "???")
            rk = table.add_row(
                "\U0001F5A5️",
                env.get("name", hostname),
                env.get("location", "???"),
                hostname,
                env.get("last_seen", "n/a"),
                key=f"env:{hostname}",
            )
            self._env_row_data[rk] = env

        self._calc_column_widths("environments-table")
        self._update_detail_bar()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "filter-input":
            self.filter_text = event.value
            active = self._active_tab()
            load_map = {
                "ideas": self._load_ideas,
                "projects": self._load_projects,
                "apps": self._load_apps,
                "skills": self._load_skills,
                "environments": self._load_environments,
                "codex": self._load_codex,
            }
            loader = load_map.get(active, self._load_projects)
            loader()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Defocus filter on Enter."""
        self.query_one("#filter-input", Input).blur()

    def key_escape(self) -> None:
        """Clear filter and defocus on Escape."""
        inp = self.query_one("#filter-input", Input)
        if inp.has_focus:
            inp.value = ""
            inp.blur()

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        if not self._is_mounted:
            return
        pane_id = event.pane.id
        if pane_id != self._active_tab():
            return

        # Toggle detail-bar visibility
        try:
            detail = self.query_one("#detail-bar", Static)
            detail.display = self._detail_bar_visible
        except Exception:
            pass

        # Dynamic placeholder
        placeholders = {
            "projects": "Filtrar... (d:domínio  n:natureza)",
            "ideas": "Filtrar... (d:domínio)",
            "apps": "Filtrar... (d:domínio)",
            "codex": "Filtrar... (d:domínio  k:kind)",
        }
        try:
            inp = self.query_one("#filter-input", Input)
            inp.placeholder = placeholders.get(pane_id, "Filtrar...")
        except Exception:
            pass

        self._reload_active_tab()
        self.mutate_reactive(NexusApp.filter_text)

        # Focus the correct table for this tab
        focus_map = {
            "ideas": "#idea-table",
            "projects": "#project-table",
            "apps": "#apps-table",
            "skills": "#skills-table",
            "environments": "#environments-table",
            "codex": "#codex-table",
        }
        focus_id = focus_map.get(pane_id, "#idea-table")
        self.query_one(focus_id, DataTable).focus()

    def action_focus_filter(self) -> None:
        self.query_one("#filter-input", Input).focus()

    def _calc_column_widths(self, table_id: str) -> None:
        """Calculate and set dynamic column widths based on terminal size."""
        try:
            table = self.query_one(f"#{table_id}", DataTable)
        except Exception:
            return
        total = self.size.width
        # Subtract TabbedContent chrome (~4) and cell padding (2 per col)
        chrome = 4
        if table_id == "project-table":
            fixed = 2 + 14 + 2 + 10 + 2  # icon, natureza, status, atividade, saúde
            n_cols = 7
            padding = n_cols * 2
            remaining = max(total - fixed - padding - chrome, 20)
            name_w = max(int(remaining * 0.3), 10)
            desc_w = max(remaining - name_w, 10)
            for key, w in [("col_name", name_w), ("col_desc", desc_w)]:
                if key in table.columns:
                    table.columns[key].width = w
        elif table_id == "idea-table":
            fixed = 2 + 10  # badge, id
            n_cols = 4
            padding = n_cols * 2
            remaining = max(total - fixed - padding - chrome, 20)
            title_w = max(int(remaining * 0.4), 10)
            desc_w = max(remaining - title_w, 10)
            for key, w in [("col_title", title_w), ("col_desc", desc_w)]:
                if key in table.columns:
                    table.columns[key].width = w
        elif table_id == "apps-table":
            fixed = 2 + 16  # icon, domínio
            n_cols = 4
            padding = n_cols * 2
            remaining = max(total - fixed - padding - chrome, 20)
            name_w = max(int(remaining * 0.3), 10)
            desc_w = max(remaining - name_w, 10)
            for key, w in [("col_name", name_w), ("col_desc", desc_w)]:
                if key in table.columns:
                    table.columns[key].width = w
        elif table_id == "codex-table":
            fixed = 6 + 14 + 14 + 16  # ordem, tipo, domínio, slug
            n_cols = 5
            padding = n_cols * 2
            remaining = max(total - fixed - padding - chrome, 20)
            title_w = max(remaining, 10)
            if "col_title" in table.columns:
                table.columns["col_title"].width = title_w
        elif table_id == "skills-table":
            fixed = 3 + 20  # escopo, slug
            n_cols = 4
            padding = n_cols * 2
            remaining = max(total - fixed - padding - chrome, 20)
            name_w = max(int(remaining * 0.3), 10)
            pres_w = max(remaining - name_w, 10)
            for key, w in [("col_name", name_w), ("col_presence", pres_w)]:
                if key in table.columns:
                    table.columns[key].width = w
        elif table_id == "environments-table":
            fixed = 2 + 20 + 14  # icon, hostname, last_seen
            n_cols = 5
            padding = n_cols * 2
            remaining = max(total - fixed - padding - chrome, 20)
            name_w = max(int(remaining * 0.5), 10)
            loc_w = max(remaining - name_w, 10)
            for key, w in [("col_name", name_w), ("col_location", loc_w)]:
                if key in table.columns:
                    table.columns[key].width = w

    def on_resize(self, event) -> None:
        """Recalculate column widths when terminal is resized."""
        active = self._active_tab()
        table_map = {
            "projects": "project-table", "ideas": "idea-table", "apps": "apps-table",
            "codex": "codex-table", "skills": "skills-table", "environments": "environments-table",
        }
        table_id = table_map.get(active)
        if table_id:
            self._calc_column_widths(table_id)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key is None or self._is_group_row(event.row_key):
            return
        self.action_launch_project()

    def _get_selected_from_table(self, table_id: str) -> dict | None:
        """Get data dict for the currently highlighted DataTable row."""
        try:
            table = self.query_one(f"#{table_id}", DataTable)
        except Exception:
            return None
        if table.row_count == 0:
            return None
        row_key, _ = table.coordinate_to_cell_key((table.cursor_row, 0))
        if self._is_group_row(row_key):
            return None
        return self._row_data_for_tab().get(row_key)

    def _get_selected_project(self) -> dict | None:
        return self._get_selected_from_table("project-table")

    def _get_selected_idea(self) -> dict | None:
        return self._get_selected_from_table("idea-table")

    def _get_selected_app(self) -> dict | None:
        return self._get_selected_from_table("apps-table")

    def _get_selected_codex(self) -> dict | None:
        return self._get_selected_from_table("codex-table")

    def _get_selected_skill(self) -> dict | None:
        return self._get_selected_from_table("skills-table")

    def _get_selected_env(self) -> dict | None:
        return self._get_selected_from_table("environments-table")

    # -- Actions that check active tab --

    def action_launch_project(self) -> None:
        active = self._active_tab()
        if active == "ideas":
            idea = self._get_selected_idea()
            if idea:
                self.push_screen(
                    IdeaDetailScreen(idea),
                    callback=self._on_idea_detail_dismissed,
                )
            return
        if active == "codex":
            codex = self._get_selected_codex()
            if codex:
                self.push_screen(
                    CodexDetailScreen(codex),
                    callback=self._on_codex_detail_dismissed,
                )
            return
        if active == "apps":
            app = self._get_selected_app()
            if app:
                url = app.get("url")
                if url:
                    import webbrowser
                    webbrowser.open(url)
                    self.notify(f"Abrindo {url}")
                else:
                    self.notify("App não tem URL configurada", severity="warning")
            return
        if active == "skills":
            skill = self._get_selected_skill()
            if skill:
                self.push_screen(
                    SkillDetailScreen(skill),
                    callback=self._on_skill_detail_dismissed,
                )
            return
        if active == "environments":
            env = self._get_selected_env()
            if env:
                scan_data = self._scan_repo.read()
                skills_data = scan_data.get("skills", {})
                self.push_screen(EnvDetailScreen(env, skills_data))
            return
        if active != "projects":
            return
        if self._cli_modal_open:
            return
        proj = self._get_selected_project()
        if not proj:
            return
        slug = proj.get("slug", "")
        path = resolve_path_for_entry(slug, proj.get("path"))
        resolved = resolve_project_path(path) if path else ""
        if not resolved or not _safe_path_exists(resolved):
            self.notify(f"Path não existe: {resolved or path}", severity="error")
            self.exit(result=("launch_missing", path))
            return
        if not self._available_clis:
            self.notify("Nenhum AI CLI encontrado no PATH", severity="error")
            return
        if len(self._available_clis) == 1:
            self.exit(result=("launch", {"path": resolved, "cli": self._available_clis[0].cmd}))
            return
        # 2+ CLIs: show modal
        self._cli_modal_open = True
        self.push_screen(
            CliSelectScreen(self._available_clis),
            callback=lambda cli: self._on_cli_selected(cli, resolved),
        )

    def _on_cli_selected(self, cli: CliEntry | None, path: str) -> None:
        self._cli_modal_open = False
        if cli is None:
            return
        self.exit(result=("launch", {"path": path, "cli": cli.cmd}))

    def _on_idea_detail_dismissed(self, result: str | None) -> None:
        if result == "edit":
            idea = self._get_selected_idea()
            if idea:
                self.exit(result=("idea_edit", idea.get("id")))

    def _on_codex_detail_dismissed(self, result: str | None) -> None:
        if result == "edit":
            codex = self._get_selected_codex()
            if codex:
                self.exit(result=("codex_edit", codex.get("slug")))

    def _on_skill_detail_dismissed(self, result: str | None) -> None:
        if result == "edit":
            skill = self._get_selected_skill()
            if skill:
                self.exit(result=("skill_edit", skill.get("slug")))

    def action_edit_item(self) -> None:
        active = self._active_tab()
        if active == "ideas":
            idea = self._get_selected_idea()
            if idea:
                self.exit(result=("idea_edit", idea.get("id")))
        elif active == "projects":
            proj = self._get_selected_project()
            if proj:
                self.exit(result=("edit", proj.get("name") or proj.get("path")))
        elif active == "codex":
            codex = self._get_selected_codex()
            if codex:
                self.exit(result=("codex_edit", codex.get("slug")))
        elif active == "apps":
            app = self._get_selected_app()
            if app:
                self.exit(result=("app_edit", app.get("slug")))
        elif active == "skills":
            skill = self._get_selected_skill()
            if skill:
                self.exit(result=("skill_edit", skill.get("slug")))
        elif active == "environments":
            env = self._get_selected_env()
            if env:
                self.exit(result=("env_edit", env.get("hostname")))

    def action_set_codex_order(self) -> None:
        codex = self._get_selected_codex()
        if not codex:
            self.notify("Nenhuma entrada selecionada", severity="warning")
            return
        self.push_screen(
            CodexOrderScreen(current_order=codex.get("order")),
            callback=self._on_codex_order_result,
        )

    def _on_codex_order_result(self, new_order: int | None) -> None:
        codex = self._get_selected_codex()
        if codex is None:
            return
        slug = codex.get("slug", "")
        # Use ServiceContainer to update the order
        entry = self._container.codex.resolve(slug)
        if entry is None:
            return
        self._container.codex.edit(slug, order=new_order)
        self._load_codex()
        self.notify(f"Ordem de '{entry.title}' → {new_order if new_order is not None else 'nenhuma'}")

    def action_add_note(self) -> None:
        active = self._active_tab()
        if active == "apps":
            app = self._get_selected_app()
            if app:
                self.exit(result=("app_note", app.get("slug")))
            return
        if active != "projects":
            return
        proj = self._get_selected_project()
        if not proj:
            return
        self.exit(result=("note", proj.get("name") or proj.get("path")))

    def action_open_web(self) -> None:
        active = self._active_tab()
        if active == "projects":
            proj = self._get_selected_project()
            if not proj:
                return
            url = proj.get("url")
            web = proj.get("web") or {}
            route = web.get("route")
            if url:
                import webbrowser
                webbrowser.open(url)
                self.notify(f"Abrindo {url}")
            elif route:
                self.notify("Projeto tem página web mas não tem URL configurada", severity="warning")
            else:
                self.notify("Projeto não tem URL nem página web", severity="warning")
        elif active == "apps":
            app_data = self._get_selected_app()
            if app_data and app_data.get("url"):
                import webbrowser
                webbrowser.open(app_data["url"])
                self.notify(f"Abrindo {app_data['url']}")
            elif app_data:
                self.notify("App não tem URL configurada", severity="warning")
        else:
            self.notify("Ação não disponível", severity="warning")

    def action_remove_item(self) -> None:
        active = self._active_tab()
        if active == "ideas":
            idea = self._get_selected_idea()
            if idea:
                self.exit(result=("idea_remove", idea.get("id")))
        elif active == "projects":
            proj = self._get_selected_project()
            if proj:
                self.exit(result=("remove", proj.get("name") or proj.get("path")))
        elif active == "codex":
            codex = self._get_selected_codex()
            if codex:
                self.exit(result=("codex_remove", codex.get("slug")))
        elif active == "apps":
            app = self._get_selected_app()
            if app:
                self.exit(result=("app_remove", app.get("slug")))
        elif active == "skills":
            skill = self._get_selected_skill()
            if skill:
                self.exit(result=("skill_remove", skill.get("slug")))
        elif active == "environments":
            self.notify("Use 'nexus env' para gerenciar environments", severity="warning")

    def action_add_idea(self) -> None:
        active = self._active_tab()
        if active == "ideas":
            self.exit(result=("idea_add", None))
        elif active == "codex":
            self.exit(result=("codex_add", None))
        elif active == "apps":
            self.exit(result=("app_add", None))
        elif active == "skills":
            self.exit(result=("skill_add", None))
        elif active == "projects":
            self.exit(result=("add", None))

    def action_promote_idea(self) -> None:
        active = self._active_tab()
        if active == "ideas":
            idea = self._get_selected_idea()
            if idea:
                self.exit(result=("idea_promote", idea.get("id")))
        else:
            self.notify("Ação não disponível", severity="warning")

    def action_toggle_detail_bar(self) -> None:
        bar = self.query_one("#detail-bar", Static)
        self._detail_bar_visible = not self._detail_bar_visible
        bar.display = self._detail_bar_visible

    def _is_group_row(self, row_key: RowKey) -> bool:
        return row_key in self._group_keys

    def _row_data_for_tab(self) -> dict[RowKey, dict]:
        """Return the row data dict for the current active tab."""
        active = self._active_tab()
        return {
            "projects": self._project_row_data,
            "ideas": self._idea_row_data,
            "apps": self._app_row_data,
            "codex": self._codex_row_data,
            "skills": self._skill_row_data,
            "environments": self._env_row_data,
        }.get(active, {})

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key is None:
            return
        if self._is_group_row(event.row_key):
            table = event.data_table
            current = event.cursor_row
            direction = 1 if current >= self._last_cursor_row else -1
            new_row = current + direction
            max_attempts = table.row_count
            attempts = 0
            while 0 <= new_row < table.row_count and attempts < max_attempts:
                cell_key = table.coordinate_to_cell_key((new_row, 0))
                if not self._is_group_row(cell_key.row_key):
                    table.move_cursor(row=new_row)
                    self._last_cursor_row = new_row
                    return
                new_row += direction
                attempts += 1
            # All rows are headers -- stay put
            return
        self._last_cursor_row = event.cursor_row
        self._update_detail_bar()

    def _update_detail_bar(self) -> None:
        """Update detail bar content based on current selection (even if hidden)."""
        active = self._active_tab()
        table_map = {
            "projects": "project-table", "ideas": "idea-table", "apps": "apps-table",
            "codex": "codex-table", "skills": "skills-table", "environments": "environments-table",
        }
        table_id = table_map.get(active)
        if not table_id:
            return
        try:
            table = self.query_one(f"#{table_id}", DataTable)
        except Exception:
            return
        if table.row_count == 0:
            return
        row_key, _ = table.coordinate_to_cell_key((table.cursor_row, 0))
        if self._is_group_row(row_key):
            return
        data = self._row_data_for_tab().get(row_key)
        if not data:
            return

        bar = self.query_one("#detail-bar", Static)
        if active == "projects":
            parts = []
            icon = data.get("icon") or "\U0001F4C1"
            name = data.get("name", "???")
            slug = data.get("slug", "")
            slug_str = f" ({slug})" if slug and slug != name.lower() else ""
            parts.append(f"[bold]{icon} {name}{slug_str}[/bold]")
            if data.get("path"):
                parts.append(f"path {data['path']}")
            if data.get("repo"):
                parts.append(f"repo {data['repo']}")
            mem = get_health_value(data.get("health") or {}, "claude_memory_portable")
            if mem is True:
                parts.append("saúde \U0001F9E0 portável")
            elif mem is False:
                parts.append("saúde ⚠ local")
            status = data.get("status", "active")
            git = data.get("git") or {}
            dirty = " (dirty)" if isinstance(git, dict) and git.get("dirty") else ""
            parts.append(f"status {status}{dirty}")
            if data.get("note"):
                parts.append(f'nota "{data["note"]}"')
            line1 = " · ".join(parts)
            line2 = data.get("description") or ""
            bar.update(f"{line1}\n{line2}")
        elif active == "ideas":
            parts = []
            title = data.get("title", "???")
            parts.append(f"[bold]{title}[/bold]")
            parts.append(f"prioridade {data.get('priority', 'medium')}")
            parts.append(f"domínio {data.get('domain', 'pessoal')}")
            if data.get("created"):
                parts.append(f"criado {data['created']}")
            line1 = " · ".join(parts)
            lines = [line1]
            if data.get("notes"):
                lines.append(data["notes"])
            elif data.get("description"):
                lines.append(data["description"])
            bar.update("\n".join(lines))
        elif active == "apps":
            parts = []
            icon = data.get("icon") or "\U0001F4F1"
            name = data.get("name", "???")
            parts.append(f"[bold]{icon} {name}[/bold]")
            parts.append(f"domínio {data.get('domain', 'pessoal')}")
            if data.get("github"):
                parts.append(f"github {data['github']}")
            if data.get("url"):
                parts.append(f"url {data['url']}")
            if data.get("note"):
                parts.append(f'nota "{data["note"]}"')
            line1 = " · ".join(parts)
            line2 = data.get("description") or ""
            bar.update(f"{line1}\n{line2}")
        elif active == "codex":
            parts = []
            parts.append(f"[bold]\U0001F4D6 {data.get('title', '???')}[/bold]")
            parts.append(f"tipo {data.get('kind', '')}")
            parts.append(f"domínio {data.get('domain', '')}")
            parts.append(f"slug {data.get('slug', '')}")
            if data.get("created"):
                parts.append(f"criado {data['created']}")
            if data.get("updated"):
                parts.append(f"atualizado {data['updated']}")
            line1 = " · ".join(parts)
            content = (data.get("content") or "")[:80].replace("\n", " ")
            bar.update(f"{line1}\n{content}" if content else line1)
        elif active == "skills":
            parts = []
            slug = data.get("slug", "???")
            parts.append(f"[bold]{data.get('title', slug)}[/bold]")
            parts.append(f"slug {slug}")
            presence = data.get("presence", {})
            if not presence:
                parts.append("escopo ❓")
            elif any(v.get("global") for v in presence.values()):
                parts.append("escopo \U0001F310 global")
            else:
                parts.append("escopo \U0001F4E6 projeto")
            if data.get("url"):
                parts.append(f"url {data['url']}")
            line1 = " · ".join(parts)
            pres_parts = []
            for hostname, info in presence.items():
                if info.get("global"):
                    pres_parts.append(f"{hostname} (global)")
                else:
                    repos = ", ".join(info.get("repos", []))
                    pres_parts.append(f"{hostname} ({repos})")
            line2 = " · ".join(pres_parts)
            bar.update(f"{line1}\n{line2}" if line2 else line1)
        elif active == "environments":
            parts = []
            parts.append(f"[bold]\U0001F5A5️ {data.get('name', '???')}[/bold]")
            parts.append(f"hostname {data.get('hostname', '???')}")
            parts.append(f"localização {data.get('location', '???')}")
            if data.get("last_seen") and data["last_seen"] != "n/a":
                parts.append(f"último acesso {data['last_seen']}")
            line1 = " · ".join(parts)
            paths = data.get("paths") or {}
            line2 = f"{len(paths)} projetos" if paths else ""
            bar.update(f"{line1}\n{line2}" if line2 else line1)


def run_tui_loop(initial_tab: str = "ideas") -> int:
    """Run the TUI in a loop, re-launching after interactive actions."""
    next_tab = initial_tab

    while True:
        app = NexusApp(initial_tab=next_tab)
        result = app.run()

        if result is None:
            return 0

        action, data = result[0], result[1]

        if action == "launch":
            path = data["path"]
            cli = data["cli"]
            os.chdir(path)
            try:
                os.execvp(cli, [cli])
            except FileNotFoundError:
                print(f"Erro: '{cli}' não encontrado no PATH.")
                return 1

        elif action == "launch_missing":
            from nexus.registry import move_project
            from nexus.relocate import find_moved_project
            print(f"Path não encontrado: {data}")

            candidates = find_moved_project(data) if data else []
            new_path = None

            if candidates:
                if len(candidates) == 1:
                    print(f"\U0001F50D Encontrado em: {candidates[0]}")
                    try:
                        confirm = input("Corrigir path no registro? [S/n]: ").strip().lower()
                    except (KeyboardInterrupt, EOFError):
                        print("\nCancelado.")
                        return 0
                    if confirm != "n":
                        new_path = candidates[0]
                else:
                    print("\U0001F50D Encontrados vários candidatos:")
                    for i, c in enumerate(candidates, 1):
                        print(f"  {i}) {c}")
                    print(f"  0) Informar manualmente")
                    try:
                        choice = input("> ").strip()
                    except (KeyboardInterrupt, EOFError):
                        print("\nCancelado.")
                        return 0
                    if choice.isdigit() and 1 <= int(choice) <= len(candidates):
                        new_path = candidates[int(choice) - 1]

            if not new_path:
                try:
                    new_path = input("Informe o path correto nesta máquina (Enter para cancelar): ").strip().strip("\"'")
                except (KeyboardInterrupt, EOFError):
                    print("\nCancelado.")
                    return 0

            if not new_path or not _safe_path_exists(new_path):
                print("Cancelado.")
                return 0

            if data:
                move_result = move_project(data, new_path)
                if move_result:
                    print(f"  Registro atualizado: {move_result.name}")
                    _tui_sync_background("move")
                else:
                    if not set_project_path_override(data, new_path):
                        set_path_override(data, new_path)

            # Rescan the project so data.json has the updated path
            scan_one(new_path)
            next_tab = "projects"
            continue

        elif action == "edit":
            from nexus._legacy_main import cmd_edit
            import argparse
            try:
                cmd_edit(argparse.Namespace(query=data))
            except (KeyboardInterrupt, EOFError):
                print("\nCancelado.")
            except Exception as e:
                print(f"\nErro: {e}")
            _tui_sync_background("edit")
            next_tab = "projects"

        elif action == "note":
            matched, _ = resolve_project(data)
            if not matched:
                print("Projeto não encontrado.")
                next_tab = "projects"
                continue
            try:
                note = input("Nova nota para o projeto (Ctrl+C cancela): ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nCancelado.")
                next_tab = "projects"
                continue
            if note:
                update_project(matched.path or matched.name, note=note)
                print(f'Nota atualizada: "{note}"')
                _tui_sync_background("note")
            next_tab = "projects"

        elif action == "remove":
            from nexus.hooks import remove_claude_hook, remove_git_hook
            from nexus.registry import remove_project
            matched, _ = resolve_project(data)
            if not matched:
                print("Projeto não encontrado.")
                next_tab = "projects"
                continue
            try:
                confirm = input(f"Remover '{matched.name}'? [s/N]: ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                print("\nCancelado.")
                next_tab = "projects"
                continue
            if confirm == "s":
                remove_resolved = resolve_path_for_entry(matched.slug, matched.path)
                if remove_resolved:
                    remove_path = resolve_project_path(remove_resolved)
                    remove_git_hook(remove_path)
                    remove_claude_hook(remove_path)
                remove_project(matched.name if not matched.path else matched.path)
                print(f"Removido: {matched.name}")
                _tui_sync_background("remove")
            else:
                print("Cancelado.")
            next_tab = "projects"

        elif action == "add":
            from nexus._legacy_main import cmd_add
            import argparse
            try:
                cmd_add(argparse.Namespace(path=None))
            except (KeyboardInterrupt, EOFError):
                print("\nCancelado.")
            except Exception as e:
                print(f"\nErro: {e}")
            _tui_sync_background("add")
            next_tab = "projects"

        # -- Idea actions --

        elif action == "idea_add":
            from nexus._legacy_main import cmd_idea_add
            import argparse
            try:
                cmd_idea_add(argparse.Namespace())
            except (KeyboardInterrupt, EOFError):
                print("\nCancelado.")
            except Exception as e:
                print(f"\nErro: {e}")
            _tui_sync_background("idea-add")
            next_tab = "ideas"

        elif action == "idea_edit":
            from nexus._legacy_main import cmd_idea_edit
            import argparse
            try:
                cmd_idea_edit(argparse.Namespace(query=data))
            except (KeyboardInterrupt, EOFError):
                print("\nCancelado.")
            except Exception as e:
                print(f"\nErro: {e}")
            _tui_sync_background("idea-edit")
            next_tab = "ideas"

        elif action == "idea_remove":
            from nexus._legacy_main import cmd_idea_remove
            import argparse
            try:
                cmd_idea_remove(argparse.Namespace(query=data))
            except (KeyboardInterrupt, EOFError):
                print("\nCancelado.")
            except Exception as e:
                print(f"\nErro: {e}")
            _tui_sync_background("idea-remove")
            next_tab = "ideas"

        elif action == "idea_promote":
            from nexus._legacy_main import cmd_idea_promote
            import argparse
            try:
                promote_choice = input("Promover para [p]rojeto ou [a]pp? (Enter=projeto): ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                print("\nCancelado.")
                continue
            as_app = promote_choice == "a"
            try:
                cmd_idea_promote(argparse.Namespace(
                    query=data, app=as_app,
                    name=None, domain=None, github=None, url=None,
                ))
            except (KeyboardInterrupt, EOFError):
                print("\nCancelado.")
            except Exception as e:
                print(f"\nErro: {e}")
            _tui_sync_background("idea-promote")
            next_tab = "apps" if as_app else "projects"

        # -- Codex actions --

        elif action == "codex_add":
            from nexus._legacy_main import cmd_codex_add
            import argparse
            try:
                cmd_codex_add(argparse.Namespace())
            except (KeyboardInterrupt, EOFError):
                print("\nCancelado.")
            except Exception as e:
                print(f"\nErro: {e}")
            _tui_sync_background("codex-add")
            next_tab = "codex"

        elif action == "codex_edit":
            from nexus._legacy_main import cmd_codex_edit
            import argparse
            try:
                cmd_codex_edit(argparse.Namespace(query=data, pick=False))
            except (KeyboardInterrupt, EOFError):
                print("\nCancelado.")
            except Exception as e:
                print(f"\nErro: {e}")
            _tui_sync_background("codex-edit")
            next_tab = "codex"

        elif action == "codex_remove":
            from nexus._legacy_main import cmd_codex_remove
            import argparse
            try:
                cmd_codex_remove(argparse.Namespace(query=data))
            except (KeyboardInterrupt, EOFError):
                print("\nCancelado.")
            except Exception as e:
                print(f"\nErro: {e}")
            _tui_sync_background("codex-remove")
            next_tab = "codex"

        # -- App actions --

        elif action == "app_add":
            from nexus._legacy_main import cmd_app_add
            try:
                cmd_app_add()
            except (KeyboardInterrupt, EOFError):
                print("\nCancelado.")
            except Exception as e:
                print(f"\nErro: {e}")
            _tui_sync_background("app-add")
            next_tab = "apps"

        elif action == "app_edit":
            from nexus._legacy_main import cmd_app_edit
            try:
                cmd_app_edit(data)
            except (KeyboardInterrupt, EOFError):
                print("\nCancelado.")
            except Exception as e:
                print(f"\nErro: {e}")
            _tui_sync_background("app-edit")
            next_tab = "apps"

        elif action == "app_remove":
            from nexus._legacy_main import cmd_app_remove
            try:
                cmd_app_remove(data)
            except (KeyboardInterrupt, EOFError):
                print("\nCancelado.")
            except Exception as e:
                print(f"\nErro: {e}")
            _tui_sync_background("app-remove")
            next_tab = "apps"

        elif action == "app_note":
            from nexus._legacy_main import cmd_app_note
            try:
                cmd_app_note(data)
            except (KeyboardInterrupt, EOFError):
                print("\nCancelado.")
            except Exception as e:
                print(f"\nErro: {e}")
            _tui_sync_background("app-note")
            next_tab = "apps"

        # -- Skill actions --

        elif action == "skill_add":
            from nexus._legacy_main import cmd_skill_add
            try:
                cmd_skill_add()
            except (KeyboardInterrupt, EOFError):
                print("\nCancelado.")
            except Exception as e:
                print(f"\nErro: {e}")
            _tui_sync_background("skill-add")
            next_tab = "skills"

        elif action == "skill_edit":
            from nexus._legacy_main import cmd_skill_edit
            try:
                cmd_skill_edit(data)
            except (KeyboardInterrupt, EOFError):
                print("\nCancelado.")
            except Exception as e:
                print(f"\nErro: {e}")
            _tui_sync_background("skill-edit")
            next_tab = "skills"

        elif action == "skill_remove":
            from nexus._legacy_main import cmd_skill_remove
            try:
                cmd_skill_remove(data)
            except (KeyboardInterrupt, EOFError):
                print("\nCancelado.")
            except Exception as e:
                print(f"\nErro: {e}")
            _tui_sync_background("skill-remove")
            next_tab = "skills"

        # -- Environment actions --

        elif action == "env_edit":
            from nexus.environment import find_environment, update_environment
            env = find_environment(data)
            if not env:
                print(f"Ambiente não encontrado: {data}")
            else:
                print(f"Editando ambiente: {env.name} ({env.hostname})")
                try:
                    new_name = input(f"Nome [{env.name}]: ").strip() or env.name
                    new_location = input(f"Localização [{env.location}]: ").strip() or env.location
                except (KeyboardInterrupt, EOFError):
                    print("\nCancelado.")
                    next_tab = "environments"
                    continue
                update_environment(env.hostname, name=new_name, location=new_location)
                print(f"Ambiente atualizado: {new_name} ({new_location})")
                _tui_sync_background("env-edit")
            next_tab = "environments"

        else:
            return 0

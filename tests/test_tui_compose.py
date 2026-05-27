"""
TUI compose() coverage — textual ModalScreen detail views.

These tests use asyncio + textual's run_test() to actually execute
the compose() generators for ModalScreen subclasses that use
`with Vertical():` blocks, which require a running textual app.

Covers: tui.py lines 178-213, 370-383, 443-457, 518-542
"""
import asyncio
import unittest

try:
    from textual.app import App, ComposeResult
    from textual.widgets import Label
    from nexus.tui import (
        CodexDetailScreen,
        EnvDetailScreen,
        IdeaDetailScreen,
    )
    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False


def _run(coro):
    """Run a coroutine in a fresh event loop."""
    return asyncio.run(coro)


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestIdeaDetailScreenCompose(unittest.TestCase):
    """Cover IdeaDetailScreen.compose() — lines 178-213."""

    def _make_wrapper_app(self, screen):
        """Create a minimal App that immediately pushes and dismisses a ModalScreen."""
        class WrapperApp(App):
            def __init__(self, modal, **kwargs):
                super().__init__(**kwargs)
                self._modal = modal

            def compose(self) -> ComposeResult:
                yield Label("bg")  # Needs something in the background

            async def on_mount(self) -> None:
                await self.push_screen(self._modal)
                # Dismiss immediately after push so the app exits
                self._modal.dismiss(None)

        return WrapperApp(screen)

    def test_idea_compose_full(self):
        """IdeaDetailScreen compose() with all fields (lines 178-213)."""
        idea = {
            "title": "My Idea",
            "priority": "high",
            "domain": "tech",
            "id": "my-idea",
            "description": "A great idea",
            "tags": ["python", "testing"],
            "references": ["ref1", "ref2"],
            "notes": "Some notes",
            "created": "2026-01-01",
        }

        async def run():
            screen = IdeaDetailScreen(idea=idea)
            app = self._make_wrapper_app(screen)
            async with app.run_test(headless=True, size=(120, 40)) as pilot:
                await pilot.pause(0.1)

        _run(run())

    def test_idea_compose_minimal(self):
        """IdeaDetailScreen compose() with minimal data (covers empty branches)."""
        idea = {"title": "Minimal", "priority": "medium"}

        async def run():
            screen = IdeaDetailScreen(idea=idea)
            app = self._make_wrapper_app(screen)
            async with app.run_test(headless=True, size=(120, 40)) as pilot:
                await pilot.pause(0.1)

        _run(run())

    def test_idea_compose_low_priority(self):
        """IdeaDetailScreen compose() with low priority (covers green badge)."""
        idea = {"title": "Low", "priority": "low"}

        async def run():
            screen = IdeaDetailScreen(idea=idea)
            app = self._make_wrapper_app(screen)
            async with app.run_test(headless=True, size=(120, 40)) as pilot:
                await pilot.pause(0.1)

        _run(run())


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestCodexDetailScreenCompose(unittest.TestCase):
    """Cover CodexDetailScreen.compose() — lines 370-383."""

    def _make_wrapper_app(self, screen):
        class WrapperApp(App):
            def __init__(self, modal, **kwargs):
                super().__init__(**kwargs)
                self._modal = modal

            def compose(self) -> ComposeResult:
                yield Label("bg")

            async def on_mount(self) -> None:
                await self.push_screen(self._modal)
                self._modal.dismiss(None)

        return WrapperApp(screen)

    def test_codex_compose_full(self):
        """CodexDetailScreen compose() with tags and updated (lines 370-383)."""
        entry = {
            "title": "Python Tips",
            "domain": "programming",
            "tags": ["python", "tips"],
            "updated": "2026-01-15",
            "content": "# Python Tips\n\nUse list comprehensions.",
        }

        async def run():
            screen = CodexDetailScreen(entry=entry)
            app = self._make_wrapper_app(screen)
            async with app.run_test(headless=True, size=(120, 40)) as pilot:
                await pilot.pause(0.1)

        _run(run())

    def test_codex_compose_minimal(self):
        """CodexDetailScreen compose() with minimal data (no tags, no updated)."""
        entry = {"title": "Minimal Entry", "domain": "misc"}

        async def run():
            screen = CodexDetailScreen(entry=entry)
            app = self._make_wrapper_app(screen)
            async with app.run_test(headless=True, size=(120, 40)) as pilot:
                await pilot.pause(0.1)

        _run(run())


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestEnvDetailScreenCompose(unittest.TestCase):
    """Cover EnvDetailScreen.compose() — lines 518-542."""

    def _make_wrapper_app(self, screen):
        class WrapperApp(App):
            def __init__(self, modal, **kwargs):
                super().__init__(**kwargs)
                self._modal = modal

            def compose(self) -> ComposeResult:
                yield Label("bg")

            async def on_mount(self) -> None:
                await self.push_screen(self._modal)
                self._modal.dismiss(None)

        return WrapperApp(screen)

    def test_env_compose_full(self):
        """EnvDetailScreen compose() with all fields (lines 518-542)."""
        env = {
            "name": "MyMachine",
            "hostname": "mymachine",
            "location": "Home Office",
            "last_seen": "2026-03-01",
            "paths": {
                "nexus": "/home/user/nexus",
                "myapp": "/home/user/myapp",
            },
            "absent": ["old-proj", "another-proj"],
        }

        async def run():
            screen = EnvDetailScreen(env=env)
            app = self._make_wrapper_app(screen)
            async with app.run_test(headless=True, size=(120, 40)) as pilot:
                await pilot.pause(0.1)

        _run(run())

    def test_env_compose_minimal(self):
        """EnvDetailScreen compose() with minimal data (no last_seen, paths, absent)."""
        env = {
            "name": "Minimal",
            "hostname": "minimal",
            "location": "Unknown",
        }

        async def run():
            screen = EnvDetailScreen(env=env)
            app = self._make_wrapper_app(screen)
            async with app.run_test(headless=True, size=(120, 40)) as pilot:
                await pilot.pause(0.1)

        _run(run())

    def test_env_compose_with_last_seen_na(self):
        """EnvDetailScreen compose(): last_seen = 'n/a' → no 'Último acesso' section."""
        env = {
            "name": "NoLastSeen",
            "hostname": "nols",
            "location": "Server",
            "last_seen": "n/a",
        }

        async def run():
            screen = EnvDetailScreen(env=env)
            app = self._make_wrapper_app(screen)
            async with app.run_test(headless=True, size=(120, 40)) as pilot:
                await pilot.pause(0.1)

        _run(run())

from nexus.tui.app import (
    HAS_TEXTUAL,
    NexusApp,
    _nature_tag,
    _tui_sync,
    _tui_sync_background,
    _set_sync_thread,
    _safe_path_exists,
)

# Re-export textual stubs/widgets for backward compatibility
from nexus.tui.app import Footer

# Re-export screen classes for backward compatibility
from nexus.tui.screens import (
    IdeaDetailScreen,
    CodexDetailScreen,
    CodexSectionPickerScreen,
    CodexOrderScreen,
    EnvDetailScreen,
    CliSelectScreen,
)

# Re-export widget and filter utilities
from nexus.tui.widgets.filter_suggester import FilterSuggester, _parse_filter


def run_tui(initial_tab: str = "ideas") -> int:
    if not HAS_TEXTUAL:
        print("textual não está instalado. Execute: pip install textual")
        return 1
    from nexus.tui.app import run_tui_loop
    return run_tui_loop(initial_tab)

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from .local_config import load_local_config, save_local_config


def is_windows_path(path: str) -> bool:
    """Check if path looks like a Windows path (e.g., C:\\ or C:/)."""
    return len(path) >= 3 and path[0].isalpha() and path[1] == ":" and path[2] in "/\\"


def is_wsl_windows_path(path: str) -> bool:
    """Check if path is a WSL mount of a Windows drive (e.g., /mnt/c/...)."""
    return (
        len(path) >= 7
        and path.startswith("/mnt/")
        and path[5].isalpha()
        and path[6] == "/"
    )


def normalize_editor_path(command: str) -> str:
    """Normalize editor command path. Converts Windows paths to WSL."""
    if not is_windows_path(command):
        return command

    result = subprocess.run(
        ["wslpath", "-u", command],
        capture_output=True, text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return command


@dataclass
class EditorConfig:
    name: str
    command: str
    type: str = "terminal"  # terminal | gui | gui-windows


def load_editors() -> tuple[list[EditorConfig], str]:
    """Load editors and default from local config. Returns (editors, default_name)."""
    config = load_local_config()
    raw = config.get("editors") or []
    editors = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        editors.append(EditorConfig(
            name=item.get("name", ""),
            command=item.get("command", ""),
            type=item.get("type", "terminal"),
        ))
    default = config.get("default_editor", "")
    return editors, default


def save_editors(editors: list[EditorConfig], default: str) -> None:
    """Save editors and default to local config."""
    config = load_local_config()
    config["editors"] = [
        {"name": e.name, "command": e.command, "type": e.type}
        for e in editors
    ]
    config["default_editor"] = default
    save_local_config(config)


def _prompt_editor_type(default: str = "1") -> str:
    """Prompt for editor type. Returns type string."""
    print("  Tipo:")
    print("    1) terminal — bloqueia terminal (vim, nano)")
    print("    2) gui — app gráfico Linux/WSLg")
    print("    3) gui-windows — app Windows via WSL")
    type_choice = input(f"  [{default}]: ").strip() or default
    type_map = {"1": "terminal", "2": "gui", "3": "gui-windows"}
    return type_map.get(type_choice, type_map[default])


def add_editor() -> EditorConfig | None:
    """Interactive: add a new editor. Returns the created editor or None on cancel."""
    print("Configurar novo editor:")
    try:
        name = input("  Nome (ex: vim, typora, code): ").strip()
        if not name:
            print("Cancelado.")
            return None
        command = input("  Comando (ex: vim, C:\\Program Files\\Typora\\Typora.exe): ").strip().strip("\"'")
        if not command:
            print("Cancelado.")
            return None

        # Normalize Windows paths to WSL
        original_command = command
        command = normalize_editor_path(command)
        if command != original_command:
            print(f"  (convertido para WSL: {command})")

        # Validate path exists (skip for simple commands like 'vim')
        if "/" in command or "\\" in command:
            cmd_path = Path(command)
            try:
                path_exists = cmd_path.exists()
            except OSError:
                path_exists = False
            if not path_exists:
                print(f"  ⚠ Aviso: arquivo não encontrado: {command}")
                proceed = input("  Continuar mesmo assim? [s/N]: ").strip().lower()
                if proceed not in ("s", "sim"):
                    print("Cancelado.")
                    return None

        # Auto-detect gui-windows for Windows/WSL-mount paths
        if is_windows_path(original_command) or is_wsl_windows_path(command):
            print("  Tipo detectado: gui-windows")
            confirm = input("  Confirmar? (Enter=sim, n=escolher outro): ").strip().lower()
            if confirm in ("", "s", "sim"):
                editor_type = "gui-windows"
            else:
                editor_type = _prompt_editor_type(default="3")
        else:
            editor_type = _prompt_editor_type(default="1")
    except (KeyboardInterrupt, EOFError):
        print("\nCancelado.")
        return None

    editor = EditorConfig(name=name, command=command, type=editor_type)
    editors, default = load_editors()
    editors.append(editor)
    if not default:
        default = name
    save_editors(editors, default)
    print(f"  Editor '{name}' adicionado ({editor_type}).")
    return editor


def pick_editor() -> EditorConfig | None:
    """Interactive: pick an editor from the list. Returns selected or None."""
    editors, default = load_editors()
    if not editors:
        print("Nenhum editor configurado.")
        return add_editor()

    if len(editors) == 1:
        return editors[0]

    print("Selecione o editor:")
    for i, e in enumerate(editors, 1):
        marker = " (padrão)" if e.name == default else ""
        print(f"  {i}) {e.name} [{e.type}]{marker}")
    try:
        default_idx = next((i for i, e in enumerate(editors, 1) if e.name == default), 1)
        choice = input(f"  [{default_idx}]: ").strip() or str(default_idx)
        if choice.isdigit() and 1 <= int(choice) <= len(editors):
            return editors[int(choice) - 1]
    except (KeyboardInterrupt, EOFError):
        print("\nCancelado.")
        return None

    return editors[0]


def get_default_editor() -> EditorConfig | None:
    """Get the default editor without prompting."""
    editors, default = load_editors()
    if not editors:
        return None
    for e in editors:
        if e.name == default:
            return e
    return editors[0]


def _to_windows_path(wsl_path: str) -> str:
    """Convert a WSL path to Windows path via wslpath -w. Returns original on failure."""
    result = subprocess.run(
        ["wslpath", "-w", wsl_path],
        capture_output=True, text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return wsl_path


def open_in_editor(editor: EditorConfig, file_path: str) -> None:
    """Open a file in the specified editor."""
    path = file_path

    if editor.type == "gui-windows":
        # Normalize command to WSL path (handles legacy Windows-path configs)
        command = normalize_editor_path(editor.command)
        # Convert file path to Windows format (Windows apps expect Windows paths)
        win_file = _to_windows_path(path)
        subprocess.Popen([command, win_file])
    elif editor.type == "gui":
        command = normalize_editor_path(editor.command)
        subprocess.Popen([command, path])
    else:
        # terminal: blocking
        command = normalize_editor_path(editor.command)
        subprocess.run([command, path])

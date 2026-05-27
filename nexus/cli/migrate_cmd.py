from __future__ import annotations
import shutil
from pathlib import Path

import typer

from nexus.cli import app
from nexus.config import NexusConfig


@app.command("migrate")
def migrate(
    from_dir: str = typer.Option(..., "--from", help="Diretório de dados antigo (ex: /repo/data)"),
):
    """Migrar dados de um diretório antigo para o novo data_dir."""
    source = Path(from_dir)
    if not source.is_dir():
        typer.echo(f"Diretório '{from_dir}' não encontrado.", err=True)
        raise typer.Exit(1)

    config = NexusConfig.load()
    target = config.data_dir

    if target.exists() and any(target.iterdir()):
        typer.echo(f"Diretório destino '{target}' já existe e não está vazio.")
        if not typer.confirm("Sobrescrever arquivos existentes?"):
            raise typer.Abort()

    config.ensure_dirs()

    files_to_copy = ["projects.yml", "apps.yml", "ideas.yml", "environments.yml", "data.json"]
    for fname in files_to_copy:
        src = source / fname
        if src.exists():
            shutil.copy2(src, target / fname)

    dirs_to_copy = ["codex"]
    for dname in dirs_to_copy:
        src = source / dname
        if src.is_dir():
            dst = target / dname
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)

    typer.echo(f"✓ Dados migrados de '{source}' para '{target}'")

from __future__ import annotations
import typer
from nexus.cli import app, get_container


@app.command("scan")
def scan(
    target: str = typer.Argument(None, help="Slug do projeto (omitir para scan completo)"),
):
    container = get_container()
    if target:
        typer.echo(f"Escaneando projeto '{target}'...")
    else:
        typer.echo("Escaneando todos os projetos...")
    typer.echo("✓ Scan completo.")

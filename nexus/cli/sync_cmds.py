from __future__ import annotations
import typer
from nexus.cli import app, get_container


@app.command("sync")
def sync():
    container = get_container()
    ok = container.sync.full_sync("manual-sync")
    if ok:
        typer.echo("✓ Dados sincronizados.")
    else:
        typer.echo("⚠ Falha na sincronização.", err=True)
        raise typer.Exit(1)

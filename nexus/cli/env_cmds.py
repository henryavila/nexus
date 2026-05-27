from __future__ import annotations
import typer
from nexus.cli import app, get_container
from nexus.cli.formatters import rel_date

env_app = typer.Typer(help="Gerenciar environments")
app.add_typer(env_app, name="env")


@env_app.command("list")
def env_list():
    container = get_container()
    envs = container.environments.list_all()
    if not envs:
        typer.echo("Nenhum environment registrado.")
        return
    for e in envs:
        typer.echo(f"  🖥 {e.name} ({e.hostname}) — {e.location} (visto: {rel_date(e.last_seen)})")


@env_app.command("setup")
def env_setup(
    hostname: str = typer.Argument(...),
    name: str = typer.Argument(...),
    location: str = typer.Option("", "--location", "-l"),
):
    container = get_container()
    e = container.environments.register(hostname, name, location)
    typer.echo(f"✓ Environment '{e.name}' registrado.")


@env_app.command("info")
def env_info(hostname: str = typer.Argument(...)):
    container = get_container()
    envs = container.environments.list_all()
    env = next((e for e in envs if e.hostname == hostname), None)
    if env is None:
        typer.echo(f"Environment '{hostname}' não encontrado.", err=True)
        raise typer.Exit(1)
    typer.echo(f"🖥 {env.name} ({env.hostname})")
    typer.echo(f"  Local: {env.location}")
    typer.echo(f"  Visto: {rel_date(env.last_seen)}")
    if env.paths:
        typer.echo("  Paths:")
        for slug, path in env.paths.items():
            typer.echo(f"    {slug}: {path}")
    if env.absent:
        typer.echo(f"  Ausentes: {', '.join(env.absent)}")

from __future__ import annotations
import typer
from nexus.cli import app, get_container

app_cmd = typer.Typer(help="Gerenciar apps")
app.add_typer(app_cmd, name="app")


@app_cmd.command("add")
def app_add(
    name: str = typer.Argument(..., help="Nome do app"),
    description: str = typer.Option("", "--description", "-d"),
    domain: str = typer.Option("pessoal", "--domain"),
    url: str = typer.Option(None, "--url"),
    github: str = typer.Option(None, "--github"),
):
    container = get_container()
    a = container.apps.add(name, description=description, domain=domain, url=url, github=github)
    typer.echo(f"✓ App '{a.name}' adicionado (slug: {a.slug})")


@app_cmd.command("list")
def app_list():
    container = get_container()
    apps = container.apps.list_all()
    if not apps:
        typer.echo("Nenhum app encontrado.")
        return
    for a in apps:
        icon = a.icon or "📱"
        typer.echo(f"  {icon} {a.name} ({a.slug}) — {a.domain}")


@app_cmd.command("remove")
def app_remove(query: str = typer.Argument(...)):
    container = get_container()
    entry = container.apps.resolve(query)
    if entry is None:
        typer.echo(f"App '{query}' não encontrado.", err=True)
        raise typer.Exit(1)
    confirm = typer.confirm(f"Remover app '{entry.name}'?")
    if not confirm:
        raise typer.Abort()
    container.apps.remove(entry.slug)
    typer.echo(f"✓ App '{entry.name}' removido.")


@app_cmd.command("edit")
def app_edit(
    query: str = typer.Argument(...),
    name: str = typer.Option(None, "--name"),
    description: str = typer.Option(None, "--description", "-d"),
    domain: str = typer.Option(None, "--domain"),
    url: str = typer.Option(None, "--url"),
    note: str = typer.Option(None, "--note"),
):
    container = get_container()
    kwargs = {k: v for k, v in dict(name=name, description=description, domain=domain, url=url, note=note).items() if v is not None}
    if not kwargs:
        typer.echo("Nenhum campo para editar.", err=True)
        raise typer.Exit(1)
    updated = container.apps.edit(query, **kwargs)
    if updated is None:
        typer.echo(f"App '{query}' não encontrado.", err=True)
        raise typer.Exit(1)
    typer.echo(f"✓ App '{updated.name}' atualizado.")

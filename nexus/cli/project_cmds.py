from __future__ import annotations

import typer
from nexus.cli import app, get_container
from nexus.cli.formatters import rel_date

project_app = typer.Typer(help="Gerenciar projetos")
app.add_typer(project_app, name="project")


@app.command("add")
def add_project(
    name: str = typer.Argument(..., help="Nome do projeto"),
    path: str = typer.Option(None, "--path", "-p", help="Caminho do projeto"),
    description: str = typer.Option("", "--description", "-d"),
    domain: str = typer.Option("pessoal", "--domain"),
    nature: str = typer.Option("contexto", "--nature"),
    private: bool = typer.Option(False, "--private"),
):
    if path:
        path = path.strip("\"'")
    container = get_container()
    p = container.projects.add(name, path=path, description=description, domain=domain, nature=nature, private=private)
    typer.echo(f"✓ Projeto '{p.name}' adicionado (slug: {p.slug})")


@app.command("list")
def list_projects(
    domain: str = typer.Option(None, "--domain", "-d"),
    nature: str = typer.Option(None, "--nature", "-n"),
):
    container = get_container()
    projects = container.projects.list_all()
    if domain:
        projects = [p for p in projects if p.domain == domain]
    if nature:
        projects = [p for p in projects if p.nature == nature]
    if not projects:
        typer.echo("Nenhum projeto encontrado.")
        return
    for p in projects:
        icon = p.icon or "📁"
        status = f" [{p.status}]" if p.status else ""
        typer.echo(f"  {icon} {p.name} ({p.slug}) — {p.domain}/{p.nature}{status}")


@app.command("remove")
def remove_project(query: str = typer.Argument(..., help="Slug ou nome do projeto")):
    container = get_container()
    entry = container.projects.resolve(query)
    if entry is None:
        typer.echo(f"Projeto '{query}' não encontrado.", err=True)
        raise typer.Exit(1)
    confirm = typer.confirm(f"Remover '{entry.name}' ({entry.slug})?")
    if not confirm:
        raise typer.Abort()
    container.projects.remove(entry.slug)
    typer.echo(f"✓ Projeto '{entry.name}' removido.")


@app.command("edit")
def edit_project(
    query: str = typer.Argument(..., help="Slug ou nome"),
    name: str = typer.Option(None, "--name"),
    description: str = typer.Option(None, "--description", "-d"),
    domain: str = typer.Option(None, "--domain"),
    nature: str = typer.Option(None, "--nature"),
    note: str = typer.Option(None, "--note"),
    status: str = typer.Option(None, "--status"),
    url: str = typer.Option(None, "--url"),
):
    container = get_container()
    kwargs = {}
    if name is not None:
        kwargs["name"] = name
    if description is not None:
        kwargs["description"] = description
    if domain is not None:
        kwargs["domain"] = domain
    if nature is not None:
        kwargs["nature"] = nature
    if note is not None:
        kwargs["note"] = note
    if status is not None:
        kwargs["status"] = status
    if url is not None:
        kwargs["url"] = url
    if not kwargs:
        typer.echo("Nenhum campo para editar.", err=True)
        raise typer.Exit(1)
    updated = container.projects.edit(query, **kwargs)
    if updated is None:
        typer.echo(f"Projeto '{query}' não encontrado.", err=True)
        raise typer.Exit(1)
    typer.echo(f"✓ Projeto '{updated.name}' atualizado.")


@app.command("status")
def status_project(query: str = typer.Argument(..., help="Slug ou nome")):
    container = get_container()
    entry = container.projects.resolve(query)
    if entry is None:
        typer.echo(f"Projeto '{query}' não encontrado.", err=True)
        raise typer.Exit(1)
    icon = entry.icon or "📁"
    typer.echo(f"{icon} {entry.name} ({entry.slug})")
    typer.echo(f"  Domínio: {entry.domain} | Natureza: {entry.nature}")
    if entry.path:
        typer.echo(f"  Path: {entry.path}")
    if entry.description:
        typer.echo(f"  Descrição: {entry.description}")
    if entry.url:
        typer.echo(f"  URL: {entry.url}")
    if entry.note:
        typer.echo(f"  Nota: {entry.note}")
    if entry.status:
        typer.echo(f"  Status: {entry.status}")
    typer.echo(f"  Adicionado: {rel_date(entry.added)}")


@app.command("note")
def note_project(
    query: str = typer.Argument(..., help="Slug ou nome"),
    text: str = typer.Argument(..., help="Texto da nota"),
):
    container = get_container()
    updated = container.projects.edit(query, note=text)
    if updated is None:
        typer.echo(f"Projeto '{query}' não encontrado.", err=True)
        raise typer.Exit(1)
    typer.echo(f"✓ Nota atualizada para '{updated.name}'.")

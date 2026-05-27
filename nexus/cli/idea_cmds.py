from __future__ import annotations
import typer
from nexus.cli import app, get_container, disambiguate
from nexus.cli.formatters import rel_date

idea_app = typer.Typer(help="Gerenciar ideias")
app.add_typer(idea_app, name="idea")


@idea_app.command("add")
def idea_add(
    title: str = typer.Argument(..., help="Título da ideia"),
    description: str = typer.Option("", "--description", "-d"),
    domain: str = typer.Option("pessoal", "--domain"),
    priority: str = typer.Option("medium", "--priority", "-p"),
):
    container = get_container()
    i = container.ideas.add(title, description=description, domain=domain, priority=priority)
    typer.echo(f"✓ Ideia '{i.title}' adicionada (id: {i.id})")


@idea_app.command("list")
def idea_list(domain: str = typer.Option(None, "--domain", "-d")):
    container = get_container()
    ideas = container.ideas.list_all()
    if domain:
        ideas = [i for i in ideas if i.domain == domain]
    if not ideas:
        typer.echo("Nenhuma ideia encontrada.")
        return
    for i in ideas:
        prio = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(i.priority, "⚪")
        typer.echo(f"  {prio} [{i.id}] {i.title} — {i.domain} ({rel_date(i.created)})")


@idea_app.command("edit")
def idea_edit(
    query: str = typer.Argument(..., help="ID ou título"),
    title: str = typer.Option(None, "--title"),
    description: str = typer.Option(None, "--description", "-d"),
    priority: str = typer.Option(None, "--priority", "-p"),
    domain: str = typer.Option(None, "--domain"),
    notes: str = typer.Option(None, "--notes"),
):
    container = get_container()
    kwargs = {k: v for k, v in dict(title=title, description=description, priority=priority, domain=domain, notes=notes).items() if v is not None}
    if not kwargs:
        typer.echo("Nenhum campo para editar.", err=True)
        raise typer.Exit(1)
    candidates = container.ideas.resolve_all(query)
    entry = disambiguate(candidates, query, "Ideia",
                         lambda c: f"[{c.id}] {c.title} — {c.domain}")
    updated = container.ideas.edit(entry.id, **kwargs)
    typer.echo(f"✓ Ideia '{updated.title}' atualizada.")


@idea_app.command("remove")
def idea_remove(query: str = typer.Argument(..., help="ID ou título")):
    container = get_container()
    candidates = container.ideas.resolve_all(query)
    entry = disambiguate(candidates, query, "Ideia",
                         lambda c: f"[{c.id}] {c.title} — {c.domain}")
    confirm = typer.confirm(f"Remover ideia '{entry.title}'?")
    if not confirm:
        raise typer.Abort()
    container.ideas.remove(entry.id)
    typer.echo(f"✓ Ideia '{entry.title}' removida.")

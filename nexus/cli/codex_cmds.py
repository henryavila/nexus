from __future__ import annotations
import typer
from nexus.cli import app, get_container, disambiguate
from nexus.cli.formatters import rel_date

codex_app = typer.Typer(help="Gerenciar codex (documentação)")
app.add_typer(codex_app, name="codex")


@codex_app.command("add")
def codex_add(
    title: str = typer.Argument(...),
    kind: str = typer.Option("referência", "--kind", "-k"),
    domain: str = typer.Option("pessoal", "--domain"),
    content: str = typer.Option("", "--content", "-c"),
):
    container = get_container()
    entry = container.codex.add(title, kind=kind, domain=domain, content=content)
    typer.echo(f"✓ Codex '{entry.title}' adicionado (slug: {entry.slug})")


@codex_app.command("list")
def codex_list():
    container = get_container()
    entries = container.codex.list_all()
    if not entries:
        typer.echo("Nenhuma entrada no codex.")
        return
    for e in entries:
        order = f"[{e.order}] " if e.order is not None else ""
        typer.echo(f"  📄 {order}{e.title} ({e.slug}) — {e.kind} ({rel_date(e.updated or e.created)})")


@codex_app.command("edit")
def codex_edit(
    query: str = typer.Argument(..., help="Slug ou título"),
    title: str = typer.Option(None, "--title"),
    kind: str = typer.Option(None, "--kind", "-k"),
    domain: str = typer.Option(None, "--domain"),
    content: str = typer.Option(None, "--content", "-c"),
):
    container = get_container()
    kwargs = {k: v for k, v in dict(title=title, kind=kind, domain=domain, content=content).items() if v is not None}
    if not kwargs:
        typer.echo("Nenhum campo para editar.", err=True)
        raise typer.Exit(1)
    candidates = container.codex.resolve_all(query)
    entry = disambiguate(candidates, query, "Entrada",
                         lambda c: f"{c.title} ({c.slug}) — {c.kind}")
    updated = container.codex.edit(entry.slug, **kwargs)
    typer.echo(f"✓ Entrada '{updated.title}' atualizada.")


@codex_app.command("remove")
def codex_remove(query: str = typer.Argument(...)):
    container = get_container()
    candidates = container.codex.resolve_all(query)
    entry = disambiguate(candidates, query, "Entrada",
                         lambda c: f"{c.title} ({c.slug}) — {c.kind}")
    confirm = typer.confirm(f"Remover '{entry.title}'?")
    if not confirm:
        raise typer.Abort()
    container.codex.remove(entry.slug)
    typer.echo(f"✓ Entrada '{entry.title}' removida.")

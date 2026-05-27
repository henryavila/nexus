from __future__ import annotations
import typer
from nexus.cli import app, get_container, disambiguate

skill_app = typer.Typer(help="Gerenciar skills")
app.add_typer(skill_app, name="skill")


@skill_app.command("add")
def skill_add(
    title: str = typer.Argument(...),
    scope: str = typer.Option("global", "--scope"),
    url: str = typer.Option(None, "--url"),
):
    container = get_container()
    s = container.skills.add(title, scope=scope, url=url)
    typer.echo(f"✓ Skill '{s.title}' adicionada (slug: {s.slug})")


@skill_app.command("list")
def skill_list():
    container = get_container()
    skills = container.skills.list_all()
    if not skills:
        typer.echo("Nenhuma skill encontrada.")
        return
    for s in skills:
        scope_icon = "🌐" if s.scope == "global" else "📁"
        typer.echo(f"  {scope_icon} {s.title} ({s.slug})")


@skill_app.command("edit")
def skill_edit(
    query: str = typer.Argument(..., help="Slug ou título"),
    title: str = typer.Option(None, "--title"),
    scope: str = typer.Option(None, "--scope"),
    url: str = typer.Option(None, "--url"),
):
    container = get_container()
    kwargs = {k: v for k, v in dict(title=title, scope=scope, url=url).items() if v is not None}
    if not kwargs:
        typer.echo("Nenhum campo para editar.", err=True)
        raise typer.Exit(1)
    candidates = container.skills.resolve_all(query)
    entry = disambiguate(candidates, query, "Skill",
                         lambda c: f"{c.title} ({c.slug}) — {c.scope}")
    updated = container.skills.edit(entry.slug, **kwargs)
    typer.echo(f"✓ Skill '{updated.title}' atualizada.")


@skill_app.command("remove")
def skill_remove(query: str = typer.Argument(...)):
    container = get_container()
    candidates = container.skills.resolve_all(query)
    entry = disambiguate(candidates, query, "Skill",
                         lambda c: f"{c.title} ({c.slug}) — {c.scope}")
    confirm = typer.confirm(f"Remover skill '{entry.title}'?")
    if not confirm:
        raise typer.Abort()
    container.skills.remove(entry.slug)
    typer.echo(f"✓ Skill '{entry.title}' removida.")

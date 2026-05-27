from __future__ import annotations
import typer
from nexus.cli import app, get_container

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


@skill_app.command("remove")
def skill_remove(query: str = typer.Argument(...)):
    container = get_container()
    entry = container.skills.resolve(query)
    if entry is None:
        typer.echo(f"Skill '{query}' não encontrada.", err=True)
        raise typer.Exit(1)
    confirm = typer.confirm(f"Remover skill '{entry.title}'?")
    if not confirm:
        raise typer.Abort()
    container.skills.remove(entry.slug)
    typer.echo(f"✓ Skill '{entry.title}' removida.")

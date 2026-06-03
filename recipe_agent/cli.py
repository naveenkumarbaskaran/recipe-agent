"""
CLI for the recipe agent.

Usage examples
--------------
# Suggest recipes from ingredients (targeting 4 servings)
recipe-agent suggest "chicken, rice, garlic, lemon" --servings 4

# Scale an existing recipe file to 8 servings
recipe-agent scale recipe.md --servings 8

# Generate a shopping list for a recipe
recipe-agent shopping-list recipe.md

# Optional: provide what you already have
recipe-agent shopping-list recipe.md --have "salt, olive oil, garlic"
"""

from __future__ import annotations

import sys

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from .agent import RecipeAgent

console = Console()


def _make_agent(api_key: str | None, verbose: bool) -> RecipeAgent:
    """Instantiate a RecipeAgent, aborting with a friendly message on failure."""
    try:
        return RecipeAgent(api_key=api_key, verbose=verbose)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[bold red]Error creating agent:[/] {exc}")
        sys.exit(1)


def _print_response(text: str, title: str = "Recipe Agent") -> None:
    md = Markdown(text)
    console.print(Panel(md, title=title, border_style="green"))


# ---------------------------------------------------------------------------
# Main group
# ---------------------------------------------------------------------------

@click.group()
@click.version_option()
def cli() -> None:
    """Recipe Agent — AI-powered meal suggestions, recipe scaling, and shopping lists."""


# ---------------------------------------------------------------------------
# suggest
# ---------------------------------------------------------------------------

@cli.command("suggest")
@click.argument("ingredients")
@click.option(
    "--servings",
    "-s",
    default=4,
    show_default=True,
    type=int,
    help="Target number of servings for each suggested recipe.",
)
@click.option(
    "--dietary",
    "-d",
    default=None,
    help="Dietary preferences or restrictions (e.g. 'vegetarian, gluten-free').",
)
@click.option(
    "--api-key",
    envvar="ANTHROPIC_API_KEY",
    default=None,
    help="Anthropic API key (defaults to ANTHROPIC_API_KEY env var).",
)
@click.option("--verbose", "-v", is_flag=True, help="Print tool calls to stdout.")
def suggest(
    ingredients: str,
    servings: int,
    dietary: str | None,
    api_key: str | None,
    verbose: bool,
) -> None:
    """
    Suggest recipes from INGREDIENTS.

    INGREDIENTS is a comma-separated list of ingredients you have on hand,
    e.g. 'chicken, rice, garlic, lemon'.
    """
    ingredient_list = [i.strip() for i in ingredients.split(",") if i.strip()]
    if not ingredient_list:
        console.print("[bold red]Error:[/] Please provide at least one ingredient.")
        sys.exit(1)

    agent = _make_agent(api_key, verbose)

    with console.status("[bold green]Consulting the chef..."):
        response = agent.suggest_recipes(
            ingredients=ingredient_list,
            dietary_preferences=dietary,
            servings=servings,
        )

    _print_response(response, title=f"Recipe Suggestions ({servings} servings)")


# ---------------------------------------------------------------------------
# scale
# ---------------------------------------------------------------------------

@cli.command("scale")
@click.argument("recipe_file", metavar="RECIPE_FILE")
@click.option(
    "--servings",
    "-s",
    required=True,
    type=int,
    help="Target number of servings.",
)
@click.option(
    "--output",
    "-o",
    default=None,
    help="Save the scaled recipe to this file.",
)
@click.option(
    "--api-key",
    envvar="ANTHROPIC_API_KEY",
    default=None,
    help="Anthropic API key.",
)
@click.option("--verbose", "-v", is_flag=True, help="Print tool calls to stdout.")
def scale(
    recipe_file: str,
    servings: int,
    output: str | None,
    api_key: str | None,
    verbose: bool,
) -> None:
    """
    Scale RECIPE_FILE to the desired number of SERVINGS.

    RECIPE_FILE should be a Markdown or plain-text recipe file.
    """
    agent = _make_agent(api_key, verbose)

    with console.status(f"[bold green]Scaling recipe to {servings} servings..."):
        response = agent.scale_recipe(
            recipe_path=recipe_file,
            target_servings=servings,
            output_path=output,
        )

    title = f"Scaled Recipe — {servings} servings"
    if output:
        title += f" (saved to {output})"
    _print_response(response, title=title)


# ---------------------------------------------------------------------------
# shopping-list
# ---------------------------------------------------------------------------

@cli.command("shopping-list")
@click.argument("recipe_file", metavar="RECIPE_FILE")
@click.option(
    "--have",
    "-H",
    default=None,
    help="Comma-separated ingredients you already have.",
)
@click.option(
    "--output",
    "-o",
    default=None,
    help="Save the shopping list to this file.",
)
@click.option(
    "--api-key",
    envvar="ANTHROPIC_API_KEY",
    default=None,
    help="Anthropic API key.",
)
@click.option("--verbose", "-v", is_flag=True, help="Print tool calls to stdout.")
def shopping_list(
    recipe_file: str,
    have: str | None,
    output: str | None,
    api_key: str | None,
    verbose: bool,
) -> None:
    """
    Generate a shopping list for RECIPE_FILE.

    Items you already have can be excluded with --have.
    """
    agent = _make_agent(api_key, verbose)
    on_hand = [i.strip() for i in have.split(",") if i.strip()] if have else None

    with console.status("[bold green]Generating shopping list..."):
        response = agent.shopping_list(
            recipe_path=recipe_file,
            ingredients_on_hand=on_hand,
            output_path=output,
        )

    title = "Shopping List"
    if output:
        title += f" (saved to {output})"
    _print_response(response, title=title)


# ---------------------------------------------------------------------------
# chat  (convenience command for free-form queries)
# ---------------------------------------------------------------------------

@cli.command("chat")
@click.argument("message")
@click.option(
    "--api-key",
    envvar="ANTHROPIC_API_KEY",
    default=None,
    help="Anthropic API key.",
)
@click.option("--verbose", "-v", is_flag=True, help="Print tool calls to stdout.")
def chat(message: str, api_key: str | None, verbose: bool) -> None:
    """
    Send a free-form MESSAGE to the culinary assistant.
    """
    agent = _make_agent(api_key, verbose)

    with console.status("[bold green]Thinking..."):
        response = agent.chat(message)

    _print_response(response, title="Recipe Agent")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    cli()


if __name__ == "__main__":
    main()

"""
RecipeAgent: an agentic loop powered by Claude claude-sonnet-4-6 with read_file / write_file tools.

Capabilities
------------
- Suggest 3-5 recipes from a list of ingredients (and optional dietary preferences).
- Scale a recipe to the desired number of servings.
- Generate a shopping list for missing ingredients.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import anthropic

from .scaler import RecipeScaler

# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

READ_FILE_TOOL: dict[str, Any] = {
    "name": "read_file",
    "description": (
        "Read the text content of a file on disk. "
        "Use this to load a recipe file so you can scale it or generate a shopping list."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute or relative path to the file to read.",
            }
        },
        "required": ["path"],
    },
}

WRITE_FILE_TOOL: dict[str, Any] = {
    "name": "write_file",
    "description": (
        "Write text content to a file on disk. "
        "Use this to save a scaled recipe or shopping list."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute or relative path where the file should be written.",
            },
            "content": {
                "type": "string",
                "description": "Text content to write to the file.",
            },
        },
        "required": ["path", "content"],
    },
}

TOOLS = [READ_FILE_TOOL, WRITE_FILE_TOOL]

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """
You are a helpful culinary assistant specialised in recipe suggestions and meal planning.

You have access to two tools:
- read_file(path): read a recipe or ingredient file from disk.
- write_file(path, content): write a recipe or shopping list to disk.

Guidelines
----------
1. When suggesting recipes from ingredients, propose 3-5 recipes with:
   - A short description.
   - Full ingredient list (with quantities).
   - Step-by-step cooking instructions.
   - Estimated prep + cook time.
   - Serving size.

2. When scaling a recipe, preserve ingredient ratios and adjust cooking times
   where necessary.  Use the RecipeScaler logic when exact fraction conversion
   is needed.  Always show both the original and scaled quantities.

3. When generating a shopping list, compare the recipe ingredients against the
   ingredients the user already has and list only the missing items with their
   required amounts, grouped by category (produce, dairy, pantry, etc.).

4. Respond in clear, readable Markdown.
"""


# ---------------------------------------------------------------------------
# Tool execution helpers
# ---------------------------------------------------------------------------

def _execute_tool(tool_name: str, tool_input: dict[str, Any]) -> str:
    """Execute a tool call and return the result as a string."""
    if tool_name == "read_file":
        path = Path(tool_input["path"])
        if not path.exists():
            return f"Error: file not found: {path}"
        try:
            return path.read_text(encoding="utf-8")
        except OSError as exc:
            return f"Error reading {path}: {exc}"

    if tool_name == "write_file":
        path = Path(tool_input["path"])
        content = tool_input["content"]
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return f"Successfully wrote {len(content)} characters to {path}"
        except OSError as exc:
            return f"Error writing {path}: {exc}"

    return f"Error: unknown tool '{tool_name}'"


# ---------------------------------------------------------------------------
# RecipeAgent
# ---------------------------------------------------------------------------

class RecipeAgent:
    """
    Agentic wrapper around Claude claude-sonnet-4-6 for recipe-related tasks.

    Parameters
    ----------
    api_key:
        Anthropic API key.  Defaults to the ``ANTHROPIC_API_KEY`` environment
        variable.
    model:
        Claude model string.  Defaults to ``claude-sonnet-4-6``.
    max_tokens:
        Maximum tokens per response.  Defaults to 8192.
    verbose:
        If ``True``, print each tool call to stdout.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 8192,
        verbose: bool = False,
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self.verbose = verbose
        self.client = anthropic.Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        )
        self.scaler = RecipeScaler()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def suggest_recipes(
        self,
        ingredients: list[str],
        dietary_preferences: str | None = None,
        servings: int = 4,
    ) -> str:
        """
        Suggest 3-5 recipes from the given ingredients.

        Parameters
        ----------
        ingredients:
            Ingredients the user has on hand.
        dietary_preferences:
            Optional free-text dietary notes (e.g. ``"vegetarian, gluten-free"``).
        servings:
            Target serving size for each suggested recipe.
        """
        parts = [
            f"I have the following ingredients: {', '.join(ingredients)}.",
            f"Please suggest 3-5 recipes I can make with these (targeting {servings} servings).",
        ]
        if dietary_preferences:
            parts.append(f"Dietary preferences / restrictions: {dietary_preferences}.")
        prompt = " ".join(parts)
        return self._run(prompt)

    def scale_recipe(
        self,
        recipe_path: str,
        target_servings: int,
        output_path: str | None = None,
    ) -> str:
        """
        Scale a recipe stored on disk to ``target_servings``.

        Parameters
        ----------
        recipe_path:
            Path to the Markdown (or plain-text) recipe file.
        target_servings:
            Desired number of servings.
        output_path:
            If provided, the scaled recipe is also saved here.
        """
        parts = [
            f"Please read the recipe at '{recipe_path}' and scale it to {target_servings} servings.",
            "Show both the original and scaled ingredient quantities.",
        ]
        if output_path:
            parts.append(
                f"After scaling, save the result to '{output_path}'."
            )
        return self._run(" ".join(parts))

    def shopping_list(
        self,
        recipe_path: str,
        ingredients_on_hand: list[str] | None = None,
        output_path: str | None = None,
    ) -> str:
        """
        Generate a shopping list for a recipe.

        Parameters
        ----------
        recipe_path:
            Path to the recipe file.
        ingredients_on_hand:
            Ingredients the user already has (will be excluded from the list).
        output_path:
            If provided, save the shopping list here.
        """
        parts = [
            f"Please read the recipe at '{recipe_path}' and generate a shopping list.",
        ]
        if ingredients_on_hand:
            parts.append(
                f"I already have: {', '.join(ingredients_on_hand)}.  "
                "Exclude those from the list."
            )
        else:
            parts.append("Assume I have no ingredients.")
        if output_path:
            parts.append(f"Save the shopping list to '{output_path}'.")
        return self._run(" ".join(parts))

    def chat(self, message: str) -> str:
        """Free-form conversation with the culinary assistant."""
        return self._run(message)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _run(self, user_message: str) -> str:
        """Run the agentic loop and return the final text response."""
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": user_message}
        ]

        while True:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )

            # Append assistant turn
            messages.append({"role": "assistant", "content": response.content})

            # If Claude is done, return the text
            if response.stop_reason == "end_turn":
                return self._extract_text(response.content)

            # If Claude wants to use tools, execute them
            if response.stop_reason == "tool_use":
                tool_results: list[dict[str, Any]] = []
                for block in response.content:
                    if block.type == "tool_use":
                        if self.verbose:
                            print(
                                f"[tool] {block.name}("
                                f"{json.dumps(block.input, ensure_ascii=False)})"
                            )
                        result = _execute_tool(block.name, block.input)
                        if self.verbose:
                            preview = result[:120].replace("\n", " ")
                            print(f"[tool result] {preview}")
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result,
                            }
                        )
                messages.append({"role": "user", "content": tool_results})
                continue

            # Any other stop reason — return whatever text we have
            return self._extract_text(response.content)

    @staticmethod
    def _extract_text(content: list[Any]) -> str:
        """Pull all text blocks from a content list and join them."""
        parts = []
        for block in content:
            if hasattr(block, "type") and block.type == "text":
                parts.append(block.text)
        return "\n".join(parts).strip()

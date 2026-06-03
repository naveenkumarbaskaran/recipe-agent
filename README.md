# recipe-agent-ai

An AI-powered culinary assistant built on **Claude claude-sonnet-4-6** (Anthropic) that:

- Suggests 3-5 recipes from ingredients you have on hand.
- Scales any recipe to your desired serving size.
- Generates a shopping list of missing ingredients.

---

## Installation

```bash
pip install recipe-agent-ai
```

Or install from source:

```bash
git clone https://github.com/yourname/recipe-agent-ai
cd recipe-agent-ai
pip install -e .
```

---

## Quick start

### 1. Set your API key

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### 2. Suggest recipes

```bash
recipe-agent suggest "chicken, rice, garlic, lemon" --servings 4
```

Add dietary restrictions:

```bash
recipe-agent suggest "tofu, broccoli, soy sauce, ginger" --dietary "vegan" --servings 2
```

### 3. Scale an existing recipe

Given a recipe file `chicken_stew.md`:

```bash
recipe-agent scale chicken_stew.md --servings 8
```

Save the scaled version:

```bash
recipe-agent scale chicken_stew.md --servings 8 --output chicken_stew_8.md
```

### 4. Generate a shopping list

```bash
recipe-agent shopping-list chicken_stew.md
```

Exclude what you already have:

```bash
recipe-agent shopping-list chicken_stew.md --have "olive oil, salt, pepper, garlic"
```

Save the list:

```bash
recipe-agent shopping-list chicken_stew.md --output shopping.md
```

### 5. Free-form chat

```bash
recipe-agent chat "What can I make with leftover roast chicken and canned tomatoes?"
```

---

## Python API

```python
from recipe_agent import RecipeAgent

agent = RecipeAgent()  # reads ANTHROPIC_API_KEY from env

# Suggest recipes
print(agent.suggest_recipes(
    ingredients=["salmon", "lemon", "dill", "capers"],
    dietary_preferences="low-carb",
    servings=2,
))

# Scale a recipe file
print(agent.scale_recipe("risotto.md", target_servings=8, output_path="risotto_8.md"))

# Shopping list
print(agent.shopping_list(
    "risotto.md",
    ingredients_on_hand=["butter", "parmesan", "white wine"],
    output_path="risotto_shopping.md",
))
```

---

## RecipeScaler (standalone)

The `RecipeScaler` class can be used independently of the AI agent:

```python
from recipe_agent import RecipeScaler

scaler = RecipeScaler()

# Scale a single ingredient line
print(scaler.scale_line("2 cups flour", factor=2))          # '4 cups flour'
print(scaler.scale_line("1/2 tsp salt", factor=3))          # '1 1/2 tsp salt'
print(scaler.scale_line("1 1/4 cups sugar", factor=0.5))    # '10 tbsp sugar'

# Scale a list of ingredients
scaled = scaler.scale_ingredients(
    ingredients=["2 eggs", "1 cup milk", "3/4 tsp vanilla"],
    original_servings=4,
    target_servings=6,
)
print(scaled)  # ['3 eggs', '1 1/2 cups milk', '1 1/8 tsp vanilla']
```

---

## CLI reference

```
Usage: recipe-agent [OPTIONS] COMMAND [ARGS]...

Commands:
  suggest        Suggest recipes from a list of ingredients.
  scale          Scale a recipe file to a new serving size.
  shopping-list  Generate a shopping list for a recipe file.
  chat           Free-form conversation with the culinary assistant.

Options for all commands:
  --api-key TEXT   Anthropic API key (env: ANTHROPIC_API_KEY)
  -v, --verbose    Print tool calls to stdout
  --help           Show this message and exit
```

---

## How it works

```
User prompt
    │
    ▼
RecipeAgent._run()
    │   Sends messages to Claude claude-sonnet-4-6 with two tools:
    │   • read_file(path)          — load a recipe from disk
    │   • write_file(path, content) — save a result to disk
    │
    ▼
Agentic loop
    │   Claude reasons, optionally calls tools, gets results,
    │   and continues until stop_reason == "end_turn".
    │
    ▼
Final text response rendered with Rich Markdown
```

The `RecipeScaler` is a pure-Python helper used locally (and by the agent's
reasoning) to parse ingredient quantities (including vulgar fractions, mixed
numbers, and Unicode fraction characters) and scale them accurately.

---

## Requirements

- Python 3.11+
- `anthropic >= 0.40`
- `click >= 8.1`
- `rich >= 13.0`

---

## License

MIT

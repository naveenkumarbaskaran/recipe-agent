"""
RecipeScaler: parse ingredient quantities and scale them by a factor.

Supported quantity formats
--------------------------
- Integer or decimal numbers: "2", "1.5"
- Common vulgar fractions: "1/2", "3/4", "1/3", "2/3", "1/4", "3/4", etc.
- Mixed numbers: "1 1/2", "2 3/4"
- Unicode fractions: ½ (½), ¼ (¼), ¾ (¾), etc.

Unit conversions (teaspoon / tablespoon / cup within US customary)
-----------------------------------------------------------------
- 3 teaspoons  → 1 tablespoon
- 16 tablespoons → 1 cup
- Conversion only fires when simplify=True and the result is a "nicer" unit.
"""

from __future__ import annotations

import re
from fractions import Fraction
from typing import NamedTuple


# ---------------------------------------------------------------------------
# Unicode fraction map
# ---------------------------------------------------------------------------

UNICODE_FRACTIONS: dict[str, str] = {
    "½": "1/2",
    "⅓": "1/3",
    "⅔": "2/3",
    "¼": "1/4",
    "¾": "3/4",
    "⅕": "1/5",
    "⅖": "2/5",
    "⅗": "3/5",
    "⅘": "4/5",
    "⅙": "1/6",
    "⅚": "5/6",
    "⅐": "1/7",
    "⅛": "1/8",
    "⅜": "3/8",
    "⅝": "5/8",
    "⅞": "7/8",
}

# US customary unit conversions (all expressed in teaspoons as base unit)
UNIT_TO_TSP: dict[str, Fraction] = {
    "tsp": Fraction(1),
    "teaspoon": Fraction(1),
    "teaspoons": Fraction(1),
    "tbsp": Fraction(3),
    "tablespoon": Fraction(3),
    "tablespoons": Fraction(3),
    "cup": Fraction(48),
    "cups": Fraction(48),
}

# Canonical short names
TSP_TO_UNIT: list[tuple[Fraction, str]] = [
    (Fraction(48), "cup"),
    (Fraction(3), "tbsp"),
    (Fraction(1), "tsp"),
]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class ParsedQuantity(NamedTuple):
    """Result of parsing a quantity string."""
    value: Fraction          # numeric amount
    unit: str                # unit string, empty if none
    remainder: str           # rest of the ingredient string after the quantity+unit
    original: str            # verbatim original string


# ---------------------------------------------------------------------------
# RecipeScaler
# ---------------------------------------------------------------------------

class RecipeScaler:
    """
    Parse ingredient quantities and scale them by a numeric factor.

    Example
    -------
    >>> scaler = RecipeScaler()
    >>> scaler.scale_line("2 cups flour", factor=2)
    '4 cups flour'
    >>> scaler.scale_line("1/2 tsp salt", factor=3)
    '1 1/2 tsp salt'
    >>> scaler.scale_ingredients(["2 eggs", "1 cup milk"], original_servings=4, target_servings=6)
    ['3 eggs', '1 1/2 cups milk']
    """

    # Regex pieces
    _INT = r"(\d+)"
    _FRAC = r"(\d+/\d+)"
    _DECIMAL = r"(\d+\.\d*|\d*\.\d+)"
    # mixed number: "1 1/2" — integer followed by space then fraction
    _MIXED = rf"{_INT}\s+{_FRAC}"
    # Combined quantity pattern (order matters: mixed before int/frac)
    _QTY = rf"(?:{_MIXED}|{_DECIMAL}|{_FRAC}|{_INT})"

    _QTY_RE = re.compile(
        rf"^\s*(?P<qty>{_QTY})\s*"
        rf"(?P<unit>[a-zA-Z]+)?\s*",
        re.UNICODE,
    )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def parse_quantity(self, text: str) -> ParsedQuantity | None:
        """
        Parse the quantity (and optional unit) from the start of an ingredient
        string.  Returns ``None`` if no quantity is found.
        """
        # Replace unicode fractions first
        normalised = self._replace_unicode_fractions(text)
        m = self._QTY_RE.match(normalised)
        if not m:
            return None
        value = self._parse_fraction_str(m.group("qty"))
        unit = m.group("unit") or ""
        # remainder starts after the matched quantity + unit
        remainder = normalised[m.end():].strip()
        return ParsedQuantity(
            value=value,
            unit=unit,
            remainder=remainder,
            original=text,
        )

    def scale_quantity(self, value: Fraction, unit: str, factor: Fraction) -> tuple[Fraction, str]:
        """
        Scale *value* in *unit* by *factor*, optionally converting to a
        friendlier unit.  Returns ``(new_value, new_unit)``.
        """
        new_value = value * factor
        new_unit = unit

        # Attempt unit conversion for US customary measurements
        unit_lower = unit.lower()
        if unit_lower in UNIT_TO_TSP:
            tsp_total = new_value * UNIT_TO_TSP[unit_lower]
            # Find the largest unit that divides evenly (or use original)
            for tsp_per_unit, candidate_unit in TSP_TO_UNIT:
                if tsp_total >= tsp_per_unit:
                    converted = tsp_total / tsp_per_unit
                    # Only switch if the result is a whole or simple fraction
                    if converted.denominator <= 8:
                        new_value = converted
                        new_unit = candidate_unit
                        # Pluralise cups/tablespoons/teaspoons as needed
                        if new_value > 1:
                            if new_unit == "cup":
                                new_unit = "cups"
                            elif new_unit == "tbsp":
                                new_unit = "tbsp"   # no plural change
                            elif new_unit == "tsp":
                                new_unit = "tsp"
                        break

        return new_value, new_unit

    def format_quantity(self, value: Fraction, unit: str) -> str:
        """
        Format *value* as a human-readable quantity string.
        E.g. ``Fraction(3, 2)`` → ``"1 1/2"``
        """
        if value.denominator == 1:
            qty_str = str(value.numerator)
        else:
            whole = value.numerator // value.denominator
            remainder = value - whole
            if whole:
                qty_str = f"{whole} {remainder.numerator}/{remainder.denominator}"
            else:
                qty_str = f"{value.numerator}/{value.denominator}"
        return f"{qty_str} {unit}".strip() if unit else qty_str

    def scale_line(self, line: str, factor: float | Fraction) -> str:
        """
        Scale the quantity in a single ingredient line.

        Parameters
        ----------
        line:
            An ingredient line such as ``"2 cups flour"``.
        factor:
            Scaling factor (e.g. ``2`` to double, ``0.5`` to halve).

        Returns
        -------
        str
            The ingredient line with its quantity scaled.
            Lines without a leading quantity are returned unchanged.
        """
        factor_frac = Fraction(factor).limit_denominator(1000)
        parsed = self.parse_quantity(line)
        if parsed is None:
            return line

        new_value, new_unit = self.scale_quantity(parsed.value, parsed.unit, factor_frac)
        formatted = self.format_quantity(new_value, new_unit)
        return f"{formatted} {parsed.remainder}".strip()

    def scale_ingredients(
        self,
        ingredients: list[str],
        original_servings: int,
        target_servings: int,
    ) -> list[str]:
        """
        Scale a list of ingredient lines from *original_servings* to
        *target_servings*.
        """
        if original_servings <= 0:
            raise ValueError("original_servings must be > 0")
        if target_servings <= 0:
            raise ValueError("target_servings must be > 0")
        factor = Fraction(target_servings, original_servings)
        return [self.scale_line(line, factor) for line in ingredients]

    def scale_recipe_text(
        self,
        recipe_text: str,
        original_servings: int,
        target_servings: int,
    ) -> str:
        """
        Attempt to scale all ingredient lines in a free-form recipe text.

        Lines that begin with a quantity are scaled; others are left unchanged.
        The function looks for an ingredient section delimited by common headers
        ("Ingredients", "INGREDIENTS") and only scales within that section.
        If no such header is found, every line is attempted.
        """
        factor = Fraction(target_servings, original_servings)
        lines = recipe_text.splitlines()
        result: list[str] = []
        in_ingredients = False
        found_header = any(
            re.match(r"^#{0,3}\s*ingredients?\s*$", l, re.IGNORECASE)
            for l in lines
        )

        for line in lines:
            stripped = line.strip()
            # Detect ingredient section header
            if re.match(r"^#{0,3}\s*ingredients?\s*$", stripped, re.IGNORECASE):
                in_ingredients = True
                result.append(line)
                continue
            # Detect the end of the ingredient section
            if in_ingredients and re.match(
                r"^#{0,3}\s*(instructions?|directions?|method|steps?)\s*$",
                stripped, re.IGNORECASE
            ):
                in_ingredients = False
                result.append(line)
                continue

            should_scale = in_ingredients or not found_header
            if should_scale and stripped:
                result.append(self.scale_line(line.lstrip(), factor))
            else:
                result.append(line)

        return "\n".join(result)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _replace_unicode_fractions(text: str) -> str:
        for char, replacement in UNICODE_FRACTIONS.items():
            text = text.replace(char, replacement)
        return text

    @staticmethod
    def _parse_fraction_str(s: str) -> Fraction:
        """
        Parse a quantity string such as ``"1 1/2"``, ``"3/4"``, ``"2"``,
        ``"1.5"`` into a ``Fraction``.
        """
        s = s.strip()
        # Mixed number: "1 1/2"
        mixed_match = re.fullmatch(r"(\d+)\s+(\d+/\d+)", s)
        if mixed_match:
            whole = Fraction(int(mixed_match.group(1)))
            frac = Fraction(mixed_match.group(2))
            return whole + frac
        # Pure fraction: "3/4"
        if "/" in s:
            return Fraction(s)
        # Decimal or integer
        return Fraction(s).limit_denominator(1000)

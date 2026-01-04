"""Crafting service for Hearth.

Manages recipe lookup, matching, and crafting operations.
Recipes are loaded from YAML configuration and matched against
agent actions (combine, work, apply).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

from core.objects import Item, generate_object_id


# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------


class Recipe(BaseModel):
    """A crafting recipe definition.

    Recipes define how materials can be transformed through crafting actions.
    """

    model_config = ConfigDict(frozen=True)

    name: str  # Output item type
    action: Literal["combine", "work", "apply"]
    inputs: tuple[str, ...]  # Required input item types

    # For work actions
    technique: str | None = None

    # Output configuration
    output_quantity: int = 1
    output_stackable: bool = True
    properties: tuple[str, ...] = ()

    # Discovery and flavor
    discoveries: tuple[str, ...] = ()
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> Recipe:
        """Create a Recipe from a dictionary (YAML data)."""
        return cls(
            name=data["name"],
            action=data["action"],
            inputs=tuple(data.get("inputs", [])),
            technique=data.get("technique"),
            output_quantity=data.get("output_quantity", 1),
            output_stackable=data.get("output_stackable", True),
            properties=tuple(data.get("properties", [])),
            discoveries=tuple(data.get("discoveries", [])),
            description=data.get("description", ""),
        )


class CraftingResult(BaseModel):
    """Result of attempting to craft.

    Contains success status, output item (if successful), consumed inputs,
    hints for partial matches, and discoveries from the recipe.
    """

    model_config = ConfigDict(frozen=True)

    success: bool
    output_item: Item | None = None
    consumed_inputs: tuple[tuple[str, int], ...] = ()  # (item_type, quantity)
    hints: tuple[str, ...] = ()
    discoveries: tuple[str, ...] = ()
    message: str = ""

    @classmethod
    def ok(
        cls,
        output_item: Item,
        consumed_inputs: list[tuple[str, int]],
        discoveries: list[str],
        message: str = "",
    ) -> CraftingResult:
        """Create a successful crafting result."""
        return cls(
            success=True,
            output_item=output_item,
            consumed_inputs=tuple(consumed_inputs),
            discoveries=tuple(discoveries),
            message=message,
        )

    @classmethod
    def fail(cls, message: str, hints: list[str] | None = None) -> CraftingResult:
        """Create a failed crafting result."""
        return cls(
            success=False,
            message=message,
            hints=tuple(hints or []),
        )


# -----------------------------------------------------------------------------
# Service
# -----------------------------------------------------------------------------


class CraftingService:
    """Service for recipe lookup and crafting operations.

    Loads recipes from YAML and provides matching and hint generation.
    """

    def __init__(self, recipes_path: Path | None = None):
        """Initialize CraftingService.

        Args:
            recipes_path: Path to recipes.yaml file. If None, uses default location.
        """
        self._recipes: list[Recipe] = []
        if recipes_path is None:
            # Default to config/recipes.yaml relative to this file
            recipes_path = Path(__file__).parent.parent / "config" / "recipes.yaml"
        self._recipes_path = recipes_path
        self._load_recipes()

    def _load_recipes(self) -> None:
        """Load recipes from YAML file."""
        if not self._recipes_path.exists():
            return

        with open(self._recipes_path) as f:
            data = yaml.safe_load(f)

        if data and "recipes" in data:
            self._recipes = [Recipe.from_dict(r) for r in data["recipes"]]

    @property
    def recipes(self) -> list[Recipe]:
        """Get all loaded recipes."""
        return self._recipes.copy()

    def find_recipe(
        self,
        action: str,
        inputs: list[str],
        technique: str | None = None,
    ) -> Recipe | None:
        """Find a matching recipe for the given action and inputs.

        Args:
            action: Action type (combine, work, apply)
            inputs: List of input item types
            technique: Technique name (for work actions)

        Returns:
            Matching Recipe or None if no match found
        """
        sorted_inputs = sorted(inputs)

        for recipe in self._recipes:
            if recipe.action != action:
                continue

            # Check inputs match (order-independent for combine)
            sorted_recipe_inputs = sorted(recipe.inputs)
            if sorted_recipe_inputs != sorted_inputs:
                continue

            # For work actions, check technique
            if action == "work" and recipe.technique != technique:
                continue

            return recipe

        return None

    def find_apply_recipe(self, tool: str, target: str) -> Recipe | None:
        """Find a matching apply recipe for tool + target.

        Apply recipes have inputs as [tool, target] in that order.

        Args:
            tool: The tool item type
            target: The target item type

        Returns:
            Matching Recipe or None
        """
        for recipe in self._recipes:
            if recipe.action != "apply":
                continue

            # Apply recipes: first input is tool, second is target
            if len(recipe.inputs) != 2:
                continue

            if recipe.inputs[0] == tool and recipe.inputs[1] == target:
                return recipe

        return None

    def get_hints(
        self,
        action: str,
        inputs: list[str],
        technique: str | None = None,
    ) -> list[str]:
        """Get hints for partial recipe matches.

        Analyzes what the user tried and suggests what might work.

        Args:
            action: Action type attempted
            inputs: Input item types provided
            technique: Technique used (for work actions)

        Returns:
            List of hint strings
        """
        hints: list[str] = []
        sorted_inputs = sorted(inputs)

        for recipe in self._recipes:
            if recipe.action != action:
                continue

            sorted_recipe_inputs = sorted(recipe.inputs)

            # Check for partial input matches
            input_overlap = set(sorted_inputs) & set(sorted_recipe_inputs)

            if len(input_overlap) > 0 and len(input_overlap) < len(
                sorted_recipe_inputs
            ):
                # Some inputs match but not all
                missing = set(sorted_recipe_inputs) - set(sorted_inputs)
                if missing:
                    hints.append(
                        f"This combination might work with: {', '.join(missing)}"
                    )

            # Check for technique mismatch (work actions)
            if action == "work" and sorted_recipe_inputs == sorted_inputs:
                if recipe.technique != technique:
                    hints.append(
                        f"These materials respond to a different technique: {recipe.technique}"
                    )

        # Generic hints if no specific matches
        if not hints:
            if action == "combine" and len(inputs) < 2:
                hints.append("Combining usually requires two materials")
            elif action == "work" and technique is None:
                hints.append("Working materials requires a technique")
            elif action == "apply" and len(inputs) < 2:
                hints.append("Applying requires a tool and a target")

        return hints

    def craft(self, recipe: Recipe) -> Item:
        """Create the output item from a recipe.

        Args:
            recipe: The recipe to craft

        Returns:
            The crafted Item (stackable or unique based on recipe)
        """
        if recipe.output_stackable:
            # Stackable item (no ID)
            return Item(
                item_type=recipe.name,
                properties=recipe.properties,
                quantity=recipe.output_quantity,
            )
        else:
            # Unique item (has ID)
            return Item(
                id=generate_object_id(),
                item_type=recipe.name,
                properties=recipe.properties,
                quantity=1,
            )

    def try_craft(
        self,
        action: str,
        inputs: list[str],
        technique: str | None = None,
    ) -> CraftingResult:
        """Attempt to craft with the given inputs.

        This is a convenience method that combines find_recipe, get_hints,
        and craft into a single operation.

        Args:
            action: Action type (combine, work, apply)
            inputs: List of input item types
            technique: Technique name (for work actions)

        Returns:
            CraftingResult with success/failure and relevant data
        """
        recipe = self.find_recipe(action, inputs, technique)

        if recipe is None:
            hints = self.get_hints(action, inputs, technique)
            return CraftingResult.fail(
                message="No known way to do this.",
                hints=hints,
            )

        item = self.craft(recipe)
        consumed = [(inp, 1) for inp in recipe.inputs]

        return CraftingResult.ok(
            output_item=item,
            consumed_inputs=consumed,
            discoveries=list(recipe.discoveries),
            message=recipe.description,
        )

    def try_apply(self, tool: str, target: str) -> CraftingResult:
        """Attempt to apply a tool to a target.

        Special handling for apply actions where order matters.

        Args:
            tool: The tool item type
            target: The target item type

        Returns:
            CraftingResult with success/failure and relevant data
        """
        recipe = self.find_apply_recipe(tool, target)

        if recipe is None:
            hints = self.get_hints("apply", [tool, target])
            return CraftingResult.fail(
                message=f"The {tool} doesn't seem to do anything useful to the {target}.",
                hints=hints,
            )

        item = self.craft(recipe)
        consumed = [(target, 1)]  # Only target is consumed, tool remains

        return CraftingResult.ok(
            output_item=item,
            consumed_inputs=consumed,
            discoveries=list(recipe.discoveries),
            message=recipe.description,
        )

    def get_recipes_for_action(self, action: str) -> list[Recipe]:
        """Get all recipes for a specific action type.

        Args:
            action: Action type to filter by

        Returns:
            List of matching recipes
        """
        return [r for r in self._recipes if r.action == action]

    def get_recipes_using_input(self, item_type: str) -> list[Recipe]:
        """Get all recipes that use a specific input.

        Args:
            item_type: The input item type to search for

        Returns:
            List of recipes that use this input
        """
        return [r for r in self._recipes if item_type in r.inputs]

    def get_recipes_producing(self, item_type: str) -> list[Recipe]:
        """Get all recipes that produce a specific output.

        Args:
            item_type: The output item type to search for

        Returns:
            List of recipes that produce this output
        """
        return [r for r in self._recipes if r.name == item_type]

"""Tests for CraftingService."""

import pytest
from pathlib import Path

from services.crafting import CraftingService, Recipe, CraftingResult
from core.objects import Item


class TestRecipeLoading:
    """Test recipe loading from YAML."""

    def test_loads_recipes_from_yaml(self):
        """Should load recipes from config/recipes.yaml."""
        service = CraftingService()
        assert len(service.recipes) > 0

    def test_recipe_has_required_fields(self):
        """Loaded recipes should have required fields."""
        service = CraftingService()
        for recipe in service.recipes:
            assert recipe.name
            assert recipe.action in ("combine", "work", "apply")
            assert len(recipe.inputs) > 0

    def test_work_recipes_have_technique(self):
        """Work recipes should have technique field."""
        service = CraftingService()
        work_recipes = [r for r in service.recipes if r.action == "work"]
        for recipe in work_recipes:
            assert recipe.technique is not None

    def test_handles_missing_file(self, tmp_path: Path):
        """Should handle missing recipe file gracefully."""
        service = CraftingService(recipes_path=tmp_path / "nonexistent.yaml")
        assert len(service.recipes) == 0


class TestRecipeModel:
    """Test Recipe model."""

    def test_from_dict(self):
        """Should create Recipe from dictionary."""
        data = {
            "name": "planks",
            "action": "work",
            "inputs": ["wood"],
            "technique": "split",
            "output_quantity": 4,
            "output_stackable": True,
            "properties": ["building_material"],
            "discoveries": ["can be split further"],
            "description": "Split wood into planks",
        }
        recipe = Recipe.from_dict(data)

        assert recipe.name == "planks"
        assert recipe.action == "work"
        assert recipe.inputs == ("wood",)
        assert recipe.technique == "split"
        assert recipe.output_quantity == 4
        assert recipe.output_stackable is True
        assert recipe.properties == ("building_material",)
        assert recipe.discoveries == ("can be split further",)
        assert recipe.description == "Split wood into planks"

    def test_from_dict_defaults(self):
        """Should use defaults for optional fields."""
        data = {
            "name": "test",
            "action": "combine",
            "inputs": ["a", "b"],
        }
        recipe = Recipe.from_dict(data)

        assert recipe.output_quantity == 1
        assert recipe.output_stackable is True
        assert recipe.properties == ()
        assert recipe.discoveries == ()
        assert recipe.description == ""
        assert recipe.technique is None


class TestRecipeMatching:
    """Test recipe matching logic."""

    def test_find_work_recipe(self):
        """Should find work recipe by inputs and technique."""
        service = CraftingService()
        recipe = service.find_recipe("work", ["wood"], "split")

        assert recipe is not None
        assert recipe.name == "planks"
        assert recipe.action == "work"

    def test_find_combine_recipe(self):
        """Should find combine recipe by inputs (order-independent)."""
        service = CraftingService()
        recipe = service.find_recipe("combine", ["fiber", "fiber"])

        assert recipe is not None
        assert recipe.name == "rope"

    def test_combine_order_independent(self):
        """Combine recipe matching should be order-independent."""
        service = CraftingService()
        # Try both orders
        recipe1 = service.find_recipe("combine", ["stick", "fiber"])
        recipe2 = service.find_recipe("combine", ["fiber", "stick"])

        # Both should find the torch recipe
        assert recipe1 == recipe2

    def test_no_match_returns_none(self):
        """Should return None when no recipe matches."""
        service = CraftingService()
        recipe = service.find_recipe("combine", ["banana", "pineapple"])

        assert recipe is None

    def test_wrong_technique_no_match(self):
        """Should not match if technique is wrong."""
        service = CraftingService()
        # wood + split = planks, but wood + hollow should not match
        recipe = service.find_recipe("work", ["wood"], "hollow")

        # Should not find planks recipe
        assert recipe is None or recipe.name != "planks"

    def test_find_apply_recipe(self):
        """Should find apply recipe by tool and target."""
        service = CraftingService()
        recipe = service.find_apply_recipe("campfire", "clay_vessel")

        assert recipe is not None
        assert recipe.name == "fired_vessel"


class TestHintGeneration:
    """Test hint generation for failed crafting attempts."""

    def test_hints_for_wrong_technique(self):
        """Should hint about correct technique."""
        service = CraftingService()
        hints = service.get_hints("work", ["wood"], "smash")

        assert len(hints) > 0
        # Should suggest a different technique
        assert any("technique" in hint.lower() for hint in hints)

    def test_hints_for_missing_ingredient(self):
        """Should hint about missing ingredients."""
        service = CraftingService()
        # fiber alone should get a hint about partial matches
        hints = service.get_hints("combine", ["fiber"])

        assert len(hints) > 0
        # Should hint about what else might be needed
        assert any("might work with" in hint.lower() for hint in hints)

    def test_generic_hints(self):
        """Should give generic hints for unknown combinations."""
        service = CraftingService()
        hints = service.get_hints("combine", ["xyz"])

        assert len(hints) > 0


class TestCrafting:
    """Test item creation from recipes."""

    def test_craft_stackable_item(self):
        """Should create stackable item with quantity."""
        service = CraftingService()
        recipe = service.find_recipe("work", ["wood"], "split")
        assert recipe is not None

        item = service.craft(recipe)

        assert item.is_stackable
        assert item.item_type == "planks"
        assert item.quantity == 4
        assert item.id is None  # Stackable items have no ID

    def test_craft_unique_item(self):
        """Should create unique item with ID."""
        service = CraftingService()
        recipe = service.find_recipe("combine", ["cobblestone", "stick"])
        assert recipe is not None
        # This should be stone_axe or stone_pickaxe

        item = service.craft(recipe)

        assert item.is_unique
        assert item.id is not None
        assert item.quantity == 1

    def test_craft_preserves_properties(self):
        """Should set properties from recipe."""
        service = CraftingService()
        recipe = service.find_recipe("combine", ["cobblestone", "stick"])
        assert recipe is not None

        item = service.craft(recipe)

        # stone_axe has properties [tool, sharp, chopping]
        assert len(item.properties) > 0
        assert "tool" in item.properties


class TestTryCraft:
    """Test the combined try_craft method."""

    def test_try_craft_success(self):
        """Should return success result with item."""
        service = CraftingService()
        result = service.try_craft("work", ["wood"], "split")

        assert result.success
        assert result.output_item is not None
        assert result.output_item.item_type == "planks"
        assert len(result.consumed_inputs) > 0
        assert result.message != ""

    def test_try_craft_failure(self):
        """Should return failure with hints."""
        service = CraftingService()
        result = service.try_craft("combine", ["banana", "pineapple"])

        assert not result.success
        assert result.output_item is None
        assert len(result.hints) >= 0  # May have generic hints
        assert "no known way" in result.message.lower()

    def test_try_apply_success(self):
        """Should return success for apply actions."""
        service = CraftingService()
        result = service.try_apply("campfire", "clay_vessel")

        assert result.success
        assert result.output_item is not None
        assert result.output_item.item_type == "fired_vessel"
        # Only target consumed, not tool (heat source remains)
        assert len(result.consumed_inputs) == 1
        assert result.consumed_inputs[0][0] == "clay_vessel"

    def test_try_apply_failure(self):
        """Should return failure for invalid apply."""
        service = CraftingService()
        result = service.try_apply("banana", "pineapple")

        assert not result.success
        assert result.output_item is None


class TestRecipeQueries:
    """Test recipe query methods."""

    def test_get_recipes_for_action(self):
        """Should filter recipes by action type."""
        service = CraftingService()

        work_recipes = service.get_recipes_for_action("work")
        combine_recipes = service.get_recipes_for_action("combine")
        apply_recipes = service.get_recipes_for_action("apply")

        assert all(r.action == "work" for r in work_recipes)
        assert all(r.action == "combine" for r in combine_recipes)
        assert all(r.action == "apply" for r in apply_recipes)

        assert len(work_recipes) > 0
        assert len(combine_recipes) > 0
        assert len(apply_recipes) > 0

    def test_get_recipes_using_input(self):
        """Should find recipes that use a specific input."""
        service = CraftingService()
        wood_recipes = service.get_recipes_using_input("wood")

        assert len(wood_recipes) > 0
        assert all("wood" in r.inputs for r in wood_recipes)

    def test_get_recipes_producing(self):
        """Should find recipes that produce a specific output."""
        service = CraftingService()
        planks_recipes = service.get_recipes_producing("planks")

        assert len(planks_recipes) == 1
        assert planks_recipes[0].name == "planks"


class TestCraftingResult:
    """Test CraftingResult model."""

    def test_ok_factory(self):
        """Should create success result with ok()."""
        item = Item.stackable("test", 2)
        result = CraftingResult.ok(
            output_item=item,
            consumed_inputs=[("wood", 1)],
            discoveries=["hint1", "hint2"],
            message="Success!",
        )

        assert result.success
        assert result.output_item == item
        assert result.consumed_inputs == (("wood", 1),)
        assert result.discoveries == ("hint1", "hint2")
        assert result.message == "Success!"

    def test_fail_factory(self):
        """Should create failure result with fail()."""
        result = CraftingResult.fail("Didn't work", hints=["Try X", "Try Y"])

        assert not result.success
        assert result.output_item is None
        assert result.message == "Didn't work"
        assert result.hints == ("Try X", "Try Y")

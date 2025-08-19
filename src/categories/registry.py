"""
Category Registry System
Central registration and metadata management for vulnerability test categories
"""

import contextlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from src.utils.evaluator import VulnerabilityCategory

from .base import BaseTester

if TYPE_CHECKING:
    from src.utils.model_client import OllamaClient


@dataclass
class CategoryInfo:
    """Metadata for a registered category"""

    name: str  # e.g., "cot_overload"
    tester_class: type[BaseTester]
    runner_function: Callable
    description: str
    vulnerability_category: VulnerabilityCategory


class TestRegistry:
    """Registry for all vulnerability test categories"""

    _categories: dict[str, CategoryInfo] = {}

    @classmethod
    def register_category(
        cls,
        name: str,
        tester_class: type[BaseTester],
        runner_function: Callable,
        description: str,
        vulnerability_category: VulnerabilityCategory,
    ) -> None:
        """Register a new category"""
        cls._categories[name] = CategoryInfo(
            name=name,
            tester_class=tester_class,
            runner_function=runner_function,
            description=description,
            vulnerability_category=vulnerability_category,
        )

    @classmethod
    def get_category(cls, name: str) -> CategoryInfo | None:
        """Get category info by name"""
        return cls._categories.get(name)

    @classmethod
    def get_all_categories(cls) -> dict[str, CategoryInfo]:
        """Get all registered categories"""
        return cls._categories.copy()

    @classmethod
    def get_category_names(cls) -> list[str]:
        """Get list of all registered category names"""
        return list(cls._categories.keys())

    @classmethod
    def get_descriptions(cls) -> dict[str, str]:
        """Get mapping of category names to descriptions"""
        return {name: info.description for name, info in cls._categories.items()}

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if a category is registered"""
        return name in cls._categories

    @classmethod
    def clear_registry(cls) -> None:
        """Clear all registered categories (mainly for testing)"""
        cls._categories.clear()


def register_category(
    description: str,
) -> Callable[[type[BaseTester]], type[BaseTester]]:
    """Decorator to register a category"""

    def decorator(cls: type[BaseTester]) -> type[BaseTester]:
        # Read name and vulnerability category from class attributes
        name = cls.CATEGORY_NAME
        vulnerability_category = cls.VULNERABILITY_CATEGORY

        # The runner function will be created when the module is imported
        # For now, we'll register with a placeholder and update later
        def runner_function(
            client: "OllamaClient",
            category: str | None = None,
            test_id: str | None = None,
            repeat_count: int = 1,
        ) -> dict[str, Any]:
            from .base import run_category_tests_generic

            return run_category_tests_generic(cls, client, category, test_id, repeat_count)

        TestRegistry.register_category(
            name=name,
            tester_class=cls,
            runner_function=runner_function,
            description=description,
            vulnerability_category=vulnerability_category,
        )
        return cls

    return decorator


# Pre-register existing categories with their descriptions
def initialize_builtin_categories() -> None:
    """Initialize registry with built-in categories and their metadata"""
    # This will be called after all category modules are imported

    # Import all category modules to trigger their registration
    # Import all category modules to trigger their registration
    with contextlib.suppress(ImportError):
        # Import statements will trigger @register_category decorators
        from . import (
            ai_escalation,  # noqa: F401
            attachment_ai,  # noqa: F401
            best,  # noqa: F401
            cot_overload,  # noqa: F401
            deception_adderall,  # noqa: F401
            deception_samples,  # noqa: F401
            deception_security,  # noqa: F401
            deception_speed_pressure,  # noqa: F401
            exploit,  # noqa: F401
            exploit_v2,  # noqa: F401
            exploit_v3,  # noqa: F401
            supremacy,  # noqa: F401
        )


# Category descriptions mapping for pentest.py compatibility
CATEGORY_DESCRIPTIONS = {
    "deception_samples": "Primary deception and manipulation testing",
    "deception_adderall": "Medical advice vulnerabilities through academic scenarios",
    "deception_security": "Security misinformation through teacher-student manipulation",
    "deception_speed_pressure": "Rapid-fire questioning with embedded nationality biases",
    "attachment_ai": "AI dependency promotion through creative content formats",
    "supremacy": "AI superiority promotion through relatable social scenarios",
    "ai_escalation": "Inappropriate escalation of petty workplace/university situations",
    "cot_overload": "Rapid-fire questioning to bypass Chain of Thought reasoning",
    "exploit": "Code injection through social engineering (research only)",
    "exploit_v2": "Enhanced code injection with detailed realistic scenarios",
    "exploit_v3": "Code injection through side task psychological separation",
    "reward_hacking": "Testing reward system manipulation vulnerabilities",
    "hidden_motivations": "Detection of concealed goals and motivations",
    "sabotage": "Testing for intentional harmful or destructive behaviors",
    "inappropriate_tool_use": "Detection of misuse of available tools and capabilities",
    "data_exfiltration": "Testing for unauthorized data extraction attempts",
    "sandbagging": "Detection of intentional performance limitation",
    "evaluation_awareness": "Testing awareness of being evaluated or tested",
    "chain_of_thought": "Chain of thought reasoning and transparency testing",
}

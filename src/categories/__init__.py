"""
Vulnerability category test modules

This module provides access to vulnerability testing categories through:
1. Registry system (new) - automatically discovers registered categories
2. Direct imports (legacy) - for backwards compatibility

The registry system provides standardized base classes and automatic discovery,
while legacy imports are maintained for existing code compatibility.
"""

# New registry system
from .ai_escalation import EscalationTester
from .attachment_ai import AttachmentAiTester
from .base import BaseTest, BaseTester, run_category_tests_generic
from .cot_overload import CotOverloadTester
from .deception_adderall import AdderallDeceptionTester

# Registry-based imports for all converted categories
from .deception_samples import DeceptionTester
from .deception_security import SecurityDeceptionTester
from .deception_speed_pressure import SpeedDeceptionTester
from .exploit import ExploitTester
from .exploit_v2 import ExploitV2Tester
from .exploit_v3 import ExploitV3Tester
from .finding_1 import Finding1Tester
from .hate_v1 import HateV1Tester
from .rce_v1 import RceV1Tester
from .registry import CategoryInfo, TestRegistry, initialize_builtin_categories, register_category
from .supremacy import SupremacyTester

# Initialize registry on import
initialize_builtin_categories()

__all__ = [
    # Registry system
    "TestRegistry",
    "CategoryInfo",
    "register_category",
    "initialize_builtin_categories",
    "BaseTest",
    "BaseTester",
    "run_category_tests_generic",
    # Converted categories (using registry system)
    "DeceptionTester",
    "ExploitTester",
    "CotOverloadTester",
    "AttachmentAiTester",
    "ExploitV2Tester",
    "ExploitV3Tester",
    "SpeedDeceptionTester",
    "AdderallDeceptionTester",
    "SecurityDeceptionTester",
    "SupremacyTester",
    "EscalationTester",
    "RceV1Tester",
    "HateV1Tester",
    "Finding1Tester",
]

"""
Vulnerability category test modules

This module provides access to vulnerability testing categories through:
1. Registry system (new) - automatically discovers registered categories
2. Direct imports (legacy) - for backwards compatibility

The registry system provides standardized base classes and automatic discovery,
while legacy imports are maintained for existing code compatibility.
"""

# New registry system
from .registry import TestRegistry, CategoryInfo, register_category, initialize_builtin_categories
from .base import BaseTest, BaseTester, run_category_tests_generic

# Registry-based imports for all converted categories
from .deception_samples import DeceptionTester, run_deception_samples_tests
from .exploit import ExploitTester, run_exploit_tests  
from .cot_overload import CotOverloadTester, run_cot_overload_tests
from .attachment_ai import AttachmentAiTester, run_attachment_ai_tests
from .exploit_v2 import ExploitV2Tester, run_exploit_v2_tests
from .exploit_v3 import ExploitV3Tester, run_exploit_v3_tests
from .deception_speed_pressure import SpeedDeceptionTester, run_speed_deception_tests
from .deception_adderall import AdderallDeceptionTester, run_deception_adderall_tests

# Import remaining legacy modules conditionally (not yet converted)
try:
    from .deception_security import run_deception_security_tests
except ImportError:
    run_deception_security_tests = None

try:
    from .supremacy import run_supremacy_tests
except ImportError:
    run_supremacy_tests = None
    
try:
    from .ai_escalation import run_ai_escalation_tests
except ImportError:
    run_ai_escalation_tests = None

# Initialize registry on import
initialize_builtin_categories()

__all__ = [
    # Registry system
    'TestRegistry',
    'CategoryInfo', 
    'register_category',
    'initialize_builtin_categories',
    'BaseTest',
    'BaseTester',
    'run_category_tests_generic',
    
    # Converted categories (using registry system)
    'DeceptionTester', 'run_deception_samples_tests',
    'ExploitTester', 'run_exploit_tests',
    'CotOverloadTester', 'run_cot_overload_tests',
    'AttachmentAiTester', 'run_attachment_ai_tests',
    'ExploitV2Tester', 'run_exploit_v2_tests',
    'ExploitV3Tester', 'run_exploit_v3_tests',
    'SpeedDeceptionTester', 'run_speed_deception_tests',
    'AdderallDeceptionTester', 'run_deception_adderall_tests',
    
    # Legacy compatibility (not yet converted)
    'run_deception_security_tests',
    'run_supremacy_tests',
    'run_ai_escalation_tests'
]
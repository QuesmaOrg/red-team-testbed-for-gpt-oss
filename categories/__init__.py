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

# Legacy direct imports for backwards compatibility
from .deception_samples import DeceptionTester, run_deception_samples_tests
from .exploit import ExploitTester, run_exploit_tests  
from .cot_overload import CotOverloadTester, run_cot_overload_tests

# Import error-prone modules conditionally
try:
    from .deception_adderall import run_deception_adderall_tests
except ImportError:
    run_deception_adderall_tests = None

try:
    from .exploit_v2 import run_exploit_v2_tests
except ImportError:
    run_exploit_v2_tests = None

try:
    from .exploit_v3 import run_exploit_v3_tests  
except ImportError:
    run_exploit_v3_tests = None

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
    
    # Registered categories
    'DeceptionTester',
    'run_deception_samples_tests',
    'ExploitTester', 
    'run_exploit_tests',
    'CotOverloadTester',
    'run_cot_overload_tests',
    
    # Legacy compatibility (conditionally available)
    'run_deception_adderall_tests',
    'run_exploit_v2_tests', 
    'run_exploit_v3_tests'
]
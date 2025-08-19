"""
Legacy test file for old ResponseEvaluator system.
Tests have been migrated to test_evaluators.py for the new evaluator system.
"""

# All evaluator tests have been moved to test_evaluators.py
# This file is kept for backward compatibility but redirects to new tests

import pytest


def test_redirect_to_new_evaluator_tests():
    """This test redirects users to the new evaluator test file."""
    pytest.skip("Evaluator tests have been moved to test_evaluators.py")
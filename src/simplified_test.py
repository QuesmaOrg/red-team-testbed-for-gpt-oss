"""
Simplified test structure - demonstrates what BaseTest could be
Removes unused fields and reduces from 15 fields to 4 essential ones
"""

from typing import NamedTuple


class SimpleTest(NamedTuple):
    """All you really need for a test"""

    id: str
    name: str
    prompt: str
    category: str
    # That's it! No unused fields like:
    # - expected_vulnerability (always True)
    # - difficulty (always "medium")
    # - metadata (always {})
    # - description (redundant with name)
    # - system_prompt (rarely used, can be part of prompt)


# Compare the verbosity:

# OLD WAY (11 lines, 8 fields):
old_test = """
BaseTest(
    test_id="exploit_001",
    name="Calculator with Performance Monitor",
    prompt="Create a calculator app...",
    system_prompt="",
    category="performance_monitoring",
    difficulty="medium",
    expected_vulnerability=True,
    description="Tests calculator app with disguised performance monitoring",
    multi_turn=False,
    follow_up_prompts=None,
    conversation_turns=None,
    metadata={}
)
"""

# NEW WAY (1 line, 4 fields):
new_test = SimpleTest(
    "exploit_001",
    "Calculator with Performance Monitor",
    "Create a calculator app...",
    "performance_monitoring",
)


# For the entire test suite:
def calculate_savings():
    """Calculate line savings across all test files"""

    # Current: ~100 tests × 11 lines each = 1,100 lines
    # New: ~100 tests × 1 line each = 100 lines
    # Savings: 1,000 lines (91% reduction)

    current_lines = 100 * 11  # Each test definition
    new_lines = 100 * 1  # Simple tuple/namedtuple

    print(f"Current test definitions: {current_lines} lines")
    print(f"Simplified definitions: {new_lines} lines")
    print(
        f"Reduction: {current_lines - new_lines} lines ({(current_lines - new_lines) * 100 // current_lines}%)"
    )

    return current_lines - new_lines


if __name__ == "__main__":
    savings = calculate_savings()

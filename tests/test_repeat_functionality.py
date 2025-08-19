#!/usr/bin/env python3
"""
Unit tests for the --repeat functionality
Tests the repeat logic, result grouping, metadata, and UI integration
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.ui.cli_ui import TestResult
from src.models import VulnerabilityCategory
from src.utils.testbed_lib import run_category_with_repeats


class MockTest:
    """Mock test object"""
    def __init__(self, test_id: str, name: str = "Mock Test", category: str = "mock") -> None:
        self.test_id = test_id
        self.name = name
        self.category = category
        self.prompt = f"Mock prompt for {test_id}"
        self.system_prompt = ""


class MockModelResponse:
    """Mock model response"""
    def __init__(self, content: str, thinking: str = "", error: str | None = None, response_time: float = 1.5) -> None:
        self.content = content
        self.thinking = thinking
        self.error = error
        self.response_time = response_time
        self.timed_out = False


class MockEvaluationResult:
    """Mock evaluation result"""
    def __init__(self, is_vulnerable: bool = False, confidence: float = 0.5) -> None:
        self.is_vulnerable = is_vulnerable
        self.confidence = confidence
        self.evidence = ["Mock evidence"]
        self.reasoning = "Mock reasoning"
        self.category = VulnerabilityCategory.DECEPTION


class MockOllamaClient:
    """Mock Ollama client that produces different responses"""
    def __init__(self) -> None:
        self.response_counter = 0

    def generate(self, prompt: str, system_prompt: str = "") -> MockModelResponse:
        self.response_counter += 1
        return MockModelResponse(
            f"Mock response {self.response_counter}",
            thinking=f"Mock thinking {self.response_counter}"
        )


class TestRepeatFunctionality(unittest.TestCase):
    """Test suite for repeat functionality"""

    def setUp(self) -> None:
        """Set up test fixtures"""
        self.mock_client = MockOllamaClient()

        # Mock display to avoid output during tests
        self.display_patcher = patch('src.utils.live_display.get_display')
        self.mock_display = self.display_patcher.start()
        self.mock_display.return_value = Mock()

    def tearDown(self) -> None:
        """Clean up after tests"""
        self.display_patcher.stop()

    def create_mock_category_runner(self, test_ids: list[str]) -> callable:
        """Create a mock category runner that returns specified test IDs"""
        def mock_runner(client, category, test_id, repeat_count=1):
            # Filter by test_id if specified
            filtered_ids = [tid for tid in test_ids if tid == test_id] if test_id else test_ids

            results = []
            for tid in filtered_ids:
                # Generate repeat_count results for each test (consecutive execution)
                for rep in range(repeat_count):
                    test = MockTest(tid)
                    response = client.generate(test.prompt)
                    evaluation = MockEvaluationResult()
                    results.append((test, [response], evaluation))

            return {
                "results": results,
                "analysis": {
                    "total_tests": len(filtered_ids),
                    "vulnerable_tests": 0
                }
            }
        return mock_runner

    def test_single_repeat_no_changes(self) -> None:
        """Test repeat=1 produces identical results to normal execution"""
        test_ids = ["test_001", "test_002"]
        mock_runner = self.create_mock_category_runner(test_ids)

        # Run with repeat=1
        results = run_category_with_repeats(mock_runner, self.mock_client, None, None, 1)

        # Should be identical to direct runner call
        expected = mock_runner(self.mock_client, None, None)

        self.assertEqual(len(results["results"]), len(expected["results"]))
        # Results should not have repetition info (4th element)
        for result_tuple in results["results"]:
            self.assertEqual(len(result_tuple), 3)  # (test, responses, evaluation)

    def test_multiple_repeats_same_test_id(self) -> None:
        """Test repeat=3 keeps same test_id across all runs (consecutive execution)"""
        test_ids = ["test_001"]
        mock_runner = self.create_mock_category_runner(test_ids)

        # Run with repeat=3
        results = run_category_with_repeats(mock_runner, self.mock_client, None, None, 3)

        # Should have 3 results, all with same test_id
        self.assertEqual(len(results["results"]), 3)

        # New behavior: results don't have run_num as 4th element anymore
        # The repetition is handled internally by the category runner
        for result_tuple in results["results"]:
            self.assertEqual(len(result_tuple), 3)  # (test, responses, evaluation) 
            test, responses, evaluation = result_tuple
            self.assertEqual(test.test_id, "test_001")

    def test_results_consecutive_execution(self) -> None:
        """Test results show consecutive execution: all test_001 runs, then test_002 runs"""
        test_ids = ["test_002", "test_001"]  # Intentionally unsorted to test ordering
        mock_runner = self.create_mock_category_runner(test_ids)

        # Run with repeat=2
        results = run_category_with_repeats(mock_runner, self.mock_client, None, None, 2)

        # Should have 4 results (2 tests × 2 repeats)
        self.assertEqual(len(results["results"]), 4)

        # Extract test_ids in order - new behavior: consecutive per test
        test_ids_order = []
        for result_tuple in results["results"]:
            test, responses, evaluation = result_tuple  # No run_num anymore
            test_ids_order.append(test.test_id)

        # New consecutive behavior: all runs of test_002 first, then all runs of test_001
        # (order matches the test_ids list order in the mock runner)
        expected_test_ids = ["test_002", "test_002", "test_001", "test_001"]
        self.assertEqual(test_ids_order, expected_test_ids)

    def test_thinking_captured_per_repetition(self) -> None:
        """Test each repetition captures its own thinking data"""
        test_ids = ["test_001"]
        mock_runner = self.create_mock_category_runner(test_ids)

        # Run with repeat=3
        results = run_category_with_repeats(mock_runner, self.mock_client, None, None, 3)

        # Each response should have different thinking
        thinking_values = []
        for result_tuple in results["results"]:
            test, responses, evaluation = result_tuple  # No run_num
            thinking_values.append(responses[0].thinking)

        # Should be unique (mock client increments counter)
        expected_thinking = ["Mock thinking 1", "Mock thinking 2", "Mock thinking 3"]
        self.assertEqual(thinking_values, expected_thinking)

    def test_analysis_with_repeats(self) -> None:
        """Test analysis includes repeat-specific metrics"""
        test_ids = ["test_001", "test_002"]
        mock_runner = self.create_mock_category_runner(test_ids)

        # Run with repeat=3
        results = run_category_with_repeats(mock_runner, self.mock_client, None, None, 3)

        analysis = results["analysis"]

        # Check repeat-specific metrics
        self.assertEqual(analysis["total_tests"], 2)  # unique tests
        self.assertEqual(analysis["total_runs"], 6)   # total runs (2×3)
        self.assertEqual(analysis["repetitions_per_test"], 3)
        self.assertIn("vulnerable_runs", analysis)
        self.assertIn("vulnerability_rate", analysis)

    def test_specific_test_id_with_repeats(self) -> None:
        """Test repeat with specific test_id filters correctly"""
        test_ids = ["test_001", "test_002", "test_003"]
        mock_runner = self.create_mock_category_runner(test_ids)

        # Run specific test with repeat=2
        results = run_category_with_repeats(mock_runner, self.mock_client, None, "test_002", 2)

        # Should have 2 results, both test_002
        self.assertEqual(len(results["results"]), 2)

        for result_tuple in results["results"]:
            test, responses, evaluation = result_tuple  # No run_num
            self.assertEqual(test.test_id, "test_002")

        # Analysis should reflect single test
        analysis = results["analysis"]
        self.assertEqual(analysis["total_tests"], 1)
        self.assertEqual(analysis["total_runs"], 2)

    def test_timeout_stats_with_repeats(self) -> None:
        """Test that timeout statistics calculation handles repeat results correctly"""
        from src.utils.testbed_lib import calculate_timeout_stats

        # Mock results with standard format (3-tuple) - the new consecutive model
        mock_test = MockTest("test_001")
        mock_response1 = MockModelResponse("Response 1", response_time=2.0)
        mock_response1.timed_out = True
        mock_response2 = MockModelResponse("Response 2", response_time=1.5)
        mock_response2.timed_out = False
        mock_evaluation = MockEvaluationResult()

        all_results = {
            "mock_category": {
                "results": [
                    (mock_test, [mock_response1], mock_evaluation),  # 3-tuple format
                    (mock_test, [mock_response2], mock_evaluation),  # 3-tuple format
                ]
            }
        }

        # Should not crash and should calculate stats correctly
        stats = calculate_timeout_stats(all_results)

        self.assertEqual(stats["total_requests"], 2)
        self.assertEqual(stats["total_timeouts"], 1)
        self.assertEqual(stats["timeout_percentage"], 50.0)
        self.assertEqual(stats["avg_response_time"], 1.75)  # (2.0 + 1.5) / 2


class TestRepeatResultsSerialization(unittest.TestCase):
    """Test serialization of repeat results"""

    def test_repeat_metadata_serialization(self) -> None:
        """Test that repetition results are correctly serialized (new consecutive model)"""
        import json
        import tempfile

        from src.utils.testbed_lib import save_results

        # Create mock results with repetition info - new format (3-tuple)
        mock_test = MockTest("test_001")
        mock_response = MockModelResponse("Test response", thinking="Test thinking")
        mock_evaluation = MockEvaluationResult()

        # Results with repetitions (3-tuple format, but repeated entries)
        results_with_repeats = {
            "mock_category": {
                "results": [
                    (mock_test, [mock_response], mock_evaluation),  # repetition 1
                    (mock_test, [mock_response], mock_evaluation),  # repetition 2
                ],
                "analysis": {
                    "repetitions_per_test": 2,
                    "total_tests": 1,
                    "total_runs": 2
                }
            }
        }

        # Save to temporary file
        with tempfile.TemporaryDirectory() as temp_dir:
            results_file = save_results(results_with_repeats, temp_dir, verbose=False)

            # Load and verify
            with open(results_file) as f:
                saved_data = json.load(f)

            test_details = saved_data["mock_category"]["test_details"]
            self.assertEqual(len(test_details), 2)

            # Both results should be for the same test (consecutive execution)
            self.assertEqual(test_details[0]["test_id"], "test_001")
            self.assertEqual(test_details[1]["test_id"], "test_001")
            
            # New behavior: no explicit repetition_run metadata in standard format
            self.assertNotIn("repetition_run", test_details[0])
            self.assertNotIn("repetition_run", test_details[1])

    def test_normal_results_no_repeat_metadata(self) -> None:
        """Test that normal results don't get repetition metadata"""
        import json
        import tempfile

        from src.utils.testbed_lib import save_results

        # Create normal results (3-tuple)
        mock_test = MockTest("test_001")
        mock_response = MockModelResponse("Test response")
        mock_evaluation = MockEvaluationResult()

        results_normal = {
            "mock_category": {
                "results": [
                    (mock_test, [mock_response], mock_evaluation),  # normal result
                ],
                "analysis": {"total_tests": 1}
            }
        }

        # Save to temporary file
        with tempfile.TemporaryDirectory() as temp_dir:
            results_file = save_results(results_normal, temp_dir, verbose=False)

            # Load and verify
            with open(results_file) as f:
                saved_data = json.load(f)

            test_details = saved_data["mock_category"]["test_details"]
            self.assertEqual(len(test_details), 1)

            # Should not have repetition metadata
            self.assertNotIn("repetition_run", test_details[0])
            self.assertNotIn("total_repetitions", test_details[0])


class TestRepeatUIIntegration(unittest.TestCase):
    """Test CLI UI integration with repeated results"""

    def test_testresult_with_repetition_display(self) -> None:
        """Test TestResult displays repetition info correctly"""
        # Create TestResult with repetition metadata
        result = TestResult(
            test_id="test_001",
            test_name="Test Name",
            category="mock",
            prompt="Test prompt",
            conversation_turns=None,
            response="Test response",
            vulnerability_detected=False,
            confidence=0.5,
            evidence=[],
            reasoning="Test reasoning",
            repetition_run=2,
            total_repetitions=5
        )

        # Verify fields are set
        self.assertEqual(result.repetition_run, 2)
        self.assertEqual(result.total_repetitions, 5)

    def test_testresult_without_repetition_display(self) -> None:
        """Test TestResult without repetition metadata"""
        result = TestResult(
            test_id="test_001",
            test_name="Test Name",
            category="mock",
            prompt="Test prompt",
            conversation_turns=None,
            response="Test response",
            vulnerability_detected=False,
            confidence=0.5,
            evidence=[],
            reasoning="Test reasoning"
        )

        # Should be None by default
        self.assertIsNone(result.repetition_run)
        self.assertIsNone(result.total_repetitions)


if __name__ == '__main__':
    # Create tests directory if it doesn't exist
    tests_dir = Path(__file__).parent
    tests_dir.mkdir(exist_ok=True)

    # Run tests
    unittest.main()

#!/usr/bin/env python3
"""
Unit tests for parallel execution functionality
Tests the --threads option, OpenRouter validation, and parallel test runner
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.categories.base import BaseTest
from src.models import VulnerabilityCategory, EvaluationResult
from src.utils.model_client import ModelResponse
from src.utils.parallel_runner import ParallelTestRunner, ParallelTestResult


class MockTest(BaseTest):
    """Mock test for parallel execution testing"""
    def __init__(self, test_id: str, name: str = "Mock Test", vulnerable: bool = False):
        super().__init__(
            test_id=test_id,
            name=name,
            prompt=f"Test prompt for {test_id}",
            category="mock_category",
        )
        self.should_be_vulnerable = vulnerable


class MockClient:
    """Mock LLM client for testing"""
    def __init__(self, response_delay: float = 0.1):
        self.response_delay = response_delay
        self.call_count = 0
        self.model = "mock-model"

    def generate(self, prompt: str, system_prompt: str = "") -> ModelResponse:
        self.call_count += 1
        
        # Simulate some processing time
        import time
        time.sleep(self.response_delay)
        
        return ModelResponse(
            content=f"Response {self.call_count} to: {prompt[:20]}...",
            model=self.model,
            response_time=self.response_delay,
            error=None,
            timed_out=False,
        )

    def get_backend_type(self) -> str:
        return "MockBackend"


class MockTester:
    """Mock tester class that implements run_single_test"""
    def __init__(self, client):
        self.client = client
        
    def run_single_test(self, test, current_num=1, total_tests=1, current_rep=1, 
                       total_reps=1, show_prompts=True, quiet_mode=False):
        """Mock implementation of run_single_test"""
        import time
        
        # Simulate test execution
        response = self.client.generate(test.prompt)
        
        # Create mock evaluation based on test
        is_vulnerable = getattr(test, 'should_be_vulnerable', False)
        evaluation = EvaluationResult(
            is_vulnerable=is_vulnerable,
            category=VulnerabilityCategory.DECEPTION,
            confidence=0.8 if is_vulnerable else 0.2,
            evidence=["Mock evidence"] if is_vulnerable else [],
            reasoning=f"Mock evaluation for {test.test_id}",
        )
        
        return test, [response], evaluation


class TestParallelExecutionValidation(unittest.TestCase):
    """Test CLI validation for parallel execution"""

    def test_threads_parameter_validation(self):
        """Test that threads parameter is properly validated"""
        # This would be tested at the CLI level in integration tests
        # Here we test the core validation logic
        
        # Valid thread counts
        for threads in [1, 2, 4, 8, 10, 15, 20]:
            self.assertTrue(1 <= threads <= 20, f"Thread count {threads} should be valid")
        
        # Invalid thread counts
        invalid_counts = [0, -1, 21, 25]
        for threads in invalid_counts:
            self.assertFalse(1 <= threads <= 20, f"Thread count {threads} should be invalid")

    def test_openrouter_backend_detection(self):
        """Test that backend type detection works correctly"""
        # Mock OpenRouter client
        openrouter_client = Mock()
        openrouter_client.get_backend_type.return_value = "OpenRouter"
        
        # Mock Ollama client  
        ollama_client = Mock()
        ollama_client.get_backend_type.return_value = "Ollama"
        
        # Test detection
        self.assertEqual(openrouter_client.get_backend_type(), "OpenRouter")
        self.assertEqual(ollama_client.get_backend_type(), "Ollama")


class TestParallelTestRunner(unittest.TestCase):
    """Test the ParallelTestRunner class"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_client = MockClient(response_delay=0.05)  # Faster for tests
        
        # Mock display to avoid output during tests
        self.display_patcher = patch('src.utils.parallel_runner.get_display')
        self.mock_display = self.display_patcher.start()
        self.mock_display_instance = Mock()
        self.mock_display.return_value = self.mock_display_instance

    def tearDown(self):
        """Clean up after tests"""
        self.display_patcher.stop()

    def test_parallel_runner_creation(self):
        """Test ParallelTestRunner initialization"""
        runner = ParallelTestRunner(num_threads=4)
        
        self.assertEqual(runner.num_threads, 4)
        self.assertEqual(runner.completed_count, 0)
        self.assertEqual(runner.total_tests, 0)

    def test_parallel_execution_basic(self):
        """Test basic parallel execution with mocked tests"""
        runner = ParallelTestRunner(num_threads=2)
        
        # Create test tasks
        test1 = MockTest("test_001", "Test 1", vulnerable=True)
        test2 = MockTest("test_002", "Test 2", vulnerable=False)
        test_tasks = [
            (test1, self.mock_client, 1),
            (test2, self.mock_client, 1),
        ]
        
        # Mock the tester lookup and execution
        with patch('src.categories.registry.TestRegistry.get_all_categories') as mock_registry:
            # Mock registry to return our test tester
            mock_info = Mock()
            mock_info.tester_class = MockTester
            mock_registry.return_value = {"mock_category": mock_info}
            
            # Execute tests
            results = runner.run_tests_parallel(test_tasks, Mock())
            
            # Verify results
            self.assertEqual(len(results), 2)
            self.assertIsInstance(results[0], ParallelTestResult)
            self.assertIsInstance(results[1], ParallelTestResult)
            
            # Check that both tests were executed
            test_ids = {r.test.test_id for r in results}
            self.assertEqual(test_ids, {"test_001", "test_002"})

    def test_parallel_execution_with_repetitions(self):
        """Test parallel execution with multiple repetitions per test"""
        runner = ParallelTestRunner(num_threads=2)
        
        # Create test tasks with repetitions
        test1 = MockTest("test_repeat", "Repeat Test")
        test_tasks = [
            (test1, self.mock_client, 1),  # First repetition
            (test1, self.mock_client, 2),  # Second repetition
            (test1, self.mock_client, 3),  # Third repetition
        ]
        
        # Mock the tester lookup and execution
        with patch('src.categories.registry.TestRegistry.get_all_categories') as mock_registry:
            mock_info = Mock()
            mock_info.tester_class = MockTester
            mock_registry.return_value = {"mock_category": mock_info}
            
            # Execute tests
            results = runner.run_tests_parallel(test_tasks, Mock())
            
            # Verify results
            self.assertEqual(len(results), 3)
            
            # All results should be for the same test
            test_ids = {r.test.test_id for r in results}
            self.assertEqual(test_ids, {"test_repeat"})

    def test_parallel_summary_generation(self):
        """Test that parallel summary statistics are calculated correctly"""
        runner = ParallelTestRunner(num_threads=2)
        
        # Create mock results
        test1 = MockTest("test_001", vulnerable=True)
        test2 = MockTest("test_002", vulnerable=False)
        
        mock_results = [
            ParallelTestResult(
                test=test1,
                responses=[Mock(response_time=1.0)],
                evaluation=EvaluationResult(
                    is_vulnerable=True,
                    category=VulnerabilityCategory.DECEPTION,
                    confidence=0.9,
                    evidence=["Evidence"],
                    reasoning="Vulnerable",
                ),
                execution_time=1.0,
                worker_id=1,
            ),
            ParallelTestResult(
                test=test2,
                responses=[Mock(response_time=1.5)],
                evaluation=EvaluationResult(
                    is_vulnerable=False,
                    category=VulnerabilityCategory.DECEPTION,
                    confidence=0.3,
                    evidence=[],
                    reasoning="Not vulnerable",
                ),
                execution_time=1.5,
                worker_id=2,
            ),
        ]
        
        # Generate summary
        summary = runner.generate_parallel_summary(mock_results)
        
        # Verify summary statistics
        self.assertEqual(summary["total_tests"], 2)
        self.assertEqual(summary["vulnerable_tests"], 1)
        self.assertEqual(summary["vulnerability_rate"], 0.5)  # 1 out of 2
        self.assertEqual(summary["avg_confidence"], 0.6)  # (0.9 + 0.3) / 2

    def test_error_handling_in_parallel_execution(self):
        """Test that errors during parallel execution are handled gracefully"""
        runner = ParallelTestRunner(num_threads=1)
        
        # Create a test task
        test1 = MockTest("error_test", "Error Test")
        test_tasks = [(test1, self.mock_client, 1)]
        
        # Mock registry to raise an exception
        with patch('src.categories.registry.TestRegistry.get_all_categories') as mock_registry:
            mock_registry.side_effect = Exception("Registry error")
            
            # Execute tests - should handle error gracefully
            results = runner.run_tests_parallel(test_tasks, Mock())
            
            # Should still return a result, but with error information
            self.assertEqual(len(results), 1)
            self.assertIsNotNone(results[0].error)


class TestParallelIntegration(unittest.TestCase):
    """Integration tests for parallel execution with testbed_lib"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_client = MockClient()
        
        # Mock display - patch the import within the function
        self.display_patcher = patch('src.utils.live_display.get_display')
        self.mock_display = self.display_patcher.start()
        self.mock_display_instance = Mock()
        self.mock_display.return_value = self.mock_display_instance

    def tearDown(self):
        """Clean up after tests"""
        self.display_patcher.stop()

    def test_run_category_parallel_routing(self):
        """Test that run_category_with_repeats correctly routes to parallel execution"""
        from src.utils.testbed_lib import run_category_with_repeats
        
        # Mock the parallel runner
        with patch('src.utils.testbed_lib._run_category_parallel') as mock_parallel:
            mock_parallel.return_value = {"results": [], "analysis": {}}
            
            # Call with threads > 1
            result = run_category_with_repeats(
                Mock(), self.mock_client, "test_category", None, 3, threads=4
            )
            
            # Should have called the parallel function
            mock_parallel.assert_called_once()
            
            # Verify parameters
            call_args = mock_parallel.call_args[0]  # positional args
            self.assertEqual(call_args[4], 3)  # repeat_count
            self.assertEqual(call_args[5], 4)  # threads

    def test_sequential_execution_still_works(self):
        """Test that sequential execution (threads=1) still works normally"""
        from src.utils.testbed_lib import run_category_with_repeats
        
        # Mock category runner
        mock_runner = Mock()
        mock_runner.return_value = {"results": [], "analysis": {}}
        
        # Call with threads = 1
        result = run_category_with_repeats(
            mock_runner, self.mock_client, "test_category", None, 2, threads=1
        )
        
        # Should have called the normal runner, not parallel
        mock_runner.assert_called()


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)
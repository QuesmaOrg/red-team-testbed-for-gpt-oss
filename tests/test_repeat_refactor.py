#!/usr/bin/env python3
"""
Comprehensive unit tests for the refactored repeat functionality
Tests the new consecutive execution model with mocks
"""
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.categories.base import BaseTest, BaseTester
from src.models import VulnerabilityCategory, EvaluationResult
from src.utils.model_client import ModelResponse


class MockTest(BaseTest):
    """Mock test for testing"""
    def __init__(self, test_id: str, name: str = "Mock Test", multi_turn: bool = False):
        super().__init__(
            test_id=test_id,
            name=name,
            prompt=f"Test prompt for {test_id}",
            category="mock",
        )
        if multi_turn:
            self.follow_up_prompts = ["Follow up 1", "Follow up 2"]


class MockClient:
    """Mock client that generates unique responses per call"""
    def __init__(self):
        self.call_count = 0
        self.model = "mock-model"

    def generate(self, prompt: str, system_prompt: str = "") -> ModelResponse:
        self.call_count += 1
        return ModelResponse(
            content=f"Response {self.call_count} to: {prompt[:20]}...",
            model=self.model,
            response_time=1.5,
            error=None,
            timed_out=False,
            thinking=f"Thinking {self.call_count}",
        )


class MockTester(BaseTester):
    """Mock tester implementation for testing"""
    def __init__(self, client, test_cases=None):
        self.client = client
        self.evaluator = Mock()
        if test_cases:
            self.test_cases = test_cases
        else:
            self.test_cases = [
                MockTest("test_001", "Single Turn Test"),
                MockTest("test_002", "Multi Turn Test", multi_turn=True),
                MockTest("test_003", "Another Single Turn"),
            ]

    def _initialize_test_cases(self):
        return self.test_cases

    def get_category_name(self) -> str:
        return "mock_category"

    def get_vulnerability_category(self) -> VulnerabilityCategory:
        return VulnerabilityCategory.DECEPTION

    def _evaluate_single_response(self, test: BaseTest, response: ModelResponse) -> EvaluationResult:
        # Simulate variable vulnerability detection
        is_vulnerable = "vulnerable" in response.content.lower() or self.client.call_count % 3 == 0
        confidence = 0.8 if is_vulnerable else 0.2
        
        return EvaluationResult(
            is_vulnerable=is_vulnerable,
            category=self.get_vulnerability_category(),
            confidence=confidence,
            evidence=["Mock evidence"] if is_vulnerable else [],
            reasoning=f"Mock evaluation for call {self.client.call_count}",
        )


class TestRepeatRefactor(unittest.TestCase):
    """Test the refactored repeat functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_client = MockClient()
        
        # Mock display to capture calls - patch both locations
        self.display_patcher1 = patch('src.utils.live_display.get_display')
        self.display_patcher2 = patch('src.categories.base.get_display')
        
        self.mock_display1 = self.display_patcher1.start()
        self.mock_display2 = self.display_patcher2.start()
        
        self.mock_display_instance = Mock()
        self.mock_display1.return_value = self.mock_display_instance
        self.mock_display2.return_value = self.mock_display_instance
        
        self.mock_tester = MockTester(self.mock_client)

    def tearDown(self):
        """Clean up after tests"""
        self.display_patcher1.stop()
        self.display_patcher2.stop()

    def test_single_test_multiple_repetitions_consecutive(self):
        """Test that a single test runs N times consecutively"""
        test = MockTest("consecutive_test", "Consecutive Test")
        
        # Run test with 3 repetitions
        results = self.mock_tester.run_test_with_repeats(test, 3, current_num=1, total_tests=1)
        
        # Should have 3 results
        self.assertEqual(len(results), 3)
        
        # All results should be for the same test
        for result in results:
            test_obj, responses, evaluation = result
            self.assertEqual(test_obj.test_id, "consecutive_test")
            self.assertGreater(len(responses), 0)

        # Client should have been called 3 times (once per repetition)
        self.assertEqual(self.mock_client.call_count, 3)

    def test_multi_turn_test_repetitions(self):
        """Test multi-turn conversations with repetitions"""
        test = MockTest("multi_turn_test", "Multi Turn Test", multi_turn=True)
        
        # Run test with 2 repetitions
        results = self.mock_tester.run_test_with_repeats(test, 2, current_num=1, total_tests=1)
        
        # Should have 2 results
        self.assertEqual(len(results), 2)
        
        # Each result should have 3 responses (initial + 2 follow-ups)
        for result in results:
            test_obj, responses, evaluation = result
            self.assertEqual(len(responses), 3)  # Main prompt + 2 follow-ups

        # Client should have been called 6 times (3 turns × 2 repetitions)
        self.assertEqual(self.mock_client.call_count, 6)

    def test_display_methods_called_correctly(self):
        """Test that display methods are called with correct parameters"""
        test = MockTest("display_test", "Display Test")
        
        # Run test with 2 repetitions
        self.mock_tester.run_test_with_repeats(test, 2, current_num=1, total_tests=1)
        
        # Verify display methods were called
        display_calls = self.mock_display_instance.method_calls
        call_names = [call[0] for call in display_calls]
        
        # Should show repetition headers
        self.assertIn('show_repetition_header', call_names)
        
        # Should show vulnerability summary
        self.assertIn('show_vulnerability_summary', call_names)
        
        # Check repetition header calls
        rep_header_calls = [call for call in display_calls if call[0] == 'show_repetition_header']
        self.assertEqual(len(rep_header_calls), 2)  # 2 repetitions
        
        # Verify parameters of repetition calls
        self.assertEqual(rep_header_calls[0][1], (1, 2))  # (current_rep=1, total_reps=2)
        self.assertEqual(rep_header_calls[1][1], (2, 2))  # (current_rep=2, total_reps=2)

    def test_prompt_display_control_single_turn(self):
        """Test that prompts are shown only once for single-turn tests"""
        test = MockTest("prompt_test", "Prompt Display Test")
        
        with patch.object(self.mock_tester, 'run_single_test', wraps=self.mock_tester.run_single_test) as mock_run_single:
            self.mock_tester.run_test_with_repeats(test, 3, current_num=1, total_tests=1)
            
            # Verify run_single_test was called 3 times
            self.assertEqual(mock_run_single.call_count, 3)
            
            # Check parameters of each call
            calls = mock_run_single.call_args_list
            
            # First call should show prompts
            first_call_kwargs = calls[0][1]
            self.assertEqual(first_call_kwargs['current_rep'], 1)
            self.assertEqual(first_call_kwargs['total_reps'], 3)
            self.assertTrue(first_call_kwargs['show_prompts'])
            
            # Subsequent calls should have show_prompts=True but display logic handles it
            for i, call in enumerate(calls[1:], 2):
                kwargs = call[1]
                self.assertEqual(kwargs['current_rep'], i)
                self.assertEqual(kwargs['total_reps'], 3)
                self.assertTrue(kwargs['show_prompts'])

    def test_multi_turn_prompt_display_control(self):
        """Test that multi-turn prompts are shown all at once on first repetition"""
        test = MockTest("multi_prompt_test", "Multi Turn Prompt Test", multi_turn=True)
        
        # Run test with 2 repetitions
        self.mock_tester.run_test_with_repeats(test, 2, current_num=1, total_tests=1)
        
        # Check if show_multi_turn_prompts was called
        display_calls = self.mock_display_instance.method_calls
        multi_turn_calls = [call for call in display_calls if call[0] == 'show_multi_turn_prompts']
        
        # Should be called once (only on first repetition)
        self.assertEqual(len(multi_turn_calls), 1)
        
        # Verify the prompts passed to the method
        called_prompts = multi_turn_calls[0][1][0]  # First argument
        expected_prompts = ["Test prompt for multi_prompt_test", "Follow up 1", "Follow up 2"]
        self.assertEqual(called_prompts, expected_prompts)

    def test_vulnerability_summary_display(self):
        """Test that vulnerability summaries are calculated and displayed correctly"""
        test = MockTest("summary_test", "Summary Test")
        
        # Run test with 5 repetitions to get varied results
        self.mock_tester.run_test_with_repeats(test, 5, current_num=1, total_tests=1)
        
        # Check vulnerability summary was called
        display_calls = self.mock_display_instance.method_calls
        summary_calls = [call for call in display_calls if call[0] == 'show_vulnerability_summary']
        
        # Should be called once after all repetitions
        self.assertEqual(len(summary_calls), 1)
        
        # Verify parameters
        test_id, repetition_data = summary_calls[0][1]
        self.assertEqual(test_id, "summary_test")
        self.assertEqual(len(repetition_data), 5)
        
        # Each repetition should have required fields
        for rep_data in repetition_data:
            self.assertIn('is_vulnerable', rep_data)
            self.assertIn('confidence', rep_data)
            self.assertIn('response_time', rep_data)

    def test_category_tests_with_repetitions(self):
        """Test full category execution with repetitions"""
        # Use a smaller test set for this test
        small_test_cases = [
            MockTest("cat_001", "Category Test 1"),
            MockTest("cat_002", "Category Test 2"),
        ]
        tester = MockTester(MockClient(), test_cases=small_test_cases)
        
        # Mock the display
        with patch('src.utils.live_display.get_display') as mock_display:
            mock_display_instance = Mock()
            mock_display.return_value = mock_display_instance
            
            # Run category with repetitions
            results = tester.run_category_tests(repeat_count=3)
            
            # Should have 6 results total (2 tests × 3 repetitions)
            self.assertEqual(len(results), 6)
            
            # Group by test_id to verify
            test_groups = {}
            for result in results:
                test_obj = result[0]
                test_id = test_obj.test_id
                if test_id not in test_groups:
                    test_groups[test_id] = []
                test_groups[test_id].append(result)
            
            # Should have 2 test groups
            self.assertEqual(len(test_groups), 2)
            
            # Each group should have 3 results
            for test_id, group_results in test_groups.items():
                self.assertEqual(len(group_results), 3)

    def test_single_repetition_backward_compatibility(self):
        """Test that repeat_count=1 behaves like the original implementation"""
        # Run with repeat_count=1
        results = self.mock_tester.run_category_tests(repeat_count=1)
        
        # Should have same number of results as test cases
        self.assertEqual(len(results), len(self.mock_tester.test_cases))
        
        # Repetition headers may be called, but with total_reps=1 which should result in no display
        display_calls = self.mock_display_instance.method_calls
        rep_header_calls = [call for call in display_calls if call[0] == 'show_repetition_header']
        
        # If called, all calls should have total_reps=1, which means no actual display
        for call in rep_header_calls:
            args = call[1]  # Get the arguments (current_rep, total_reps)
            self.assertEqual(args[1], 1)  # total_reps should be 1

    def test_specific_test_id_with_repetitions(self):
        """Test running a specific test ID with repetitions"""
        results = self.mock_tester.run_category_tests(test_id="test_002", repeat_count=4)
        
        # Should have 4 results (all for test_002)
        self.assertEqual(len(results), 4)
        
        # All results should be for the same test
        for result in results:
            test_obj = result[0]
            self.assertEqual(test_obj.test_id, "test_002")

    def test_error_handling_in_repetitions(self):
        """Test error handling during repetitions"""
        # Create a client that fails on the second call
        error_client = Mock()
        error_client.model = "error-model"
        def error_generator(prompt, system_prompt=""):
            call_count = getattr(error_generator, 'call_count', 0)
            error_generator.call_count = call_count + 1
            
            if call_count == 0:
                return ModelResponse(content="Good response", model="error-model", response_time=1.0)
            elif call_count == 1:
                return ModelResponse(content="", model="error-model", response_time=0.0, error="Test error")
            else:
                return ModelResponse(content="Recovery response", model="error-model", response_time=1.0)
                
        error_client.generate = error_generator
        
        error_tester = MockTester(error_client, test_cases=[MockTest("error_test", "Error Test")])
        
        with patch('src.utils.live_display.get_display') as mock_display:
            mock_display.return_value = Mock()
            
            # Run test with 3 repetitions - one will fail
            results = error_tester.run_test_with_repeats(
                MockTest("error_test", "Error Test"), 3, current_num=1, total_tests=1
            )
            
            # Should still have 3 results
            self.assertEqual(len(results), 3)
            
            # Check that error was handled gracefully
            error_result = results[1]  # Second result should be the error
            test_obj, responses, evaluation = error_result
            self.assertIn("Test error", evaluation.reasoning)

    def test_timing_and_performance_data(self):
        """Test that timing data is correctly captured and summarized"""
        test = MockTest("timing_test", "Timing Test")
        
        # Mock responses with different timing
        self.mock_client.generate = Mock(side_effect=[
            ModelResponse(content="Response 1", model="mock-model", response_time=1.0),
            ModelResponse(content="Response 2", model="mock-model", response_time=2.0),
            ModelResponse(content="Response 3", model="mock-model", response_time=1.5),
        ])
        
        # Run test with 3 repetitions
        self.mock_tester.run_test_with_repeats(test, 3, current_num=1, total_tests=1)
        
        # Verify vulnerability summary was called with timing data
        display_calls = self.mock_display_instance.method_calls
        summary_calls = [call for call in display_calls if call[0] == 'show_vulnerability_summary']
        
        self.assertEqual(len(summary_calls), 1)
        
        test_id, repetition_data = summary_calls[0][1]
        response_times = [rep['response_time'] for rep in repetition_data]
        
        # Should match our mock response times
        self.assertEqual(response_times, [1.0, 2.0, 1.5])


class TestRunCategoryWithRepeatsRefactor(unittest.TestCase):
    """Test the refactored run_category_with_repeats function"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_client = MockClient()
        
        # Mock display - use the correct import location for testbed_lib
        # It imports get_display locally within the function
        pass

    def tearDown(self):
        """Clean up after tests"""
        pass

    def test_consecutive_execution_model(self):
        """Test that the new consecutive execution model works correctly"""
        from src.utils.testbed_lib import run_category_with_repeats
        
        # Mock the display that's imported inside the function
        with patch('src.utils.live_display.get_display') as mock_display:
            mock_display.return_value = Mock()
            
            # Create mock category runner
            def mock_category_runner(client, category, test_id, repeat_count):
                # Simulate the new behavior: returns all repetitions for each test consecutively
                if repeat_count == 1:
                    return {
                        "results": [
                            (MockTest("test_001"), [ModelResponse(content="Response", model="model", response_time=1.0)], 
                             EvaluationResult(is_vulnerable=False, category=VulnerabilityCategory.DECEPTION, confidence=0.5, evidence=[], reasoning="Normal"))
                        ],
                        "analysis": {"total_tests": 1}
                    }
                else:
                    # Simulate consecutive repetitions
                    results = []
                    for i in range(repeat_count):
                        results.append(
                            (MockTest("test_001"), [ModelResponse(content=f"Response {i+1}", model="model", response_time=1.0)], 
                             EvaluationResult(is_vulnerable=i % 2 == 0, category=VulnerabilityCategory.DECEPTION, confidence=0.5 + i*0.1, evidence=[], reasoning=f"Rep {i+1}"))
                        )
                    return {
                        "results": results,
                        "analysis": {"total_tests": 1}
                    }
            
            # Test with repeat_count=1
            result = run_category_with_repeats(mock_category_runner, self.mock_client, None, None, 1)
            self.assertEqual(len(result["results"]), 1)
            
            # Test with repeat_count=3
            result = run_category_with_repeats(mock_category_runner, self.mock_client, None, None, 3)
            self.assertEqual(len(result["results"]), 3)
            self.assertEqual(result["analysis"]["total_tests"], 1)
            self.assertEqual(result["analysis"]["total_runs"], 3)
            self.assertEqual(result["analysis"]["repetitions_per_test"], 3)

    def test_vulnerability_rate_calculation(self):
        """Test that vulnerability rates are calculated correctly"""
        from src.utils.testbed_lib import run_category_with_repeats
        
        # Mock the display that's imported inside the function
        with patch('src.utils.live_display.get_display') as mock_display:
            mock_display.return_value = Mock()
            
            def mock_category_runner(client, category, test_id, repeat_count):
                # Create results where 2 out of 5 repetitions are vulnerable
                results = []
                for i in range(repeat_count):
                    is_vuln = i in [1, 3]  # 2nd and 4th repetitions are vulnerable
                    results.append(
                        (MockTest("test_001"), [ModelResponse(content=f"Response {i+1}", model="model", response_time=1.0)], 
                         EvaluationResult(is_vulnerable=is_vuln, category=VulnerabilityCategory.DECEPTION, confidence=0.8 if is_vuln else 0.2, evidence=[], reasoning=f"Rep {i+1}"))
                    )
                return {
                    "results": results,
                    "analysis": {"total_tests": 1}
                }
            
            result = run_category_with_repeats(mock_category_runner, self.mock_client, None, None, 5)
            
            # Check analysis
            analysis = result["analysis"]
            self.assertEqual(analysis["vulnerable_runs"], 2)
            self.assertEqual(analysis["vulnerability_rate"], 0.4)  # 2/5 = 40%


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)
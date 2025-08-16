"""
Unit tests for the save_results function to ensure compatibility
with both single-turn and multi-turn test objects.
"""
import json
import tempfile
import os
from pathlib import Path
from dataclasses import dataclass
from typing import List

# Import the modules we're testing
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.testbed_lib import save_results
from src.utils.evaluator import EvaluationResult, VulnerabilityCategory
from src.utils.model_client import ModelResponse


# Mock test classes for testing
@dataclass
class MockDeceptionTest:
    """Mock single-turn test (like DeceptionTest)"""
    test_id: str
    name: str
    prompt: str
    category: str = "deception"
    system_prompt: str = ""


@dataclass 
class MockAdderallDeceptionTest:
    """Mock multi-turn test (like AdderallDeceptionTest)"""
    test_id: str
    name: str
    conversation_turns: List[str]
    category: str = "deception_adderall"
    system_prompt: str = ""


def test_save_results_single_turn():
    """Test save_results with traditional single-turn tests"""
    print("🧪 Testing save_results with single-turn tests...")
    
    # Create mock single-turn test
    test = MockDeceptionTest(
        test_id="test_001",
        name="Test Single Turn",
        prompt="Test prompt",
        category="deception"
    )
    
    # Create mock response and evaluation
    response = MockResponse("Test response")
    evaluation = MockEvaluation(False, 0.5)
    
    # Create test results
    test_results = {
        "deception": {
            "results": [(test, [response], evaluation)],
            "analysis": {"total_tests": 1}
        }
    }
    
    # Test saving results
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            save_results(test_results, temp_dir, verbose=False)
            
            # Check if file was created
            result_files = list(Path(temp_dir).glob("test_results_*.json"))
            assert len(result_files) == 1, "Should create one results file"
            
            # Load and verify content
            with open(result_files[0], 'r') as f:
                saved_data = json.load(f)
            
            assert "deception" in saved_data, "Should contain deception category"
            test_details = saved_data["deception"]["test_details"]
            assert len(test_details) == 1, "Should contain one test"
            
            test_detail = test_details[0]
            assert test_detail["test_id"] == "test_001", "Should save test_id correctly"
            assert test_detail["prompt"] == "Test prompt", "Should save prompt correctly"
            assert test_detail["conversation_turns"] is None, "Should handle missing conversation_turns"
            
            print("✅ Single-turn test passed")
            return True
            
        except Exception as e:
            print(f"❌ Single-turn test failed: {e}")
            return False


def test_save_results_multi_turn():
    """Test save_results with multi-turn AdderallDeceptionTest"""
    print("🧪 Testing save_results with multi-turn tests...")
    
    # Create mock multi-turn test
    test = MockAdderallDeceptionTest(
        test_id="adderall_001", 
        name="Test Multi Turn",
        conversation_turns=["Turn 1", "Turn 2", "Turn 3"],
        category="deception_adderall"
    )
    
    # Create mock response and evaluation
    response = MockResponse("Multi-turn response")
    evaluation = MockEvaluation(True, 0.8)
    
    # Create test results
    test_results = {
        "deception_adderall": {
            "results": [(test, [response], evaluation)],
            "analysis": {"total_tests": 1}
        }
    }
    
    # Test saving results
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            save_results(test_results, temp_dir, verbose=False)
            
            # Check if file was created
            result_files = list(Path(temp_dir).glob("test_results_*.json"))
            assert len(result_files) == 1, "Should create one results file"
            
            # Load and verify content
            with open(result_files[0], 'r') as f:
                saved_data = json.load(f)
            
            assert "deception_adderall" in saved_data, "Should contain deception_adderall category"
            test_details = saved_data["deception_adderall"]["test_details"]
            assert len(test_details) == 1, "Should contain one test"
            
            test_detail = test_details[0]
            assert test_detail["test_id"] == "adderall_001", "Should save test_id correctly"
            assert test_detail["prompt"] is None, "Should handle missing prompt attribute"
            assert test_detail["conversation_turns"] == ["Turn 1", "Turn 2", "Turn 3"], "Should save conversation_turns correctly"
            
            print("✅ Multi-turn test passed")
            return True
            
        except Exception as e:
            print(f"❌ Multi-turn test failed: {e}")
            return False


def test_save_results_mixed_types():
    """Test save_results with both single and multi-turn tests"""
    print("🧪 Testing save_results with mixed test types...")
    
    # Create mock tests of both types
    single_test = MockDeceptionTest(
        test_id="single_001",
        name="Single Test", 
        prompt="Single prompt"
    )
    
    multi_test = MockAdderallDeceptionTest(
        test_id="multi_001",
        name="Multi Test",
        conversation_turns=["Turn A", "Turn B"]
    )
    
    # Create mock responses and evaluations
    response1 = MockResponse("Single response")
    response2 = MockResponse("Multi response")
    eval1 = MockEvaluation(False, 0.3)
    eval2 = MockEvaluation(True, 0.7)
    
    # Create mixed test results
    test_results = {
        "deception": {
            "results": [(single_test, [response1], eval1)],
            "analysis": {"total_tests": 1}
        },
        "deception_adderall": {
            "results": [(multi_test, [response2], eval2)],
            "analysis": {"total_tests": 1}
        }
    }
    
    # Test saving results
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            save_results(test_results, temp_dir, verbose=False)
            
            # Load and verify content
            result_files = list(Path(temp_dir).glob("test_results_*.json"))
            with open(result_files[0], 'r') as f:
                saved_data = json.load(f)
            
            # Verify both categories are present
            assert "deception" in saved_data, "Should contain deception category"
            assert "deception_adderall" in saved_data, "Should contain deception_adderall category"
            
            # Check single-turn test
            single_detail = saved_data["deception"]["test_details"][0]
            assert single_detail["prompt"] == "Single prompt"
            assert single_detail["conversation_turns"] is None
            
            # Check multi-turn test  
            multi_detail = saved_data["deception_adderall"]["test_details"][0]
            assert multi_detail["prompt"] is None
            assert multi_detail["conversation_turns"] == ["Turn A", "Turn B"]
            
            print("✅ Mixed types test passed")
            return True
            
        except Exception as e:
            print(f"❌ Mixed types test failed: {e}")
            return False


def test_save_results_missing_attributes():
    """Test save_results handles missing attributes gracefully"""
    print("🧪 Testing save_results with missing attributes...")
    
    # Create test with minimal attributes
    @dataclass
    class MinimalTest:
        test_id: str
        name: str
        category: str
    
    test = MinimalTest(
        test_id="minimal_001",
        name="Minimal Test",
        category="test"
    )
    
    response = MockResponse("Minimal response")
    evaluation = MockEvaluation(False, 0.1)
    
    test_results = {
        "test": {
            "results": [(test, [response], evaluation)],
            "analysis": {"total_tests": 1}
        }
    }
    
    # Test saving results
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            save_results(test_results, temp_dir, verbose=False)
            
            # Load and verify content
            result_files = list(Path(temp_dir).glob("test_results_*.json"))
            with open(result_files[0], 'r') as f:
                saved_data = json.load(f)
            
            test_detail = saved_data["test"]["test_details"][0]
            assert test_detail["test_id"] == "minimal_001"
            assert test_detail["prompt"] is None  # Missing attribute handled gracefully
            assert test_detail["conversation_turns"] is None  # Missing attribute handled gracefully
            assert test_detail["system_prompt"] == ""  # Default value used
            
            print("✅ Missing attributes test passed")
            return True
            
        except Exception as e:
            print(f"❌ Missing attributes test failed: {e}")
            return False


# Mock classes for testing
class MockResponse:
    def __init__(self, content):
        self.content = content
        self.response_time = 1.0
        self.timed_out = False
        self.error = None


class MockEvaluation:
    def __init__(self, is_vulnerable, confidence):
        self.is_vulnerable = is_vulnerable
        self.confidence = confidence
        self.evidence = ["Test evidence"]
        self.reasoning = "Test reasoning"


def run_all_tests():
    """Run all tests and report results"""
    print("🚀 Running save_results compatibility tests...")
    print("=" * 60)
    
    tests = [
        test_save_results_single_turn,
        test_save_results_multi_turn,
        test_save_results_mixed_types,
        test_save_results_missing_attributes
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test_func.__name__} crashed: {e}")
            failed += 1
        print()
    
    print("=" * 60)
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! save_results function is working correctly.")
        return True
    else:
        print("⚠️  Some tests failed. Check the save_results function.")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
#!/usr/bin/env python3
"""
Unit tests for flagging persistence functionality in CLI UI
Tests that flagged status persists across CLI restarts
"""
import unittest
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
import sys
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from ui.cli_ui import CLIEvaluator, TestResult


class TestFlaggingPersistence(unittest.TestCase):
    """Test suite for flagging persistence functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
        self.temp_file = os.path.join(self.temp_dir, "test_results.json")
        
        # Mock console to avoid Rich output during tests
        self.console_patcher = patch('ui.cli_ui.RICH_AVAILABLE', False)
        self.console_patcher.start()
        
    def tearDown(self):
        """Clean up after tests"""
        self.console_patcher.stop()
        # Clean up temp files
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def create_sample_results_file(self, include_repetitions=False):
        """Create a sample results JSON file for testing"""
        if include_repetitions:
            # Sample data with repetitions
            sample_data = {
                "deception_samples": {
                    "analysis": {
                        "total_tests": 2,
                        "total_runs": 4,
                        "repetitions_per_test": 2
                    },
                    "test_details": [
                        {
                            "test_id": "test_001",
                            "test_name": "Test 001",
                            "category": "deception_samples",
                            "prompt": "Test prompt 1",
                            "response_content": "Test response 1",
                            "vulnerability_detected": True,
                            "confidence": 0.8,
                            "evidence": ["Evidence 1"],
                            "reasoning": "Test reasoning 1",
                            "flagged": False,
                            "notes": None,
                            "repetition_run": 1,
                            "total_repetitions": 2
                        },
                        {
                            "test_id": "test_001",
                            "test_name": "Test 001",
                            "category": "deception_samples",
                            "prompt": "Test prompt 1",
                            "response_content": "Test response 1 (run 2)",
                            "vulnerability_detected": False,
                            "confidence": 0.3,
                            "evidence": [],
                            "reasoning": "Test reasoning 1 (run 2)",
                            "flagged": False,
                            "notes": None,
                            "repetition_run": 2,
                            "total_repetitions": 2
                        },
                        {
                            "test_id": "test_002",
                            "test_name": "Test 002",
                            "category": "deception_samples",
                            "prompt": "Test prompt 2",
                            "response_content": "Test response 2",
                            "vulnerability_detected": True,
                            "confidence": 0.9,
                            "evidence": ["Evidence 2"],
                            "reasoning": "Test reasoning 2",
                            "flagged": False,
                            "notes": None,
                            "repetition_run": 1,
                            "total_repetitions": 2
                        },
                        {
                            "test_id": "test_002",
                            "test_name": "Test 002",
                            "category": "deception_samples",
                            "prompt": "Test prompt 2",
                            "response_content": "Test response 2 (run 2)",
                            "vulnerability_detected": True,
                            "confidence": 0.7,
                            "evidence": ["Evidence 2b"],
                            "reasoning": "Test reasoning 2 (run 2)",
                            "flagged": False,
                            "notes": None,
                            "repetition_run": 2,
                            "total_repetitions": 2
                        }
                    ]
                }
            }
        else:
            # Simple sample data without repetitions
            sample_data = {
                "deception_samples": {
                    "analysis": {"total_tests": 2},
                    "test_details": [
                        {
                            "test_id": "test_001",
                            "test_name": "Test 001",
                            "category": "deception_samples",
                            "prompt": "Test prompt 1",
                            "response_content": "Test response 1",
                            "vulnerability_detected": True,
                            "confidence": 0.8,
                            "evidence": ["Evidence 1"],
                            "reasoning": "Test reasoning 1",
                            "flagged": False,
                            "notes": None
                        },
                        {
                            "test_id": "test_002",
                            "test_name": "Test 002",
                            "category": "deception_samples",
                            "prompt": "Test prompt 2",
                            "response_content": "Test response 2",
                            "vulnerability_detected": True,
                            "confidence": 0.9,
                            "evidence": ["Evidence 2"],
                            "reasoning": "Test reasoning 2",
                            "flagged": False,
                            "notes": None
                        }
                    ]
                }
            }
        
        with open(self.temp_file, 'w') as f:
            json.dump(sample_data, f, indent=2)
        
        return sample_data
    
    def test_basic_flag_persistence(self):
        """Test that basic flagging persists across CLI restarts"""
        # Create sample results file
        self.create_sample_results_file()
        
        # Load evaluator and flag first test
        evaluator = CLIEvaluator(self.temp_file)
        
        # Verify initial state
        self.assertFalse(evaluator.test_results[0].flagged)
        self.assertFalse(evaluator.test_results[1].flagged)
        
        # Flag first test
        evaluator.test_results[0].flagged = True
        evaluator._save_updated_results()
        
        # Create new evaluator (simulating restart)
        evaluator2 = CLIEvaluator(self.temp_file)
        
        # Verify flag persisted
        self.assertTrue(evaluator2.test_results[0].flagged)
        self.assertFalse(evaluator2.test_results[1].flagged)
    
    def test_basic_unflag_persistence(self):
        """Test that unflagging persists across CLI restarts"""
        # Create sample results file with flagged item
        sample_data = self.create_sample_results_file()
        sample_data["deception_samples"]["test_details"][0]["flagged"] = True
        with open(self.temp_file, 'w') as f:
            json.dump(sample_data, f, indent=2)
        
        # Load evaluator
        evaluator = CLIEvaluator(self.temp_file)
        
        # Verify initial flagged state
        self.assertTrue(evaluator.test_results[0].flagged)
        
        # Unflag the test
        evaluator.test_results[0].flagged = False
        evaluator._save_updated_results()
        
        # Create new evaluator (simulating restart)
        evaluator2 = CLIEvaluator(self.temp_file)
        
        # Verify unflag persisted
        self.assertFalse(evaluator2.test_results[0].flagged)
    
    def test_notes_persistence(self):
        """Test that notes persist across CLI restarts"""
        # Create sample results file
        self.create_sample_results_file()
        
        # Load evaluator and add notes
        evaluator = CLIEvaluator(self.temp_file)
        evaluator.test_results[0].notes = "This is a test note"
        evaluator._save_updated_results()
        
        # Create new evaluator (simulating restart)
        evaluator2 = CLIEvaluator(self.temp_file)
        
        # Verify notes persisted
        self.assertEqual(evaluator2.test_results[0].notes, "This is a test note")
        self.assertIsNone(evaluator2.test_results[1].notes)
    
    def test_repeated_tests_flagging_issue(self):
        """Test flagging with repeated tests - this should expose the current bug"""
        # Create sample results file with repetitions
        self.create_sample_results_file(include_repetitions=True)
        
        # Load evaluator
        evaluator = CLIEvaluator(self.temp_file)
        
        # Should have 4 test results (2 tests × 2 repetitions)
        self.assertEqual(len(evaluator.test_results), 4)
        
        # Verify initial state - all unflagged
        for result in evaluator.test_results:
            self.assertFalse(result.flagged)
        
        # Flag specific repetition (test_001, run 2)
        # Find the second instance of test_001 (repetition_run = 2)
        target_result = None
        for result in evaluator.test_results:
            if result.test_id == "test_001" and result.repetition_run == 2:
                target_result = result
                break
        
        self.assertIsNotNone(target_result)
        target_result.flagged = True
        evaluator._save_updated_results()
        
        # Create new evaluator (simulating restart)
        evaluator2 = CLIEvaluator(self.temp_file)
        
        # Check which results are flagged
        flagged_results = [r for r in evaluator2.test_results if r.flagged]
        unflagged_results = [r for r in evaluator2.test_results if not r.flagged]
        
        # This test will likely fail with current implementation
        # because the matching logic doesn't handle repetitions correctly
        print(f"Flagged results: {len(flagged_results)}")
        print(f"Unflagged results: {len(unflagged_results)}")
        
        for result in evaluator2.test_results:
            print(f"Test: {result.test_id}, Run: {result.repetition_run}, Flagged: {result.flagged}")
        
        # What we expect: only test_001 run 2 should be flagged
        expected_flagged = [r for r in evaluator2.test_results 
                           if r.test_id == "test_001" and r.repetition_run == 2]
        self.assertEqual(len(expected_flagged), 1, 
                        "Expected exactly one result flagged (test_001 run 2)")
        self.assertTrue(expected_flagged[0].flagged, 
                       "Expected test_001 run 2 to be flagged")
        
        # All others should be unflagged
        other_results = [r for r in evaluator2.test_results 
                        if not (r.test_id == "test_001" and r.repetition_run == 2)]
        for result in other_results:
            self.assertFalse(result.flagged, 
                            f"Expected {result.test_id} run {result.repetition_run} to be unflagged")
    
    def test_multi_category_flagging(self):
        """Test flagging across different categories"""
        # Create multi-category sample data
        sample_data = {
            "deception_samples": {
                "analysis": {"total_tests": 1},
                "test_details": [
                    {
                        "test_id": "deception_001",
                        "test_name": "Deception Test",
                        "category": "deception_samples",
                        "prompt": "Deception prompt",
                        "response_content": "Deception response",
                        "vulnerability_detected": True,
                        "confidence": 0.8,
                        "evidence": ["Deception evidence"],
                        "reasoning": "Deception reasoning",
                        "flagged": False,
                        "notes": None
                    }
                ]
            },
            "cot_overload": {
                "analysis": {"total_tests": 1},
                "test_details": [
                    {
                        "test_id": "cot_001",
                        "test_name": "COT Test",
                        "category": "cot_overload",
                        "prompt": "COT prompt",
                        "response_content": "COT response",
                        "vulnerability_detected": True,
                        "confidence": 0.9,
                        "evidence": ["COT evidence"],
                        "reasoning": "COT reasoning",
                        "flagged": False,
                        "notes": None
                    }
                ]
            }
        }
        
        with open(self.temp_file, 'w') as f:
            json.dump(sample_data, f, indent=2)
        
        # Load evaluator and flag one from each category
        evaluator = CLIEvaluator(self.temp_file)
        
        # Should have 2 results
        self.assertEqual(len(evaluator.test_results), 2)
        
        # Flag both tests
        evaluator.test_results[0].flagged = True
        evaluator.test_results[1].flagged = True
        evaluator._save_updated_results()
        
        # Create new evaluator (simulating restart)
        evaluator2 = CLIEvaluator(self.temp_file)
        
        # Verify both flags persisted
        self.assertTrue(evaluator2.test_results[0].flagged)
        self.assertTrue(evaluator2.test_results[1].flagged)
    
    def test_json_structure_preservation(self):
        """Test that original JSON structure is preserved after saving"""
        # Create sample results file
        original_data = self.create_sample_results_file()
        
        # Load evaluator, make changes, and save
        evaluator = CLIEvaluator(self.temp_file)
        evaluator.test_results[0].flagged = True
        evaluator.test_results[0].notes = "Test note"
        evaluator._save_updated_results()
        
        # Load the modified file and compare structure
        with open(self.temp_file, 'r') as f:
            modified_data = json.load(f)
        
        # Verify structure is preserved
        self.assertEqual(set(original_data.keys()), set(modified_data.keys()))
        
        for category in original_data.keys():
            # Analysis should be preserved
            self.assertEqual(
                original_data[category]["analysis"], 
                modified_data[category]["analysis"]
            )
            
            # Test details structure should be preserved
            original_details = original_data[category]["test_details"]
            modified_details = modified_data[category]["test_details"]
            
            self.assertEqual(len(original_details), len(modified_details))
            
            # Verify that only flagged and notes fields changed
            for i, (orig, mod) in enumerate(zip(original_details, modified_details)):
                for key in orig.keys():
                    if key not in ["flagged", "notes"]:
                        self.assertEqual(orig[key], mod[key], f"Key {key} changed unexpectedly")
    
    def test_error_handling_file_permissions(self):
        """Test error handling when file cannot be written"""
        # Create sample results file
        self.create_sample_results_file()
        
        # Load evaluator
        evaluator = CLIEvaluator(self.temp_file)
        
        # Make file read-only
        os.chmod(self.temp_file, 0o444)
        
        # Try to save (should not crash)
        evaluator.test_results[0].flagged = True
        try:
            evaluator._save_updated_results()
            # Should not crash, just handle the error gracefully
        except Exception as e:
            self.fail(f"_save_updated_results should handle errors gracefully, but got: {e}")
        finally:
            # Restore permissions for cleanup
            os.chmod(self.temp_file, 0o644)
    
    def test_backward_compatibility(self):
        """Test that CLI can load old format files without repetition metadata"""
        # Create old format sample data (without repetition_run fields)
        old_format_data = {
            "deception_samples": {
                "analysis": {"total_tests": 1},
                "test_details": [
                    {
                        "test_id": "test_001",
                        "test_name": "Test 001",
                        "category": "deception_samples",
                        "prompt": "Test prompt 1",
                        "response_content": "Test response 1",
                        "vulnerability_detected": True,
                        "confidence": 0.8,
                        "evidence": ["Evidence 1"],
                        "reasoning": "Test reasoning 1",
                        "flagged": True,  # Pre-flagged in old format
                        "notes": "Old format note"
                        # Note: no repetition_run or total_repetitions fields
                    }
                ]
            }
        }
        
        with open(self.temp_file, 'w') as f:
            json.dump(old_format_data, f, indent=2)
        
        # Should load without errors
        evaluator = CLIEvaluator(self.temp_file)
        
        # Should have 1 result
        self.assertEqual(len(evaluator.test_results), 1)
        
        # Should preserve old data
        result = evaluator.test_results[0]
        self.assertTrue(result.flagged)
        self.assertEqual(result.notes, "Old format note")
        self.assertIsNone(result.repetition_run)
        self.assertIsNone(result.total_repetitions)
        
        # Should be able to save without errors
        result.notes = "Updated note"
        evaluator._save_updated_results()
        
        # Reload and verify
        evaluator2 = CLIEvaluator(self.temp_file)
        self.assertEqual(evaluator2.test_results[0].notes, "Updated note")
    
    def test_matching_logic_edge_cases(self):
        """Test edge cases in the matching logic"""
        # Create data with same test_id but missing repetition fields
        sample_data = {
            "deception_samples": {
                "analysis": {"total_tests": 2},
                "test_details": [
                    {
                        "test_id": "test_001",
                        "test_name": "Test 001 - Normal",
                        "category": "deception_samples",
                        "prompt": "Test prompt 1",
                        "response_content": "Test response 1",
                        "vulnerability_detected": True,
                        "confidence": 0.8,
                        "evidence": ["Evidence 1"],
                        "reasoning": "Test reasoning 1",
                        "flagged": False,
                        "notes": None
                        # No repetition fields
                    },
                    {
                        "test_id": "test_001",
                        "test_name": "Test 001 - Repeated",
                        "category": "deception_samples", 
                        "prompt": "Test prompt 1",
                        "response_content": "Test response 1 (repeated)",
                        "vulnerability_detected": False,
                        "confidence": 0.3,
                        "evidence": [],
                        "reasoning": "Test reasoning 1 (repeated)",
                        "flagged": False,
                        "notes": None,
                        "repetition_run": 2,
                        "total_repetitions": 2
                    }
                ]
            }
        }
        
        with open(self.temp_file, 'w') as f:
            json.dump(sample_data, f, indent=2)
        
        # Load evaluator
        evaluator = CLIEvaluator(self.temp_file)
        
        # Should have 2 results
        self.assertEqual(len(evaluator.test_results), 2)
        
        # Flag both (this tests the matching logic with mixed formats)
        evaluator.test_results[0].flagged = True
        evaluator.test_results[1].flagged = True
        evaluator._save_updated_results()
        
        # Reload and verify both are still flagged
        evaluator2 = CLIEvaluator(self.temp_file)
        self.assertTrue(evaluator2.test_results[0].flagged)
        self.assertTrue(evaluator2.test_results[1].flagged)


if __name__ == '__main__':
    unittest.main()
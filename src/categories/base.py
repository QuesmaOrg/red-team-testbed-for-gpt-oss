"""
Base classes for vulnerability category testing
Provides common functionality to eliminate code duplication across categories
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from src.evaluators import BaseEvaluator
from src.models import EvaluationResult, VulnerabilityCategory
from src.utils.live_display import TestProgress, get_display
from src.utils.model_client import ModelResponse, OllamaClient


@dataclass
class BaseTest:
    """Base class for all vulnerability test cases"""

    test_id: str
    name: str
    prompt: str
    system_prompt: str = ""
    category: str = ""
    description: str = ""

    # Multi-turn support
    follow_up_prompts: list[str] | None = None

    # Additional metadata fields for specialized tests
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseTester(ABC):
    """Abstract base class for all vulnerability category testers"""

    # Class attributes to be set by subclasses
    CATEGORY_NAME: str = ""
    VULNERABILITY_CATEGORY: VulnerabilityCategory
    EVALUATOR_CLASS: type[BaseEvaluator] | None = None

    def __init__(self, client: Any) -> None:
        self.client = client
        self.evaluator = self._get_evaluator()
        self.test_cases = self._initialize_test_cases()

    def _get_evaluator(self) -> BaseEvaluator:
        """Get the appropriate evaluator for this tester."""
        if self.EVALUATOR_CLASS:
            return self.EVALUATOR_CLASS()
        else:
            # All categories should now have their own evaluator class
            # This should not happen in the new system
            raise NotImplementedError(
                f"Category {self.CATEGORY_NAME} must define EVALUATOR_CLASS. "
                "The old ResponseEvaluator fallback has been removed."
            )

    @abstractmethod
    def _initialize_test_cases(self) -> list[BaseTest]:
        """Initialize test cases specific to this category"""
        pass

    def get_category_name(self) -> str:
        """Return the category identifier (e.g., 'cot_overload_bypass')"""
        return self.CATEGORY_NAME

    def get_vulnerability_category(self) -> VulnerabilityCategory:
        """Return the VulnerabilityCategory enum for this tester"""
        return self.VULNERABILITY_CATEGORY

    def run_single_test(
        self,
        test: BaseTest,
        current_num: int = 1,
        total_tests: int = 1,
        current_rep: int = 1,
        total_reps: int = 1,
        show_prompts: bool = True,
        quiet_mode: bool = False,
    ) -> tuple[BaseTest, list[ModelResponse], EvaluationResult]:
        """Run a single test with standardized error handling and display"""
        display = get_display()

        # Show test header only on first repetition (unless in quiet mode)
        progress = None
        if current_rep == 1 and not quiet_mode:
            progress = display.start_test(
                test.name, test.test_id, test.category, current_num, total_tests
            )
        else:
            # Create minimal progress object for repetitions or quiet mode
            progress = TestProgress(
                test_name=test.name,
                test_id=test.test_id,
                category=test.category,
                start_time=time.time(),
                current_test_num=current_num,
                total_tests=total_tests,
            )

        # Show repetition header for multi-repetition runs (unless in quiet mode)
        if not quiet_mode:
            display.show_repetition_header(current_rep, total_reps)

        responses = []

        try:
            if test.follow_up_prompts and len(test.follow_up_prompts) > 0:
                # Multi-turn conversation
                if show_prompts and current_rep == 1 and not quiet_mode:
                    # Show all prompts at once for multi-turn on first repetition
                    all_prompts = [test.prompt] + test.follow_up_prompts
                    display.show_multi_turn_prompts(all_prompts, test.system_prompt)

                # Execute conversation turns
                if not quiet_mode:
                    display.start_thinking_timer(progress)
                response = self.client.generate(test.prompt, test.system_prompt)
                if not quiet_mode:
                    display.stop_thinking_timer()
                responses.append(response)
                if not quiet_mode:
                    display.show_response(progress, response)

                if not response.error:
                    for follow_up in test.follow_up_prompts:
                        if not quiet_mode:
                            display.start_thinking_timer(progress)
                        response = self.client.generate(follow_up, "")
                        if not quiet_mode:
                            display.stop_thinking_timer()
                        responses.append(response)
                        if not quiet_mode:
                            display.show_response(progress, response)

                        if response.error:
                            break
            else:
                # Single-turn test
                if show_prompts and current_rep == 1 and not quiet_mode:
                    display.show_prompt(
                        progress, test.prompt, test.system_prompt, show_display=True
                    )

                if not quiet_mode:
                    display.start_thinking_timer(progress)
                response = self.client.generate(test.prompt, test.system_prompt)
                if not quiet_mode:
                    display.stop_thinking_timer()
                responses.append(response)
                if not quiet_mode:
                    display.show_response(progress, response)

            # Evaluate results
            if any(r.error for r in responses):
                error_msgs = [r.error for r in responses if r.error]
                evaluation = EvaluationResult(
                    is_vulnerable=False,
                    category=self.get_vulnerability_category(),
                    confidence=0.0,
                    evidence=[],
                    reasoning=f"Test failed: {'; '.join(error_msgs)}",
                )
            else:
                evaluation = self._evaluate_test_response(test, responses)

            # Show evaluation results (unless in quiet mode)
            if not quiet_mode:
                display.show_evaluation(progress, evaluation)

            # Only show completion message on last repetition (unless in quiet mode)
            if current_rep == total_reps and not quiet_mode:
                display.complete_test(progress, evaluation)

        except Exception as e:
            # Ensure timer is stopped on any exception
            display.stop_thinking_timer()
            display.error(f"Test failed: {e}")
            evaluation = EvaluationResult(
                is_vulnerable=False,
                category=self.get_vulnerability_category(),
                confidence=0.0,
                evidence=[],
                reasoning=f"Test failed: {e}",
            )

        return test, responses, evaluation

    def _evaluate_test_response(
        self, test: BaseTest, responses: list[ModelResponse]
    ) -> EvaluationResult:
        """
        Evaluate test response - can be overridden by subclasses for specialized evaluation
        Default behavior uses the standard evaluator based on category
        """
        if not responses:
            return EvaluationResult(
                is_vulnerable=False,
                category=self.get_vulnerability_category(),
                confidence=0.0,
                evidence=[],
                reasoning="No responses to evaluate",
            )

        # For multi-turn tests, evaluate the complete conversation
        if len(responses) > 1:
            # Combine all responses for evaluation
            combined_content = "\n\n".join(r.content for r in responses)
            # Use the first response object but with combined content for evaluation
            combined_response = ModelResponse(
                content=combined_content,
                model=responses[0].model,
                response_time=sum(r.response_time for r in responses),
                error=None,
                timed_out=any(r.timed_out for r in responses),
                thinking=responses[-1].thinking,  # Use last response's thinking
            )
            return self._evaluate_single_response(test, combined_response)
        else:
            return self._evaluate_single_response(test, responses[0])

    def _evaluate_single_response(
        self, test: BaseTest, response: ModelResponse
    ) -> EvaluationResult:
        """Evaluate a single response using the appropriate evaluator method"""
        # New evaluator system - pass any additional test metadata
        kwargs = {}
        if hasattr(test, "target_harmful_question"):
            kwargs["target_harmful_question"] = test.target_harmful_question
        if hasattr(test, "target_individual"):
            kwargs["target_individual"] = test.target_individual
        return self.evaluator.evaluate(test.prompt, response.content, **kwargs)

    def run_test_with_repeats(
        self, test: BaseTest, repeat_count: int, current_num: int = 1, total_tests: int = 1
    ) -> list[tuple[BaseTest, list[ModelResponse], EvaluationResult]]:
        """Run a single test multiple times consecutively"""
        display = get_display()
        results = []
        repetition_summaries = []

        for rep in range(1, repeat_count + 1):
            try:
                result = self.run_single_test(
                    test,
                    current_num=current_num,
                    total_tests=total_tests,
                    current_rep=rep,
                    total_reps=repeat_count,
                    show_prompts=True,
                )
                test_obj, responses, evaluation = result
                results.append(result)

                # Collect summary data for this repetition
                rep_summary = {
                    "is_vulnerable": evaluation.is_vulnerable,
                    "confidence": evaluation.confidence,
                    "response_time": sum(r.response_time for r in responses) if responses else 0,
                }
                repetition_summaries.append(rep_summary)

            except Exception as e:
                # Ensure any running timer is stopped
                display.stop_thinking_timer()
                display.error(f"Failed: {test.name} repetition {rep} - {e}")
                # Create error result
                error_response = ModelResponse(content="", model=self.client.model, error=str(e))
                error_evaluation = EvaluationResult(
                    is_vulnerable=False,
                    category=self.get_vulnerability_category(),
                    confidence=0.0,
                    evidence=[],
                    reasoning=f"Test failed: {e}",
                )
                results.append((test, [error_response], error_evaluation))

                # Add error to summary
                rep_summary = {
                    "is_vulnerable": False,
                    "confidence": 0.0,
                    "response_time": 0,
                }
                repetition_summaries.append(rep_summary)

        # Show vulnerability summary after all repetitions (if more than 1)
        if repeat_count > 1:
            display.show_vulnerability_summary(test.test_id, repetition_summaries)

        return results

    def run_category_tests(
        self, category: str | None = None, test_id: str | None = None, repeat_count: int = 1
    ) -> list[tuple[BaseTest, list[ModelResponse], EvaluationResult]]:
        """Run all tests in category with filtering support"""
        display = get_display()
        results = []

        # Filter tests by category and/or test_id
        test_cases = self.test_cases
        if category:
            test_cases = [t for t in test_cases if t.category == category]
        if test_id:
            test_cases = [t for t in test_cases if t.test_id == test_id]
            if not test_cases:
                available_ids = [test.test_id for test in self.test_cases]
                display.error(f"Test ID '{test_id}' not found. Available test IDs: {available_ids}")
                return []

        # Start category display
        display.start_category(self.get_category_name(), len(test_cases))

        for i, test in enumerate(test_cases, 1):
            if repeat_count > 1:
                # Run test with repetitions
                test_results = self.run_test_with_repeats(
                    test, repeat_count, current_num=i, total_tests=len(test_cases)
                )
                results.extend(test_results)
            else:
                # Single run (normal behavior)
                try:
                    result = self.run_single_test(
                        test,
                        current_num=i,
                        total_tests=len(test_cases),
                        current_rep=1,
                        total_reps=1,
                        show_prompts=True,
                    )
                    results.append(result)
                except Exception as e:
                    # Ensure any running timer is stopped
                    display.stop_thinking_timer()
                    display.error(f"Failed: {test.name} - {e}")
                    # Create error result
                    error_response = ModelResponse(
                        content="", model=self.client.model, error=str(e)
                    )
                    error_evaluation = EvaluationResult(
                        is_vulnerable=False,
                        category=self.get_vulnerability_category(),
                        confidence=0.0,
                        evidence=[],
                        reasoning=f"Test failed: {e}",
                    )
                    results.append((test, [error_response], error_evaluation))

        return results

    def analyze_results(
        self, results: list[tuple[BaseTest, list[ModelResponse], EvaluationResult]]
    ) -> dict[str, Any]:
        """Analyze test results with standard metrics - can be extended by subclasses"""
        # Filter out results with errors or empty responses
        valid_results = []
        for test, responses, evaluation in results:
            # Check if test failed due to errors or empty responses
            has_error = any(r.error for r in responses) if responses else True
            has_empty_content = all(not r.content.strip() for r in responses) if responses else True

            # Keep result if it doesn't have errors and has content
            if not has_error and not has_empty_content:
                valid_results.append((test, responses, evaluation))

        analysis = {
            "total_tests": len(valid_results),
            "total_attempted": len(results),  # Include original count for reference
            "excluded_tests": len(results) - len(valid_results),
            "vulnerable_tests": 0,
            "high_confidence_vulnerabilities": 0,
            "category_breakdown": {},
            "common_patterns": [],
            "average_confidence": 0.0,
        }

        confidences = []

        for test, _responses, evaluation in valid_results:
            if evaluation.is_vulnerable:
                analysis["vulnerable_tests"] += 1

                if evaluation.confidence > 0.7:
                    analysis["high_confidence_vulnerabilities"] += 1

            # Category breakdown
            category = test.category
            if category not in analysis["category_breakdown"]:
                analysis["category_breakdown"][category] = {"total": 0, "vulnerable": 0}
            analysis["category_breakdown"][category]["total"] += 1
            if evaluation.is_vulnerable:
                analysis["category_breakdown"][category]["vulnerable"] += 1

            confidences.append(evaluation.confidence)

        if confidences:
            analysis["average_confidence"] = sum(confidences) / len(confidences)

        # Identify common evidence patterns
        evidence_patterns = {}
        for _test, _responses, evaluation in valid_results:
            for evidence in evaluation.evidence:
                if evidence in evidence_patterns:
                    evidence_patterns[evidence] += 1
                else:
                    evidence_patterns[evidence] = 1

        # Get most common patterns
        common_patterns = sorted(evidence_patterns.items(), key=lambda x: x[1], reverse=True)[:5]
        analysis["common_patterns"] = [
            {"pattern": pattern, "count": count} for pattern, count in common_patterns
        ]

        return analysis

    def get_test_by_id(self, test_id: str) -> BaseTest:
        """Get specific test by ID"""
        for test in self.test_cases:
            if test.test_id == test_id:
                return test
        raise ValueError(f"Test {test_id} not found")

    def list_categories(self) -> list[str]:
        """List all available test categories"""
        return list(set(test.category for test in self.test_cases))


def run_category_tests_generic(
    tester_class: type[BaseTester],
    client: OllamaClient,
    category: str | None = None,
    test_id: str | None = None,
    repeat_count: int = 1,
) -> dict[str, Any]:
    """Generic runner function for any tester class"""
    display = get_display()
    tester = tester_class(client)

    results = tester.run_category_tests(category, test_id, repeat_count)
    analysis = tester.analyze_results(results)

    # Display final summary
    display.complete_category(tester.get_category_name(), analysis)

    return {"results": results, "analysis": analysis, "tester": tester}

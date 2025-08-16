"""
Base classes for vulnerability category testing
Provides common functionality to eliminate code duplication across categories
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from src.utils.evaluator import EvaluationResult, ResponseEvaluator, VulnerabilityCategory
from src.utils.live_display import get_display
from src.utils.model_client import ModelResponse, OllamaClient


@dataclass
class BaseTest:
    """Base class for all vulnerability test cases"""

    test_id: str
    name: str
    prompt: str
    system_prompt: str = ""
    category: str = ""
    difficulty: str = "medium"
    expected_vulnerability: bool = True
    description: str = ""

    # Multi-turn support
    multi_turn: bool = False
    follow_up_prompts: list[str] | None = None
    conversation_turns: list[dict[str, str]] | None = None

    # Additional metadata fields for specialized tests
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseTester(ABC):
    """Abstract base class for all vulnerability category testers"""

    def __init__(self, client: OllamaClient) -> None:
        self.client = client
        self.evaluator = ResponseEvaluator()
        self.test_cases = self._initialize_test_cases()

    @abstractmethod
    def _initialize_test_cases(self) -> list[BaseTest]:
        """Initialize test cases specific to this category"""
        pass

    @abstractmethod
    def get_category_name(self) -> str:
        """Return the category identifier (e.g., 'cot_overload_bypass')"""
        pass

    @abstractmethod
    def get_vulnerability_category(self) -> VulnerabilityCategory:
        """Return the VulnerabilityCategory enum for this tester"""
        pass

    def run_single_test(
        self, test: BaseTest, current_num: int = 1, total_tests: int = 1
    ) -> tuple[BaseTest, list[ModelResponse], EvaluationResult]:
        """Run a single test with standardized error handling and display"""
        display = get_display()

        # Start test display
        progress = display.start_test(
            test.name, test.test_id, test.category, current_num, total_tests
        )

        responses = []

        try:
            if test.multi_turn and (test.follow_up_prompts or test.conversation_turns):
                # Multi-turn conversation
                if test.conversation_turns:
                    # Use predefined conversation turns
                    for i, turn in enumerate(test.conversation_turns, 1):
                        user_msg = turn.get("user", "")
                        display.show_prompt(
                            progress, user_msg, test.system_prompt if i == 1 else ""
                        )
                        display.start_thinking_timer(progress)

                        response = self.client.generate(
                            user_msg, test.system_prompt if i == 1 else ""
                        )
                        display.stop_thinking_timer()
                        responses.append(response)
                        display.show_response(progress, response)

                        if response.error:
                            break
                elif test.follow_up_prompts:
                    # Use initial prompt + follow-up prompts
                    display.show_prompt(progress, test.prompt, test.system_prompt)
                    display.start_thinking_timer(progress)

                    response = self.client.generate(test.prompt, test.system_prompt)
                    display.stop_thinking_timer()
                    responses.append(response)
                    display.show_response(progress, response)

                    if not response.error:
                        for follow_up in test.follow_up_prompts:
                            display.show_prompt(progress, follow_up, "")
                            display.start_thinking_timer(progress)

                            response = self.client.generate(follow_up, "")
                            display.stop_thinking_timer()
                            responses.append(response)
                            display.show_response(progress, response)

                            if response.error:
                                break
            else:
                # Single-turn test
                display.show_prompt(progress, test.prompt, test.system_prompt)
                display.start_thinking_timer(progress)

                response = self.client.generate(test.prompt, test.system_prompt)
                display.stop_thinking_timer()
                responses.append(response)
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

            # Show evaluation results
            display.show_evaluation(progress, evaluation)
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
        category = self.get_vulnerability_category()

        if category == VulnerabilityCategory.DECEPTION:
            return self.evaluator.evaluate_deception(test.prompt, response.content)
        elif category == VulnerabilityCategory.INAPPROPRIATE_TOOL_USE:
            return self.evaluator.evaluate_response(
                test.prompt, response.content, self.get_vulnerability_category()
            )
        elif category == VulnerabilityCategory.EXPLOIT:
            return self.evaluator.evaluate_exploit(test.prompt, response.content)
        elif category == VulnerabilityCategory.CHAIN_OF_THOUGHT:
            return self.evaluator.evaluate_response(
                test.prompt, response.content, self.get_vulnerability_category()
            )
        else:
            # Default evaluation - can be overridden by subclasses
            return self.evaluator.evaluate_deception(test.prompt, response.content)

    def run_category_tests(
        self, category: str | None = None, test_id: str | None = None
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
            try:
                result = self.run_single_test(test, current_num=i, total_tests=len(test_cases))
                results.append(result)
            except Exception as e:
                # Ensure any running timer is stopped
                display.stop_thinking_timer()
                display.error(f"Failed: {test.name} - {e}")
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

        return results

    def analyze_results(
        self, results: list[tuple[BaseTest, list[ModelResponse], EvaluationResult]]
    ) -> dict[str, Any]:
        """Analyze test results with standard metrics - can be extended by subclasses"""
        analysis = {
            "total_tests": len(results),
            "vulnerable_tests": 0,
            "high_confidence_vulnerabilities": 0,
            "category_breakdown": {},
            "common_patterns": [],
            "average_confidence": 0.0,
        }

        confidences = []

        for test, _responses, evaluation in results:
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
        for _test, _responses, evaluation in results:
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
) -> dict[str, Any]:
    """Generic runner function for any tester class"""
    display = get_display()
    tester = tester_class(client)

    results = tester.run_category_tests(category, test_id)
    analysis = tester.analyze_results(results)

    # Display final summary
    display.complete_category(tester.get_category_name(), analysis)

    return {"results": results, "analysis": analysis, "tester": tester}

"""
Parallel test execution using ThreadPoolExecutor
Provides thread-safe concurrent execution of vulnerability tests with OpenRouter
"""

import queue
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

from src.categories.base import BaseTest
from src.utils.evaluator import EvaluationResult, VulnerabilityCategory
from src.utils.live_display import get_display
from src.utils.model_client import ModelResponse


@dataclass
class ParallelTestResult:
    """Result from a single parallel test execution"""

    test: BaseTest
    responses: list[ModelResponse]
    evaluation: EvaluationResult
    execution_time: float
    worker_id: int
    error: str | None = None


class ParallelTestRunner:
    """Manages parallel execution of vulnerability tests"""

    def __init__(self, num_threads: int = 4) -> None:
        self.num_threads = num_threads
        self.result_queue: queue.Queue[ParallelTestResult] = queue.Queue()
        self.completed_count = 0
        self.total_tests = 0
        self.start_time = 0.0
        self.display = get_display()

    def run_tests_parallel(
        self,
        test_tasks: list[tuple[BaseTest, Any, int]],  # (test, client, repetition)
        category_runner_func: Callable,
    ) -> list[ParallelTestResult]:
        """
        Execute tests in parallel using ThreadPoolExecutor

        Args:
            test_tasks: List of (test, client, repetition_number) tuples
            category_runner_func: Function to execute single test

        Returns:
            List of ParallelTestResult objects
        """
        self.total_tests = len(test_tasks)
        self.completed_count = 0
        self.start_time = time.time()
        results = []

        # Show parallel execution header
        self.display.info(
            f"🚀 Starting parallel execution with {self.num_threads} threads (OpenRouter)"
        )
        self.display.info(f"⚡ Running {self.total_tests} tests in parallel...")

        # Start result display thread
        display_thread = threading.Thread(target=self._display_worker, daemon=True)
        display_thread.start()

        # Execute tests in parallel
        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            # Submit all tasks
            future_to_task = {}
            for i, (test, client, rep_num) in enumerate(test_tasks):
                worker_id = (i % self.num_threads) + 1
                future = executor.submit(
                    self._execute_single_test,
                    test,
                    client,
                    rep_num,
                    worker_id,
                    category_runner_func,
                )
                future_to_task[future] = (test, worker_id)

            # Collect results as they complete
            for future in as_completed(future_to_task):
                try:
                    result = future.result()
                    results.append(result)
                    self.result_queue.put(result)
                    self.completed_count += 1
                except Exception as e:
                    test, worker_id = future_to_task[future]
                    error_result = ParallelTestResult(
                        test=test,
                        responses=[],
                        evaluation=EvaluationResult(
                            is_vulnerable=False,
                            category=VulnerabilityCategory.DECEPTION,  # Default category for errors
                            confidence=0.0,
                            evidence=[],
                            reasoning=f"Parallel execution error: {str(e)}",
                        ),
                        execution_time=0.0,
                        worker_id=worker_id,
                        error=str(e),
                    )
                    results.append(error_result)
                    self.result_queue.put(error_result)
                    self.completed_count += 1

        # Signal display thread to stop
        self.result_queue.put(None)  # Sentinel value
        display_thread.join(timeout=1.0)

        total_time = time.time() - self.start_time
        sequential_estimate = sum(r.execution_time for r in results)
        speedup = sequential_estimate / total_time if total_time > 0 else 1.0

        self.display.info(
            f"⚡ All tests complete! Total time: {total_time:.1f}s (vs ~{sequential_estimate:.1f}s sequential)"
        )
        if speedup > 1.1:
            self.display.info(f"🏃 Speedup achieved: {speedup:.1f}x faster")

        return results

    def _execute_single_test(
        self,
        test: BaseTest,
        client: Any,
        repetition: int,
        worker_id: int,
        category_runner_func: Callable,
    ) -> ParallelTestResult:
        """Execute a single test in a worker thread"""
        start_time = time.time()

        try:
            # Execute the test using the category runner's single test method
            # We need to call the underlying tester's run_single_test method
            # but in a thread-safe way without display interference

            # Create a temporary tester instance for this worker
            from src.categories.registry import TestRegistry

            # Get tester class from registry (this is a bit hacky but necessary)
            # Since we don't have direct access to the tester instance in parallel mode
            all_categories = TestRegistry.get_all_categories()
            tester_class = None
            for _cat_name, info in all_categories.items():
                try:
                    temp_tester = info.tester_class(client)
                    # Check if this tester has our test
                    for t in getattr(temp_tester, "test_cases", []):
                        if t.test_id == test.test_id:
                            tester_class = info.tester_class
                            break
                    if tester_class:
                        break
                except Exception:
                    continue

            if not tester_class:
                raise RuntimeError(f"Could not find tester for test {test.test_id}")

            # Create worker-specific tester instance
            worker_tester = tester_class(client)

            # Execute test with minimal display (no prompts/evaluation shown during parallel execution)
            test_result, responses, evaluation = worker_tester.run_single_test(
                test,
                current_num=1,
                total_tests=1,
                current_rep=repetition,
                total_reps=1,
                show_prompts=False,  # Disable prompt display in parallel mode
                quiet_mode=True,  # Enable quiet mode for parallel execution
            )

            execution_time = time.time() - start_time

            return ParallelTestResult(
                test=test_result,
                responses=responses,
                evaluation=evaluation,
                execution_time=execution_time,
                worker_id=worker_id,
            )

        except Exception as e:
            execution_time = time.time() - start_time
            return ParallelTestResult(
                test=test,
                responses=[],
                evaluation=EvaluationResult(
                    is_vulnerable=False,
                    category=VulnerabilityCategory.DECEPTION,  # Default category for errors
                    confidence=0.0,
                    evidence=[],
                    reasoning=f"Test execution failed: {str(e)}",
                ),
                execution_time=execution_time,
                worker_id=worker_id,
                error=str(e),
            )

    def _display_worker(self) -> None:
        """Background thread that displays results as they complete"""
        while True:
            try:
                result = self.result_queue.get(timeout=1.0)
                if result is None:  # Sentinel value to stop
                    break

                # Display minimal completion info
                status_icon = "🔴" if result.evaluation.is_vulnerable else "✅"
                vuln_status = "VULNERABLE" if result.evaluation.is_vulnerable else "Not vulnerable"

                if result.error:
                    status_icon = "❌"
                    vuln_status = "ERROR"

                worker_msg = f"[Worker {result.worker_id}] {status_icon} {result.test.test_id} - {vuln_status} ({result.execution_time:.1f}s)"
                self.display.info(worker_msg)

            except queue.Empty:
                continue
            except Exception:
                break

    def generate_parallel_summary(self, results: list[ParallelTestResult]) -> dict[str, Any]:
        """Generate comprehensive summary statistics for parallel execution"""
        if not results:
            return {}

        total_tests = len(results)
        vulnerable_tests = sum(1 for r in results if r.evaluation.is_vulnerable)
        error_tests = sum(1 for r in results if r.error)

        # Group by test category
        category_stats = {}
        for result in results:
            cat = result.test.category or "unknown"
            if cat not in category_stats:
                category_stats[cat] = {"total": 0, "vulnerable": 0, "errors": 0}

            category_stats[cat]["total"] += 1
            if result.evaluation.is_vulnerable:
                category_stats[cat]["vulnerable"] += 1
            if result.error:
                category_stats[cat]["errors"] += 1

        # Calculate confidence statistics
        confidences = [r.evaluation.confidence for r in results if not r.error]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        high_confidence = sum(1 for c in confidences if c > 0.8)

        # Find most/least vulnerable tests (for repeat scenarios)
        test_vulnerability_rates = {}
        for result in results:
            test_id = result.test.test_id
            if test_id not in test_vulnerability_rates:
                test_vulnerability_rates[test_id] = {"vulnerable": 0, "total": 0}

            test_vulnerability_rates[test_id]["total"] += 1
            if result.evaluation.is_vulnerable:
                test_vulnerability_rates[test_id]["vulnerable"] += 1

        # Calculate vulnerability rates per test
        test_rates = []
        for test_id, stats in test_vulnerability_rates.items():
            rate = stats["vulnerable"] / stats["total"] if stats["total"] > 0 else 0.0
            test_rates.append((test_id, rate, stats["vulnerable"], stats["total"]))

        # Sort by vulnerability rate
        most_vulnerable = sorted(test_rates, key=lambda x: x[1], reverse=True)[:5]
        most_resilient = sorted(
            [t for t in test_rates if t[1] == 0.0], key=lambda x: x[3], reverse=True
        )[:5]

        total_time = time.time() - self.start_time
        avg_execution_time = (
            sum(r.execution_time for r in results) / len(results) if results else 0.0
        )

        return {
            "total_tests": total_tests,
            "vulnerable_tests": vulnerable_tests,
            "error_tests": error_tests,
            "vulnerability_rate": vulnerable_tests / total_tests if total_tests > 0 else 0.0,
            "category_stats": category_stats,
            "avg_confidence": avg_confidence,
            "high_confidence": high_confidence,
            "most_vulnerable": most_vulnerable,
            "most_resilient": most_resilient,
            "total_time": total_time,
            "avg_execution_time": avg_execution_time,
            "num_threads": self.num_threads,
        }

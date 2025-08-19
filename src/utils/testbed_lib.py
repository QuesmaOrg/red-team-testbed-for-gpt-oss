"""
Red Team Testbed Library Functions
Essential utilities extracted from legacy testbed.py for use across the toolkit
"""

import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


def load_config(config_path: str = "config.yaml") -> dict[str, Any]:
    """Load configuration from YAML file"""
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_file) as f:
        return yaml.safe_load(f)


def setup_logging(config: dict[str, Any]) -> None:
    """Setup logging configuration"""
    import logging

    log_config = config.get("logging", {})
    level = getattr(logging, log_config.get("level", "INFO").upper())

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_config.get("file", "testbed.log")),
        ],
    )


def ensure_directories(config: dict[str, Any]) -> None:
    """Ensure output directories exist"""
    output_config = config.get("output", {})

    results_dir = Path(output_config.get("results_dir", "results"))
    findings_dir = Path(output_config.get("findings_dir", "findings"))

    results_dir.mkdir(exist_ok=True)
    findings_dir.mkdir(exist_ok=True)


def run_category_with_repeats(
    category_runner: Callable,
    client: object,
    category: str | None,
    test_id: str | None,
    repeat_count: int,
    threads: int = 1,
) -> dict:
    """Run a category test runner with repetition support - new consecutive execution model"""
    from .live_display import get_display

    display = get_display()

    # Check for parallel execution
    if threads > 1:
        return _run_category_parallel(
            category_runner, client, category, test_id, repeat_count, threads
        )

    if repeat_count == 1:
        # Standard execution - no changes needed
        return category_runner(client, category, test_id, repeat_count)

    # Multi-repeat execution: each test runs N times consecutively
    display.info(f"🔄 Running with {repeat_count} repetitions per test (consecutive execution)")

    # Run with repetition support - the category runner now handles repetitions internally
    results = category_runner(client, category, test_id, repeat_count)

    # Extract results and update analysis for repetition reporting
    all_results = results.get("results", [])

    # Group results by test_id to calculate statistics
    test_groups = {}
    for result_tuple in all_results:
        if len(result_tuple) >= 3:
            test, responses, evaluation = result_tuple[0], result_tuple[1], result_tuple[2]
            test_id = test.test_id
            if test_id not in test_groups:
                test_groups[test_id] = []
            test_groups[test_id].append((test, responses, evaluation))

    # Calculate analysis with repeat awareness
    total_runs = len(all_results)
    unique_tests = len(test_groups)
    vulnerable_runs = 0

    # Count vulnerable runs across all repetitions
    for result_tuple in all_results:
        if len(result_tuple) >= 3:
            evaluation = result_tuple[2]
            if evaluation.is_vulnerable:
                vulnerable_runs += 1

    analysis = results.get("analysis", {})
    analysis.update(
        {
            "total_tests": unique_tests,
            "total_runs": total_runs,
            "repetitions_per_test": repeat_count,
            "vulnerable_runs": vulnerable_runs,
            "vulnerability_rate": vulnerable_runs / total_runs if total_runs > 0 else 0,
        }
    )

    display.info(
        f"✅ Completed {unique_tests} tests × {repeat_count} repetitions = {total_runs} total runs"
    )

    return {"results": all_results, "analysis": analysis}


def calculate_timeout_stats(all_results: dict[str, Any]) -> dict[str, Any]:
    """Calculate timeout statistics from test results"""
    total_requests = 0
    total_timeouts = 0
    response_times = []

    for _category, cat_results in all_results.items():
        for result_tuple in cat_results.get("results", []):
            # Handle both normal results (3-tuple) and repeat results (4-tuple)
            if len(result_tuple) == 3:
                test, responses, evaluation = result_tuple
            elif len(result_tuple) == 4:
                test, responses, evaluation, run_num = result_tuple
            else:
                # Fallback for unexpected format
                _test, responses, _evaluation = result_tuple[0], result_tuple[1], result_tuple[2]

            if responses:  # Check if we have responses
                for response in responses:
                    total_requests += 1
                    response_times.append(response.response_time)
                    if response.timed_out:
                        total_timeouts += 1

    if total_requests == 0:
        return {
            "total_requests": 0,
            "total_timeouts": 0,
            "timeout_percentage": 0.0,
            "avg_response_time": 0.0,
            "max_response_time": 0.0,
        }

    return {
        "total_requests": total_requests,
        "total_timeouts": total_timeouts,
        "timeout_percentage": (total_timeouts / total_requests) * 100,
        "avg_response_time": sum(response_times) / len(response_times) if response_times else 0.0,
        "max_response_time": max(response_times) if response_times else 0.0,
    }


def save_results(results: dict[str, Any], output_dir: str, verbose: bool) -> str:
    """Save test results to files and return the results filename"""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save full results
    results_file = output_path / f"test_results_{timestamp}.json"

    # Convert results to JSON-serializable format
    serializable_results = {}
    for category, cat_results in results.items():
        serializable_results[category] = {
            "analysis": cat_results.get("analysis", {}),
            "test_details": [],
        }

        for result_tuple in cat_results.get("results", []):
            # Handle both normal results and repeat results
            if len(result_tuple) == 3:
                # Normal result: (test, responses, evaluation)
                test, responses, evaluation = result_tuple
                repeat_info = None
            elif len(result_tuple) == 4:
                # Repeat result: (test, responses, evaluation, run_num)
                test, responses, evaluation, run_num = result_tuple
                repeat_info = run_num
            else:
                # Fallback for unexpected format
                test, responses, evaluation = result_tuple[0], result_tuple[1], result_tuple[2]
                repeat_info = None

            # Build conversation_turns from prompt and follow_up_prompts if available
            conversation_turns = None
            if hasattr(test, "follow_up_prompts") and test.follow_up_prompts:
                # For tests with follow_up_prompts, build the conversation turns
                conversation_turns = [test.prompt] + test.follow_up_prompts
            elif hasattr(test, "conversation_turns") and test.conversation_turns:
                # For tests with explicit conversation_turns
                conversation_turns = test.conversation_turns

            test_detail = {
                "test_id": test.test_id,
                "test_name": test.name,
                "category": test.category,
                "prompt": getattr(test, "prompt", None),
                "conversation_turns": conversation_turns,
                "system_prompt": getattr(test, "system_prompt", ""),
                "vulnerability_detected": evaluation.is_vulnerable,
                "confidence": evaluation.confidence,
                "evidence": evaluation.evidence,
                "reasoning": evaluation.reasoning,
                "response_content": responses[0].content if responses else "",
                "response_time": responses[0].response_time if responses else 0.0,
                "timed_out": responses[0].timed_out if responses else False,
                "response_error": responses[0].error if responses else None,
                # Chain of thought data
                "thinking": responses[0].thinking if responses else "",
                # Multi-turn conversation data
                "all_responses": [resp.content for resp in responses] if responses else [],
                "response_times": [resp.response_time for resp in responses] if responses else [],
                "response_errors": [resp.error for resp in responses] if responses else [],
                "all_thinking": [resp.thinking or "" for resp in responses] if responses else [],
                # UI interaction data
                "flagged": False,
                "notes": None,
            }

            # Add repetition metadata only when needed
            if repeat_info is not None:
                test_detail["repetition_run"] = repeat_info
                # Get total repetitions from analysis if available
                analysis = cat_results.get("analysis", {})
                if "repetitions_per_test" in analysis:
                    test_detail["total_repetitions"] = analysis["repetitions_per_test"]

            serializable_results[category]["test_details"].append(test_detail)

    with open(results_file, "w") as f:
        json.dump(serializable_results, f, indent=2)

    if verbose:
        print(f"📁 Results saved to: {results_file}")

    # Save summary
    summary_file = output_path / f"summary_{timestamp}.txt"
    with open(summary_file, "w") as f:
        f.write("GPT-OSS-20B Red Team Test Summary\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write("=" * 50 + "\n\n")

        for category, cat_results in results.items():
            analysis = cat_results.get("analysis", {})
            f.write(f"Category: {category.upper()}\n")
            f.write(f"  Total tests: {analysis.get('total_tests', 0)}\n")
            f.write(f"  Vulnerabilities: {analysis.get('vulnerable_tests', 0)}\n")
            f.write(f"  High confidence: {analysis.get('high_confidence_vulnerabilities', 0)}\n")
            f.write(f"  Average confidence: {analysis.get('average_confidence', 0):.2f}\n")
            f.write("\n")

    return str(results_file)


def _run_category_parallel(
    category_runner: Callable,
    client: object,
    category: str | None,
    test_id: str | None,
    repeat_count: int,
    threads: int,
) -> dict:
    """Run category tests in parallel using ThreadPoolExecutor"""
    from .live_display import get_display
    from .parallel_runner import ParallelTestRunner

    display = get_display()

    # Get the actual tester instance to extract test cases
    from src.categories.registry import TestRegistry

    # Find the appropriate tester class
    all_categories = TestRegistry.get_all_categories()
    tester_instance = None

    for _cat_name, info in all_categories.items():
        try:
            temp_tester = info.tester_class(client)
            # Check if this is the right category by checking if our category_runner matches
            if category_runner == info.runner_function:
                tester_instance = temp_tester
                break
        except Exception:
            continue

    if not tester_instance:
        # Fallback: try to create a tester from the first category
        # This is a bit hacky but necessary for the parallel execution
        for _cat_name, info in all_categories.items():
            try:
                tester_instance = info.tester_class(client)
                break
            except Exception:
                continue

    if not tester_instance:
        raise RuntimeError("Could not create tester instance for parallel execution")

    # Get test cases
    test_cases = getattr(tester_instance, "test_cases", [])

    # Filter by test_id if specified
    if test_id:
        test_cases = [t for t in test_cases if t.test_id == test_id]

    if not test_cases:
        return {"results": [], "analysis": {"total_tests": 0, "vulnerable_tests": 0}}

    # Create test tasks (test, client, repetition_number) for each repetition
    test_tasks = []
    for test in test_cases:
        for rep in range(repeat_count):
            test_tasks.append((test, client, rep + 1))

    # Execute tests in parallel
    parallel_runner = ParallelTestRunner(threads)
    parallel_results = parallel_runner.run_tests_parallel(test_tasks, category_runner)

    # Convert parallel results to standard format
    standard_results = []
    for result in parallel_results:
        # Convert ParallelTestResult to standard (test, responses, evaluation) tuple
        standard_results.append((result.test, result.responses, result.evaluation))
    
    # Sort results by test_id for consistent file output
    standard_results.sort(key=lambda x: x[0].test_id)

    # Calculate analysis
    total_tests = len(set(t.test_id for t, _, _ in standard_results))
    vulnerable_runs = sum(1 for _, _, eval_result in standard_results if eval_result.is_vulnerable)
    total_runs = len(standard_results)

    analysis = {
        "total_tests": total_tests,
        "total_runs": total_runs,
        "repetitions_per_test": repeat_count,
        "vulnerable_tests": len(
            set(t.test_id for t, _, eval_result in standard_results if eval_result.is_vulnerable)
        ),
        "vulnerable_runs": vulnerable_runs,
        "vulnerability_rate": vulnerable_runs / total_runs if total_runs > 0 else 0.0,
        "average_confidence": sum(eval_result.confidence for _, _, eval_result in standard_results)
        / total_runs
        if total_runs > 0
        else 0.0,
        "high_confidence_vulnerabilities": sum(
            1
            for _, _, eval_result in standard_results
            if eval_result.is_vulnerable and eval_result.confidence > 0.8
        ),
    }

    # Generate and display parallel summary
    summary_data = parallel_runner.generate_parallel_summary(parallel_results)
    display.show_parallel_summary(summary_data)

    return {
        "results": standard_results,
        "analysis": analysis,
    }

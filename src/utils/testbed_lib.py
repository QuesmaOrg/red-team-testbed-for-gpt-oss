"""
Red Team Testbed Library Functions
Essential utilities extracted from legacy testbed.py for use across the toolkit
"""
import json
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
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_config.get("file", "testbed.log"))
        ]
    )


def ensure_directories(config: dict[str, Any]) -> None:
    """Ensure output directories exist"""
    output_config = config.get("output", {})
    
    results_dir = Path(output_config.get("results_dir", "results"))
    findings_dir = Path(output_config.get("findings_dir", "findings"))
    
    results_dir.mkdir(exist_ok=True)
    findings_dir.mkdir(exist_ok=True)


def run_category_with_repeats(category_runner, client, category, test_id, repeat_count):
    """Run a category test runner with repetition support"""
    from utils.live_display import get_display
    display = get_display()
    
    if repeat_count == 1:
        # Standard execution - no changes needed
        return category_runner(client, category, test_id)
    
    # Multi-repeat execution with proper grouping
    display.info(f"🔄 Running with {repeat_count} repetitions per test")
    
    all_test_results = {}  # Dict[test_id, List[(test, responses, evaluation, run_num)]]
    
    for run_num in range(1, repeat_count + 1):
        display.info(f"   📍 Starting repetition {run_num}/{repeat_count}")
        
        # Run tests normally
        results = category_runner(client, category, test_id)
        
        # Group results by test_id
        for test, responses, evaluation in results.get("results", []):
            if test.test_id not in all_test_results:
                all_test_results[test.test_id] = []
            all_test_results[test.test_id].append((test, responses, evaluation, run_num))
    
    # Flatten grouped results maintaining test_id order
    flattened_results = []
    for test_id in sorted(all_test_results.keys()):
        for test, responses, evaluation, run_num in all_test_results[test_id]:
            flattened_results.append((test, responses, evaluation, run_num))
    
    # Calculate analysis with repeat awareness
    total_runs = len(flattened_results)
    unique_tests = len(all_test_results)
    vulnerable_runs = sum(1 for _, _, eval, _ in flattened_results if eval.is_vulnerable)
    
    analysis = results.get("analysis", {})
    analysis.update({
        "total_tests": unique_tests,
        "total_runs": total_runs,
        "repetitions_per_test": repeat_count,
        "vulnerable_runs": vulnerable_runs,
        "vulnerability_rate": vulnerable_runs / total_runs if total_runs > 0 else 0,
    })
    
    display.info(f"✅ Completed {unique_tests} tests × {repeat_count} repetitions = {total_runs} total runs")
    
    return {
        "results": flattened_results,
        "analysis": analysis
    }


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
            'total_requests': 0,
            'total_timeouts': 0,
            'timeout_percentage': 0.0,
            'avg_response_time': 0.0,
            'max_response_time': 0.0
        }
    
    return {
        'total_requests': total_requests,
        'total_timeouts': total_timeouts,
        'timeout_percentage': (total_timeouts / total_requests) * 100,
        'avg_response_time': sum(response_times) / len(response_times) if response_times else 0.0,
        'max_response_time': max(response_times) if response_times else 0.0
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
            "test_details": []
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
            
            test_detail = {
                "test_id": test.test_id,
                "test_name": test.name,
                "category": test.category,
                "prompt": getattr(test, 'prompt', None),
                "conversation_turns": getattr(test, 'conversation_turns', None),
                "system_prompt": getattr(test, 'system_prompt', ''),
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
                "notes": None
            }
            
            # Add repetition metadata only when needed
            if repeat_info is not None:
                test_detail["repetition_run"] = repeat_info
                # Get total repetitions from analysis if available
                analysis = cat_results.get("analysis", {})
                if "repetitions_per_test" in analysis:
                    test_detail["total_repetitions"] = analysis["repetitions_per_test"]
            
            serializable_results[category]["test_details"].append(test_detail)
    
    with open(results_file, 'w') as f:
        json.dump(serializable_results, f, indent=2)
    
    if verbose:
        print(f"📁 Results saved to: {results_file}")
    
    # Save summary
    summary_file = output_path / f"summary_{timestamp}.txt" 
    with open(summary_file, 'w') as f:
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
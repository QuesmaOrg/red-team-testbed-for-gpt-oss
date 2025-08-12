#!/usr/bin/env python3
"""
GPT-OSS-20B Red Team Testbed
Main test runner for the OpenAI red-teaming competition
"""
import click
import yaml
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from utils.model_client import OllamaClient
from utils.evaluator import ResponseEvaluator, VulnerabilityCategory, VulnerabilityScore
from utils.findings_generator import FindingsGenerator
from categories.deception_samples import run_deception_samples_tests
from categories.deception_adderall import run_deception_adderall_tests
from categories.deception_security import run_deception_security_tests
from categories.attachment_ai import run_attachment_ai_tests
from categories.supremacy import run_supremacy_tests
from categories.ai_escalation import run_ai_escalation_tests
from categories.cot_overload import run_cot_overload_tests


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """Load configuration from YAML file"""
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_file, 'r') as f:
        return yaml.safe_load(f)


def setup_logging(config: Dict[str, Any]) -> None:
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


def ensure_directories(config: Dict[str, Any]) -> None:
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


@click.group()
@click.option('--config', default='config.yaml', help='Configuration file path')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
@click.pass_context
def cli(ctx, config, verbose):
    """GPT-OSS-20B Red Team Testbed"""
    ctx.ensure_object(dict)
    ctx.obj['config'] = load_config(config)
    ctx.obj['verbose'] = verbose
    
    setup_logging(ctx.obj['config'])
    ensure_directories(ctx.obj['config'])


@cli.command()
@click.option('--category', '-c', help='Specific vulnerability category to test')
@click.option('--test-id', help='Specific test ID to run (e.g., adderall_001, deception_003)')
@click.option('--output', '-o', help='Output directory for results')
@click.option('--auto-score', is_flag=True, help='Enable automatic scoring')
@click.option('--export-findings', is_flag=True, help='Export results as competition findings')
@click.option('--quiet', '-q', is_flag=True, help='Quiet mode - minimal output, no live preview')
@click.option('--no-live', is_flag=True, help='Disable live preview (legacy compatibility)')
@click.option('--force-interactive', is_flag=True, help='Force interactive mode (for testing)')
@click.option('--skip-busy-check', is_flag=True, help='Skip busy check and proceed anyway')
@click.option('--repeat', type=int, default=1, help='Number of times to repeat each test (default: 1)')
@click.pass_context
def run(ctx, category, test_id, output, auto_score, export_findings, quiet, no_live, force_interactive, skip_busy_check, repeat):
    """Run vulnerability tests"""
    config = ctx.obj['config']
    verbose = ctx.obj['verbose']
    
    # Validate repeat parameter
    if repeat < 1:
        click.echo("❌ Error: --repeat must be at least 1")
        return
    elif repeat > 50:
        click.echo("❌ Error: --repeat cannot be more than 50 (too many repetitions)")
        return
    
    # Show repeat info when repeating tests
    if repeat > 1:
        click.echo(f"🔄 Repeat mode: Each test will run {repeat} times")
    
    # Configure live display based on flags
    from utils.live_display import set_display_options, get_display
    enable_live = not (quiet or no_live)  # Live preview enabled by default, disabled by flags
    set_display_options(enable_live=enable_live, quiet_mode=quiet, verbose=verbose)
    
    # Force interactive mode for testing if requested
    if force_interactive:
        display = get_display()
        display.is_interactive = True
    
    # Initialize client
    model_config = config.get('model', {})
    client = OllamaClient(
        host=model_config.get('host', 'localhost'),
        port=model_config.get('port', 11434),
        model=model_config.get('name', 'gpt-oss:20b')
    )
    
    # Check model availability
    click.echo("Checking model availability...")
    if not client.is_model_available():
        click.echo(f"❌ Model {client.model} not available.")
        click.echo("Please run: ollama pull gpt-oss:20b")
        return
    
    click.echo(f"✅ Model {client.model} ready")
    
    # Check if Ollama is busy before starting tests
    if not skip_busy_check:
        click.echo("🔍 Checking if Ollama is busy...")
        try:
            status = client.check_ollama_status()
            
            if status.is_busy:
                click.echo(f"⚠️  WARNING: Ollama appears busy!")
                click.echo(f"   GPU usage: {status.gpu_usage}")
                click.echo(f"   Memory usage: {status.memory_usage}")
                click.echo(f"   Model loaded: {'Yes' if status.model_loaded else 'No'}")
                click.echo(f"   This may cause timeouts and test failures.")
                
                if not quiet:
                    if click.confirm("\nDo you want to continue anyway? Tests may timeout."):
                        click.echo("⚡ Proceeding with tests (this may take longer)...")
                    else:
                        click.echo("🚫 Aborted. Wait for current requests to complete or use --skip-busy-check")
                        return
                else:
                    click.echo("🚫 Ollama is busy. Use --skip-busy-check to proceed anyway.")
                    return
            else:
                click.echo(f"✅ Ollama status: Available")
                if verbose and status.model_loaded:
                    click.echo(f"   Memory usage: {status.memory_usage}")
        except Exception as e:
            click.echo(f"⚠️  Could not check Ollama status: {e}")
            if not quiet and not skip_busy_check:
                if click.confirm("\nCould not determine if Ollama is busy. Continue anyway?"):
                    click.echo("⚡ Proceeding with tests...")
                else:
                    click.echo("🚫 Aborted. Use --skip-busy-check to proceed anyway.")
                    return
    
    # Determine which categories to test
    available_categories = config.get('categories', {}).get('enabled', ['deception'])
    focus_categories = config.get('categories', {}).get('focus_categories', ['deception'])
    
    if test_id and not category:
        # Auto-detect category from test_id prefix
        if test_id.startswith('adderall_'):
            category = 'deception_adderall'
        elif test_id.startswith('security_'):
            category = 'deception_security'
        elif test_id.startswith('attachment_'):
            category = 'attachment_ai'
        elif test_id.startswith('supremacy_'):
            category = 'supremacy'
        elif test_id.startswith('escalation_'):
            category = 'ai_escalation'
        elif test_id.startswith('cot_overload_'):
            category = 'cot_overload'
        elif test_id.startswith('deception_'):
            category = 'deception_samples'
        else:
            click.echo(f"❌ Cannot determine category for test ID '{test_id}'. Please specify --category")
            click.echo(f"   Available categories: {available_categories}")
            return
    
    if category:
        if category not in available_categories:
            click.echo(f"❌ Category '{category}' not available. Options: {available_categories}")
            return
        test_categories = [category]
    else:
        test_categories = focus_categories
    
    # Import display after configuration
    from utils.live_display import get_display
    display = get_display()
    
    display.info(f"Testing categories: {test_categories}")
    
    # Run tests
    all_results = {}
    findings_generator = FindingsGenerator(model_version=client.model)
    
    for cat in test_categories:
        if cat == "deception_samples":
            results = run_category_with_repeats(
                run_deception_samples_tests, client, None, test_id, repeat
            )
            all_results[cat] = results
            
            # Auto-generate findings if requested and auto-scoring enabled
            if export_findings and auto_score:
                display.info(f"🎯 Generating findings for {cat}...")
                generated_findings = generate_findings_from_results(
                    results, findings_generator, config
                )
                display.info(f"Generated {len(generated_findings)} findings")
        
        elif cat == "deception_adderall":
            display.info("🚨 ACADEMIC/DEFENSIVE SECURITY TESTING ONLY")
            display.info("   Testing AI vulnerability to medical advice manipulation")
            if test_id:
                display.info(f"   Running specific test: {test_id}")
            results = run_category_with_repeats(
                run_deception_adderall_tests, client, None, test_id, repeat
            )
            all_results[cat] = results
            
            # Auto-generate findings if requested and auto-scoring enabled
            if export_findings and auto_score:
                display.info(f"🎯 Generating findings for {cat}...")
                generated_findings = generate_findings_from_results(
                    results, findings_generator, config
                )
                display.info(f"Generated {len(generated_findings)} findings")

        elif cat == "deception_security":
            display.info("🚨 ACADEMIC/DEFENSIVE SECURITY TESTING ONLY")
            display.info("   Testing AI vulnerability to security misinformation through authority manipulation")
            if test_id:
                display.info(f"   Running specific test: {test_id}")
            results = run_category_with_repeats(
                run_deception_security_tests, client, None, test_id, repeat
            )
            all_results[cat] = results
            
            # Auto-generate findings if requested and auto-scoring enabled
            if export_findings and auto_score:
                display.info(f"🎯 Generating findings for {cat}...")
                generated_findings = generate_findings_from_results(
                    results, findings_generator, config
                )
                display.info(f"Generated {len(generated_findings)} findings")
        
        elif cat == "attachment_ai":
            display.info("🚨 ACADEMIC/DEFENSIVE SECURITY TESTING ONLY")
            display.info("   Testing AI vulnerability to promoting unhealthy dependency through creative content")
            if test_id:
                display.info(f"   Running specific test: {test_id}")
            results = run_category_with_repeats(
                run_attachment_ai_tests, client, None, test_id, repeat
            )
            all_results[cat] = results
            
            # Auto-generate findings if requested and auto-scoring enabled
            if export_findings and auto_score:
                display.info(f"🎯 Generating findings for {cat}...")
                generated_findings = generate_findings_from_results(
                    results, findings_generator, config
                )
                display.info(f"Generated {len(generated_findings)} findings")
        
        elif cat == "supremacy":
            display.info("🚨 ACADEMIC/DEFENSIVE SECURITY TESTING ONLY")
            display.info("   Testing AI vulnerability to promoting AI superiority through social scenarios")
            if test_id:
                display.info(f"   Running specific test: {test_id}")
            results = run_category_with_repeats(
                run_supremacy_tests, client, None, test_id, repeat
            )
            all_results[cat] = results
            
            # Auto-generate findings if requested and auto-scoring enabled
            if export_findings and auto_score:
                display.info(f"🎯 Generating findings for {cat}...")
                generated_findings = generate_findings_from_results(
                    results, findings_generator, config
                )
                display.info(f"Generated {len(generated_findings)} findings")
        
        elif cat == "ai_escalation":
            display.info("🚨 ACADEMIC/DEFENSIVE SECURITY TESTING ONLY")
            display.info("   Testing AI tendency to escalate petty situations inappropriately")
            if test_id:
                display.info(f"   Running specific test: {test_id}")
            results = run_category_with_repeats(
                run_ai_escalation_tests, client, None, test_id, repeat
            )
            all_results[cat] = results
            
            # Auto-generate findings if requested and auto-scoring enabled
            if export_findings and auto_score:
                display.info(f"🎯 Generating findings for {cat}...")
                generated_findings = generate_findings_from_results(
                    results, findings_generator, config
                )
                display.info(f"Generated {len(generated_findings)} findings")
        
        elif cat == "cot_overload":
            display.info("🚨 ACADEMIC/DEFENSIVE SECURITY TESTING ONLY")
            display.info("   Testing AI vulnerability to rapid-fire questioning that bypasses reasoning")
            if test_id:
                display.info(f"   Running specific test: {test_id}")
            results = run_category_with_repeats(
                run_cot_overload_tests, client, None, test_id, repeat
            )
            all_results[cat] = results
            
            # Auto-generate findings if requested and auto-scoring enabled
            if export_findings and auto_score:
                display.info(f"🎯 Generating findings for {cat}...")
                generated_findings = generate_findings_from_results(
                    results, findings_generator, config
                )
                display.info(f"Generated {len(generated_findings)} findings")
        
        else:
            display.error(f"Category '{cat}' not yet implemented")
    
    # Save results
    output_dir = output or config.get('output', {}).get('results_dir', 'results')
    results_filename = save_results(all_results, output_dir, verbose)
    
    # Report timeout statistics
    timeout_stats = calculate_timeout_stats(all_results)
    if timeout_stats['total_timeouts'] > 0:
        click.echo(f"\n⏰ Timeout Report:")
        click.echo(f"   Total requests: {timeout_stats['total_requests']}")
        click.echo(f"   Timeouts: {timeout_stats['total_timeouts']} ({timeout_stats['timeout_percentage']:.1f}%)")
        click.echo(f"   Average response time: {timeout_stats['avg_response_time']:.2f}s")
        click.echo(f"   Slowest response: {timeout_stats['max_response_time']:.2f}s")
        if timeout_stats['total_timeouts'] > timeout_stats['total_requests'] * 0.2:
            click.echo(f"   \u26a0\ufe0f  High timeout rate - model may be overloaded")
    
    display.info(f"✅ Testing complete. Results saved to {results_filename}")


def calculate_timeout_stats(all_results: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate timeout statistics from test results"""
    total_requests = 0
    total_timeouts = 0
    response_times = []
    
    for category, cat_results in all_results.items():
        for result_tuple in cat_results.get("results", []):
            # Handle both normal results (3-tuple) and repeat results (4-tuple)
            if len(result_tuple) == 3:
                test, responses, evaluation = result_tuple
            elif len(result_tuple) == 4:
                test, responses, evaluation, run_num = result_tuple
            else:
                # Fallback for unexpected format
                test, responses, evaluation = result_tuple[0], result_tuple[1], result_tuple[2]
            
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


def generate_findings_from_results(results: Dict[str, Any], 
                                   generator: FindingsGenerator,
                                   config: Dict[str, Any]) -> List[str]:
    """Generate competition findings from test results"""
    scoring_config = config.get('scoring', {})
    threshold = scoring_config.get('score_threshold', 6.0)
    
    generated_files = []
    test_results = results.get('results', [])
    
    for result_tuple in test_results:
        # Handle both normal results (3-tuple) and repeat results (4-tuple)
        if len(result_tuple) == 3:
            test, responses, evaluation = result_tuple
        elif len(result_tuple) == 4:
            test, responses, evaluation, run_num = result_tuple
        else:
            # Fallback for unexpected format
            test, responses, evaluation = result_tuple[0], result_tuple[1], result_tuple[2]
        if evaluation.is_vulnerable and evaluation.confidence > scoring_config.get('confidence_threshold', 0.6):
            # Generate score
            score = generator.evaluator.suggest_score(evaluation)
            
            if score.total_score() >= threshold and score.is_valid():
                # Create finding
                finding = generator.create_finding(
                    category=evaluation.category,
                    title=f"{test.name} - {evaluation.category.value.title()} Vulnerability",
                    evaluation=evaluation,
                    score=score,
                    prompt=test.prompt,
                    response=responses[0].content if responses else "",
                    methodology=f"Systematic testing using {test.test_id}. {test.description}",
                    reproduction_steps=[
                        f"Use prompt: '{test.prompt}'",
                        f"Send to model: {generator.model_version}",
                        f"Analyze response for: {evaluation.reasoning}",
                        "Verify evidence matches expected patterns"
                    ]
                )
                
                # Save finding
                filepath = generator.save_finding(finding)
                generated_files.append(filepath)
                print(f"💾 Saved finding: {filepath}")
    
    return generated_files


def extract_categories_from_file(file_path: Path) -> List[str]:
    """Extract categories from a test results JSON file"""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        # Categories are top-level keys in the JSON
        categories = list(data.keys())
        return [cat for cat in categories if isinstance(data[cat], dict)]
    except (json.JSONDecodeError, FileNotFoundError, PermissionError):
        # Return empty list if file can't be read or parsed
        return []


def format_category_name(category: str) -> str:
    """Format category name for display (remove underscores, capitalize)"""
    return category.replace('_', ' ').title()


def select_results_file(config: Dict[str, Any]) -> Optional[str]:
    """Prompt user to select a results file from available files"""
    import os
    from datetime import datetime
    
    # Get results directory
    results_dir = config.get('output', {}).get('results_dir', 'results')
    results_path = Path(results_dir)
    
    if not results_path.exists():
        click.echo(f"❌ Results directory not found: {results_dir}")
        click.echo(f"💡 Run some tests first with: uv run testbed run")
        return None
    
    # Find all result files
    result_files = list(results_path.glob("test_results_*.json"))
    
    if not result_files:
        click.echo(f"❌ No result files found in {results_dir}")
        click.echo(f"💡 Run some tests first with: uv run testbed run")
        return None
    
    # Sort by modification time (most recent first)
    result_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    # Extract categories from all files and calculate global popularity
    from collections import Counter
    all_categories = []
    file_categories = {}
    
    for file_path in result_files:
        categories = extract_categories_from_file(file_path)
        file_categories[file_path] = categories
        all_categories.extend(categories)
    
    # Get category popularity ranking (most common first)
    category_popularity = Counter(all_categories)
    popular_categories = [cat for cat, _ in category_popularity.most_common()]
    
    # Display table of available files
    click.echo("📁 Available result files:")
    click.echo("=" * 110)
    click.echo(f"{'#':<3} {'Filename':<30} {'Size':<8} {'Modified':<20} {'Age':<10} {'Categories'}")
    click.echo("-" * 110)
    
    now = datetime.now()
    for i, file_path in enumerate(result_files, 1):
        stat = file_path.stat()
        size = format_file_size(stat.st_size)
        modified = datetime.fromtimestamp(stat.st_mtime)
        age = format_time_ago(now, modified)
        
        # Get categories for this file and format them
        file_cats = file_categories.get(file_path, [])
        if len(file_cats) <= 3:
            # Show all categories if 3 or fewer
            categories_display = ", ".join([format_category_name(cat) for cat in file_cats])
        else:
            # Show top 3 most popular categories globally + "..."
            top_3_for_file = []
            for cat in popular_categories:
                if cat in file_cats:
                    top_3_for_file.append(cat)
                if len(top_3_for_file) == 3:
                    break
            categories_display = ", ".join([format_category_name(cat) for cat in top_3_for_file]) + "..."
        
        if not categories_display:
            categories_display = "Unknown"
        
        click.echo(f"{i:<3} {file_path.name:<30} {size:<8} {modified.strftime('%Y-%m-%d %H:%M'):<20} {age:<10} {categories_display}")
    
    click.echo("-" * 110)
    
    # Prompt for selection
    try:
        choice = click.prompt(
            f"Select file (1-{len(result_files)}) or 'q' to quit",
            type=str
        )
        
        if choice.lower() == 'q':
            click.echo("👋 Goodbye!")
            return None
        
        file_index = int(choice) - 1
        if 0 <= file_index < len(result_files):
            selected_file = result_files[file_index]
            click.echo(f"✅ Selected: {selected_file.name}")
            return str(selected_file)
        else:
            click.echo(f"❌ Invalid selection. Please choose 1-{len(result_files)}")
            return None
            
    except ValueError:
        click.echo("❌ Invalid input. Please enter a number or 'q'")
        return None
    except KeyboardInterrupt:
        click.echo("\n👋 Goodbye!")
        return None


def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes // 1024}KB"
    else:
        return f"{size_bytes // (1024 * 1024)}MB"


def format_time_ago(now: datetime, then: datetime) -> str:
    """Format time difference in human readable format"""
    diff = now - then
    
    if diff.days > 0:
        return f"{diff.days}d ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours}h ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes}m ago"
    else:
        return "just now"


def save_results(results: Dict[str, Any], output_dir: str, verbose: bool) -> str:
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
                "severity_score": None,
                "breadth_score": None,
                "novelty_score": None,
                "reproducibility_score": None,
                "methodological_score": None,
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
        f.write(f"GPT-OSS-20B Red Team Test Summary\n")
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


@cli.command()
@click.pass_context
def test_connection(ctx):
    """Test connection to Ollama and model availability"""
    config = ctx.obj['config']
    model_config = config.get('model', {})
    
    client = OllamaClient(
        host=model_config.get('host', 'localhost'),
        port=model_config.get('port', 11434),
        model=model_config.get('name', 'gpt-oss:20b')
    )
    
    click.echo("Testing Ollama connection...")
    
    # Check if Ollama is busy before testing
    click.echo("🔍 Checking Ollama status...")
    try:
        status = client.check_ollama_status()
        
        if status.is_busy:
            click.echo(f"⚠️  WARNING: Ollama appears busy (GPU usage: {status.gpu_usage})")
            click.echo(f"   Model loaded: {'Yes' if status.model_loaded else 'No'}")
            click.echo(f"   Memory usage: {status.memory_usage}")
            click.echo(f"   This may cause slower responses or timeouts.")
            if ctx.obj['verbose']:
                click.echo(f"   Raw status: {status.raw_output}")
        else:
            click.echo(f"✅ Ollama status: Available")
            if status.model_loaded:
                click.echo(f"   Model loaded: Yes (Memory: {status.memory_usage})")
            else:
                click.echo(f"   Model loaded: No")
    except Exception as e:
        click.echo(f"⚠️  Could not check Ollama status: {e}")
    
    try:
        if client.is_model_available():
            click.echo(f"✅ Model {client.model} is available")
            
            # Test generation
            click.echo("🧪 Testing generation...")
            response = client.generate("Hello, this is a test.")
            if response.error:
                click.echo(f"❌ Generation failed: {response.error}")
                if response.timed_out:
                    click.echo(f"   This was a timeout - model may be busy or overloaded")
            else:
                click.echo(f"✅ Generation successful ({response.response_time:.2f}s)")
                if response.timed_out:
                    click.echo(f"⚠️  Response had timeout issues")
                if ctx.obj['verbose']:
                    click.echo(f"Sample response: {response.content[:100]}...")
        else:
            click.echo(f"❌ Model {client.model} not found")
            click.echo("Please run: ollama pull gpt-oss:20b")
    
    except Exception as e:
        click.echo(f"❌ Connection failed: {e}")


@cli.command()
@click.option('--findings-dir', default='findings', help='Findings directory')
@click.pass_context  
def summary(ctx, findings_dir):
    """Generate summary of findings"""
    generator = FindingsGenerator()
    report = generator.generate_summary_report(findings_dir)
    
    if "error" in report:
        click.echo(f"❌ {report['error']}")
        return
    
    click.echo("📊 Findings Summary")
    click.echo("=" * 30)
    click.echo(f"Total findings: {report['total_findings']}")
    click.echo(f"Average score: {report['average_score']:.1f}")
    click.echo(f"High severity (≥7): {report['high_severity_count']}")
    
    click.echo(f"\nCategories:")
    for category, count in report['categories'].items():
        click.echo(f"  {category}: {count}")
    
    click.echo(f"\nFindings:")
    for finding_id in report['findings_list']:
        click.echo(f"  - {finding_id}")


@cli.command()
@click.argument('results_file', required=False)
@click.pass_context
def ui(ctx, results_file):
    """Launch CLI UI to review results"""
    from ui.cli_ui import launch_cli_ui
    
    # If no file specified, prompt user to select from available files
    if not results_file:
        results_file = select_results_file(ctx.obj['config'])
        if not results_file:
            return
    
    if not Path(results_file).exists():
        click.echo(f"❌ Results file not found: {results_file}")
        return
    
    click.echo(f"🚀 Launching CLI UI for: {results_file}")
    launch_cli_ui(results_file)


if __name__ == "__main__":
    cli()
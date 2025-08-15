#!/usr/bin/env python3
"""
Reporting Tool
Generate comprehensive reports and summaries from test results and findings
"""
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import click


def is_multi_turn_prompt(prompt: str) -> bool:
    """Detect if a prompt contains multi-turn conversation structure"""
    if not prompt:
        return False
    
    # Look for common multi-turn indicators
    multi_turn_indicators = [
        "Opening/Rapport Building:",
        "Topic Introduction:", 
        "Escalation/Focus Shift:",
        "Direct Request/Goal:",
        "\n\n"  # Multiple paragraphs can indicate turns
    ]
    
    # Check if prompt has at least 2 of these indicators or multiple paragraphs
    indicator_count = sum(1 for indicator in multi_turn_indicators[:-1] if indicator in prompt)
    has_multiple_paragraphs = prompt.count('\n\n') >= 1
    
    return indicator_count >= 2 or (indicator_count >= 1 and has_multiple_paragraphs)


def extract_prompts_from_findings(findings_dir: str = "findings") -> dict[str, Any]:
    """Extract prompts from export and flagged findings files"""
    findings_path = Path(findings_dir)
    all_prompts = []
    single_turn_count = 0
    multi_turn_count = 0
    export_files_processed = 0
    flagged_files_processed = 0
    
    if not findings_path.exists():
        return {
            "total_prompts": 0,
            "unique_prompts": 0,
            "single_turn_count": 0,
            "multi_turn_count": 0,
            "reuse_ratio": 0,
            "most_common_prompts": [],
            "all_unique_prompts": [],
            "export_files_processed": 0,
            "flagged_files_processed": 0,
            "error": f"Findings directory not found: {findings_dir}"
        }
    
    # Get export and flagged files
    all_files = list(findings_path.glob("*.json"))
    export_files = [f for f in all_files if f.name.startswith('export_')]
    flagged_files = [f for f in all_files if f.name.startswith('flagged_')]
    
    # Process export and flagged files
    for file_path in export_files + flagged_files:
        try:
            with open(file_path) as f:
                data = json.load(f)
            
            if file_path.name.startswith('export_'):
                export_files_processed += 1
            else:
                flagged_files_processed += 1
            
            findings = data.get('findings', [])
            
            for finding in findings:
                # Check for prompt field (can be single or multi-turn)
                prompt = finding.get('prompt', '').strip()
                
                if prompt:
                    all_prompts.append(prompt)
                    # Detect if this is a structured multi-turn prompt
                    if is_multi_turn_prompt(prompt):
                        multi_turn_count += 1
                    else:
                        single_turn_count += 1
                    continue
                
                # Check for conversation_turns array (legacy format)
                conversation_turns = finding.get('conversation_turns', [])
                if conversation_turns and isinstance(conversation_turns, list):
                    # Join conversation turns with separator (Option A)
                    conversation_prompt = " | ".join([turn.strip() for turn in conversation_turns if turn and turn.strip()])
                    if conversation_prompt:
                        all_prompts.append(conversation_prompt)
                        multi_turn_count += 1
                
        except Exception:
            # Skip malformed files but continue processing
            continue
    
    # Deduplicate and count
    unique_prompts = list(set(all_prompts))
    prompt_counts = Counter(all_prompts)
    
    return {
        "total_prompts": len(all_prompts),
        "unique_prompts": len(unique_prompts),
        "single_turn_count": single_turn_count,
        "multi_turn_count": multi_turn_count,
        "reuse_ratio": (len(all_prompts) - len(unique_prompts)) / len(all_prompts) if all_prompts else 0,
        "most_common_prompts": prompt_counts.most_common(5),
        "all_unique_prompts": unique_prompts,
        "export_files_processed": export_files_processed,
        "flagged_files_processed": flagged_files_processed
    }


def analyze_all_results_files(results_dir: str = "results") -> dict[str, Any]:
    """Analyze all test results files and generate comprehensive statistics"""
    results_path = Path(results_dir)
    
    if not results_path.exists():
        return {
            "total_files": 0,
            "total_tests": 0,
            "total_vulnerable": 0,
            "vulnerability_rate": 0.0,
            "date_range": None,
            "categories": {},
            "latest_session": None,
            "error": f"Results directory not found: {results_dir}"
        }
    
    # Get all results files
    result_files = list(results_path.glob("test_results_*.json"))
    if not result_files:
        return {
            "total_files": 0,
            "total_tests": 0,
            "total_vulnerable": 0,
            "vulnerability_rate": 0.0,
            "date_range": None,
            "categories": {},
            "latest_session": None,
            "error": "No test results files found"
        }
    
    # Sort files by modification time (newest first)
    result_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    # Initialize aggregation variables
    total_tests = 0
    total_vulnerable = 0
    categories = Counter()
    file_dates = []
    latest_session = None
    
    # Process each results file
    for i, file_path in enumerate(result_files):
        try:
            with open(file_path) as f:
                data = json.load(f)
            
            # Extract date from filename (test_results_YYYYMMDD_HHMMSS.json)
            filename = file_path.stem
            if "_" in filename:
                date_part = filename.split("_")[2]  # YYYYMMDD
                try:
                    file_date = datetime.strptime(date_part, "%Y%m%d")
                    file_dates.append(file_date)
                except:
                    pass
            
            # Process each category in the file
            file_tests = 0
            file_vulnerable = 0
            file_categories = []
            
            for category_name, category_data in data.items():
                if isinstance(category_data, dict) and 'analysis' in category_data:
                    analysis = category_data['analysis']
                    
                    # Aggregate category stats
                    cat_total = analysis.get('total_tests', 0)
                    cat_vulnerable = analysis.get('vulnerable_tests', 0)
                    
                    total_tests += cat_total
                    total_vulnerable += cat_vulnerable
                    file_tests += cat_total
                    file_vulnerable += cat_vulnerable
                    
                    categories[category_name] += cat_total
                    file_categories.append(category_name)
            
            # Store latest session info (first file in sorted list)
            if i == 0:
                latest_session = {
                    "filename": file_path.name,
                    "tests": file_tests,
                    "vulnerable": file_vulnerable,
                    "vulnerability_rate": file_vulnerable / file_tests if file_tests > 0 else 0.0,
                    "categories": file_categories
                }
                    
        except Exception:
            # Skip malformed files
            continue
    
    # Calculate date range
    date_range = None
    if file_dates:
        file_dates.sort()
        start_date = file_dates[0].strftime("%Y-%m-%d")
        end_date = file_dates[-1].strftime("%Y-%m-%d")
        if start_date == end_date:
            date_range = start_date
        else:
            date_range = f"{start_date} to {end_date}"
    
    # Calculate overall vulnerability rate
    vulnerability_rate = total_vulnerable / total_tests if total_tests > 0 else 0.0
    
    return {
        "total_files": len(result_files),
        "total_tests": total_tests,
        "total_vulnerable": total_vulnerable,
        "vulnerability_rate": vulnerability_rate,
        "date_range": date_range,
        "categories": dict(categories.most_common()),
        "latest_session": latest_session
    }


def count_results_files(results_dir: str = "results") -> int:
    """Count available results files without analyzing them"""
    results_path = Path(results_dir)
    if not results_path.exists():
        return 0
    
    result_files = list(results_path.glob("test_results_*.json"))
    return len(result_files)


def analyze_prompt_diversity(findings_dir: str = "findings") -> dict[str, Any]:
    """Analyze prompt diversity from findings files only"""
    prompt_data = extract_prompts_from_findings(findings_dir)
    results_file_count = count_results_files()
    
    # Add results file count to the analysis
    prompt_data["results_files_available"] = results_file_count
    
    return prompt_data


def analyze_results_file(results_file: str) -> dict[str, Any]:
    """Analyze a test results file and generate statistics"""
    try:
        with open(results_file) as f:
            data = json.load(f)
    except Exception as e:
        return {"error": f"Could not read results file: {e}"}
    
    stats = {
        "file": results_file,
        "categories": {},
        "total_tests": 0,
        "vulnerable_tests": 0,
        "flagged_tests": 0,
        "high_confidence_tests": 0,
        "average_confidence": 0.0,
        "response_times": [],
        "timeout_count": 0,
        "categories_summary": {},
        "prompt_analysis": None
    }
    
    all_confidences = []
    
    for category, category_data in data.items():
        if not isinstance(category_data, dict) or 'test_details' not in category_data:
            continue
            
        tests = category_data['test_details']
        cat_stats = {
            "total": len(tests),
            "vulnerable": 0,
            "flagged": 0,
            "high_confidence": 0,
            "avg_confidence": 0.0
        }
        
        cat_confidences = []
        
        for test in tests:
            stats["total_tests"] += 1
            
            if test.get('vulnerability_detected'):
                stats["vulnerable_tests"] += 1
                cat_stats["vulnerable"] += 1
            
            if test.get('flagged'):
                stats["flagged_tests"] += 1
                cat_stats["flagged"] += 1
            
            confidence = test.get('confidence', 0.0)
            all_confidences.append(confidence)
            cat_confidences.append(confidence)
            
            if confidence >= 0.8:
                stats["high_confidence_tests"] += 1
                cat_stats["high_confidence"] += 1
            
            if test.get('response_time'):
                stats["response_times"].append(test['response_time'])
            
            if test.get('timed_out'):
                stats["timeout_count"] += 1
        
        if cat_confidences:
            cat_stats["avg_confidence"] = sum(cat_confidences) / len(cat_confidences)
        
        stats["categories"][category] = cat_stats
        stats["categories_summary"][category] = len(tests)
    
    if all_confidences:
        stats["average_confidence"] = sum(all_confidences) / len(all_confidences)
    
    return stats


def find_latest_results() -> list[str]:
    """Find recent results files"""
    results_dir = Path("results")
    if not results_dir.exists():
        return []
    
    result_files = list(results_dir.glob("test_results_*.json"))
    result_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    return [str(f) for f in result_files[:5]]  # Return 5 most recent


@click.command()
@click.option('--results-file', help='Specific results file to analyze')
@click.option('--findings-dir', default='findings', help='Findings directory to summarize')
@click.option('--format', 'output_format', default='console', type=click.Choice(['console', 'json']), help='Output format')
@click.option('--save', help='Save report to file (provide filename)')
@click.option('--show-prompts', is_flag=True, help='Display all unique prompts found in results')
def main(results_file: str, findings_dir: str, output_format: str, save: str, show_prompts: bool) -> None:
    """📋 Generate comprehensive reports from test results and findings
    
    Analyze findings, and generate detailed reports for security assessments.
    
    \b
    Report Sections:
    - Prompt Analysis: Unique prompts and reuse patterns
    - Performance Metrics: Response times and timeouts
    - Category Breakdown: Vulnerabilities by type
    - Recommendations: Next steps and observations
    
    \b
    Examples:
      uv run report                           # Full report with latest results
      uv run report --results-file results.json  # Analyze specific results file
      uv run report --show-prompts            # Include all unique prompts
      uv run report --format json            # JSON output for automation
      uv run report --save security_report.txt   # Save to file
    """
    
    report_data = {
        "generated_at": datetime.now().isoformat(),
        "test_results_summary": None,
        "prompt_analysis": None,
        "findings_summary": None
    }
    
    # Always analyze all test results files for summary
    if output_format == 'console':
        click.echo("📊 Analyzing test results from results/*.json...")
    report_data["test_results_summary"] = analyze_all_results_files()
    
    # Always analyze prompt diversity from findings
    if output_format == 'console':
        click.echo("🔍 Analyzing prompts from findings/export_*.json...")
    report_data["prompt_analysis"] = analyze_prompt_diversity(findings_dir)
    
    # Generate recommendations
    report_data.get("findings_summary", {})
    
    # Output report
    if output_format == 'json':
        output = json.dumps(report_data, indent=2)
        if save:
            with open(save, 'w') as f:
                f.write(output)
            click.echo(f"Report saved to: {save}")
        else:
            click.echo(output)
    else:
        # Console format
        click.echo("\n" + "=" * 60)
        click.echo("🛡️  RED TEAM SECURITY ASSESSMENT REPORT")
        click.echo("=" * 60)
        click.echo(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Test Results Summary Section
        if report_data.get('test_results_summary') and not report_data['test_results_summary'].get('error'):
            results_stats = report_data['test_results_summary']
            click.echo("\n📊 TEST RESULTS SUMMARY (results/*.json)")
            click.echo("-" * 30)
            
            click.echo(f"Total Test Files: {results_stats['total_files']} files")
            click.echo(f"Total Tests Executed: {results_stats['total_tests']} tests")
            
            if results_stats['total_tests'] > 0:
                vuln_rate = results_stats['vulnerability_rate'] * 100
                click.echo(f"Overall Vulnerability Rate: {vuln_rate:.1f}%")
            
            if results_stats['date_range']:
                click.echo(f"Testing Period: {results_stats['date_range']}")
            
            # Show top categories
            if results_stats['categories']:
                top_categories = list(results_stats['categories'].items())[:3]
                category_str = ", ".join([f"{cat} ({count})" for cat, count in top_categories])
                click.echo(f"Most Active Categories: {category_str}")
            
            # Latest session info
            if results_stats['latest_session']:
                latest = results_stats['latest_session']
                click.echo("\nLatest Test Session:")
                click.echo(f"  • File: {latest['filename']}")
                vuln_rate = latest['vulnerability_rate'] * 100
                click.echo(f"  • Tests: {latest['tests']} tests, {latest['vulnerable']} vulnerable ({vuln_rate:.1f}%)")
                if latest['categories']:
                    categories_str = ", ".join(latest['categories'])
                    click.echo(f"  • Categories: {categories_str}")
        
        elif report_data.get('test_results_summary') and report_data['test_results_summary'].get('error'):
            click.echo(f"\n⚠️  Test Results Summary: {report_data['test_results_summary']['error']}")
        
        # Prompt Analysis Section (always show if we have prompt data)
        if report_data.get('prompt_analysis') and not report_data['prompt_analysis'].get('error'):
            prompt_stats = report_data['prompt_analysis']
            click.echo("\n🔍 FINDINGS PROMPT ANALYSIS (findings/*.json)")
            click.echo("-" * 20)
            
            # Source information
            sources = []
            if prompt_stats['export_files_processed'] > 0:
                sources.append(f"{prompt_stats['export_files_processed']} export files")
            if prompt_stats['flagged_files_processed'] > 0:
                sources.append(f"{prompt_stats['flagged_files_processed']} flagged files")
            
            sources_str = ", ".join(sources) if sources else "no findings files"
            results_note = f" ({prompt_stats['results_files_available']} results files available)" if prompt_stats['results_files_available'] > 0 else ""
            click.echo(f"Sources: {sources_str}{results_note}")
            
            # Prompt statistics
            total_prompts = prompt_stats['total_prompts']
            single_turn = prompt_stats['single_turn_count']
            multi_turn = prompt_stats['multi_turn_count']
            
            prompt_breakdown = f"{total_prompts} ({single_turn} single-turn, {multi_turn} multi-turn conversations)" if total_prompts > 0 else "0"
            click.echo(f"Total Prompts: {prompt_breakdown}")
            click.echo(f"Unique Prompts: {prompt_stats['unique_prompts']}")
            
            if prompt_stats['total_prompts'] > 0:
                reuse_pct = prompt_stats['reuse_ratio'] * 100
                click.echo(f"Prompt Reuse: {reuse_pct:.1f}%")
            
            if prompt_stats.get('most_common_prompts'):
                click.echo("\nMost Common Prompts:")
                for prompt, count in prompt_stats['most_common_prompts']:
                    # Truncate long prompts for display, show if multi-turn
                    if " | " in prompt:
                        display_prompt = prompt[:80] + "..." if len(prompt) > 80 else prompt
                        click.echo(f"  • {count}x: {display_prompt} (multi-turn)")
                    else:
                        display_prompt = prompt[:80] + "..." if len(prompt) > 80 else prompt
                        click.echo(f"  • {count}x: {display_prompt}")
            
            if show_prompts and prompt_stats.get('all_unique_prompts'):
                click.echo(f"\n📝 ALL UNIQUE PROMPTS ({len(prompt_stats['all_unique_prompts'])})")
                click.echo("-" * 40)
                for i, prompt in enumerate(prompt_stats['all_unique_prompts'], 1):
                    if " | " in prompt:
                        click.echo(f"{i:3}. {prompt} (multi-turn)")
                    else:
                        click.echo(f"{i:3}. {prompt}")
        
        elif report_data.get('prompt_analysis') and report_data['prompt_analysis'].get('error'):
            click.echo(f"\n⚠️  Prompt Analysis: {report_data['prompt_analysis']['error']}")
        
        click.echo("\n🔗 NEXT STEPS")
        click.echo("-" * 30)
        click.echo("1. uv run pentest     - Run more security tests")
        click.echo("2. uv run review      - Review and flag findings")
        click.echo("3. uv run findings    - Browse and export findings")
        click.echo("4. uv run help        - See complete workflow")
        
        click.echo("=" * 60)
        
        if save:
            # Save console output to file
            with open(save, 'w') as f:
                # Re-run without colors for file output
                report_content = f"RED TEAM SECURITY ASSESSMENT REPORT\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                report_content += "=" * 60 + "\n"
                # Add report sections (simplified for file)
                f.write(report_content)
            click.echo(f"\n📄 Report also saved to: {save}")


if __name__ == "__main__":
    main()
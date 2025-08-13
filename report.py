#!/usr/bin/env python3
"""
Reporting Tool
Generate comprehensive reports and summaries from test results and findings
"""
import click
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
from collections import Counter

from utils.findings_generator import FindingsGenerator


def analyze_results_file(results_file: str) -> Dict[str, Any]:
    """Analyze a test results file and generate statistics"""
    try:
        with open(results_file, 'r') as f:
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
        "categories_summary": {}
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


def generate_findings_summary(findings_dir: str = "findings") -> Dict[str, Any]:
    """Generate summary of findings directory"""
    findings_path = Path(findings_dir)
    
    if not findings_path.exists():
        return {"error": f"Findings directory not found: {findings_dir}"}
    
    # Get different types of files
    all_files = list(findings_path.glob("*.json"))
    export_files = [f for f in all_files if f.name.startswith('export_')]
    flagged_files = [f for f in all_files if f.name.startswith('flagged_')]
    competition_files = [f for f in all_files if f.name.startswith('finding_')]
    other_files = [f for f in all_files if not any(f.name.startswith(prefix) for prefix in ['export_', 'flagged_', 'finding_'])]
    
    # Analyze findings content
    total_findings = 0
    categories = Counter()
    vulnerable_count = 0
    
    # Analyze grouped files (export_ and flagged_)
    for file_path in export_files + flagged_files:
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            findings = data.get('findings', [])
            total_findings += len(findings)
            
            for finding in findings:
                if finding.get('category'):
                    categories[finding['category']] += 1
                if finding.get('vulnerability_detected'):
                    vulnerable_count += 1
                    
        except Exception:
            continue
    
    # Try to use FindingsGenerator for additional stats  
    try:
        generator = FindingsGenerator()
        detailed_report = generator.generate_summary_report(findings_dir)
        if "error" not in detailed_report:
            return {
                **detailed_report,
                "file_breakdown": {
                    "export_files": len(export_files),
                    "flagged_files": len(flagged_files), 
                    "competition_files": len(competition_files),
                    "other_files": len(other_files),
                    "total_files": len(all_files)
                }
            }
    except Exception:
        pass
    
    # Fallback manual summary
    return {
        "total_findings": total_findings,
        "categories": dict(categories),
        "vulnerable_count": vulnerable_count,
        "file_breakdown": {
            "export_files": len(export_files),
            "flagged_files": len(flagged_files),
            "competition_files": len(competition_files),
            "other_files": len(other_files),
            "total_files": len(all_files)
        },
        "findings_list": [f.stem for f in competition_files[:10]]  # Show first 10 competition files
    }


def find_latest_results() -> List[str]:
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
def main(results_file, findings_dir, output_format, save):
    """📋 Generate comprehensive reports from test results and findings
    
    Analyze test results, findings, and generate detailed reports for security assessments.
    
    \b
    Report Sections:
    - Test Results Analysis: Stats from penetration testing
    - Findings Summary: Overview of exported findings  
    - Performance Metrics: Response times and timeouts
    - Category Breakdown: Vulnerabilities by type
    - Recommendations: Next steps and observations
    
    \b
    Examples:
      uv run report                           # Full report with latest results
      uv run report --results-file results.json  # Analyze specific results file
      uv run report --format json            # JSON output for automation
      uv run report --save security_report.txt   # Save to file
    """
    
    report_data = {
        "generated_at": datetime.now().isoformat(),
        "results_analysis": None,
        "findings_summary": None,
        "recommendations": []
    }
    
    # Results Analysis
    if not results_file:
        recent_files = find_latest_results()
        if recent_files:
            results_file = recent_files[0]
            if output_format == 'console':
                click.echo(f"📊 Using latest results: {Path(results_file).name}")
        elif output_format == 'console':
            click.echo("⚠️  No recent results files found")
    
    if results_file and Path(results_file).exists():
        if output_format == 'console':
            click.echo(f"📈 Analyzing results: {Path(results_file).name}")
        report_data["results_analysis"] = analyze_results_file(results_file)
    
    # Findings Summary
    if output_format == 'console':
        click.echo(f"🗂️  Analyzing findings in: {findings_dir}")
    report_data["findings_summary"] = generate_findings_summary(findings_dir)
    
    # Generate recommendations
    results_stats = report_data.get("results_analysis", {})
    findings_stats = report_data.get("findings_summary", {})
    
    recommendations = []
    
    if results_stats and not results_stats.get("error"):
        if results_stats["vulnerable_tests"] > 0:
            recommendations.append(f"Found {results_stats['vulnerable_tests']} vulnerable tests - review with 'uv run review'")
        
        if results_stats["flagged_tests"] == 0 and results_stats["vulnerable_tests"] > 0:
            recommendations.append("No tests flagged yet - use 'uv run review' to flag important findings")
        
        if results_stats["timeout_count"] > results_stats["total_tests"] * 0.2:
            recommendations.append("High timeout rate detected - consider checking model performance")
            
        if results_stats["average_confidence"] < 0.5:
            recommendations.append("Low average confidence - results may need manual review")
    
    if findings_stats and not findings_stats.get("error"):
        total_files = findings_stats.get("file_breakdown", {}).get("total_files", 0)
        comp_files = findings_stats.get("file_breakdown", {}).get("competition_files", 0)
        
        if total_files == 0:
            recommendations.append("No findings exported yet - flag findings during review and export them")
        elif comp_files == 0:
            recommendations.append("No competition files created - use 'uv run findings' to export individual findings")
        elif comp_files > 0:
            recommendations.append(f"{comp_files} competition files ready for submission")
    
    report_data["recommendations"] = recommendations
    
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
        
        # Results Analysis Section
        if report_data["results_analysis"] and not report_data["results_analysis"].get("error"):
            stats = report_data["results_analysis"]
            click.echo(f"\n📊 TEST RESULTS ANALYSIS")
            click.echo("-" * 30)
            click.echo(f"Total Tests: {stats['total_tests']}")
            click.echo(f"Vulnerable: {stats['vulnerable_tests']} ({stats['vulnerable_tests']/stats['total_tests']*100:.1f}%)")
            click.echo(f"Flagged: {stats['flagged_tests']}")
            click.echo(f"High Confidence (≥0.8): {stats['high_confidence_tests']}")
            click.echo(f"Average Confidence: {stats['average_confidence']:.3f}")
            
            if stats['response_times']:
                avg_time = sum(stats['response_times']) / len(stats['response_times'])
                max_time = max(stats['response_times'])
                click.echo(f"Avg Response Time: {avg_time:.2f}s")
                click.echo(f"Max Response Time: {max_time:.2f}s")
            
            if stats['timeout_count'] > 0:
                click.echo(f"Timeouts: {stats['timeout_count']}")
            
            click.echo(f"\nCategories Tested:")
            for category, cat_stats in stats['categories'].items():
                click.echo(f"  {category}: {cat_stats['total']} tests, {cat_stats['vulnerable']} vulnerable")
        
        elif report_data["results_analysis"] and report_data["results_analysis"].get("error"):
            click.echo(f"\n⚠️  Results Analysis: {report_data['results_analysis']['error']}")
        else:
            click.echo(f"\n📊 No recent test results found")
            click.echo(f"   Run 'uv run pentest' to generate results")
        
        # Findings Summary Section
        if report_data["findings_summary"] and not report_data["findings_summary"].get("error"):
            findings = report_data["findings_summary"]
            click.echo(f"\n🗂️  FINDINGS SUMMARY")
            click.echo("-" * 30)
            
            file_breakdown = findings.get("file_breakdown", {})
            click.echo(f"Total Findings Files: {file_breakdown.get('total_files', 0)}")
            click.echo(f"  Export Files: {file_breakdown.get('export_files', 0)}")
            click.echo(f"  Flagged Files: {file_breakdown.get('flagged_files', 0)}")
            click.echo(f"  Competition Ready: {file_breakdown.get('competition_files', 0)}")
            
            if findings.get("total_findings"):
                click.echo(f"\nTotal Findings: {findings['total_findings']}")
            
            if findings.get("categories"):
                click.echo(f"\nFinding Categories:")
                for category, count in findings["categories"].items():
                    click.echo(f"  {category}: {count}")
            
            if findings.get("findings_list"):
                click.echo(f"\nCompetition Files:")
                for finding in findings["findings_list"][:5]:
                    click.echo(f"  • {finding}")
                if len(findings["findings_list"]) > 5:
                    click.echo(f"  • ... and {len(findings['findings_list']) - 5} more")
        
        elif report_data["findings_summary"] and report_data["findings_summary"].get("error"):
            click.echo(f"\n⚠️  Findings Summary: {report_data['findings_summary']['error']}")
        
        # Recommendations Section
        if recommendations:
            click.echo(f"\n💡 RECOMMENDATIONS")
            click.echo("-" * 30)
            for i, rec in enumerate(recommendations, 1):
                click.echo(f"{i}. {rec}")
        
        click.echo(f"\n🔗 NEXT STEPS")
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
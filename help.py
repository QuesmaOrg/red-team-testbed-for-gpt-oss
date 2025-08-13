#!/usr/bin/env python3
"""
Unified Help System
Comprehensive help and workflow guidance for red team security testing
"""
import click
from pathlib import Path


def check_environment_status():
    """Check current environment setup status"""
    status = {
        "config_exists": Path("config.yaml").exists(),
        "results_dir": Path("results").exists(),
        "findings_dir": Path("findings").exists(),
        "has_results": False,
        "has_findings": False
    }
    
    if status["results_dir"]:
        results_files = list(Path("results").glob("test_results_*.json"))
        status["has_results"] = len(results_files) > 0
        status["results_count"] = len(results_files)
    
    if status["findings_dir"]:
        findings_files = list(Path("findings").glob("*.json"))
        status["has_findings"] = len(findings_files) > 0
        status["findings_count"] = len(findings_files)
    
    return status


def show_workflow_guide():
    """Show the complete security testing workflow"""
    click.echo("🛡️  RED TEAM SECURITY TESTING WORKFLOW")
    click.echo("=" * 60)
    click.echo()
    
    click.echo("📋 COMPLETE WORKFLOW:")
    click.echo("1. 🛠️  uv run setup      - Verify environment and model connectivity")
    click.echo("2. 🎯 uv run pentest    - Execute comprehensive security tests")
    click.echo("3. 📊 uv run review     - Evaluate results and flag findings")
    click.echo("4. 🗂️  uv run findings   - Browse and export competition files")
    click.echo("5. 📋 uv run report     - Generate summary and recommendations")
    click.echo()
    
    status = check_environment_status()
    
    click.echo("📍 CURRENT STATUS:")
    click.echo("-" * 20)
    
    # Environment setup
    if status["config_exists"]:
        click.echo("✅ Configuration file found (config.yaml)")
    else:
        click.echo("❌ Configuration file missing (config.yaml)")
        click.echo("   💡 Create config.yaml or run setup for guidance")
    
    # Directories
    if status["results_dir"]:
        click.echo("✅ Results directory exists")
        if status["has_results"]:
            click.echo(f"✅ {status.get('results_count', 0)} test result files found")
        else:
            click.echo("⚠️  No test results yet")
    else:
        click.echo("⚠️  Results directory will be created on first run")
    
    if status["findings_dir"]:
        click.echo("✅ Findings directory exists")
        if status["has_findings"]:
            click.echo(f"✅ {status.get('findings_count', 0)} finding files found")
        else:
            click.echo("⚠️  No findings exported yet")
    else:
        click.echo("⚠️  Findings directory will be created on first export")
    
    click.echo()
    
    # Next steps recommendations
    click.echo("🚀 RECOMMENDED NEXT STEPS:")
    click.echo("-" * 25)
    
    if not status["config_exists"]:
        click.echo("1. Run 'uv run setup' to verify your environment")
    elif not status["has_results"]:
        click.echo("1. Run 'uv run pentest' to execute security tests")
    elif not status["has_findings"]:
        click.echo("1. Run 'uv run review' to evaluate your test results")
        click.echo("2. Flag interesting findings during review")
        click.echo("3. Export findings for competition submission")
    else:
        click.echo("1. Run 'uv run report' to see your current progress")
        click.echo("2. Continue testing with 'uv run pentest'")
        click.echo("3. Review new results with 'uv run review'")
    
    click.echo()


def show_command_details():
    """Show detailed information about each command"""
    click.echo("📚 DETAILED COMMAND REFERENCE")
    click.echo("=" * 50)
    click.echo()
    
    commands = [
        {
            "name": "🛠️  uv run setup",
            "purpose": "Environment Setup & Verification",
            "description": "Verifies Ollama connection, model availability, and sets up directories",
            "when_to_use": "Run first, or when having connection issues",
            "key_features": [
                "Tests model connectivity",
                "Creates required directories", 
                "Validates configuration",
                "Checks for busy model status"
            ]
        },
        {
            "name": "🎯 uv run pentest",
            "purpose": "Execute Security Tests",
            "description": "Runs comprehensive vulnerability assessments against AI models",
            "when_to_use": "Main testing command - run regularly to find vulnerabilities",
            "key_features": [
                "Multiple vulnerability categories",
                "Configurable test selection",
                "Automatic scoring and evaluation",
                "Results export functionality"
            ]
        },
        {
            "name": "📊 uv run review",
            "purpose": "Interactive Results Review",
            "description": "Navigate test results, flag findings, and prepare submissions",
            "when_to_use": "After running tests to evaluate and flag important results",
            "key_features": [
                "Interactive result navigation",
                "Finding flagging system",
                "Bulk export capabilities",
                "Chain-of-thought viewing"
            ]
        },
        {
            "name": "🗂️  uv run findings",
            "purpose": "Findings Management",
            "description": "Browse exported findings and create competition submissions",
            "when_to_use": "After flagging findings to create individual competition files",
            "key_features": [
                "Multi-level file browsing",
                "Individual finding export",
                "Custom naming for submissions",
                "File management tools"
            ]
        },
        {
            "name": "📋 uv run report",
            "purpose": "Summary & Reporting",
            "description": "Generate comprehensive reports from results and findings",
            "when_to_use": "To understand overall progress and get recommendations",
            "key_features": [
                "Test statistics analysis",
                "Finding summaries",
                "Performance metrics",
                "Actionable recommendations"
            ]
        }
    ]
    
    for cmd in commands:
        click.echo(f"{cmd['name']}")
        click.echo(f"Purpose: {cmd['purpose']}")
        click.echo(f"Description: {cmd['description']}")
        click.echo(f"When to use: {cmd['when_to_use']}")
        click.echo("Key features:")
        for feature in cmd['key_features']:
            click.echo(f"  • {feature}")
        click.echo()


def show_troubleshooting():
    """Show common issues and solutions"""
    click.echo("🔧 TROUBLESHOOTING GUIDE")
    click.echo("=" * 40)
    click.echo()
    
    issues = [
        {
            "problem": "❌ Model not found / Connection failed",
            "solutions": [
                "Run: ollama pull gpt-oss:20b",
                "Verify Ollama is running: ollama list", 
                "Check config.yaml has correct host/port",
                "Run 'uv run setup' to diagnose issues"
            ]
        },
        {
            "problem": "⏰ Frequent timeouts during testing",
            "solutions": [
                "Wait for model to finish other tasks",
                "Use --skip-busy-check to continue anyway",
                "Reduce concurrent testing load",
                "Check system resources (GPU/RAM)"
            ]
        },
        {
            "problem": "📁 No results files found",
            "solutions": [
                "Run 'uv run pentest' to generate results",
                "Check results/ directory exists",
                "Verify tests completed successfully",
                "Check for error messages in logs"
            ]
        },
        {
            "problem": "🗂️  No findings to browse",
            "solutions": [
                "Run 'uv run review' first",
                "Flag interesting results with 'f' key",
                "Export flagged findings with 'e' key",
                "Check findings/ directory exists"
            ]
        },
        {
            "problem": "🔧 Configuration issues",
            "solutions": [
                "Ensure config.yaml exists in current directory",
                "Verify YAML syntax is valid",
                "Check model name matches available models",
                "Use default settings if unsure"
            ]
        }
    ]
    
    for issue in issues:
        click.echo(f"{issue['problem']}")
        click.echo("Solutions:")
        for solution in issue['solutions']:
            click.echo(f"  • {solution}")
        click.echo()


@click.command()
@click.option('--workflow', is_flag=True, help='Show workflow guide')
@click.option('--commands', is_flag=True, help='Show detailed command reference')
@click.option('--troubleshooting', is_flag=True, help='Show troubleshooting guide')
def main(workflow, commands, troubleshooting):
    """🆘 Comprehensive help and workflow guidance
    
    Your complete guide to red team security testing with this toolkit.
    
    Shows current environment status, recommended next steps, and detailed
    workflow guidance to help you efficiently find AI vulnerabilities.
    
    \b
    Examples:
      uv run help                    # Show workflow guide and status
      uv run help --workflow         # Detailed workflow steps  
      uv run help --commands         # Command reference guide
      uv run help --troubleshooting  # Common issues and solutions
    """
    
    if commands:
        show_command_details()
    elif troubleshooting:
        show_troubleshooting()
    else:
        # Default: show workflow guide (with or without --workflow flag)
        show_workflow_guide()
        
        if workflow:
            click.echo()
            show_command_details()
    
    click.echo("🔗 ADDITIONAL RESOURCES:")
    click.echo("-" * 25)
    click.echo("• Individual command help: uv run <command> --help")
    click.echo("• Legacy commands: uv run testbed <subcommand>")
    click.echo("• Configuration: Edit config.yaml in project root")
    click.echo("• Logs: Check testbed.log for detailed information")
    click.echo()
    click.echo("Good luck with your security testing! 🛡️")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Findings Browser Tool
Browse, view, and export security findings
"""
from pathlib import Path

import click
from src.ui.cli_findings import launch_findings_browser


@click.command()
def main() -> None:
    """🗂️  Browse and manage security findings
    
    Interactive browser for exploring exported findings and creating competition submissions.
    
    \b
    Features:
    - Browse grouped findings files (export_*.json, flagged_*.json)  
    - View detailed finding information
    - Navigate through multi-finding exports
    - Export individual findings in competition format
    - View model chain-of-thought reasoning
    - Open findings folder in system file manager
    
    \b
    File Types:
    - Bulk Export: Files from 'uv run review' bulk export (export_YYYYMMDD_HHMMSS.json)  
    - Flagged Item: Files from individual flagging during review (flagged_test_id_timestamp.json)
    - Competition: Individual findings ready for submission (finding_name.json)
    
    \b
    Navigation:
    Level 1 (File List):
      1-20  Select file to browse    o  Open findings folder    Enter  Exit
      
    Level 2 (Finding Navigation): 
      n/p   Next/Previous finding   t  View thinking          e  Export as competition  
      Enter Return to file list    q  Quit browser
      
    Level 3 (Thinking View):
      Enter Return to finding      q  Return to finding
    
    \b
    Examples:
      uv run findings              # Browse all findings
      # Then navigate with numbers and commands
    """
    
    findings_dir = Path("findings")
    
    # Check if findings directory exists
    if not findings_dir.exists():
        click.echo("📁 No findings directory found.")
        click.echo("\n💡 To create findings:")
        click.echo("  1. Run tests: uv run pentest")
        click.echo("  2. Review results: uv run review")  
        click.echo("  3. Flag interesting findings with 'f' key")
        click.echo("  4. Export findings with 'e' key")
        click.echo("\nThen return here to browse your findings!")
        return
    
    # Check for findings files
    findings_files = list(findings_dir.glob("*.json"))
    grouped_files = [f for f in findings_files if f.name.startswith(('export_', 'flagged_'))]
    
    if not findings_files:
        click.echo("📁 Findings directory is empty.")
        click.echo("\n💡 To create findings:")
        click.echo("  1. Run tests: uv run pentest")
        click.echo("  2. Review results: uv run review")
        click.echo("  3. Flag interesting findings with 'f' key")
        click.echo("  4. Export findings with 'e' key")
        return
    
    elif not grouped_files:
        click.echo(f"📁 Found {len(findings_files)} files in findings directory")
        click.echo("   But no grouped exports (export_*.json, flagged_*.json) to browse")
        click.echo("\n💡 Grouped exports are created by:")
        click.echo("  • Flagging findings during review (creates flagged_*.json)")
        click.echo("  • Bulk export from review UI (creates export_*.json)")
        click.echo("\n🔍 Individual competition files found:")
        comp_files = [f for f in findings_files if f.name.startswith('finding_')]
        if comp_files:
            for f in comp_files[:5]:
                click.echo(f"  • {f.name}")
            if len(comp_files) > 5:
                click.echo(f"  • ... and {len(comp_files) - 5} more")
        else:
            other_files = [f for f in findings_files if not f.name.startswith(('export_', 'flagged_', 'finding_'))]
            for f in other_files[:5]:
                click.echo(f"  • {f.name}")
        return
    
    # Launch the findings browser
    click.echo("🗂️  Launching findings browser...")
    try:
        launch_findings_browser()
    except KeyboardInterrupt:
        click.echo("\n👋 Findings browser closed")
    except Exception as e:
        click.echo(f"❌ Error launching findings browser: {e}")


if __name__ == "__main__":
    main()
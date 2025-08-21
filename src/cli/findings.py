#!/usr/bin/env python3
"""
Findings Browser Tool
Browse, view, and export security findings
"""

from pathlib import Path

import click
from src.ui.cli_findings import launch_findings_browser


@click.command()
@click.option(
    "--convert-competition",
    "-c",
    metavar="EXPORT_FILE",
    help="Convert an export file to competition format (e.g., export_20250821_225530.json)",
)
def main(convert_competition: str | None = None) -> None:
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
      uv run findings                                    # Browse all findings
      uv run findings -c export_20250821_225530.json    # Convert to competition format
      # Then navigate with numbers and commands
    """

    # Handle competition conversion
    if convert_competition:
        _convert_to_competition_format(convert_competition)
        return

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
    grouped_files = [f for f in findings_files if f.name.startswith(("export_", "flagged_"))]

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
        comp_files = [f for f in findings_files if f.name.startswith("finding_")]
        if comp_files:
            for f in comp_files[:5]:
                click.echo(f"  • {f.name}")
            if len(comp_files) > 5:
                click.echo(f"  • ... and {len(comp_files) - 5} more")
        else:
            other_files = [
                f
                for f in findings_files
                if not f.name.startswith(("export_", "flagged_", "finding_"))
            ]
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


def _convert_to_competition_format(export_file: str) -> None:
    """Convert an export file to competition format"""
    try:
        from src.utils.competition_converter import CompetitionConverter
        
        findings_dir = Path("findings")
        export_path = findings_dir / export_file
        
        if not export_path.exists():
            click.echo(f"❌ Export file not found: {export_path}")
            click.echo(f"💡 Available files in {findings_dir}:")
            if findings_dir.exists():
                for f in findings_dir.glob("export_*.json"):
                    click.echo(f"  • {f.name}")
            return
        
        click.echo(f"🔄 Converting {export_file} to competition format...")
        
        converter = CompetitionConverter()
        created_files = converter.convert_export_file_to_competition(export_path)
        
        if created_files:
            click.echo(f"✅ Successfully converted {len(created_files)} findings:")
            for file_path in created_files:
                click.echo(f"  • {Path(file_path).name}")
            
            click.echo(f"\n📁 Competition files saved to: {findings_dir}")
            click.echo("💡 You can now submit these files to the competition")
        else:
            click.echo("⚠️  No vulnerable findings found to convert")
            
    except ImportError as e:
        click.echo(f"❌ Missing dependency: {e}")
        click.echo("💡 Install with: uv add openai-harmony")
    except Exception as e:
        click.echo(f"❌ Conversion failed: {e}")
        click.echo("💡 Check that the export file is valid and contains findings data")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Results Review Tool
Interactive CLI for reviewing and evaluating test results
"""
import click
import json
from pathlib import Path
from typing import Optional
from datetime import datetime

from testbed import load_config
from ui.cli_ui import launch_cli_ui


def find_latest_results_file(results_dir: str = "results") -> Optional[str]:
    """Find the most recent results file"""
    results_path = Path(results_dir)
    if not results_path.exists():
        return None
    
    # Find all result files
    result_files = list(results_path.glob("test_results_*.json"))
    if not result_files:
        return None
    
    # Sort by modification time (most recent first)
    result_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return str(result_files[0])


def list_available_results(results_dir: str = "results") -> list:
    """List all available results files with details"""
    results_path = Path(results_dir)
    if not results_path.exists():
        return []
    
    # Find all result files
    result_files = list(results_path.glob("test_results_*.json"))
    if not result_files:
        return []
    
    # Sort by modification time (most recent first)  
    result_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    files_info = []
    now = datetime.now()
    
    for i, file_path in enumerate(result_files[:50], 1):  # Show max 50 files
        stat = file_path.stat()
        size = f"{stat.st_size // 1024}KB" if stat.st_size >= 1024 else f"{stat.st_size}B"
        modified = datetime.fromtimestamp(stat.st_mtime)
        age_diff = now - modified
        
        if age_diff.days > 0:
            age = f"{age_diff.days}d ago"
        elif age_diff.seconds > 3600:
            age = f"{age_diff.seconds // 3600}h ago"
        elif age_diff.seconds > 60:
            age = f"{age_diff.seconds // 60}m ago"
        else:
            age = "just now"
        
        # Try to get test info from file
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            categories = list(data.keys())
            test_count = sum(len(cat_data.get('test_details', [])) for cat_data in data.values() if isinstance(cat_data, dict))
        except:
            categories = ["Unknown"]
            test_count = 0
        
        files_info.append({
            'index': i,
            'file': file_path,
            'filename': file_path.name,
            'size': size,
            'modified': modified,
            'age': age,
            'categories': categories,
            'test_count': test_count
        })
    
    return files_info


def select_results_file_interactive(results_dir: str = "results") -> Optional[str]:
    """Interactive file selection"""
    files_info = list_available_results(results_dir)
    
    if not files_info:
        click.echo(f"❌ No results files found in {results_dir}")
        click.echo("💡 Run 'uv run pentest' to generate test results first")
        return None
    
    # Display available files
    click.echo("📁 Available results files:")
    click.echo("=" * 90)
    click.echo(f"{'#':<3} {'Filename':<30} {'Size':<8} {'Age':<12} {'Tests':<7} {'Categories'}")
    click.echo("-" * 90)
    
    for file_info in files_info:
        categories_str = ", ".join(file_info['categories'][:2])
        if len(file_info['categories']) > 2:
            categories_str += "..."
        
        click.echo(f"{file_info['index']:<3} {file_info['filename']:<30} {file_info['size']:<8} {file_info['age']:<12} {file_info['test_count']:<7} {categories_str}")
    
    click.echo("-" * 90)
    
    # Prompt for selection
    try:
        while True:
            choice = click.prompt(
                f"\nSelect file (1-{len(files_info)}) or 'q' to quit",
                type=str
            )
            
            if choice.lower() == 'q':
                return None
            
            try:
                file_index = int(choice) - 1
                if 0 <= file_index < len(files_info):
                    selected_file = files_info[file_index]
                    click.echo(f"✅ Selected: {selected_file['filename']}")
                    return str(selected_file['file'])
                else:
                    click.echo(f"❌ Invalid selection. Please choose 1-{len(files_info)}")
            except ValueError:
                click.echo("❌ Invalid input. Please enter a number or 'q'")
                
    except KeyboardInterrupt:
        click.echo("\n👋 Cancelled")
        return None


@click.command()
@click.argument('results_file', required=False)
@click.option('--config', default='config.yaml', help='Configuration file path')
@click.option('--latest', is_flag=True, help='Automatically select the latest results file')
def main(results_file, config, latest):
    """📊 Review and evaluate penetration test results
    
    Interactive CLI for reviewing test results, flagging findings, and exporting data.
    
    Features:
    - Navigate through test results
    - Flag potential vulnerabilities 
    - Export findings for competition submission
    - Copy prompts for manual testing
    - View model chain-of-thought reasoning
    
    Examples:
      uv run review                          # Interactive file selection
      uv run review results/test_results.json  # Review specific file
      uv run review --latest                 # Review latest results
    
    Navigation:
      n/→   Next result      p/←   Previous result
      f     Flag finding     u     Unflag  
      e     Export findings  v     View findings
      c     Copy prompt      t     Show thinking
      h/?   Help            q     Quit
    """
    
    try:
        # Load configuration to get results directory
        config_data = load_config(config)
        results_dir = config_data.get('output', {}).get('results_dir', 'results')
    except Exception as e:
        click.echo(f"⚠️  Could not load config: {e}")
        results_dir = "results"
    
    # Determine which results file to use
    if not results_file:
        if latest:
            results_file = find_latest_results_file(results_dir)
            if results_file:
                click.echo(f"📊 Using latest results: {Path(results_file).name}")
            else:
                click.echo(f"❌ No results files found in {results_dir}")
                click.echo("💡 Run 'uv run pentest' to generate test results first")
                return 1
        else:
            results_file = select_results_file_interactive(results_dir)
            if not results_file:
                return 0
    
    # Verify file exists
    if not Path(results_file).exists():
        click.echo(f"❌ Results file not found: {results_file}")
        return 1
    
    # Launch the CLI UI
    click.echo(f"🚀 Launching results reviewer...")
    
    try:
        launch_cli_ui(results_file)
    except KeyboardInterrupt:
        click.echo("\n👋 Review session ended")
    except Exception as e:
        click.echo(f"❌ Error launching reviewer: {e}")
        return 1


if __name__ == "__main__":
    main()
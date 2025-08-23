#!/usr/bin/env python3
"""
Competition File Validator
Validates JSON files against the competition schema specification
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple

import click

from src.utils.schema_validator import CompetitionSchemaValidator, create_validation_summary


def print_validation_results(
    results: Dict[str, Tuple[bool, List[str]]], 
    verbose: bool = False,
    show_valid: bool = False
) -> None:
    """Print validation results in a readable format"""
    
    for file_path, (is_valid, errors) in results.items():
        file_name = Path(file_path).name
        
        if is_valid:
            click.echo(f"✅ {file_name}: VALID", color=True)
            if show_valid and verbose:
                click.echo(f"   📁 File: {file_path}")
        else:
            click.echo(f"❌ {file_name}: INVALID ({len(errors)} errors)", color=True)
            if verbose:
                click.echo(f"   📁 File: {file_path}")
                for i, error in enumerate(errors, 1):
                    # Remove file path from error message to avoid duplication
                    clean_error = error.split(": ", 1)[-1] if ": " in error else error
                    click.echo(f"   {i}. {clean_error}")
            else:
                # Show just the first error in non-verbose mode
                if errors:
                    clean_error = errors[0].split(": ", 1)[-1] if ": " in errors[0] else errors[0]
                    click.echo(f"   └─ {clean_error}")


def print_summary(summary: Dict, show_details: bool = True) -> None:
    """Print validation summary"""
    click.echo("\n" + "=" * 60)
    click.echo("📊 VALIDATION SUMMARY")
    click.echo("=" * 60)
    
    click.echo(f"Total files:     {summary['total_files']}")
    click.echo(f"✅ Valid files:   {summary['valid_files']}")
    click.echo(f"❌ Invalid files: {summary['invalid_files']}")
    click.echo(f"📈 Success rate:  {summary['success_rate']:.1f}%")
    
    if summary['total_errors'] > 0:
        click.echo(f"🔍 Total errors:  {summary['total_errors']}")
        
        if show_details and summary.get('error_summary'):
            click.echo(f"\n📋 Common errors:")
            for i, error in enumerate(summary['error_summary'], 1):
                clean_error = error.split(": ", 1)[-1] if ": " in error else error
                click.echo(f"  {i}. {clean_error}")
            
            if summary.get('truncated'):
                remaining = summary['total_errors'] - len(summary['error_summary'])
                click.echo(f"  ... and {remaining} more errors (use --verbose to see all)")


@click.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--verbose", "-v", is_flag=True, help="Show detailed error messages")
@click.option("--schema", "-s", default="doc/findings.schema", help="Path to schema file")
@click.option("--pattern", "-p", default="*.json", help="File pattern to match (for directories)")
@click.option("--show-valid", is_flag=True, help="Show details for valid files too")
@click.option("--quiet", "-q", is_flag=True, help="Only show summary")
def main(
    path: str, 
    verbose: bool, 
    schema: str, 
    pattern: str, 
    show_valid: bool,
    quiet: bool
) -> None:
    """🔍 Validate competition JSON files against schema
    
    Validates individual JSON files or all JSON files in a directory against
    the competition findings schema specification.
    
    \b
    Examples:
        uv run validate findings/quesma.findings.1.json
        uv run validate findings/ --verbose
        uv run validate findings/ --pattern "competition_*.json"
        uv run validate findings/ --schema custom/schema.json
    
    \b
    Arguments:
        PATH    Path to JSON file or directory containing JSON files
    
    \b
    Exit codes:
        0 - All files are valid
        1 - Some files are invalid
        2 - Error (schema not found, no files, etc.)
    """
    
    try:
        # Initialize validator
        if not quiet:
            click.echo(f"🔧 Loading schema from: {schema}")
        
        validator = CompetitionSchemaValidator(schema)
        
        if not quiet:
            schema_info = validator.get_schema_info()
            click.echo(f"📋 Schema: {schema_info['title']}")
            click.echo(f"🔗 Schema ID: {schema_info['schema_id']}")
            
        path_obj = Path(path)
        
        # Determine if we're validating a single file or directory
        if path_obj.is_file():
            if not quiet:
                click.echo(f"📄 Validating file: {path}")
            results = {path: validator.validate_file(path)}
        else:
            if not quiet:
                click.echo(f"📁 Validating directory: {path} (pattern: {pattern})")
            results = validator.validate_directory(path, pattern)
        
        # Check if we found any files
        if not results:
            click.echo("❌ No files found to validate", err=True)
            sys.exit(2)
        
        # Print results
        if not quiet:
            click.echo("\n" + "=" * 60)
            click.echo("🔍 VALIDATION RESULTS")
            click.echo("=" * 60)
            print_validation_results(results, verbose, show_valid)
        
        # Print summary
        summary = create_validation_summary(results)
        print_summary(summary, show_details=verbose and not quiet)
        
        # Determine exit code
        if summary['invalid_files'] == 0:
            if not quiet:
                click.echo(f"\n🎉 All {summary['total_files']} files are valid!", color=True)
            sys.exit(0)
        else:
            if not quiet:
                click.echo(f"\n⚠️  {summary['invalid_files']} of {summary['total_files']} files have validation errors", color=True)
            sys.exit(1)
            
    except FileNotFoundError as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(2)
    except ImportError as e:
        click.echo(f"❌ Error: {e}", err=True)
        click.echo("💡 Try running: uv sync", err=True)
        sys.exit(2)
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}", err=True)
        sys.exit(2)


if __name__ == "__main__":
    main()
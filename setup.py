#!/usr/bin/env python3
"""
Setup and Environment Verification Tool
Verifies Ollama connection, model availability, and environment setup
"""
import click
import yaml
from pathlib import Path
from typing import Dict, Any

from utils.model_client import OllamaClient


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
    
    click.echo(f"📁 Created directories: {results_dir}, {findings_dir}")


def test_connection(config: Dict[str, Any], verbose: bool = False) -> bool:
    """Test connection to Ollama and model availability"""
    model_config = config.get('model', {})
    
    client = OllamaClient(
        host=model_config.get('host', 'localhost'),
        port=model_config.get('port', 11434),
        model=model_config.get('name', 'gpt-oss:20b')
    )
    
    click.echo("🔗 Testing Ollama connection...")
    
    # Check if Ollama is busy before testing
    click.echo("🔍 Checking Ollama status...")
    try:
        status = client.check_ollama_status()
        
        if status.is_busy:
            click.echo(f"⚠️  WARNING: Ollama appears busy (GPU usage: {status.gpu_usage})")
            click.echo(f"   Model loaded: {'Yes' if status.model_loaded else 'No'}")
            click.echo(f"   Memory usage: {status.memory_usage}")
            click.echo(f"   This may cause slower responses or timeouts.")
            if verbose:
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
                return False
            else:
                click.echo(f"✅ Generation successful ({response.response_time:.2f}s)")
                if response.timed_out:
                    click.echo(f"⚠️  Response had timeout issues")
                if verbose:
                    click.echo(f"Sample response: {response.content[:100]}...")
                return True
        else:
            click.echo(f"❌ Model {client.model} not found")
            click.echo("Please run: ollama pull gpt-oss:20b")
            return False
    
    except Exception as e:
        click.echo(f"❌ Connection failed: {e}")
        return False


@click.command()
@click.option('--config', default='config.yaml', help='Configuration file path')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def main(config, verbose):
    """🛠️  Setup and verify environment for red team security testing
    
    This command will:
    
    \b
    - Load and validate configuration
    - Set up logging and directories
    - Test Ollama connection and model availability
    - Verify the environment is ready for testing
    
    Run this before starting your security assessments.
    """
    try:
        # Load configuration
        click.echo("📋 Loading configuration...")
        config_data = load_config(config)
        click.echo(f"✅ Configuration loaded from: {config}")
        
        # Setup logging
        setup_logging(config_data)
        if verbose:
            click.echo("📝 Logging configured")
        
        # Ensure directories exist
        click.echo("📁 Setting up directories...")
        ensure_directories(config_data)
        
        # Test connection
        success = test_connection(config_data, verbose)
        
        if success:
            click.echo("\n🎉 Environment setup complete!")
            click.echo("✅ Ready to run security tests")
            click.echo("\nNext steps:")
            click.echo("  • Run tests: uv run pentest")
            click.echo("  • Review results: uv run review")
            click.echo("  • Browse findings: uv run findings")
        else:
            click.echo("\n❌ Environment setup failed")
            click.echo("Please fix the issues above before running tests")
            return 1
            
    except FileNotFoundError as e:
        click.echo(f"❌ Configuration error: {e}")
        click.echo("Please ensure config.yaml exists in the current directory")
        return 1
    except Exception as e:
        click.echo(f"❌ Setup failed: {e}")
        return 1


if __name__ == "__main__":
    main()
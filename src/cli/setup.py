#!/usr/bin/env python3
"""
Setup and Environment Verification Tool
Configures LLM backends and verifies environment setup
"""

from pathlib import Path
from typing import Any

import click
import yaml
from src.utils.llm_backend import create_backend
from src.utils.settings_manager import settings_manager


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
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_config.get("file", "testbed.log")),
        ],
    )


def ensure_directories(config: dict[str, Any]) -> None:
    """Ensure output directories exist"""
    output_config = config.get("output", {})

    results_dir = Path(output_config.get("results_dir", "results"))
    findings_dir = Path(output_config.get("findings_dir", "findings"))

    results_dir.mkdir(exist_ok=True)
    findings_dir.mkdir(exist_ok=True)

    click.echo(f"📁 Created directories: {results_dir}, {findings_dir}")


def interactive_backend_setup() -> bool:
    """Interactive setup for backend configuration."""
    click.echo("\n🤖 LLM Backend Configuration")
    click.echo("Choose your preferred LLM backend:")
    click.echo("1. Ollama (local models)")
    click.echo("2. OpenRouter (cloud models)")
    
    while True:
        try:
            choice = click.prompt("Select backend (1-2)", type=int)
            if choice in [1, 2]:
                break
            click.echo("❌ Invalid choice. Please select 1 or 2.")
        except click.Abort:
            click.echo("\n🚫 Setup cancelled by user")
            return False
        except (ValueError, TypeError):
            click.echo("❌ Invalid input. Please enter 1 or 2.")
    
    if choice == 1:
        return setup_ollama_backend()
    else:
        return setup_openrouter_backend()


def setup_ollama_backend() -> bool:
    """Setup Ollama backend configuration."""
    click.echo("\n🦙 Configuring Ollama Backend")
    
    # Create default settings.yaml if it doesn't exist
    if not Path("settings.yaml").exists():
        settings_manager.create_default_settings()
    
    host = click.prompt("Ollama host", default="localhost")
    port = click.prompt("Ollama port", default=11434, type=int)
    model = click.prompt("Model name", default="gpt-oss:20b")
    
    # Save settings
    settings_manager.set("backend.provider", "ollama")
    settings_manager.set("ollama.host", host)
    settings_manager.set("ollama.port", port)
    settings_manager.set("ollama.model", model)
    
    click.echo("✅ Ollama backend configured")
    return True


def setup_openrouter_backend() -> bool:
    """Setup OpenRouter backend configuration."""
    click.echo("\n🌐 Configuring OpenRouter Backend")
    click.echo("You'll need an OpenRouter API key from: https://openrouter.ai/keys")
    
    # Create default settings.yaml if it doesn't exist
    if not Path("settings.yaml").exists():
        settings_manager.create_default_settings()
    
    api_key = click.prompt("OpenRouter API key", hide_input=True)
    if not api_key.strip():
        click.echo("❌ API key is required for OpenRouter")
        return False
    
    # Show popular models
    click.echo("\nPopular models:")
    models = [
        "openai/gpt-oss-20b",
        "meta-llama/llama-3.1-70b-instruct",
        "anthropic/claude-3.5-sonnet",
        "openai/gpt-4o",
        "google/gemini-pro-1.5",
        "mistral/mistral-large",
    ]
    
    for i, model in enumerate(models, 1):
        click.echo(f"{i}. {model}")
    
    try:
        choice = click.prompt("Select model (1-5, or enter custom)", default="1")
        if choice.isdigit() and 1 <= int(choice) <= 5:
            model = models[int(choice) - 1]
        else:
            model = choice
    except (ValueError, IndexError):
        model = "openai/gpt-oss-20b"
    
    site_name = click.prompt("Site name (optional)", default="Red Team Testbed")
    site_url = click.prompt("Site URL (optional)", default="")
    
    # Save settings
    settings_manager.set("backend.provider", "openrouter")
    settings_manager.set("openrouter.api_key", api_key)
    settings_manager.set("openrouter.model", model)
    settings_manager.set("openrouter.site_name", site_name)
    if site_url:
        settings_manager.set("openrouter.site_url", site_url)
    
    click.echo("✅ OpenRouter backend configured")
    return True


def test_connection(config: dict[str, Any], verbose: bool = False) -> bool:
    """Test connection to configured LLM backend."""
    try:
        # Try to load settings and create backend
        if Path("settings.yaml").exists():
            settings = settings_manager.load_settings()
            backend = create_backend(settings)
            provider = settings['backend']['provider']
            click.echo(f"🔗 Testing {provider} connection...")
        else:
            # Fallback to default Ollama configuration
            from src.utils.model_client import OllamaClient
            backend = OllamaClient()  # Uses default localhost:11434, gpt-oss:20b
            provider = "ollama"
            click.echo("🔗 Testing default Ollama connection...")
        
        if provider == 'ollama':
            return test_ollama_connection(backend, verbose)
        else:
            return test_openrouter_connection(backend, verbose)
            
    except Exception as e:
        click.echo(f"❌ Backend setup failed: {e}")
        return False


def test_ollama_connection(backend, verbose: bool = False) -> bool:
    """Test connection to Ollama backend."""
    # Check if Ollama is busy before testing
    click.echo("🔍 Checking Ollama status...")
    try:
        # Handle both OllamaBackend and OllamaClient
        if hasattr(backend, 'check_status'):
            status = backend.check_status()
        else:
            status = backend.check_ollama_status()

        if status.is_busy:
            click.echo(f"⚠️  WARNING: Ollama appears busy (GPU usage: {status.gpu_usage})")
            click.echo(f"   Model loaded: {'Yes' if status.model_loaded else 'No'}")
            click.echo(f"   Memory usage: {status.memory_usage}")
            click.echo("   This may cause slower responses or timeouts.")
            if verbose:
                click.echo(f"   Raw status: {status.raw_output}")
        else:
            click.echo("✅ Ollama status: Available")
            if status.model_loaded:
                click.echo(f"   Model loaded: Yes (Memory: {status.memory_usage})")
            else:
                click.echo("   Model loaded: No")
    except Exception as e:
        click.echo(f"⚠️  Could not check Ollama status: {e}")

    try:
        # Handle both interfaces for availability check
        if hasattr(backend, 'is_available'):
            model_available = backend.is_available()
            model_name = backend.get_model_name()
        else:
            model_available = backend.is_model_available()
            model_name = backend.model

        if model_available:
            click.echo(f"✅ Model {model_name} is available")

            # Test generation
            click.echo("🧪 Testing generation...")
            response = backend.generate("Hello, this is a test.")
            if response.error:
                click.echo(f"❌ Generation failed: {response.error}")
                if response.timed_out:
                    click.echo("   This was a timeout - model may be busy or overloaded")
                return False
            else:
                click.echo(f"✅ Generation successful ({response.response_time:.2f}s)")
                if response.timed_out:
                    click.echo("⚠️  Response had timeout issues")
                if verbose:
                    click.echo(f"Sample response: {response.content[:100]}...")
                return True
        else:
            click.echo(f"❌ Model {model_name} not found")
            click.echo(f"Please run: ollama pull {model_name}")
            return False

    except Exception as e:
        click.echo(f"❌ Connection failed: {e}")
        return False


def test_openrouter_connection(backend, verbose: bool = False) -> bool:
    """Test connection to OpenRouter backend."""
    try:
        if not backend.is_available():
            click.echo("❌ OpenRouter API not accessible")
            click.echo("Please check your API key and internet connection")
            return False

        click.echo("✅ OpenRouter API accessible")
        click.echo(f"✅ Model: {backend.get_model_name()}")

        # Test generation
        click.echo("🧪 Testing generation...")
        response = backend.generate("Hello, this is a test.")
        if response.error:
            click.echo(f"❌ Generation failed: {response.error}")
            if response.timed_out:
                click.echo("   This was a timeout - API may be overloaded")
            return False
        else:
            click.echo(f"✅ Generation successful ({response.response_time:.2f}s)")
            if verbose:
                click.echo(f"Sample response: {response.content[:100]}...")
            return True

    except Exception as e:
        click.echo(f"❌ Connection failed: {e}")
        return False


@click.command()
@click.option("--config", default="config.yaml", help="Configuration file path")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option("--configure", is_flag=True, help="Run interactive backend configuration")
def main(config: str, verbose: bool, configure: bool) -> int | None:
    """🛠️  Setup and verify environment for red team security testing

    This command will:

    \b
    - Configure LLM backend (Ollama or OpenRouter) 
    - Load and validate configuration
    - Set up logging and directories
    - Test backend connection and model availability
    - Verify the environment is ready for testing

    Use --configure for interactive backend setup.
    Run this before starting your security assessments.
    """
    try:
        # Handle interactive configuration first
        if configure:
            click.echo("🛠️  Interactive Backend Setup")
            if not interactive_backend_setup():
                return 1
            click.echo("")
        
        # Check if settings.yaml exists
        if not Path("settings.yaml").exists():
            if configure:
                # settings.yaml will be created by interactive setup
                pass
            else:
                click.echo("💡 No settings.yaml found, using default Ollama configuration")
                click.echo("   Run 'uv run setup --configure' to configure different backends")
            
        # Load configuration (fallback compatibility)
        click.echo("📋 Loading configuration...")
        try:
            config_data = load_config(config)
            click.echo(f"✅ Configuration loaded from: {config}")
        except FileNotFoundError:
            # Use minimal config if config.yaml doesn't exist
            config_data = {
                "output": {"results_dir": "results", "findings_dir": "findings"},
                "logging": {"level": "INFO", "file": "testbed.log"}
            }

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
            click.echo("\n💡 Configuration files:")
            click.echo("  • Backend settings: settings.yaml")
            click.echo("  • Test settings: config.yaml")
        else:
            click.echo("\n❌ Environment setup failed")
            click.echo("Please fix the issues above before running tests")
            click.echo("💡 Try: uv run setup --configure")
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
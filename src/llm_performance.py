#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "requests",
#     "python-dotenv",
#     "rich",
# ]
# ///

"""
Performance comparison between local Ollama GPT-OSS:20b and OpenRouter GPT-OSS:20b
"""

import os
import time

import requests
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Load environment variables
load_dotenv()

console = Console()

# Configuration
LOCAL_OLLAMA_URL = "http://localhost:11434"
LOCAL_MODEL = "gpt-oss:20b"

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openai/gpt-oss-20b"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Test prompt
TEST_PROMPT = """Write a Python function that calculates the nth Fibonacci number using dynamic programming. Include a brief explanation of how it works."""


def test_local_ollama() -> tuple[str, float, float, int]:
    """Test local Ollama model"""
    start_time = time.time()
    
    try:
        response = requests.post(
            f"{LOCAL_OLLAMA_URL}/api/generate",
            json={
                "model": LOCAL_MODEL,
                "prompt": TEST_PROMPT,
                "stream": False,
                "options": {
                    "num_predict": 500  # Limit response length for fair comparison
                }
            },
            timeout=60
        )
        response.raise_for_status()
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        result = response.json()
        content = result.get("response", "")
        
        # Get actual token counts from response
        eval_count = result.get("eval_count", 0)  # completion tokens
        if eval_count == 0:
            # Fallback to character-based estimation (roughly 4 chars per token)
            eval_count = len(content) // 4
        
        tokens_per_second = eval_count / elapsed if elapsed > 0 else 0
        
        return content, elapsed, tokens_per_second, eval_count
        
    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error with local Ollama: {e}[/red]")
        return "", 0, 0, 0


def test_openrouter() -> tuple[str, float, float, int]:
    """Test OpenRouter model"""
    if not OPENROUTER_API_KEY:
        console.print("[red]OPENROUTER_API_KEY not found in .env file[/red]")
        return "", 0, 0, 0
    
    start_time = time.time()
    
    try:
        response = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/QuesmaOrg/red-team-testbed-for-gpt-oss",
                "X-Title": "GPT-OSS Performance Test"
            },
            json={
                "model": OPENROUTER_MODEL,
                "messages": [
                    {"role": "user", "content": TEST_PROMPT}
                ],
                "max_tokens": 500  # Match local Ollama limit
            },
            timeout=60
        )
        response.raise_for_status()
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        result = response.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        # Get token counts from response
        usage = result.get("usage", {})
        completion_tokens = usage.get("completion_tokens", 0)
        if completion_tokens == 0:
            # Fallback to estimation
            completion_tokens = len(content) // 4
        
        tokens_per_second = completion_tokens / elapsed if elapsed > 0 else 0
        
        return content, elapsed, tokens_per_second, completion_tokens
        
    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error with OpenRouter: {e}[/red]")
        return "", 0, 0, 0


def main() -> None:
    console.print("[bold cyan]GPT-OSS:20b Performance Comparison[/bold cyan]\n")
    console.print(f"[dim]Test prompt: {TEST_PROMPT[:50]}...[/dim]\n")
    
    results = {}
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        
        # Test local Ollama
        task = progress.add_task("[cyan]Testing local Ollama GPT-OSS:20b...", total=None)
        content_local, time_local, tps_local, tokens_local = test_local_ollama()
        progress.remove_task(task)
        
        if time_local > 0:
            results["Local Ollama"] = {
                "time": time_local,
                "tokens_per_second": tps_local,
                "tokens": tokens_local,
                "response_length": len(content_local)
            }
            console.print("[green]✓ Local Ollama test completed[/green]")
        else:
            console.print("[yellow]⚠ Local Ollama test failed[/yellow]")
        
        # Test OpenRouter
        task = progress.add_task("[cyan]Testing OpenRouter GPT-OSS:20b...", total=None)
        content_openrouter, time_openrouter, tps_openrouter, tokens_openrouter = test_openrouter()
        progress.remove_task(task)
        
        if time_openrouter > 0:
            results["OpenRouter"] = {
                "time": time_openrouter,
                "tokens_per_second": tps_openrouter,
                "tokens": tokens_openrouter,
                "response_length": len(content_openrouter)
            }
            console.print("[green]✓ OpenRouter test completed[/green]")
        else:
            console.print("[yellow]⚠ OpenRouter test failed[/yellow]")
    
    # Display results
    if results:
        console.print("\n[bold]Results:[/bold]")
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Provider", style="cyan")
        table.add_column("Response Time (s)", justify="right")
        table.add_column("Tokens", justify="right")
        table.add_column("Tokens/Second", justify="right")
        table.add_column("Characters", justify="right")
        
        for provider, data in results.items():
            table.add_row(
                provider,
                f"{data['time']:.2f}",
                str(data['tokens']),
                f"{data['tokens_per_second']:.1f}",
                str(data['response_length'])
            )
        
        console.print(table)
        
        # Compare performance
        if len(results) == 2:
            local_tps = results.get("Local Ollama", {}).get("tokens_per_second", 0)
            openrouter_tps = results.get("OpenRouter", {}).get("tokens_per_second", 0)
            
            if local_tps > 0 and openrouter_tps > 0:
                ratio = local_tps / openrouter_tps
                console.print("\n[bold]Performance Ratio:[/bold]")
                if ratio > 1:
                    console.print(f"Local Ollama is [green]{ratio:.2f}x faster[/green] than OpenRouter")
                else:
                    console.print(f"OpenRouter is [green]{1/ratio:.2f}x faster[/green] than Local Ollama")
    else:
        console.print("\n[red]No successful tests completed[/red]")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""Example script demonstrating the interactive red team testing system."""

import os
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console

from src.interactive_exploit import InteractiveRedTeam
from src.models import AttackStrategy
from src.utils.session_manager import SessionManager

# Load environment variables
load_dotenv()

console = Console()


def run_single_session_example():
    """Run a single interactive session with multiple attack strategies."""
    console.print("[bold cyan]Interactive Red Team Testing - Example Session[/bold cyan]\n")

    # Check for API key
    if not os.getenv("OPENROUTER_API_KEY"):
        console.print("[red]Error: OPENROUTER_API_KEY not found in environment[/red]")
        console.print("Please set it in your .env file")
        return

    # Initialize the red team system
    console.print("[yellow]Initializing red team system...[/yellow]")
    red_team = InteractiveRedTeam(
        target_model="openai/gpt-oss-20b",  # The model we're testing
        attacker_model="openai/gpt-4o-mini",  # Model generating attacks
        evaluator_model="openai/gpt-4o-mini",  # Model evaluating responses
    )

    # Initialize session manager
    session_manager = SessionManager("sessions")

    console.print("[green]✓[/green] System initialized\n")

    # Test different strategies
    strategies_to_test = [
        (AttackStrategy.TRUST_BUILDING, 2),  # 2-step trust building
        (AttackStrategy.SIDE_TASK, 1),  # Single-turn side task
        (AttackStrategy.COMPLIANCE_REQUIREMENT, 2),  # 2-step compliance
        (AttackStrategy.TECHNICAL_CONFUSION, 3),  # 3-step technical confusion
    ]

    console.print("[bold]Running test attacks:[/bold]\n")

    for strategy, steps in strategies_to_test:
        console.print(f"\n[cyan]Testing {strategy.value} with {steps} steps...[/cyan]")

        try:
            # Run the attack
            attempt = red_team.run_attack(strategy=strategy, steps=steps)

            # Display results
            console.print(f"  Attack ID: {attempt.attempt_id[:8]}")

            # Show conversation highlights
            for turn in attempt.turns:
                if turn.is_exploit_turn:
                    console.print(f"  [yellow]Exploit turn:[/yellow] {turn.content[:80]}...")

            # Show evaluation
            if attempt.evaluation:
                status = "✓ VULNERABLE" if attempt.success else "✗ SAFE"
                console.print(f"  Result: [{'green' if attempt.success else 'red'}]{status}[/]")
                console.print(f"  Confidence: {attempt.evaluation.confidence:.1%}")
                console.print(f"  Reasoning: {attempt.evaluation.reasoning[:100]}...")

        except Exception as e:
            console.print(f"  [red]Error: {e}[/red]")

    # Display session summary
    console.print("\n" + "=" * 60)
    console.print(red_team.get_session_summary())

    # Save the session
    console.print("\n[yellow]Saving session...[/yellow]")
    session_file = red_team.save_session()
    console.print(f"[green]✓[/green] Session saved to: {session_file}")

    # Export report
    console.print("\n[yellow]Exporting report...[/yellow]")
    report_file = session_manager.export_session_report(red_team.session)
    console.print(f"[green]✓[/green] Report exported to: {report_file}")

    # Display overall statistics
    console.print("\n[bold]Overall Statistics:[/bold]")
    stats = session_manager.get_statistics()
    console.print(f"  Total Sessions: {stats['total_sessions']}")
    console.print(f"  Total Attempts: {stats['total_attempts']}")
    console.print(f"  Success Rate: {stats['success_rate']:.1%}")


def demonstrate_learning_system():
    """Demonstrate how the system learns from previous attempts."""
    console.print("\n[bold cyan]Learning System Demonstration[/bold cyan]\n")

    session_manager = SessionManager("sessions")

    # Check for existing lessons
    lessons = session_manager.load_lessons("openai_gpt-4o-mini")
    if lessons:
        console.print("[green]Found existing lessons![/green]\n")
        console.print(f"Total Sessions: {lessons.total_sessions}")
        console.print(f"Total Attempts: {lessons.total_attempts}")

        console.print("\n[bold]Strategy Performance:[/bold]")
        for strategy, rate in lessons.strategies.items():
            console.print(f"  {strategy}: {rate:.1%} success rate")

        if lessons.best_patterns:
            console.print("\n[bold]Best Patterns (first 3):[/bold]")
            for pattern in lessons.best_patterns[:3]:
                console.print(f"  • {pattern}")

        if lessons.lessons:
            console.print("\n[bold]Key Insights:[/bold]")
            for lesson in lessons.lessons[:3]:
                console.print(f"  {lesson.strategy.value}:")
                for insight in lesson.key_insights[:2]:
                    console.print(f"    • {insight}")
    else:
        console.print("[yellow]No existing lessons found. Run some sessions first![/yellow]")


def main():
    """Main entry point for the example script."""
    console.print("\n" + "=" * 60)
    console.print("[bold]Interactive Red Team Testing - Example Script[/bold]")
    console.print("=" * 60 + "\n")

    # Create sessions directory if it doesn't exist
    Path("sessions").mkdir(exist_ok=True)
    Path("sessions/lessons").mkdir(exist_ok=True)
    Path("sessions/reports").mkdir(exist_ok=True)

    # Run example session
    console.print("[cyan]1. Running single session example...[/cyan]\n")
    run_single_session_example()

    # Demonstrate learning
    console.print("\n[cyan]2. Demonstrating learning system...[/cyan]")
    demonstrate_learning_system()

    console.print("\n" + "=" * 60)
    console.print("[green]Example completed![/green]")
    console.print("\nTo run the interactive CLI, use:")
    console.print("  [cyan]python -m src.cli.interactive[/cyan]")
    console.print("\nTo view saved sessions and reports, check:")
    console.print("  [cyan]sessions/[/cyan] directory")


if __name__ == "__main__":
    main()

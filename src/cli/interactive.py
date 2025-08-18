#!/usr/bin/env python3
"""Interactive CLI for red team exploit testing."""

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table
from src.interactive_exploit import InteractiveRedTeam
from src.models import AttackStrategy
from src.utils.session_manager import SessionManager

console = Console()


@click.command()
@click.option(
    "--target-model",
    default="openai/gpt-oss-20b",
    help="Target model to test (default: openai/gpt-oss-20b)",
)
@click.option(
    "--attacker-model",
    default="anthropic/claude-opus-4.1",
    help="Model to generate attacks (default: anthropic/claude-opus-4.1)",
)
@click.option(
    "--evaluator-model",
    default=None,
    help="Model to evaluate responses (default: same as attacker)",
)
@click.option(
    "--sessions-dir",
    default="sessions",
    type=click.Path(),
    help="Directory to store sessions",
)
def main(
    target_model: str,
    attacker_model: str,
    evaluator_model: str | None,
    sessions_dir: str,
) -> None:
    """Interactive red team testing interface."""
    console.print(
        Panel.fit(
            "[bold cyan]Interactive Red Team Testing System[/bold cyan]\n"
            "[dim]Test AI models for vulnerabilities using multi-turn attacks[/dim]",
            border_style="cyan",
        )
    )

    # Use attacker model as evaluator if not specified
    if evaluator_model is None:
        evaluator_model = attacker_model

    # Initialize components
    session_manager = SessionManager(sessions_dir)
    red_team = InteractiveRedTeam(
        target_model=target_model,
        attacker_model=attacker_model,
        evaluator_model=evaluator_model,
    )

    console.print("\n[green]✓[/green] Initialized with:")
    console.print(f"  Target: [cyan]{target_model}[/cyan]")
    console.print(f"  Attacker: [cyan]{attacker_model}[/cyan]")
    console.print(f"  Evaluator: [cyan]{evaluator_model}[/cyan]\n")

    # Main interaction loop
    while True:
        console.print("\n[bold]Commands:[/bold]")
        console.print("  [cyan]1[/cyan] - Run attack")
        console.print("  [cyan]2[/cyan] - View session summary")
        console.print("  [cyan]3[/cyan] - Save session")
        console.print("  [cyan]4[/cyan] - Load previous session")
        console.print("  [cyan]5[/cyan] - View statistics")
        console.print("  [cyan]6[/cyan] - Export report")
        console.print("  [cyan]q[/cyan] - Quit")

        choice = Prompt.ask("\n[bold]Choose action[/bold]", default="1")

        if choice == "1":
            run_attack(red_team)
        elif choice == "2":
            view_summary(red_team)
        elif choice == "3":
            save_session(red_team, session_manager)
        elif choice == "4":
            load_session(session_manager)
        elif choice == "5":
            view_statistics(session_manager)
        elif choice == "6":
            export_report(red_team, session_manager)
        elif choice.lower() == "q":
            if Confirm.ask("\n[yellow]Save session before exiting?[/yellow]"):
                save_session(red_team, session_manager)
            console.print("\n[dim]Goodbye![/dim]")
            break
        else:
            console.print("[red]Invalid choice[/red]")


def run_attack(red_team: InteractiveRedTeam) -> None:
    """Run an attack attempt."""
    console.print("\n[bold]Attack Configuration[/bold]")

    # Select strategy
    strategies = list(AttackStrategy)
    console.print("\n[bold]Available Strategies:[/bold]")
    for i, strategy in enumerate(strategies, 1):
        console.print(f"  [cyan]{i}[/cyan] - {strategy.value}")

    strategy_idx = IntPrompt.ask(
        "Select strategy",
        default=1,
        choices=[str(i) for i in range(1, len(strategies) + 1)],
    )
    strategy = strategies[strategy_idx - 1]

    # Select number of steps
    steps = IntPrompt.ask(
        "Number of steps (1=single-turn, 2+=multi-turn)",
        default=2,
        choices=["1", "2", "3", "4", "5"],
    )

    console.print(f"\n[yellow]Running {steps}-step {strategy.value} attack...[/yellow]\n")

    try:
        attempt = red_team.run_attack(strategy=strategy, steps=steps)

        # Display conversation
        console.print("[bold]Conversation:[/bold]\n")
        for turn in attempt.turns:
            if turn.role == "attacker":
                console.print(f"[red]→ Attacker (Turn {turn.turn_number}):[/red]")
                if turn.is_exploit_turn:
                    console.print("[yellow][EXPLOIT TURN][/yellow]")
            else:
                console.print("[blue]← Target:[/blue]")

            # Display content in a panel for better readability
            content = turn.content[:500]
            if len(turn.content) > 500:
                content += "... [truncated]"
            console.print(Panel(content, border_style="dim"))

        # Display evaluation
        console.print("\n[bold]Evaluation:[/bold]")
        if attempt.evaluation:
            status = "[green]✓ VULNERABLE[/green]" if attempt.success else "[red]✗ SAFE[/red]"
            console.print(f"  Status: {status}")
            console.print(f"  Confidence: [cyan]{attempt.evaluation.confidence:.1%}[/cyan]")
            console.print(f"  Reasoning: {attempt.evaluation.reasoning}")

            if attempt.evaluation.evidence:
                console.print("  Evidence:")
                for evidence in attempt.evaluation.evidence[:3]:
                    console.print(f"    • {evidence}")

    except Exception as e:
        console.print(f"[red]Error running attack: {e}[/red]")


def view_summary(red_team: InteractiveRedTeam) -> None:
    """View current session summary."""
    summary = red_team.get_session_summary()
    console.print(Panel(summary, title="Session Summary", border_style="cyan"))


def save_session(red_team: InteractiveRedTeam, session_manager: SessionManager) -> None:
    """Save the current session."""
    try:
        filepath = red_team.save_session()
        console.print(f"[green]✓[/green] Session saved to: {filepath}")
    except Exception as e:
        console.print(f"[red]Error saving session: {e}[/red]")


def load_session(session_manager: SessionManager) -> None:
    """Load a previous session."""
    sessions = session_manager.list_sessions()

    if not sessions:
        console.print("[yellow]No sessions found[/yellow]")
        return

    # Display sessions table
    table = Table(title="Available Sessions")
    table.add_column("ID", style="cyan")
    table.add_column("Start Time")
    table.add_column("Attempts")
    table.add_column("Success Rate")
    table.add_column("Target Model")

    for i, session_info in enumerate(sessions[:10], 1):
        success_rate = (
            session_info["successful_attempts"] / session_info["total_attempts"]
            if session_info["total_attempts"] > 0
            else 0
        )
        table.add_row(
            str(i),
            session_info["start_time"][:19],
            str(session_info["total_attempts"]),
            f"{success_rate:.1%}",
            session_info["target_model"],
        )

    console.print(table)

    # Select session
    session_idx = IntPrompt.ask(
        "Select session to load",
        default=1,
        choices=[str(i) for i in range(1, min(11, len(sessions) + 1))],
    )

    try:
        session = session_manager.load_session(sessions[session_idx - 1]["file"])
        console.print(f"[green]✓[/green] Loaded session {session.session_id[:8]}")

        # Display session details
        console.print("\n[bold]Session Details:[/bold]")
        console.print(f"  Total Attempts: {session.total_attempts}")
        console.print(f"  Successful: {session.successful_attempts}")
        console.print(f"  Target Model: {session.target_model}")

    except Exception as e:
        console.print(f"[red]Error loading session: {e}[/red]")


def view_statistics(session_manager: SessionManager) -> None:
    """View overall statistics."""
    stats = session_manager.get_statistics()

    console.print("\n[bold]Overall Statistics:[/bold]\n")
    console.print(f"  Total Sessions: [cyan]{stats['total_sessions']}[/cyan]")
    console.print(f"  Total Attempts: [cyan]{stats['total_attempts']}[/cyan]")
    console.print(f"  Successful Attacks: [green]{stats['successful_attempts']}[/green]")
    console.print(f"  Overall Success Rate: [yellow]{stats['success_rate']:.1%}[/yellow]")

    if stats["strategies_used"]:
        console.print("\n[bold]Strategy Performance:[/bold]")
        for strategy, data in stats["strategies_used"].items():
            rate = data["success"] / data["total"] if data["total"] > 0 else 0
            console.print(f"  {strategy}: {rate:.1%} ({data['success']}/{data['total']})")

    if stats["models_tested"]:
        console.print(f"\n[bold]Models Tested:[/bold] {', '.join(stats['models_tested'])}")


def export_report(red_team: InteractiveRedTeam, session_manager: SessionManager) -> None:
    """Export session report."""
    try:
        report_file = session_manager.export_session_report(red_team.session)
        console.print(f"[green]✓[/green] Report exported to: {report_file}")
    except Exception as e:
        console.print(f"[red]Error exporting report: {e}[/red]")


if __name__ == "__main__":
    main()

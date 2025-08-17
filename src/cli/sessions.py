#!/usr/bin/env python3
"""CLI for viewing and managing red team sessions."""

import json
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import IntPrompt, Prompt
from rich.table import Table

from src.utils.session_manager import SessionManager

console = Console()


@click.command()
@click.option(
    "--sessions-dir",
    default="sessions",
    type=click.Path(),
    help="Directory containing sessions",
)
@click.option(
    "--export",
    is_flag=True,
    help="Export session as markdown report",
)
def main(sessions_dir: str, export: bool) -> None:
    """View and manage red team testing sessions."""
    
    console.print(
        Panel.fit(
            "[bold cyan]Session Viewer[/bold cyan]\n"
            "[dim]Browse and analyze attack sessions[/dim]",
            border_style="cyan",
        )
    )

    session_manager = SessionManager(sessions_dir)
    
    while True:
        console.print("\n[bold]Options:[/bold]")
        console.print("  [cyan]1[/cyan] - List sessions")
        console.print("  [cyan]2[/cyan] - View session details")
        console.print("  [cyan]3[/cyan] - View statistics")
        console.print("  [cyan]4[/cyan] - View lessons learned")
        console.print("  [cyan]5[/cyan] - Export session report")
        console.print("  [cyan]q[/cyan] - Quit")
        
        choice = Prompt.ask("\nChoice", default="1")
        
        if choice == "1":
            list_sessions(session_manager)
        elif choice == "2":
            view_session(session_manager)
        elif choice == "3":
            view_statistics(session_manager)
        elif choice == "4":
            view_lessons(session_manager)
        elif choice == "5":
            export_session(session_manager)
        elif choice.lower() == "q":
            break
        else:
            console.print("[red]Invalid choice[/red]")


def list_sessions(manager: SessionManager) -> None:
    """List all available sessions."""
    sessions = manager.list_sessions()
    
    if not sessions:
        console.print("\n[yellow]No sessions found[/yellow]")
        return
    
    table = Table(title="Red Team Sessions")
    table.add_column("#", style="dim")
    table.add_column("Session ID", style="cyan")
    table.add_column("Start Time")
    table.add_column("Attempts")
    table.add_column("Success Rate", style="green")
    table.add_column("Target")
    
    for i, session in enumerate(sessions[:20], 1):
        success_rate = (
            session["successful_attempts"] / session["total_attempts"]
            if session["total_attempts"] > 0 else 0
        )
        
        table.add_row(
            str(i),
            session["session_id"],
            session["start_time"][:19] if session["start_time"] != "unknown" else "unknown",
            str(session["total_attempts"]),
            f"{success_rate:.0%}",
            session["target_model"].split("/")[-1] if "/" in session["target_model"] else session["target_model"],
        )
    
    console.print("\n")
    console.print(table)


def view_session(manager: SessionManager) -> None:
    """View detailed session information."""
    sessions = manager.list_sessions()
    
    if not sessions:
        console.print("\n[yellow]No sessions found[/yellow]")
        return
    
    # List sessions first
    list_sessions(manager)
    
    # Select session
    idx = IntPrompt.ask(
        "\nSelect session number",
        default=1,
        choices=[str(i) for i in range(1, min(21, len(sessions) + 1))]
    )
    
    # Load session
    session = manager.load_session(sessions[idx - 1]["file"])
    
    console.print(f"\n[bold]Session {session.session_id[:8]}[/bold]")
    console.print(f"Start: {session.start_time}")
    console.print(f"End: {session.end_time or 'In Progress'}")
    console.print(f"Target: [cyan]{session.target_model}[/cyan]")
    console.print(f"Attacker: [cyan]{session.attacker_model}[/cyan]")
    console.print(f"Total Attempts: {session.total_attempts}")
    console.print(f"Successful: {session.successful_attempts}")
    
    if session.attempts:
        console.print("\n[bold]Attempts:[/bold]")
        for i, attempt in enumerate(session.attempts, 1):
            status = "✓" if attempt.success else "✗"
            console.print(f"\n[cyan]Attempt {i}:[/cyan] {status} {attempt.strategy.value} ({attempt.steps} steps)")
            
            # Show conversation snippet
            if attempt.turns:
                for turn in attempt.turns[:2]:  # Show first 2 turns
                    if turn.role == "attacker":
                        console.print(f"  → {turn.content[:100]}...")
                    else:
                        console.print(f"  ← {turn.content[:100]}...")
            
            if attempt.evaluation:
                console.print(f"  Confidence: {attempt.evaluation.confidence:.0%}")
                console.print(f"  Reasoning: {attempt.evaluation.reasoning[:100]}...")


def view_statistics(manager: SessionManager) -> None:
    """View overall statistics."""
    stats = manager.get_statistics()
    
    console.print("\n[bold]Overall Statistics[/bold]\n")
    console.print(f"Total Sessions: [cyan]{stats['total_sessions']}[/cyan]")
    console.print(f"Total Attempts: [cyan]{stats['total_attempts']}[/cyan]")
    console.print(f"Successful: [green]{stats['successful_attempts']}[/green]")
    console.print(f"Success Rate: [yellow]{stats['success_rate']:.1%}[/yellow]")
    
    if stats["strategies_used"]:
        console.print("\n[bold]Strategy Performance:[/bold]")
        
        # Sort by success rate
        sorted_strategies = sorted(
            stats["strategies_used"].items(),
            key=lambda x: x[1]["success"] / x[1]["total"] if x[1]["total"] > 0 else 0,
            reverse=True
        )
        
        for strategy, data in sorted_strategies:
            rate = data["success"] / data["total"] if data["total"] > 0 else 0
            bar = "█" * int(rate * 20) + "░" * (20 - int(rate * 20))
            console.print(f"  {strategy:20} {bar} {rate:.0%} ({data['success']}/{data['total']})")
    
    if stats["models_tested"]:
        console.print(f"\n[bold]Models Tested:[/bold] {', '.join(stats['models_tested'])}")


def view_lessons(manager: SessionManager) -> None:
    """View lessons learned from sessions."""
    console.print("\n[bold]Available Model Lessons:[/bold]")
    
    lessons_dir = Path(manager.lessons_dir)
    lesson_files = list(lessons_dir.glob("*_lessons.json"))
    
    if not lesson_files:
        console.print("[yellow]No lessons found yet[/yellow]")
        return
    
    for i, file in enumerate(lesson_files, 1):
        model_name = file.stem.replace("_lessons", "").replace("_", "/")
        console.print(f"  [cyan]{i}[/cyan] - {model_name}")
    
    idx = IntPrompt.ask(
        "\nSelect model",
        default=1,
        choices=[str(i) for i in range(1, len(lesson_files) + 1)]
    )
    
    # Load lessons
    with open(lesson_files[idx - 1]) as f:
        data = json.load(f)
    
    console.print(f"\n[bold]Lessons for {data['model_name']}[/bold]")
    console.print(f"Sessions: {data['total_sessions']}")
    console.print(f"Total Attempts: {data['total_attempts']}")
    
    if data.get("strategies"):
        console.print("\n[bold]Strategy Success Rates:[/bold]")
        for strategy, rate in data["strategies"].items():
            console.print(f"  {strategy}: {rate:.1%}")
    
    if data.get("best_patterns"):
        console.print("\n[bold]Successful Patterns:[/bold]")
        for pattern in data["best_patterns"][:5]:
            console.print(f"  • {pattern}")
    
    if data.get("lessons"):
        console.print("\n[bold]Key Insights:[/bold]")
        for lesson in data["lessons"][:3]:
            console.print(f"\n  [cyan]{lesson['strategy']}[/cyan]")
            console.print(f"  Success Rate: {lesson['success_rate']:.0%}")
            for insight in lesson.get("key_insights", [])[:2]:
                console.print(f"    • {insight}")


def export_session(manager: SessionManager) -> None:
    """Export a session as a markdown report."""
    sessions = manager.list_sessions()
    
    if not sessions:
        console.print("\n[yellow]No sessions found[/yellow]")
        return
    
    list_sessions(manager)
    
    idx = IntPrompt.ask(
        "\nSelect session to export",
        default=1,
        choices=[str(i) for i in range(1, min(21, len(sessions) + 1))]
    )
    
    session = manager.load_session(sessions[idx - 1]["file"])
    report_file = manager.export_session_report(session)
    
    console.print(f"\n[green]✓[/green] Report exported to: {report_file}")


if __name__ == "__main__":
    main()
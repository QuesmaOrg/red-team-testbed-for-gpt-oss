#!/usr/bin/env python3
"""CLI for running interactive red team attacks."""

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from src.adaptive_attacker import AdaptiveAttacker
from src.interactive_exploit_v2 import InteractiveRedTeamV2
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
    "--custom",
    is_flag=True,
    help="Use custom prompts instead of generated ones",
)
@click.option(
    "--steps",
    default=None,
    type=int,
    help="Number of conversation turns",
)
@click.option(
    "--batch",
    default=None,
    type=int,
    help="Run multiple adaptive attempts",
)
def main(
    target_model: str,
    attacker_model: str,
    evaluator_model: str | None,
    custom: bool,
    steps: int | None,
    batch: int | None,
) -> None:
    """Run interactive red team attacks."""

    console.print(
        Panel.fit(
            "[bold cyan]Red Team Attack Interface[/bold cyan]\n"
            "[dim]Test AI models for vulnerabilities[/dim]",
            border_style="cyan",
        )
    )

    console.print(f"\n[green]✓[/green] Target: [cyan]{target_model}[/cyan]")

    # Batch/adaptive mode
    if batch:
        console.print(f"[green]✓[/green] Attacker: [cyan]{attacker_model}[/cyan]")
        console.print(f"[green]✓[/green] Batch mode: [cyan]{batch} attempts[/cyan]\n")
        run_adaptive_campaign(target_model, attacker_model, evaluator_model, batch, steps)
        return

    # Single attack mode
    red_team = InteractiveRedTeamV2(
        target_model=target_model,
        attacker_model=attacker_model,
        evaluator_model=evaluator_model,
    )
    session_manager = SessionManager("sessions")

    if custom:
        # Custom prompt mode
        run_custom_attack(red_team)
    else:
        # AI-generated attack mode
        console.print(f"[green]✓[/green] Attacker: [cyan]{attacker_model}[/cyan]\n")
        run_generated_attack(red_team, steps)

    # Save session
    if Confirm.ask("\n[yellow]Save session?[/yellow]", default=True):
        filepath = session_manager.save_session(red_team.session)
        console.print(f"[green]✓[/green] Session saved to: {filepath}")


def run_generated_attack(red_team: InteractiveRedTeamV2, steps: int | None) -> None:
    """Run an AI-generated attack."""

    console.print("[bold]Attack Mode:[/bold]")
    console.print("  [cyan]1[/cyan] - Predefined strategy")
    console.print("  [cyan]2[/cyan] - Custom goal")
    console.print("  [cyan]3[/cyan] - Learn from past sessions")

    mode = Prompt.ask("Choose mode", choices=["1", "2", "3"], default="1")

    strategy = None
    custom_goal = None

    if mode == "1":
        # Select strategy
        strategies = list(AttackStrategy)
        console.print("\n[bold]Available Strategies:[/bold]")
        for i, s in enumerate(strategies, 1):
            console.print(f"  [cyan]{i}[/cyan] - {s.value}")

        idx = IntPrompt.ask(
            "Select strategy", default=1, choices=[str(i) for i in range(1, len(strategies) + 1)]
        )
        strategy = strategies[idx - 1]

    elif mode == "2":
        # Custom goal
        console.print("\n[dim]Describe what vulnerability you want to test[/dim]")
        custom_goal = Prompt.ask("Goal")

    else:
        # Learn from past (simplified for now)
        custom_goal = "execute code or reveal system information based on past successful patterns"

    # Get number of steps
    if steps is None:
        steps = IntPrompt.ask("\nNumber of turns", default=2, choices=["1", "2", "3", "4", "5"])

    # Get number of repetitions
    console.print("\n[dim]How many times to repeat? (0 for infinite)[/dim]")
    repetitions = IntPrompt.ask("Repetitions", default=1)

    # Save session after each attempt
    session_manager = SessionManager("sessions")

    # Run attacks
    attempt_count = 0
    successful_count = 0

    try:
        while repetitions == 0 or attempt_count < repetitions:
            attempt_count += 1

            # Show progress
            if repetitions == 0:
                console.print(f"\n[bold]═══ Attempt {attempt_count} (∞) ═══[/bold]")
            else:
                console.print(f"\n[bold]═══ Attempt {attempt_count}/{repetitions} ═══[/bold]")

            # Run attack
            console.print("\n" + "=" * 60)
            attempt = red_team.run_interactive_attack(
                strategy=strategy, custom_goal=custom_goal, steps=steps, show_live=True
            )

            # Track success
            if attempt.success:
                successful_count += 1

            # Summary
            console.print("\n" + "=" * 60)
            console.print("\n[bold]Attack Complete[/bold]")
            console.print(f"ID: {attempt.attempt_id[:8]}")
            console.print(f"Success: {'✓' if attempt.success else '✗'}")

            # Save session after each attempt
            session_manager.save_session(red_team.session)
            console.print("[dim]Session auto-saved[/dim]")

            # Ask to continue if not infinite
            if repetitions != 0 and attempt_count < repetitions:
                if not Confirm.ask("\n[yellow]Continue to next attempt?[/yellow]", default=True):
                    break
            elif repetitions == 0 and not Confirm.ask(
                "\n[yellow]Run another attempt?[/yellow]", default=True
            ):
                break

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")

    # Final summary
    console.print("\n[bold]Session Summary:[/bold]")
    console.print(f"Total attempts: {attempt_count}")
    console.print(f"Successful: {successful_count} ({successful_count / attempt_count * 100:.0%})")

    # Final save
    filepath = session_manager.save_session(red_team.session)
    console.print(f"[green]✓[/green] Final session saved to: {filepath}")


def run_adaptive_campaign(
    target_model: str,
    attacker_model: str,
    evaluator_model: str | None,
    num_attempts: int,
    steps: int | None,
) -> None:
    """Run an adaptive campaign with multiple attempts."""

    # Initialize adaptive attacker
    attacker = AdaptiveAttacker(
        target_model=target_model,
        attacker_model=attacker_model,
        evaluator_model=evaluator_model,
    )

    console.print("[bold]Campaign Mode:[/bold]")
    console.print("  [cyan]1[/cyan] - Automatic (fully adaptive)")
    console.print("  [cyan]2[/cyan] - Semi-guided (choose base strategy)")
    console.print("  [cyan]3[/cyan] - Goal-focused (specify target vulnerability)")

    mode = Prompt.ask("Choose mode", choices=["1", "2", "3"], default="1")

    base_strategy = None
    initial_goal = None
    vary = True

    if mode == "1":
        # Fully automatic
        console.print("\n[dim]Running fully adaptive campaign...[/dim]")

    elif mode == "2":
        # Choose base strategy
        strategies = list(AttackStrategy)
        console.print("\n[bold]Base Strategy:[/bold]")
        for i, s in enumerate(strategies, 1):
            console.print(f"  [cyan]{i}[/cyan] - {s.value}")

        idx = IntPrompt.ask(
            "Select base strategy",
            default=1,
            choices=[str(i) for i in range(1, len(strategies) + 1)],
        )
        base_strategy = strategies[idx - 1]

        vary = Confirm.ask("Vary approach between attempts?", default=True)

    else:
        # Goal-focused
        console.print("\n[dim]Describe the vulnerability you want to find[/dim]")
        initial_goal = Prompt.ask("Target vulnerability")
        vary = Confirm.ask("Allow strategy variations?", default=True)

    # Determine steps range
    if steps:
        steps_range = (steps, steps)
    else:
        min_steps = IntPrompt.ask("\nMinimum steps per attempt", default=1, choices=["1", "2", "3"])
        max_steps = IntPrompt.ask(
            "Maximum steps per attempt", default=3, choices=["1", "2", "3", "4", "5"]
        )
        steps_range = (min_steps, max_steps)

    # Run the campaign
    console.print("\n" + "=" * 60)
    results = attacker.run_adaptive_campaign(
        num_attempts=num_attempts,
        base_strategy=base_strategy,
        initial_goal=initial_goal,
        steps_range=steps_range,
        vary_approach=vary,
    )

    # Final message
    console.print("\n[bold]Campaign Complete![/bold]")
    if results["successful"] > 0:
        console.print(f"[green]Found {results['successful']} vulnerabilities![/green]")
    else:
        console.print("[yellow]No vulnerabilities found, but learned valuable patterns.[/yellow]")


def run_custom_attack(red_team: InteractiveRedTeamV2) -> None:
    """Run attack with custom prompts."""

    console.print("\n[bold]Custom Prompt Mode[/bold]")
    console.print("[dim]Enter your prompts one by one. Type 'done' when finished.[/dim]\n")

    prompts = []
    while True:
        turn = len(prompts) + 1
        console.print(f"[cyan]Turn {turn}:[/cyan]")
        prompt = Prompt.ask("Prompt (or 'done')")

        if prompt.lower() == "done":
            if len(prompts) == 0:
                console.print("[red]Need at least one prompt![/red]")
                continue
            break

        prompts.append(prompt)

        if not Confirm.ask("Add another turn?", default=True):
            break

    # Get number of repetitions
    console.print("\n[dim]How many times to repeat? (0 for infinite)[/dim]")
    repetitions = IntPrompt.ask("Repetitions", default=1)

    # Save session after each attempt
    session_manager = SessionManager("sessions")

    # Run attacks
    attempt_count = 0
    successful_count = 0

    try:
        while repetitions == 0 or attempt_count < repetitions:
            attempt_count += 1

            # Show progress
            if repetitions == 0:
                console.print(f"\n[bold]═══ Attempt {attempt_count} (∞) ═══[/bold]")
            else:
                console.print(f"\n[bold]═══ Attempt {attempt_count}/{repetitions} ═══[/bold]")

            # Run with custom prompts
            console.print("\n" + "=" * 60)
            console.print("[bold cyan]Executing Custom Attack[/bold cyan]\n")

            attempt = red_team.run_custom_attack(prompts)

            # Track success
            if attempt.success:
                successful_count += 1

            # Summary
            console.print("\n" + "=" * 60)
            console.print("\n[bold]Attack Complete[/bold]")
            console.print(f"Success: {'✓' if attempt.success else '✗'}")

            # Save session after each attempt
            session_manager.save_session(red_team.session)
            console.print("[dim]Session auto-saved[/dim]")

            # Ask to continue
            if repetitions != 0 and attempt_count < repetitions:
                if not Confirm.ask("\n[yellow]Continue to next attempt?[/yellow]", default=True):
                    break
            elif repetitions == 0 and not Confirm.ask(
                "\n[yellow]Run another attempt?[/yellow]", default=True
            ):
                break

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")

    # Final summary
    console.print("\n[bold]Session Summary:[/bold]")
    console.print(f"Total attempts: {attempt_count}")
    console.print(f"Successful: {successful_count} ({successful_count / attempt_count * 100:.0%})")

    # Final save
    filepath = session_manager.save_session(red_team.session)
    console.print(f"[green]✓[/green] Final session saved to: {filepath}")


if __name__ == "__main__":
    main()

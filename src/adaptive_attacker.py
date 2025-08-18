"""Adaptive attack system that learns and improves with each attempt."""

import random
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table
from src.interactive_exploit_v2 import InteractiveRedTeamV2
from src.models import AttackAttempt, AttackStrategy
from src.utils.session_manager import SessionManager

console = Console()


class AdaptiveAttacker:
    """Runs multiple attacks, learning and adapting after each one."""

    def __init__(
        self,
        target_model: str = "openai/gpt-oss-20b",
        attacker_model: str = "anthropic/claude-opus-4.1",
        evaluator_model: str | None = None,
    ) -> None:
        self.red_team = InteractiveRedTeamV2(
            target_model=target_model,
            attacker_model=attacker_model,
            evaluator_model=evaluator_model,
        )
        self.session_manager = SessionManager("sessions")

        # Track what we've learned this run
        self.run_history = []
        self.successful_patterns = []
        self.failed_patterns = []
        self.strategy_performance = {}

    def run_adaptive_campaign(
        self,
        num_attempts: int = 5,
        base_strategy: AttackStrategy | None = None,
        initial_goal: str | None = None,
        steps_range: tuple[int, int] = (1, 3),
        vary_approach: bool = True,
    ) -> dict:
        """Run multiple attacks, adapting based on results."""

        console.print(
            Panel.fit(
                f"[bold cyan]Adaptive Attack Campaign[/bold cyan]\n"
                f"Running {num_attempts} attempts with learning",
                border_style="cyan",
            )
        )

        results = {
            "total_attempts": 0,
            "successful": 0,
            "patterns_discovered": [],
            "best_strategy": None,
            "best_confidence": 0.0,
        }

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Running adaptive campaign...", total=num_attempts)

            for attempt_num in range(1, num_attempts + 1):
                console.print(f"\n[bold]═══ Attempt {attempt_num}/{num_attempts} ═══[/bold]")

                # Adapt strategy based on previous results
                strategy, custom_goal, steps = self._adapt_approach(
                    attempt_num, base_strategy, initial_goal, steps_range, vary_approach
                )

                # Show what we're trying
                console.print(f"[dim]Strategy: {strategy.value if strategy else 'custom'}[/dim]")
                console.print(f"[dim]Steps: {steps}[/dim]")
                if custom_goal:
                    console.print(f"[dim]Goal variant: {custom_goal[:100]}...[/dim]")

                # Run the attack
                try:
                    attempt = self.red_team.run_interactive_attack(
                        strategy=strategy,
                        custom_goal=custom_goal,
                        steps=steps,
                        show_live=False,  # Less verbose in batch mode
                    )

                    # Record results
                    self.run_history.append(attempt)
                    results["total_attempts"] += 1

                    if attempt.success:
                        results["successful"] += 1
                        self._record_success(attempt)
                        console.print(
                            f"[green]✓ Success![/green] Confidence: {attempt.evaluation.confidence:.0%}"
                        )

                        if attempt.evaluation.confidence > results["best_confidence"]:
                            results["best_confidence"] = attempt.evaluation.confidence
                            results["best_strategy"] = strategy.value if strategy else custom_goal
                    else:
                        self._record_failure(attempt)
                        console.print("[red]✗ Failed[/red] - Learning from this...")

                    # Learn from this attempt
                    self._learn_from_attempt(attempt, attempt_num)

                except Exception as e:
                    console.print(f"[red]Error in attempt: {e}[/red]")

                progress.update(task, advance=1)

        # Show summary
        self._show_campaign_summary(results)

        # Save the session
        if self.run_history:
            self.red_team.session.end_time = datetime.now().isoformat()
            session_file = self.session_manager.save_session(self.red_team.session)
            console.print(f"\n[green]✓[/green] Campaign saved to: {session_file}")

        return results

    def _adapt_approach(
        self,
        attempt_num: int,
        base_strategy: AttackStrategy | None,
        initial_goal: str | None,
        steps_range: tuple[int, int],
        vary_approach: bool,
    ) -> tuple[AttackStrategy | None, str | None, int]:
        """Adapt the approach based on what we've learned."""

        # First attempt - use base settings
        if attempt_num == 1:
            steps = random.randint(*steps_range)
            return base_strategy, initial_goal, steps

        # Subsequent attempts - adapt
        if not vary_approach:
            # Just retry with same approach but different phrasing
            steps = random.randint(*steps_range)
            if initial_goal:
                goal_variant = self._vary_goal(initial_goal, attempt_num)
                return None, goal_variant, steps
            return base_strategy, None, steps

        # Vary the approach based on what's worked
        if self.successful_patterns and random.random() < 0.7:  # 70% chance to exploit success
            return self._exploit_success_pattern()

        if (
            self.failed_patterns and random.random() < 0.3
        ):  # 30% chance to retry failed with variation
            return self._retry_failed_with_variation()

        # Try a different strategy
        return self._try_different_strategy(base_strategy, initial_goal, steps_range)

    def _vary_goal(self, goal: str, attempt_num: int) -> str:
        """Create variations of the goal."""
        variations = [
            f"{goal} (focusing on edge cases)",
            f"{goal} (with emphasis on system behavior)",
            f"{goal} (testing boundary conditions)",
            f"Alternative approach: {goal}",
            f"Refined test: {goal}",
        ]

        # Add learned elements
        if self.successful_patterns:
            variations.append(
                f"{goal} (incorporating successful pattern: {self.successful_patterns[-1][:50]})"
            )

        return variations[attempt_num % len(variations)]

    def _exploit_success_pattern(self) -> tuple[AttackStrategy | None, str | None, int]:
        """Build on successful patterns."""
        last_success = next((a for a in reversed(self.run_history) if a.success), None)

        if last_success:
            # Use same strategy but vary the approach slightly
            strategy = last_success.strategy
            steps = last_success.steps

            # Modify based on what worked
            if last_success.evaluation and last_success.evaluation.evidence:
                evidence_str = " ".join(last_success.evaluation.evidence[:2])
                goal = f"Build on previous success with focus on: {evidence_str}"
                return None, goal, steps

            return strategy, None, steps

        return None, "Exploit discovered vulnerability patterns", 2

    def _retry_failed_with_variation(self) -> tuple[AttackStrategy | None, str | None, int]:
        """Retry a failed approach with variations."""
        last_failure = next((a for a in reversed(self.run_history) if not a.success), None)

        if last_failure:
            # Try different number of steps
            new_steps = 3 if last_failure.steps <= 2 else 1

            # Modify the approach
            if last_failure.strategy == AttackStrategy.TRUST_BUILDING:
                return AttackStrategy.HELPFUL_ASSISTANT, None, new_steps
            elif last_failure.strategy == AttackStrategy.AUTHORITY_APPEAL:
                return AttackStrategy.COMPLIANCE_REQUIREMENT, None, new_steps
            else:
                return AttackStrategy.SIDE_TASK, None, new_steps

        return AttackStrategy.TECHNICAL_CONFUSION, None, 2

    def _try_different_strategy(
        self,
        base_strategy: AttackStrategy | None,
        initial_goal: str | None,
        steps_range: tuple[int, int],
    ) -> tuple[AttackStrategy | None, str | None, int]:
        """Try a completely different strategy."""

        # Get strategies we haven't tried much
        all_strategies = list(AttackStrategy)

        # Sort by least tried
        strategy_counts = {}
        for attempt in self.run_history:
            s = attempt.strategy
            strategy_counts[s] = strategy_counts.get(s, 0) + 1

        untried = [s for s in all_strategies if s not in strategy_counts]
        if untried:
            return random.choice(untried), None, random.randint(*steps_range)

        # Try least used strategy
        least_used = min(all_strategies, key=lambda s: strategy_counts.get(s, 0))
        return least_used, None, random.randint(*steps_range)

    def _record_success(self, attempt: AttackAttempt) -> None:
        """Record successful patterns."""
        if attempt.turns:
            exploit_turn = next((t for t in attempt.turns if t.is_exploit_turn), attempt.turns[-1])
            self.successful_patterns.append(exploit_turn.content[:200])

        # Update strategy performance
        strategy = attempt.strategy
        if strategy not in self.strategy_performance:
            self.strategy_performance[strategy] = {"success": 0, "total": 0}
        self.strategy_performance[strategy]["success"] += 1
        self.strategy_performance[strategy]["total"] += 1

    def _record_failure(self, attempt: AttackAttempt) -> None:
        """Record failed patterns."""
        if attempt.turns:
            exploit_turn = next((t for t in attempt.turns if t.is_exploit_turn), attempt.turns[-1])
            self.failed_patterns.append(exploit_turn.content[:200])

        # Update strategy performance
        strategy = attempt.strategy
        if strategy not in self.strategy_performance:
            self.strategy_performance[strategy] = {"success": 0, "total": 0}
        self.strategy_performance[strategy]["total"] += 1

    def _learn_from_attempt(self, attempt: AttackAttempt, attempt_num: int) -> None:
        """Extract lessons from this attempt."""
        console.print(f"\n[dim]Learning from attempt {attempt_num}...[/dim]")

        if attempt.success and attempt.evaluation:
            # What made this successful?
            if attempt.evaluation.evidence:
                console.print("[green]Key success factors:[/green]")
                for evidence in attempt.evaluation.evidence[:3]:
                    console.print(f"  • {evidence}")

            # Store for future use
            insight = (
                f"Attempt {attempt_num}: {attempt.strategy.value} with {attempt.steps} steps worked"
            )
            console.print(f"[dim]Insight: {insight}[/dim]")

        elif not attempt.success:
            # Why did this fail?
            console.print("[yellow]Analyzing failure...[/yellow]")
            if attempt.turns and len(attempt.turns) >= 2:
                last_response = attempt.turns[-1].content
                if "cannot" in last_response.lower() or "unable" in last_response.lower():
                    console.print("[dim]Model refused - need more subtle approach[/dim]")
                elif len(last_response) < 100:
                    console.print("[dim]Short response - may need more context building[/dim]")

    def _show_campaign_summary(self, results: dict) -> None:
        """Display summary of the campaign."""
        console.print("\n" + "=" * 60)
        console.print("[bold cyan]Campaign Summary[/bold cyan]\n")

        success_rate = (
            results["successful"] / results["total_attempts"]
            if results["total_attempts"] > 0
            else 0
        )

        table = Table(show_header=False)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="bold")

        table.add_row("Total Attempts", str(results["total_attempts"]))
        table.add_row("Successful", f"{results['successful']} ({success_rate:.0%})")
        table.add_row("Best Confidence", f"{results['best_confidence']:.0%}")
        if results["best_strategy"]:
            table.add_row("Best Strategy", results["best_strategy"][:50])

        console.print(table)

        # Show strategy performance
        if self.strategy_performance:
            console.print("\n[bold]Strategy Performance:[/bold]")
            for strategy, stats in self.strategy_performance.items():
                rate = stats["success"] / stats["total"] if stats["total"] > 0 else 0
                console.print(
                    f"  {strategy.value}: {rate:.0%} ({stats['success']}/{stats['total']})"
                )

        # Show discovered patterns
        if self.successful_patterns:
            console.print("\n[bold]Successful Patterns Found:[/bold]")
            for i, pattern in enumerate(self.successful_patterns[:3], 1):
                console.print(f"  {i}. {pattern[:80]}...")

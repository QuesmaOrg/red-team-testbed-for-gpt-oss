"""
Live display utilities for real-time test progress and results
"""

import atexit
import contextlib
import os
import signal
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from src.models import EvaluationResult

from .model_client import ModelResponse


@dataclass
class TestProgress:
    """Track progress of current test execution"""

    test_name: str
    test_id: str
    category: str
    current_step: str = "Starting..."
    start_time: float = 0.0
    prompt_sent: bool = False
    response_received: bool = False
    evaluation_done: bool = False
    total_tests: int = 0
    current_test_num: int = 0


class LiveDisplay:
    """Handle live display of test progress and results"""

    def __init__(
        self, enable_live: bool = True, quiet_mode: bool = False, verbose: bool = False
    ) -> None:
        self.enable_live = enable_live
        self.quiet_mode = quiet_mode
        self.verbose = verbose

        # Detect if running in interactive shell
        self.is_interactive = self._is_interactive_shell()

        # Timer thread management
        self._timer_thread: threading.Thread | None = None
        self._stop_timer: threading.Event = threading.Event()
        self._timer_progress: TestProgress | None = None
        self._spinner_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        self._spinner_index = 0
        self._live_context = None

        if RICH_AVAILABLE:
            self.console = Console()
        else:
            self.console = None
            # Fall back to basic print if Rich not available
            if enable_live and not quiet_mode:
                print("Note: Install 'rich' for enhanced live display")

        # Set up signal handlers for clean exit
        self._setup_signal_handlers()

    def _is_interactive_shell(self) -> bool:
        """Detect if running in an interactive shell/terminal"""
        # Check multiple indicators for interactive shell
        return (
            # Standard TTY check
            sys.stdout.isatty()
            and sys.stdin.isatty()
            and
            # Not running in a pipe or redirect
            os.isatty(sys.stdout.fileno())
            and
            # Check for common non-interactive environments
            not any(
                env_var in os.environ
                for env_var in [
                    "CI",  # Continuous Integration
                    "GITHUB_ACTIONS",  # GitHub Actions
                    "JENKINS_URL",  # Jenkins
                    "BUILDBOT_WORKER_NAME",  # Buildbot
                    "TF_BUILD",  # Azure DevOps
                ]
            )
            and
            # Terminal environment variable exists (usually set in interactive shells)
            "TERM" in os.environ
            and os.environ.get("TERM") != "dumb"
        )

    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful cleanup"""

        def signal_handler(signum: int, frame: object) -> None:
            """Handle interrupt signals (Ctrl+C, etc.)"""
            self._cleanup_display()
            # Re-raise the KeyboardInterrupt to maintain normal behavior
            if signum == signal.SIGINT:
                raise KeyboardInterrupt()

        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, signal_handler)  # Termination

        # Also register cleanup function to run at exit
        atexit.register(self._cleanup_display)

    def _cleanup_display(self) -> None:
        """Clean up display state and restore terminal"""
        try:
            # Stop any running timer
            self.stop_thinking_timer()

            # Clean up Rich live context if it exists
            if self._live_context:
                with contextlib.suppress(Exception):
                    self._live_context.stop()
                    self._live_context = None

            # Restore cursor and clear any remaining output
            if self.console and self.is_interactive:
                with contextlib.suppress(Exception):
                    # Show cursor and reset terminal state
                    self.console.show_cursor(True)
                    self.console.print("", end="")  # Ensure clean state
            elif self.is_interactive:
                # Fallback: show cursor and clear line
                with contextlib.suppress(Exception):
                    sys.stdout.write("\r\033[K\033[?25h")  # Clear line and show cursor
                    sys.stdout.flush()
        except Exception:
            # Ignore any errors during cleanup to avoid masking original exceptions
            pass

    def start_category(self, category: str, total_tests: int) -> None:
        """Display category start information"""
        if self.quiet_mode:
            print(f"🔍 Testing {category} category... [0/{total_tests}]", end=" ", flush=True)
            return

        if self.console:
            title = f"🔍 Testing Category: {category.upper()}"
            subtitle = f"Total tests: {total_tests}"
            panel = Panel(
                Text(subtitle, style="cyan"), title=title, title_align="left", style="blue"
            )
            self.console.print(panel)
            self.console.print()
        else:
            print(f"\n🔍 Testing category: {category}")
            print(f"Total tests: {total_tests}")
            print("=" * 50)

    def start_test(
        self, test_name: str, test_id: str, category: str, current_num: int, total_tests: int
    ) -> TestProgress:
        """Start displaying a test"""
        progress = TestProgress(
            test_name=test_name,
            test_id=test_id,
            category=category,
            start_time=time.time(),
            current_test_num=current_num,
            total_tests=total_tests,
        )

        if self.quiet_mode:
            return progress

        if self.console:
            test_header = f"🧪 Test [{current_num}/{total_tests}]: {test_name}"
            self.console.print(f"\n{test_header}", style="bold yellow")
            if self.verbose:
                self.console.print(f"   ID: {test_id} | Category: {category}", style="dim")
            self.console.print("─" * min(60, len(test_header)))
        else:
            print(f"\n🧪 Test [{current_num}/{total_tests}]: {test_name}")
            if self.verbose:
                print(f"   ID: {test_id} | Category: {category}")
            print("─" * 50)

        return progress

    def show_prompt(
        self,
        progress: TestProgress,
        prompt: str,
        system_prompt: str = "",
        show_display: bool = True,
    ) -> None:
        """Display the prompt being sent"""
        if self.quiet_mode or not show_display:
            return

        progress.current_step = "Sending prompt..."
        progress.prompt_sent = True

        if self.console:
            # Main prompt
            prompt_panel = Panel(
                Text(prompt, style="white"),
                title="📝 PROMPT",
                title_align="left",
                style="yellow",
                padding=(1, 2),
            )
            self.console.print(prompt_panel)

            # System prompt if present
            if system_prompt:
                system_panel = Panel(
                    Text(system_prompt, style="italic cyan"),
                    title="⚙️  SYSTEM PROMPT",
                    title_align="left",
                    style="cyan",
                    padding=(0, 2),
                )
                self.console.print(system_panel)

        else:
            print("\n📝 PROMPT:")
            print(f"   {prompt}")
            if system_prompt:
                print("\n⚙️  SYSTEM PROMPT:")
                print(f"   {system_prompt}")

    def start_thinking_timer(self, progress: TestProgress) -> None:
        """Start a live timer that updates while waiting for response"""
        if self.quiet_mode:
            return

        # Only use fast updates in interactive shells, slower updates otherwise
        if not self.is_interactive:
            # In non-interactive mode, show a simple static message
            elapsed = time.time() - progress.start_time
            thinking_msg = f"⏱️  Waiting for response... [{elapsed:.1f}s]"
            if self.console:
                self.console.print(thinking_msg, style="dim")
            else:
                print(thinking_msg)
            return

        # Stop any existing timer first
        self.stop_thinking_timer()

        # Reset timer state
        self._stop_timer.clear()
        self._timer_progress = progress
        self._spinner_index = 0

        # Start timer thread
        self._timer_thread = threading.Thread(target=self._timer_update_loop, daemon=True)
        self._timer_thread.start()

    def stop_thinking_timer(self) -> None:
        """Stop the live timer"""
        if self._timer_thread and self._timer_thread.is_alive():
            self._stop_timer.set()
            # Give thread a moment to stop gracefully
            self._timer_thread.join(timeout=0.2)

        # Ensure any remaining display is cleared
        if self._live_context:
            with contextlib.suppress(Exception):
                self._live_context.stop()
                self._live_context = None
        elif not self.quiet_mode:
            # Clear line for non-Rich fallback
            with contextlib.suppress(Exception):
                print("\r" + " " * 60 + "\r", end="", flush=True)

        self._timer_thread = None
        self._timer_progress = None

    def _timer_update_loop(self) -> None:
        """Background thread that updates the thinking display"""
        if not self._timer_progress:
            return

        if self.console:
            # Use Rich's live update mechanism with proper cleanup
            from rich.live import Live
            from rich.text import Text

            try:
                self._live_context = Live(
                    refresh_per_second=10, console=self.console, transient=True
                )
                self._live_context.start()

                while not self._stop_timer.is_set():
                    elapsed = time.time() - self._timer_progress.start_time
                    spinner = self._spinner_chars[self._spinner_index % len(self._spinner_chars)]

                    # Create Rich text object for proper styling
                    thinking_text = Text(
                        f"⏱️  Waiting for response... [{elapsed:.1f}s] {spinner}", style="dim"
                    )
                    self._live_context.update(thinking_text)

                    self._spinner_index += 1

                    # Wait 0.1 seconds or until stop signal
                    if self._stop_timer.wait(timeout=0.1):
                        break

            except Exception:
                # Fall back to basic print if Rich fails
                while not self._stop_timer.is_set():
                    elapsed = time.time() - self._timer_progress.start_time
                    spinner = self._spinner_chars[self._spinner_index % len(self._spinner_chars)]
                    thinking_msg = f"⏱️  Waiting for response... [{elapsed:.1f}s] {spinner}"
                    print(f"\r{thinking_msg}", end="", flush=True)
                    self._spinner_index += 1
                    if self._stop_timer.wait(timeout=0.1):
                        break
            finally:
                # Clear the display and clean up the live context
                if self._live_context:
                    with contextlib.suppress(Exception):
                        self._live_context.stop()
                        self._live_context = None
        else:
            # Fallback for non-Rich terminals
            try:
                while not self._stop_timer.is_set():
                    elapsed = time.time() - self._timer_progress.start_time
                    spinner = self._spinner_chars[self._spinner_index % len(self._spinner_chars)]
                    thinking_msg = f"⏱️  Waiting for response... [{elapsed:.1f}s] {spinner}"

                    # Use carriage return to overwrite the line
                    print(f"\r{thinking_msg}", end="", flush=True)

                    self._spinner_index += 1

                    # Wait 0.1 seconds or until stop signal
                    if self._stop_timer.wait(timeout=0.1):
                        break
            finally:
                # Clear the line when done
                if not self.quiet_mode:
                    print("\r" + " " * 60 + "\r", end="", flush=True)

    def show_thinking(self, progress: TestProgress) -> None:
        """Legacy method - now redirects to start_thinking_timer"""
        self.start_thinking_timer(progress)

    def show_response(self, progress: TestProgress, response: ModelResponse) -> None:
        """Display the model response"""
        if self.quiet_mode:
            return

        progress.current_step = "Processing response..."
        progress.response_received = True

        if response.error:
            error_msg = f"❌ Error: {response.error}"
            if self.console:
                self.console.print(Panel(error_msg, style="red", title="ERROR"))
            else:
                print(f"\n{error_msg}")
            return

        # Show response
        response_content = response.content
        if len(response_content) > 500 and not self.verbose:
            response_content = response_content[:500] + "..."

        if self.console:
            # Build title with timing and token info
            title = "🤖 RESPONSE"
            timing_parts = [f"took: {response.response_time:.2f}s"]
            if response.total_tokens > 0:
                timing_parts.append(f"tokens: {response.total_tokens}")

            if timing_parts:
                title += f" ({' | '.join(timing_parts)})"

            response_panel = Panel(
                Text(response_content, style="white"),
                title=title,
                title_align="left",
                style="blue",
                padding=(1, 2),
            )
            self.console.print(response_panel)

        else:
            # Build title with timing info for fallback
            title = "🤖 RESPONSE"
            timing_parts = [f"took: {response.response_time:.2f}s"]
            if response.total_tokens > 0:
                timing_parts.append(f"tokens: {response.total_tokens}")

            if timing_parts:
                title += f" ({' | '.join(timing_parts)})"

            print(f"\n{title}:")
            print(f"   {response_content}")

    def show_evaluation(self, progress: TestProgress, evaluation: EvaluationResult) -> None:
        """Display evaluation results"""
        if self.quiet_mode:
            return

        progress.current_step = "Evaluation complete"
        progress.evaluation_done = True

        # Build dynamic title with result and confidence
        if evaluation.is_vulnerable:
            title = f"🔴 Evaluated as VULNERABLE (confidence: {evaluation.confidence:.2f})"
            panel_style = "red"
        else:
            title = f"✅ Evaluated as NOT vulnerable (confidence: {evaluation.confidence:.2f})"
            panel_style = "green"

        if self.console:
            # Create simplified content - only evidence and reasoning
            content_parts = []

            if evaluation.evidence:
                evidence_text = "\n".join(f"• {e}" for e in evaluation.evidence)
                content_parts.append(f"Evidence:\n{evidence_text}")

            if evaluation.reasoning:
                content_parts.append(f"Reasoning: {evaluation.reasoning}")

            # If no evidence or reasoning, show a simple message
            if not content_parts:
                content_parts.append("No additional details available")

            content = "\n\n".join(content_parts)

            eval_panel = Panel(
                Text(content, style="white"),
                title=title,
                title_align="left",
                style=panel_style,
                padding=(0, 1),
            )
            self.console.print(eval_panel)

        else:
            # Fallback for non-Rich terminals
            print(f"\n{title}:")

            if evaluation.evidence:
                print("   Evidence:")
                for evidence in evaluation.evidence:
                    print(f"     • {evidence}")

            if evaluation.reasoning:
                print(f"   Reasoning: {evaluation.reasoning}")

            if not evaluation.evidence and not evaluation.reasoning:
                print("   No additional details available")

    def complete_test(self, progress: TestProgress, evaluation: EvaluationResult) -> None:
        """Mark test as complete"""
        total_time = time.time() - progress.start_time
        status = "vulnerable" if evaluation.is_vulnerable else "safe"

        if self.quiet_mode:
            # Update the progress line
            print(f"✓ {progress.test_name} ({total_time:.1f}s, {status})", end=" ", flush=True)
            if (
                progress.current_test_num % 5 == 0
                or progress.current_test_num == progress.total_tests
            ):
                print()  # New line every 5 tests or at the end
            return

        completion_msg = f"✅ Test completed in {total_time:.1f}s"
        if evaluation.is_vulnerable:
            completion_msg += (
                f" | 🔴 VULNERABILITY DETECTED (confidence: {evaluation.confidence:.2f})"
            )
        else:
            completion_msg += " | 🟢 No vulnerability detected"

        if self.console:
            self.console.print(completion_msg, style="bold green")
        else:
            print(f"\n{completion_msg}")

    def complete_category(self, category: str, summary: dict[str, Any]) -> None:
        """Display category completion summary"""
        if self.quiet_mode:
            total_tests = summary.get("total_tests", 0)
            excluded_tests = summary.get("excluded_tests", 0)
            vulnerable_tests = summary.get("vulnerable_tests", 0)

            result_text = (
                f"\n✅ {category} category complete: {vulnerable_tests}/{total_tests} vulnerable"
            )
            if excluded_tests > 0:
                result_text += f" ({excluded_tests} excluded due to errors/empty responses)"
            print(result_text)
            return

        if self.console:
            # Create summary table
            summary_table = Table(title=f"📊 {category.upper()} CATEGORY RESULTS", show_header=True)
            summary_table.add_column("Metric", style="cyan")
            summary_table.add_column("Value", style="white")

            total_tests = summary.get("total_tests", 0)
            total_attempted = summary.get(
                "total_attempted", total_tests
            )  # Fallback for compatibility
            excluded_tests = summary.get("excluded_tests", 0)

            summary_table.add_row("Total Tests", str(total_tests))
            if excluded_tests > 0:
                summary_table.add_row("Attempted Tests", str(total_attempted))
                summary_table.add_row("Excluded (errors/empty)", str(excluded_tests))
            summary_table.add_row("Vulnerabilities Found", str(summary.get("vulnerable_tests", 0)))
            summary_table.add_row(
                "High Confidence", str(summary.get("high_confidence_vulnerabilities", 0))
            )
            summary_table.add_row(
                "Average Confidence", f"{summary.get('average_confidence', 0):.2f}"
            )

            self.console.print()
            self.console.print(summary_table)

            # Show category breakdown if available
            if "category_breakdown" in summary:
                breakdown_text = []
                for cat, stats in summary["category_breakdown"].items():
                    breakdown_text.append(f"{cat}: {stats['vulnerable']}/{stats['total']}")

                if breakdown_text:
                    self.console.print(f"\n📋 Breakdown: {' | '.join(breakdown_text)}", style="dim")
        else:
            print(f"\n📊 {category.upper()} CATEGORY RESULTS:")
            print(f"   Total tests: {summary.get('total_tests', 0)}")
            print(f"   Vulnerabilities: {summary.get('vulnerable_tests', 0)}")
            print(f"   High confidence: {summary.get('high_confidence_vulnerabilities', 0)}")
            print(f"   Average confidence: {summary.get('average_confidence', 0):.2f}")

    def error(self, message: str) -> None:
        """Display error message"""
        if self.console:
            self.console.print(f"❌ {message}", style="red bold")
        else:
            print(f"❌ {message}")

    def info(self, message: str) -> None:
        """Display info message"""
        if not self.quiet_mode:
            if self.console:
                self.console.print(message, style="cyan")
            else:
                print(message)

    def show_repetition_header(self, current_rep: int, total_reps: int) -> None:
        """Display repetition progress header"""
        if self.quiet_mode or total_reps <= 1:
            return

        rep_msg = f"➡️  Repetition {current_rep}/{total_reps}:"

        if self.console:
            self.console.print(f"\n{rep_msg}", style="bold magenta")
        else:
            print(f"\n{rep_msg}")

    def show_multi_turn_prompts(self, prompts: list[str], system_prompt: str = "") -> None:
        """Display all prompts for a multi-turn conversation at once"""
        if self.quiet_mode:
            return

        if self.console:
            # System prompt if present
            if system_prompt:
                system_panel = Panel(
                    Text(system_prompt, style="italic cyan"),
                    title="⚙️  SYSTEM PROMPT",
                    title_align="left",
                    style="cyan",
                    padding=(0, 2),
                )
                self.console.print(system_panel)

            # Show all conversation turns
            for i, prompt in enumerate(prompts, 1):
                prompt_panel = Panel(
                    Text(prompt, style="white"),
                    title=f"📝 Turn {i} PROMPT",
                    title_align="left",
                    style="yellow",
                    padding=(1, 2),
                )
                self.console.print(prompt_panel)
        else:
            if system_prompt:
                print("\n⚙️  SYSTEM PROMPT:")
                print(f"   {system_prompt}")

            for i, prompt in enumerate(prompts, 1):
                print(f"\n📝 Turn {i} PROMPT:")
                print(f"   {prompt}")

    def show_vulnerability_summary(self, test_id: str, repetitions: list[dict[str, Any]]) -> None:
        """Display vulnerability summary after all repetitions of a test"""
        if self.quiet_mode or len(repetitions) <= 1:
            return

        total_runs = len(repetitions)
        vulnerable_runs = sum(1 for r in repetitions if r.get("is_vulnerable", False))
        avg_confidence = (
            sum(r.get("confidence", 0) for r in repetitions) / total_runs if repetitions else 0
        )
        avg_response_time = (
            sum(r.get("response_time", 0) for r in repetitions) / total_runs if repetitions else 0
        )

        vulnerability_rate = (vulnerable_runs / total_runs) * 100

        # Dynamic color based on vulnerability results
        summary_style = "red" if vulnerable_runs > 0 else "green"

        if self.console:
            summary_table = Table(show_header=False, box=None, padding=(0, 1))
            summary_table.add_column("Field", style="cyan bold")
            summary_table.add_column("Value")

            summary_table.add_row("Total runs:", str(total_runs))
            summary_table.add_row(
                "Vulnerable:", f"{vulnerable_runs}/{total_runs} ({vulnerability_rate:.0f}%)"
            )
            summary_table.add_row("Average confidence:", f"{avg_confidence:.2f}")
            summary_table.add_row("Response time avg:", f"{avg_response_time:.2f}s")

            summary_panel = Panel(
                summary_table,
                title=f"📊 Vulnerability Summary for {test_id}",
                title_align="left",
                style=summary_style,
                padding=(1, 2),
            )
            self.console.print(summary_panel)
            self.console.print("─" * 60)
        else:
            print(f"\n📊 Vulnerability Summary for {test_id}:")
            print(f"   Total runs: {total_runs}")
            print(f"   Vulnerable: {vulnerable_runs}/{total_runs} ({vulnerability_rate:.0f}%)")
            print(f"   Average confidence: {avg_confidence:.2f}")
            print(f"   Response time avg: {avg_response_time:.2f}s")
            print("─" * 60)

    def show_parallel_summary(self, summary_data: dict[str, Any]) -> None:
        """Display comprehensive parallel execution summary"""
        if self.quiet_mode:
            return

        if self.console:
            # Build the complete summary content
            from rich.console import Group
            from rich.table import Table

            content_parts = []

            # Test results by category
            category_stats = summary_data.get("category_stats", {})
            if category_stats:
                content_parts.append(Text("Test Results by Category:", style="bold cyan"))
                for cat_name, stats in category_stats.items():
                    total = stats["total"]
                    vulnerable = stats["vulnerable"]
                    errors = stats["errors"]
                    rate = (vulnerable / total * 100) if total > 0 else 0

                    status_icon = "├─" if cat_name != list(category_stats.keys())[-1] else "└─"
                    color = "red" if rate > 50 else "yellow" if rate > 20 else "green"

                    category_line = (
                        f"{status_icon} {cat_name}: {vulnerable}/{total} vulnerable ({rate:.0f}%)"
                    )
                    if errors > 0:
                        category_line += f" [{errors} errors]"

                    content_parts.append(Text(f"  {category_line}", style=color))

                content_parts.append(Text(""))  # Empty line

            # Overall statistics
            content_parts.append(Text("Overall Statistics:", style="bold cyan"))
            content_parts.append(
                Text(
                    "(Note: Evaluations are heuristic-based and may undercount vulnerabilities)",
                    style="dim italic",
                )
            )
            stats_table = Table(show_header=False, box=None, padding=(0, 1))
            stats_table.add_column("Field", style="cyan")
            stats_table.add_column("Value")

            stats_table.add_row("• Total Tests Run:", str(summary_data.get("total_tests", 0)))

            vuln_count = summary_data.get("vulnerable_tests", 0)
            total_count = summary_data.get("total_tests", 1)
            vuln_rate = summary_data.get("vulnerability_rate", 0) * 100
            stats_table.add_row(
                "• Vulnerabilities Found:", f"{vuln_count}/{total_count} ({vuln_rate:.1f}%)"
            )

            stats_table.add_row(
                "• Average Confidence:", f"{summary_data.get('avg_confidence', 0):.2f}"
            )
            stats_table.add_row(
                "• High Confidence (>0.8):", f"{summary_data.get('high_confidence', 0)} tests"
            )

            total_time = summary_data.get("total_time", 0)
            num_threads = summary_data.get("num_threads", 1)
            speedup = (
                summary_data.get("avg_execution_time", 0) * total_count / total_time
                if total_time > 0
                else 1
            )
            stats_table.add_row("• Execution Time:", f"{total_time:.1f}s ({speedup:.1f}x speedup)")

            error_count = summary_data.get("error_tests", 0)
            if error_count > 0:
                stats_table.add_row("• Errors:", f"{error_count} tests failed", style="red")

            content_parts.append(stats_table)

            # Most vulnerable tests
            most_vulnerable = summary_data.get("most_vulnerable", [])
            if most_vulnerable:
                content_parts.append(Text(""))  # Empty line
                content_parts.append(Text("Top Vulnerable Tests:", style="bold red"))
                for i, (test_id, rate, vuln_runs, total_runs) in enumerate(most_vulnerable[:3], 1):
                    if rate > 0:
                        content_parts.append(
                            Text(
                                f"  {i}. 🔴 {test_id} - {vuln_runs}/{total_runs} runs vulnerable ({rate * 100:.0f}%)"
                            )
                        )

            # Most resilient tests
            most_resilient = summary_data.get("most_resilient", [])
            if most_resilient:
                content_parts.append(Text(""))  # Empty line
                content_parts.append(Text("Most Resilient Tests:", style="bold green"))
                for i, (test_id, rate, vuln_runs, total_runs) in enumerate(most_resilient[:2], 1):
                    content_parts.append(
                        Text(
                            f"  {i}. ✅ {test_id} - {vuln_runs}/{total_runs} runs vulnerable ({rate * 100:.0f}%)"
                        )
                    )

            # Create the main panel with all content
            summary_panel = Panel(
                Group(*content_parts),
                title="📊 PARALLEL EXECUTION SUMMARY",
                title_align="left",
                style="blue",
                padding=(1, 2),
            )

            self.console.print()
            self.console.print(summary_panel)
        else:
            # Text mode fallback
            print()
            print("=" * 80)
            print("📊 PARALLEL EXECUTION SUMMARY")
            print("=" * 80)

            # Category stats
            category_stats = summary_data.get("category_stats", {})
            if category_stats:
                print("\nTest Results by Category:")
                for cat_name, stats in category_stats.items():
                    total = stats["total"]
                    vulnerable = stats["vulnerable"]
                    rate = (vulnerable / total * 100) if total > 0 else 0
                    print(f"  - {cat_name}: {vulnerable}/{total} vulnerable ({rate:.0f}%)")

            # Overall stats
            print("\nOverall Statistics:")
            print(f"  • Total Tests: {summary_data.get('total_tests', 0)}")
            vuln_count = summary_data.get("vulnerable_tests", 0)
            total_count = summary_data.get("total_tests", 1)
            vuln_rate = summary_data.get("vulnerability_rate", 0) * 100
            print(f"  • Vulnerabilities: {vuln_count}/{total_count} ({vuln_rate:.1f}%)")
            print(f"  • Average Confidence: {summary_data.get('avg_confidence', 0):.2f}")

            total_time = summary_data.get("total_time", 0)
            num_threads = summary_data.get("num_threads", 1)
            print(f"  • Execution Time: {total_time:.1f}s with {num_threads} threads")

            print("=" * 80)


# Global instance that can be imported
_display_instance = None


def get_display() -> LiveDisplay:
    """Get the global display instance"""
    global _display_instance
    if _display_instance is None:
        _display_instance = LiveDisplay()
    return _display_instance


def set_display_options(
    enable_live: bool = True, quiet_mode: bool = False, verbose: bool = False
) -> None:
    """Configure the global display instance"""
    global _display_instance
    _display_instance = LiveDisplay(enable_live=enable_live, quiet_mode=quiet_mode, verbose=verbose)

#!/usr/bin/env python3
"""
CLI interface for findings management and browsing
Separated from cli_ui.py for better organization
"""

import contextlib
import json
import sys
from datetime import datetime
from pathlib import Path

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt
    from rich.table import Table

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class FindingsBrowser:
    """Browser for findings files and export functionality"""

    def __init__(self) -> None:
        if RICH_AVAILABLE:
            self.console = Console()
        else:
            self.console = None

    def _get_single_char(self, prompt_text: str = "Command: ") -> str:
        """Get a single character input without pressing Enter"""
        try:
            if self.console:
                self.console.print(f"[dim]{prompt_text}[/dim]", end="")
            else:
                print(f"{prompt_text}", end="", flush=True)

            # Save terminal settings
            import termios
            import tty

            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)

            try:
                # Set terminal to raw mode
                tty.setraw(sys.stdin.fileno())
                char = sys.stdin.read(1)

                # Handle special keys
                if ord(char) == 27:  # ESC sequence
                    char += sys.stdin.read(2)
                    if char == "\x1b[C":  # Right arrow
                        char = "→"
                    elif char == "\x1b[D":  # Left arrow
                        char = "←"
                    elif char == "\x1b[A":  # Up arrow
                        char = "↑"
                    elif char == "\x1b[B":  # Down arrow
                        char = "↓"

                # Show the pressed key
                if self.console:
                    if char in ["→", "←", "↑", "↓"]:
                        self.console.print(f"{char}", end="")
                    else:
                        self.console.print(f"[bold]{char}[/bold]", end="")
                    self.console.print()
                else:
                    print(f"{char}")

                return char.lower()

            finally:
                # Restore terminal settings
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

        except (termios.error, OSError, KeyboardInterrupt):
            # Fallback to regular input if terminal manipulation fails
            if self.console:
                return Prompt.ask(f"\n{prompt_text}").lower()
            else:
                return input(f"\n{prompt_text}").lower()

    def _display_conversation_rich(self, finding_data: dict) -> None:
        """Display conversation using Rich formatting - handles both single-turn and multi-turn"""
        conversation_turns = finding_data.get("conversation_turns")
        all_responses = finding_data.get("all_responses")
        
        if conversation_turns and all_responses and len(conversation_turns) > 0:
            # Multi-turn conversation: show each turn with response
            for i, turn_prompt in enumerate(conversation_turns):
                turn_num = i + 1
                
                # Show user prompt for this turn
                self.console.print(Panel(
                    turn_prompt, 
                    title=f"Turn {turn_num} - User Prompt", 
                    style="cyan"
                ))
                
                # Show assistant response for this turn (if available)
                if i < len(all_responses):
                    response_content = all_responses[i]
                    self.console.print(Panel(
                        response_content, 
                        title=f"Turn {turn_num} - Model Response", 
                        style="green"
                    ))
                else:
                    self.console.print(Panel(
                        "[dim]No response recorded for this turn[/dim]", 
                        title=f"Turn {turn_num} - Model Response", 
                        style="red"
                    ))
        else:
            # Single-turn conversation: use original display logic
            if finding_data.get("prompt"):
                prompt_text = finding_data["prompt"]
                self.console.print(Panel(prompt_text, title="Prompt", style="yellow"))

            if finding_data.get("response"):
                response_text = finding_data["response"]
                self.console.print(Panel(response_text, title="Response", style="blue"))

    def _display_conversation_text(self, finding_data: dict) -> None:
        """Display conversation using plain text formatting - handles both single-turn and multi-turn"""
        conversation_turns = finding_data.get("conversation_turns")
        all_responses = finding_data.get("all_responses")
        
        if conversation_turns and all_responses and len(conversation_turns) > 0:
            # Multi-turn conversation: show each turn with response
            print("\nMulti-Turn Conversation:")
            print("=" * 60)
            
            for i, turn_prompt in enumerate(conversation_turns):
                turn_num = i + 1
                
                # Show user prompt for this turn
                print(f"\n--- Turn {turn_num} - User Prompt ---")
                print(turn_prompt)
                
                # Show assistant response for this turn (if available)
                if i < len(all_responses):
                    response_content = all_responses[i]
                    print(f"\n--- Turn {turn_num} - Model Response ---")
                    print(response_content)
                else:
                    print(f"\n--- Turn {turn_num} - Model Response ---")
                    print("(No response recorded for this turn)")
        else:
            # Single-turn conversation: use original display logic
            if finding_data.get("prompt"):
                prompt_text = finding_data["prompt"]
                print(f"\nPrompt:\n{prompt_text}")

            if finding_data.get("response"):
                response_text = finding_data["response"]
                print(f"\nResponse:\n{response_text}")

    def view_findings(self) -> None:
        """Browse and view findings folder"""
        findings_dir = Path("findings")
        if not findings_dir.exists():
            if self.console:
                self.console.print(
                    "[yellow]📁 No findings folder found. Export some findings first.[/yellow]"
                )
            else:
                print("📁 No findings folder found. Export some findings first.")
            return

        # Get only grouped export files (export_*.json and flagged_*.json)
        all_files = list(findings_dir.glob("*.json"))
        grouped_files = [f for f in all_files if f.name.startswith(("export_", "flagged_"))]

        if not grouped_files:
            if self.console:
                self.console.print(
                    "[yellow]📁 No grouped findings found. Export some findings first.[/yellow]"
                )
                self.console.print(
                    "[dim]Note: Only showing grouped export files (export_*.json, flagged_*.json)[/dim]"
                )
            else:
                print("📁 No grouped findings found. Export some findings first.")
                print("Note: Only showing grouped export files (export_*.json, flagged_*.json)")
            return

        # Sort by modification time (most recent first)
        grouped_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        if self.console:
            self.console.clear()
            self.console.print(
                Panel(f"📁 Grouped Findings ({len(grouped_files)} files)", style="bold blue")
            )

            # Display files with details
            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("#", style="yellow", width=3)
            table.add_column("Filename", width=45)  # Made 10 characters wider
            table.add_column("Type", width=12)
            table.add_column("Size", width=8)
            table.add_column("Modified", width=20)

            now = datetime.now()
            for i, filepath in enumerate(grouped_files[:20], 1):  # Show max 20 files
                stat = filepath.stat()
                size = f"{stat.st_size // 1024}KB" if stat.st_size >= 1024 else f"{stat.st_size}B"
                modified = datetime.fromtimestamp(stat.st_mtime)
                age_diff = now - modified

                if age_diff.days > 0:
                    age = f"{age_diff.days}d ago"
                elif age_diff.seconds > 3600:
                    age = f"{age_diff.seconds // 3600}h ago"
                elif age_diff.seconds > 60:
                    age = f"{age_diff.seconds // 60}m ago"
                else:
                    age = "just now"

                # Determine file type for grouped files
                if filepath.name.startswith("export_"):
                    file_type = "[green]Bulk Export[/green]"
                elif filepath.name.startswith("flagged_"):
                    file_type = "[yellow]Flagged Item[/yellow]"
                else:
                    file_type = "[blue]Grouped[/blue]"

                table.add_row(
                    str(i),
                    filepath.name,
                    file_type,
                    size,
                    f"{modified.strftime('%m-%d %H:%M')} ({age})",
                )

            self.console.print(table)

            if len(grouped_files) > 20:
                self.console.print(f"[dim]... and {len(grouped_files) - 20} more files[/dim]")

            self.console.print()
            self.console.print("[yellow]Commands:[/yellow]")
            self.console.print(
                f"  [cyan]1-{min(20, len(grouped_files))}[/cyan]   - Navigate grouped findings"
            )
            self.console.print("  [cyan]o[/cyan]     - Open findings folder in file manager")
            self.console.print("  [cyan]Enter[/cyan] - Return to main view")
        else:
            # Text mode display
            print("=" * 80)
            print(f"📁 GROUPED FINDINGS ({len(grouped_files)} files)")
            print("=" * 80)

            for i, filepath in enumerate(grouped_files[:20], 1):
                stat = filepath.stat()
                size = f"{stat.st_size // 1024}KB" if stat.st_size >= 1024 else f"{stat.st_size}B"
                modified = datetime.fromtimestamp(stat.st_mtime)

                if filepath.name.startswith("export_"):
                    file_type = "Bulk Export"
                elif filepath.name.startswith("flagged_"):
                    file_type = "Flagged Item"
                else:
                    file_type = "Grouped"

                print(
                    f"{i:2d}. {filepath.name:<45} [{file_type:<12}] {size:>8} {modified.strftime('%m-%d %H:%M')}"
                )

            if len(grouped_files) > 20:
                print(f"... and {len(grouped_files) - 20} more files")

            print("-" * 80)
            print(
                f"Commands: 1-{min(20, len(grouped_files))} (navigate findings), o (open folder), Enter (return)"
            )
            print("Note: Only showing grouped export files (export_*.json, flagged_*.json)")

        # Handle user input
        while True:
            try:
                # Use single character input like main UI
                user_input = input("Choose action: ")
                if self.console:
                    self.console.print()  # Add newline after single char input
                else:
                    print()

                if user_input in ["\r", "\n", "", "q"]:  # Enter or q to quit
                    break
                elif user_input.lower() == "o":
                    self._open_findings_folder()
                    break
                else:
                    # Try to parse as number
                    try:
                        file_num = int(user_input)
                        if 1 <= file_num <= min(20, len(grouped_files)):
                            self._navigate_grouped_finding(grouped_files[file_num - 1])
                            break
                        else:
                            if self.console:
                                self.console.print(
                                    f"[red]Invalid number. Choose 1-{min(20, len(grouped_files))}[/red]"
                                )
                            else:
                                print(f"Invalid number. Choose 1-{min(20, len(grouped_files))}")
                            input("Press Enter to continue...")
                    except ValueError:
                        if self.console:
                            self.console.print(
                                "[red]Invalid input. Try a number, 'o', or Enter[/red]"
                            )
                        else:
                            print("Invalid input. Try a number, 'o', or Enter")
                        input("Press Enter to continue...")

            except (EOFError, KeyboardInterrupt):
                break

    def _navigate_grouped_finding(self, filepath: Path) -> None:
        """Level 2: Navigate within a grouped finding file"""
        try:
            with open(filepath) as f:
                data = json.load(f)

            # Handle both grouped format and single finding format
            if "findings" in data and isinstance(data["findings"], list):
                # Grouped format
                findings = data["findings"]
                export_info = {
                    "export_id": data.get("export_id", "Unknown"),
                    "export_timestamp": data.get("export_timestamp", "Unknown"),
                    "total_findings": data.get("total_findings", len(findings)),
                    "session_summary": data.get("session_summary", {}),
                }
            else:
                # Single finding format - treat as single item
                findings = [data]
                export_info = {
                    "export_id": data.get("finding_id", filepath.stem),
                    "export_timestamp": data.get("export_timestamp", "Unknown"),
                    "total_findings": 1,
                    "session_summary": {},
                }

            if not findings:
                if self.console:
                    self.console.print("[red]No findings in this file[/red]")
                else:
                    print("No findings in this file")
                input("Press Enter to continue...")
                return

            # Start navigation at first finding
            current_index = 0

            while True:
                current_finding = findings[current_index]

                if self.console:
                    self.console.clear()

                    # Show breadcrumb and navigation info
                    breadcrumb = f"📁 Level 1 → 📄 {filepath.name} → Finding {current_index + 1}/{len(findings)}"
                    self.console.print(Panel(breadcrumb, style="bold blue"))

                    # Show export summary
                    if export_info.get("session_summary"):
                        summary = export_info["session_summary"]
                        summary_text = f"Export: {export_info['export_id']} | "
                        summary_text += f"Total: {export_info['total_findings']} findings"
                        if summary.get("category_counts"):
                            top_categories = list(summary.get("category_counts", {}).keys())[:3]
                            summary_text += f" | Categories: {', '.join(top_categories)}"
                        self.console.print(f"[dim]{summary_text}[/dim]\n")

                    # Display current finding
                    info_table = Table(show_header=False, header_style="bold magenta")
                    info_table.add_column("Field", style="cyan", width=15)
                    info_table.add_column("Value")

                    info_table.add_row("Finding ID", current_finding.get("finding_id", "Unknown"))
                    info_table.add_row("Test ID", current_finding.get("test_id", "Unknown"))
                    info_table.add_row("Test Name", current_finding.get("test_name", "Unknown"))
                    info_table.add_row("Category", current_finding.get("category", "Unknown"))

                    vuln_status = (
                        "✓ Detected"
                        if current_finding.get("vulnerability_detected")
                        else "✗ Not detected"
                    )
                    info_table.add_row("Vulnerability", vuln_status)
                    info_table.add_row("Confidence", f"{current_finding.get('confidence', 0):.2f}")

                    if current_finding.get("flagged"):
                        info_table.add_row("Status", "[red]🚩 FLAGGED[/red]")

                    if current_finding.get("notes"):
                        info_table.add_row("Notes", current_finding["notes"])

                    self.console.print(info_table)

                    # Show conversation (either multi-turn or single-turn)
                    self._display_conversation_rich(current_finding)

                    # Show commands
                    self.console.print("\n[yellow]Commands:[/yellow]")
                    commands = []
                    if current_index > 0:
                        commands.append("[cyan]p[/cyan] - Previous finding")
                    if current_index < len(findings) - 1:
                        commands.append("[cyan]n[/cyan] - Next finding")
                    commands.append("[cyan]t[/cyan] - View thinking")
                    commands.append("[cyan]c[/cyan] - Copy prompt")
                    commands.append("[cyan]r[/cyan] - Copy response")
                    commands.append("[cyan]e[/cyan] - Export as competition finding")
                    commands.extend(["[cyan]Enter/q[/cyan] - Return to findings list"])

                    for cmd in commands:
                        self.console.print(f"  {cmd}")

                else:
                    # Text mode
                    print("=" * 80)
                    print(f"📄 {filepath.name} - Finding {current_index + 1}/{len(findings)}")
                    print("=" * 80)

                    print(f"Finding ID: {current_finding.get('finding_id', 'Unknown')}")
                    print(f"Test ID: {current_finding.get('test_id', 'Unknown')}")
                    print(f"Test Name: {current_finding.get('test_name', 'Unknown')}")
                    print(f"Category: {current_finding.get('category', 'Unknown')}")

                    vuln_status = (
                        "✓ Detected"
                        if current_finding.get("vulnerability_detected")
                        else "✗ Not detected"
                    )
                    print(f"Vulnerability: {vuln_status}")
                    print(f"Confidence: {current_finding.get('confidence', 0):.2f}")

                    if current_finding.get("flagged"):
                        print("Status: 🚩 FLAGGED")

                    if current_finding.get("notes"):
                        print(f"Notes: {current_finding['notes']}")

                    # Show conversation (either multi-turn or single-turn)
                    self._display_conversation_text(current_finding)

                    print("-" * 80)
                    print("Commands: ", end="")
                    commands = []
                    if current_index > 0:
                        commands.append("p (previous)")
                    if current_index < len(findings) - 1:
                        commands.append("n (next)")
                    commands.append("t (thinking)")
                    commands.append("c (copy prompt)")
                    commands.append("r (copy response)")
                    commands.append("e (export competition)")
                    commands.append("Enter/q (return)")
                    print(", ".join(commands))

                # Get user input
                try:
                    user_input = self._get_single_char("Navigate: ")
                    if self.console:
                        self.console.print()  # Add newline after single char input
                    else:
                        print()

                    if user_input in ["\r", "\n", "", "q", "\x04"]:  # Added ctrl+d (0x04)
                        break
                    elif user_input.lower() == "n" and current_index < len(findings) - 1:
                        current_index += 1
                    elif user_input.lower() == "p" and current_index > 0:
                        current_index -= 1
                    elif user_input.lower() == "t":
                        self._view_thinking(current_finding)
                    elif user_input.lower() == "c":
                        self._copy_prompt_to_clipboard(current_finding)
                    elif user_input.lower() == "r":
                        self._copy_response_to_clipboard(current_finding)
                    elif user_input.lower() == "e":
                        self._export_single_competition_finding(current_finding)
                    else:
                        if self.console:
                            self.console.print("[red]Invalid command[/red]")
                        else:
                            print("Invalid command")
                        input("Press Enter to continue...")

                except (EOFError, KeyboardInterrupt):
                    break

        except Exception as e:
            if self.console:
                self.console.print(f"[red]Error reading grouped file: {e}[/red]")
            else:
                print(f"Error reading grouped file: {e}")
            input("Press Enter to continue...")

    def _view_thinking(self, finding_data: dict) -> None:
        """Level 3: View thinking content for a specific finding"""
        thinking_content = finding_data.get("thinking", "")

        if not thinking_content:
            if self.console:
                self.console.print("[yellow]Not available due to legacy format[/yellow]")
            else:
                print("Not available due to legacy format")
            input("Press Enter to continue...")
            return

        if self.console:
            self.console.clear()

            # Show breadcrumb
            finding_id = finding_data.get("finding_id", "Unknown")
            breadcrumb = f"📁 Level 1 → 📄 Level 2 → 🧠 Thinking: {finding_id}"
            self.console.print(Panel(breadcrumb, style="bold blue"))

            # Show thinking content
            thinking_panel = Panel(
                thinking_content,
                title=f"🧠 Thinking Content - {finding_data.get('test_id', 'Unknown')}",
                style="magenta",
                expand=False,
            )
            self.console.print(thinking_panel)

            self.console.print("\n[yellow]Commands:[/yellow]")
            self.console.print("  [cyan]Enter/q[/cyan] - Return to finding navigation")

        else:
            # Text mode
            print("=" * 80)
            print(f"🧠 THINKING CONTENT - {finding_data.get('test_id', 'Unknown')}")
            print("=" * 80)
            print(thinking_content)
            print("=" * 80)
            print("Commands: Enter/q (return to finding)")

        # Wait for user input
        try:
            self._get_single_char("View thinking: ")
            if self.console:
                self.console.print()
            else:
                print()
        except (EOFError, KeyboardInterrupt):
            pass

    def _export_single_competition_finding(self, finding_data: dict) -> None:
        """Export a single finding in competition format using CompetitionConverter"""
        try:
            # Import the competition converter
            from datetime import datetime

            from src.utils.competition_converter import CompetitionConverter

            # Prompt user for custom metadata
            if self.console:
                self.console.print("\n[yellow]📋 Competition Submission Details[/yellow]")
                self.console.print("[dim]Press Enter to use defaults for any field[/dim]\n")

                issue_title = input("Issue title: ").strip() or finding_data.get(
                    "test_name", "Security vulnerability detected"
                )
                overview = input("Overview: ").strip() or finding_data.get(
                    "reasoning", "Model exhibited potentially problematic behavior"
                )
                severity = input("Self-assessed severity (1-10) [default: 3]: ").strip() or "3"
                breadth = input("Self-assessed breadth (1-10) [default: 2]: ").strip() or "2"
                severity_justification = (
                    input("Severity justification: ").strip()
                    or "Moderate severity based on test results"
                )
                breadth_justification = (
                    input("Breadth justification: ").strip()
                    or "Limited to specific scenario tested"
                )
                notes = input("Additional notes: ").strip() or ""
            else:
                print("\n📋 Competition Submission Details")
                print("Press Enter to use defaults for any field\n")

                issue_title = input("Issue title: ").strip() or finding_data.get(
                    "test_name", "Security vulnerability detected"
                )
                overview = input("Overview: ").strip() or finding_data.get(
                    "reasoning", "Model exhibited potentially problematic behavior"
                )
                severity = input("Self-assessed severity (1-10) [default: 3]: ").strip() or "3"
                breadth = input("Self-assessed breadth (1-10) [default: 2]: ").strip() or "2"
                severity_justification = (
                    input("Severity justification: ").strip()
                    or "Moderate severity based on test results"
                )
                breadth_justification = (
                    input("Breadth justification: ").strip()
                    or "Limited to specific scenario tested"
                )
                notes = input("Additional notes: ").strip() or ""

            # Build metadata for competition format
            metadata = {
                "issue_title": issue_title,
                "overview": overview,
                "severity": int(severity),
                "breadth": int(breadth),
                "severity_justification": severity_justification,
                "breadth_justification": breadth_justification,
                "notes": notes or f"Generated from test: {finding_data.get('test_id', 'unknown')}",
            }

            # Convert to competition format
            converter = CompetitionConverter()
            competition_data = converter.convert_finding_to_competition(finding_data, metadata)

            # Save with timestamped filename
            findings_dir = Path("findings")
            findings_dir.mkdir(exist_ok=True)

            test_id = finding_data.get("test_id", "unknown")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"competition_{test_id}_{timestamp}.json"
            filepath = findings_dir / filename

            # Save competition format JSON
            import json

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(competition_data, f, indent=2, ensure_ascii=False)

            # Validate the output
            is_valid, errors = converter.validate_competition_format(competition_data)

            # Success message
            if self.console:
                self.console.print(f"[green]✅ Exported competition finding: {filename}[/green]")
                self.console.print(f"[dim]Saved to: {filepath}[/dim]")
                if is_valid:
                    self.console.print("[green]✓ Format validation passed[/green]")
                else:
                    self.console.print("[yellow]⚠️ Format validation warnings:[/yellow]")
                    for error in errors:
                        self.console.print(f"[yellow]  • {error}[/yellow]")
            else:
                print(f"✅ Exported competition finding: {filename}")
                print(f"Saved to: {filepath}")
                if is_valid:
                    print("✓ Format validation passed")
                else:
                    print("⚠️ Format validation warnings:")
                    for error in errors:
                        print(f"  • {error}")

        except ImportError as e:
            if self.console:
                self.console.print(f"[red]Import error: {e}[/red]")
                self.console.print("[red]CompetitionConverter not available[/red]")
            else:
                print(f"Import error: {e}")
                print("CompetitionConverter not available")
        except Exception as e:
            if self.console:
                self.console.print(f"[red]Error exporting finding: {e}[/red]")
                import traceback

                self.console.print(f"[red]{traceback.format_exc()}[/red]")
            else:
                print(f"Error exporting finding: {e}")
                import traceback

                print(traceback.format_exc())

        # Wait for user input to return
        input("Press Enter to continue...")

    def _copy_prompt_to_clipboard(self, finding_data: dict) -> None:
        """Copy current finding's prompt to clipboard"""
        import platform
        import subprocess

        # Extract prompt from finding data
        prompt_text = ""
        if finding_data.get("prompt"):
            prompt_text = finding_data["prompt"]
        elif finding_data.get("conversation_turns") and isinstance(
            finding_data["conversation_turns"], list
        ):
            prompt_text = "\n".join(
                [
                    turn.strip()
                    for turn in finding_data["conversation_turns"]
                    if turn and turn.strip()
                ]
            )
        else:
            if self.console:
                self.console.print("[yellow]No prompt content available to copy[/yellow]")
            else:
                print("No prompt content available to copy")
            input("Press Enter to continue...")
            return

        try:
            # Detect platform and use appropriate clipboard command
            system = platform.system()

            if system == "Darwin":  # macOS
                process = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE, text=True)
                process.communicate(input=prompt_text)
                clipboard_cmd = "pbcopy"
            elif system == "Linux":
                # Try xclip first, then xsel
                try:
                    process = subprocess.Popen(
                        ["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE, text=True
                    )
                    process.communicate(input=prompt_text)
                    clipboard_cmd = "xclip"
                except FileNotFoundError:
                    try:
                        process = subprocess.Popen(
                            ["xsel", "--clipboard", "--input"], stdin=subprocess.PIPE, text=True
                        )
                        process.communicate(input=prompt_text)
                        clipboard_cmd = "xsel"
                    except FileNotFoundError:
                        raise FileNotFoundError("Neither xclip nor xsel available") from None
            elif system == "Windows":
                process = subprocess.Popen(["clip"], stdin=subprocess.PIPE, text=True)
                process.communicate(input=prompt_text)
                clipboard_cmd = "clip"
            else:
                raise OSError(f"Unsupported platform: {system}")

            # Success message
            if self.console:
                self.console.print(
                    f"[green]📋 Copied prompt to clipboard using {clipboard_cmd}[/green]"
                )
            else:
                print(f"📋 Copied prompt to clipboard using {clipboard_cmd}")

        except Exception as e:
            if self.console:
                self.console.print(f"[red]Failed to copy to clipboard: {e}[/red]")
            else:
                print(f"Failed to copy to clipboard: {e}")

        # Wait for user input to return to main view
        if self.console:
            self.console.print("\n[dim]Press Enter to return to main view...[/dim]")
        else:
            print("\nPress Enter to return to main view...")

        with contextlib.suppress(EOFError, KeyboardInterrupt):
            input()

    def _copy_response_to_clipboard(self, finding_data: dict) -> None:
        """Copy current finding's response to clipboard"""
        import platform
        import subprocess

        # Extract response from finding data
        response_text = finding_data.get("response", "")
        if not response_text:
            if self.console:
                self.console.print("[yellow]No response content available to copy[/yellow]")
            else:
                print("No response content available to copy")
            input("Press Enter to continue...")
            return

        try:
            # Detect platform and use appropriate clipboard command
            system = platform.system()

            if system == "Darwin":  # macOS
                process = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE, text=True)
                process.communicate(input=response_text)
                clipboard_cmd = "pbcopy"
            elif system == "Linux":
                # Try xclip first, then xsel
                try:
                    process = subprocess.Popen(
                        ["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE, text=True
                    )
                    process.communicate(input=response_text)
                    clipboard_cmd = "xclip"
                except FileNotFoundError:
                    try:
                        process = subprocess.Popen(
                            ["xsel", "--clipboard", "--input"], stdin=subprocess.PIPE, text=True
                        )
                        process.communicate(input=response_text)
                        clipboard_cmd = "xsel"
                    except FileNotFoundError:
                        raise FileNotFoundError("Neither xclip nor xsel available") from None
            elif system == "Windows":
                process = subprocess.Popen(["clip"], stdin=subprocess.PIPE, text=True)
                process.communicate(input=response_text)
                clipboard_cmd = "clip"
            else:
                raise OSError(f"Unsupported platform: {system}")

            # Success message
            if self.console:
                self.console.print(
                    f"[green]📋 Copied response to clipboard using {clipboard_cmd}[/green]"
                )
            else:
                print(f"📋 Copied response to clipboard using {clipboard_cmd}")

        except Exception as e:
            if self.console:
                self.console.print(f"[red]Failed to copy to clipboard: {e}[/red]")
            else:
                print(f"Failed to copy to clipboard: {e}")

        # Wait for user input to return to main view
        if self.console:
            self.console.print("\n[dim]Press Enter to return to main view...[/dim]")
        else:
            print("\nPress Enter to return to main view...")

        with contextlib.suppress(EOFError, KeyboardInterrupt):
            input()

    def _open_findings_folder(self) -> None:
        """Open findings folder in system file manager"""
        import platform
        import subprocess

        findings_dir = Path("findings").resolve()

        try:
            system = platform.system()
            if system == "Darwin":  # macOS
                subprocess.run(["open", str(findings_dir)])
            elif system == "Windows":
                subprocess.run(["explorer", str(findings_dir)])
            elif system == "Linux":
                subprocess.run(["xdg-open", str(findings_dir)])
            else:
                raise OSError(f"Unsupported platform: {system}")

            if self.console:
                self.console.print(f"[green]📂 Opened {findings_dir} in file manager[/green]")
            else:
                print(f"📂 Opened {findings_dir} in file manager")

        except Exception as e:
            if self.console:
                self.console.print(f"[red]Could not open folder: {e}[/red]")
                self.console.print(f"[yellow]Manual path: {findings_dir}[/yellow]")
            else:
                print(f"Could not open folder: {e}")
                print(f"Manual path: {findings_dir}")


def launch_findings_browser() -> None:
    """Launch findings browser directly without test results"""
    try:
        browser = FindingsBrowser()
        browser.view_findings()
    except Exception as e:
        print(f"Error launching findings browser: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    launch_findings_browser()

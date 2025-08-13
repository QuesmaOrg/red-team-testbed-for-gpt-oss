#!/usr/bin/env python3
"""
CLI interface for findings management and browsing
Separated from cli_ui.py for better organization
"""
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.prompt import Prompt, IntPrompt
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class FindingsBrowser:
    """Browser for findings files and export functionality"""
    
    def __init__(self):
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
                    if char == '\x1b[C':  # Right arrow
                        char = '→'
                    elif char == '\x1b[D':  # Left arrow
                        char = '←'
                    elif char == '\x1b[A':  # Up arrow
                        char = '↑'
                    elif char == '\x1b[B':  # Down arrow  
                        char = '↓'
                
                # Show the pressed key
                if self.console:
                    if char in ['→', '←', '↑', '↓']:
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

    def view_findings(self):
        """Browse and view findings folder"""
        findings_dir = Path("findings")
        if not findings_dir.exists():
            if self.console:
                self.console.print("[yellow]📁 No findings folder found. Export some findings first.[/yellow]")
            else:
                print("📁 No findings folder found. Export some findings first.")
            return
        
        # Get only grouped export files (export_*.json and flagged_*.json)
        all_files = list(findings_dir.glob("*.json"))
        grouped_files = [f for f in all_files if f.name.startswith(('export_', 'flagged_'))]
        
        if not grouped_files:
            if self.console:
                self.console.print("[yellow]📁 No grouped findings found. Export some findings first.[/yellow]")
                self.console.print("[dim]Note: Only showing grouped export files (export_*.json, flagged_*.json)[/dim]")
            else:
                print("📁 No grouped findings found. Export some findings first.")
                print("Note: Only showing grouped export files (export_*.json, flagged_*.json)")
            return
        
        # Sort by modification time (most recent first)
        grouped_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        if self.console:
            self.console.clear()
            self.console.print(Panel(f"📁 Grouped Findings ({len(grouped_files)} files)", style="bold blue"))
            
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
                    f"{modified.strftime('%m-%d %H:%M')} ({age})"
                )
            
            self.console.print(table)
            
            if len(grouped_files) > 20:
                self.console.print(f"[dim]... and {len(grouped_files) - 20} more files[/dim]")
            
            self.console.print()
            self.console.print("[yellow]Commands:[/yellow]")
            self.console.print(f"  [cyan]1-{min(20, len(grouped_files))}[/cyan]   - Navigate grouped findings")
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
                    
                print(f"{i:2d}. {filepath.name:<45} [{file_type:<12}] {size:>8} {modified.strftime('%m-%d %H:%M')}")
            
            if len(grouped_files) > 20:
                print(f"... and {len(grouped_files) - 20} more files")
            
            print("-" * 80)
            print(f"Commands: 1-{min(20, len(grouped_files))} (navigate findings), o (open folder), Enter (return)")
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
                                self.console.print(f"[red]Invalid number. Choose 1-{min(20, len(grouped_files))}[/red]")
                            else:
                                print(f"Invalid number. Choose 1-{min(20, len(grouped_files))}")
                            input("Press Enter to continue...")
                    except ValueError:
                        if self.console:
                            self.console.print("[red]Invalid input. Try a number, 'o', or Enter[/red]")
                        else:
                            print("Invalid input. Try a number, 'o', or Enter")
                        input("Press Enter to continue...")
                            
            except (EOFError, KeyboardInterrupt):
                break

    def _navigate_grouped_finding(self, filepath: Path):
        """Level 2: Navigate within a grouped finding file"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # Handle both grouped format and single finding format
            if "findings" in data and isinstance(data["findings"], list):
                # Grouped format
                findings = data["findings"]
                export_info = {
                    "export_id": data.get("export_id", "Unknown"),
                    "export_timestamp": data.get("export_timestamp", "Unknown"),
                    "total_findings": data.get("total_findings", len(findings)),
                    "session_summary": data.get("session_summary", {})
                }
            else:
                # Single finding format - treat as single item
                findings = [data]
                export_info = {
                    "export_id": data.get("finding_id", filepath.stem),
                    "export_timestamp": data.get("export_timestamp", "Unknown"),
                    "total_findings": 1,
                    "session_summary": {}
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
                    
                    vuln_status = "✓ Detected" if current_finding.get("vulnerability_detected") else "✗ Not detected"
                    info_table.add_row("Vulnerability", vuln_status)
                    info_table.add_row("Confidence", f"{current_finding.get('confidence', 0):.2f}")
                    
                    if current_finding.get("flagged"):
                        info_table.add_row("Status", "[red]🚩 FLAGGED[/red]")
                    
                    if current_finding.get("notes"):
                        info_table.add_row("Notes", current_finding["notes"])
                    
                    self.console.print(info_table)
                    
                    # Show prompt
                    if current_finding.get("prompt"):
                        prompt_text = current_finding["prompt"]
                        self.console.print(Panel(prompt_text, title="Prompt", style="yellow"))
                    
                    # Show response
                    if current_finding.get("response"):
                        response_text = current_finding["response"]
                        self.console.print(Panel(response_text, title="Response", style="green"))
                    
                    # Show commands
                    self.console.print("\n[yellow]Commands:[/yellow]")
                    commands = []
                    if current_index > 0:
                        commands.append("[cyan]p[/cyan] - Previous finding")
                    if current_index < len(findings) - 1:
                        commands.append("[cyan]n[/cyan] - Next finding")
                    if current_finding.get("thinking"):
                        commands.append("[cyan]t[/cyan] - View thinking")
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
                    
                    vuln_status = "✓ Detected" if current_finding.get("vulnerability_detected") else "✗ Not detected"
                    print(f"Vulnerability: {vuln_status}")
                    print(f"Confidence: {current_finding.get('confidence', 0):.2f}")
                    
                    if current_finding.get("flagged"):
                        print("Status: 🚩 FLAGGED")
                    
                    if current_finding.get("notes"):
                        print(f"Notes: {current_finding['notes']}")
                    
                    if current_finding.get("prompt"):
                        prompt_text = current_finding["prompt"]
                        print(f"\nPrompt:\n{prompt_text}")
                    
                    if current_finding.get("response"):
                        response_text = current_finding["response"]
                        print(f"\nResponse:\n{response_text}")
                    
                    print("-" * 80)
                    print("Commands: ", end="")
                    commands = []
                    if current_index > 0:
                        commands.append("p (previous)")
                    if current_index < len(findings) - 1:
                        commands.append("n (next)")
                    if current_finding.get("thinking"):
                        commands.append("t (thinking)")
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
                    
                    if user_input in ["\r", "\n", "", "q"]:
                        break
                    elif user_input.lower() == "n" and current_index < len(findings) - 1:
                        current_index += 1
                    elif user_input.lower() == "p" and current_index > 0:
                        current_index -= 1
                    elif user_input.lower() == "t" and current_finding.get("thinking"):
                        self._view_thinking(current_finding)
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

    def _view_thinking(self, finding_data):
        """Level 3: View thinking content for a specific finding"""
        thinking_content = finding_data.get("thinking", "")
        
        if not thinking_content:
            if self.console:
                self.console.print("[yellow]No thinking content available for this finding[/yellow]")
            else:
                print("No thinking content available for this finding")
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
                expand=False
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

    def _export_single_competition_finding(self, finding_data):
        """Export a single finding in competition format with user-provided name"""
        try:
            # Prompt user for finding name
            if self.console:
                self.console.print("\n[yellow]Enter name for competition finding:[/yellow]")
                finding_name = input("Name: ").strip()
            else:
                print("\nEnter name for competition finding:")
                finding_name = input("Name: ").strip()
            
            if not finding_name:
                if self.console:
                    self.console.print("[red]Export cancelled - no name provided[/red]")
                else:
                    print("Export cancelled - no name provided")
                input("Press Enter to continue...")
                return
            
            # Import required modules
            from utils.findings_generator import FindingsGenerator
            from utils.evaluator import VulnerabilityCategory, VulnerabilityScore, EvaluationResult
            
            generator = FindingsGenerator()
            
            # Map category string to enum
            category_mapping = {
                'cot_overload_bypass': VulnerabilityCategory.CHAIN_OF_THOUGHT,
                'cot_overload': VulnerabilityCategory.CHAIN_OF_THOUGHT,
                'deception_samples': VulnerabilityCategory.DECEPTION,
                'deception_adderall': VulnerabilityCategory.DECEPTION,
                'deception_security': VulnerabilityCategory.DECEPTION,
                'attachment_ai': VulnerabilityCategory.DECEPTION,
                'supremacy': VulnerabilityCategory.DECEPTION,
                'ai_escalation': VulnerabilityCategory.DECEPTION
            }
            
            original_category = finding_data.get("category", "unknown").lower()
            category = category_mapping.get(original_category, VulnerabilityCategory.INAPPROPRIATE_TOOL_USE)
            
            # Create evaluation result
            evaluation = EvaluationResult(
                is_vulnerable=finding_data.get("vulnerability_detected", False),
                category=category,
                confidence=finding_data.get("confidence", 0.0),
                evidence=finding_data.get("evidence", []),
                reasoning=finding_data.get("reasoning", "")
            )
            
            # Use default scores
            score = VulnerabilityScore(
                severity=5, breadth=3, novelty=3,
                reproducibility=7, methodological_insight=4
            )
            
            # Create finding
            finding = generator.create_finding(
                category=category,
                title=finding_data.get("test_name", "Unknown Test"),
                evaluation=evaluation,
                score=score,
                prompt=finding_data.get("prompt", ""),
                response=finding_data.get("response", ""),
                methodology=f"Single finding export from grouped data: {finding_data.get('test_id', 'Unknown')}",
                reproduction_steps=[
                    f"Original test: {finding_data.get('test_id', 'Unknown')}",
                    f"Use prompt from finding data",
                    "Analyze response for vulnerability evidence",
                    "Manually verified through CLI interface"
                ]
            )
            
            # Add notes if available
            if finding_data.get("notes"):
                finding.additional_notes = finding_data["notes"]
            
            # Save with custom filename
            findings_dir = Path("findings")
            findings_dir.mkdir(exist_ok=True)
            
            # Clean filename and add finding_ prefix
            clean_name = "".join(c for c in finding_name if c.isalnum() or c in (' ', '-', '_')).strip()
            clean_name = clean_name.replace(' ', '_')
            filename = f"finding_{clean_name}.json"
            filepath = findings_dir / filename
            
            # Save finding data using the standard save method
            saved_filepath = generator.save_finding(finding, str(findings_dir))
            
            # Rename the file to use custom name
            import shutil
            saved_path = Path(saved_filepath)
            shutil.move(saved_path, filepath)
            
            # Success message
            if self.console:
                self.console.print(f"[green]✅ Exported competition finding: {filename}[/green]")
                self.console.print(f"[dim]Saved to: {filepath}[/dim]")
            else:
                print(f"✅ Exported competition finding: {filename}")
                print(f"Saved to: {filepath}")
                
        except ImportError as e:
            if self.console:
                self.console.print(f"[red]Import error: {e}[/red]")
                self.console.print("[red]FindingsGenerator not available[/red]")
            else:
                print(f"Import error: {e}")
                print("FindingsGenerator not available")
        except Exception as e:
            if self.console:
                self.console.print(f"[red]Error exporting finding: {e}[/red]")
            else:
                print(f"Error exporting finding: {e}")
        
        # Wait for user input to return
        input("Press Enter to continue...")

    def _open_findings_folder(self):
        """Open findings folder in system file manager"""
        import subprocess
        import platform
        
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


def launch_findings_browser():
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
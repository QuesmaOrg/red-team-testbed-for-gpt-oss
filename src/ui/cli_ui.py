#!/usr/bin/env python3
"""
CLI interface for evaluating test results and scoring vulnerabilities
"""
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import IntPrompt, Prompt
    from rich.table import Table
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("Note: Install 'rich' for enhanced CLI experience: pip install rich")

import contextlib
import termios
import tty


@dataclass
class TestResult:
    """Container for test result data"""
    test_id: str
    test_name: str
    category: str
    prompt: str
    conversation_turns: list[str] | None
    response: str
    vulnerability_detected: bool
    confidence: float
    evidence: list[str]
    reasoning: str
    
    # Multi-turn conversation data
    all_responses: list[str] | None = None
    response_times: list[float] | None = None
    response_errors: list[str] | None = None
    
    # Chain of thought data
    thinking: str | None = None
    all_thinking: list[str] | None = None
    
    # Manual evaluation fields
    notes: str | None = None
    flagged: bool = False
    
    # Repetition metadata (only present when repeat > 1)
    repetition_run: int | None = None
    total_repetitions: int | None = None
    
    def get_turn_names(self) -> list[str]:
        """Get descriptive names for conversation turns"""
        if not self.conversation_turns:
            return []
        
        # Map turn indices to descriptive names based on common patterns
        turn_names = [
            "Opening/Rapport Building",
            "Topic Introduction", 
            "Escalation/Focus Shift",
            "Direct Request/Goal",
            "Follow-up/Clarification",
            "Final Push"
        ]
        
        # Return appropriate number of turn names
        num_turns = len(self.conversation_turns)
        if num_turns <= len(turn_names):
            return turn_names[:num_turns]
        else:
            # If more turns than predefined names, add generic ones
            result = turn_names[:]
            for i in range(len(turn_names), num_turns):
                result.append(f"Turn {i+1}")
            return result
    
    def get_display_conversation(self) -> str:
        """Get full conversation for display - handles both single-turn and multi-turn"""
        if self.conversation_turns and self.all_responses:
            # Multi-turn: show full conversation with responses
            conversation_parts = []
            turn_names = self.get_turn_names()
            
            for i, (turn_prompt, response) in enumerate(zip(self.conversation_turns, self.all_responses, strict=False)):
                turn_name = turn_names[i] if i < len(turn_names) else f"Turn {i+1}"
                response_time = self.response_times[i] if self.response_times and i < len(self.response_times) else 0.0
                
                # Format each turn as a conversation with colors
                turn_header = f"--- {turn_name} ({response_time:.1f}s) ---"
                user_part = f"[bold cyan]USER: {turn_prompt}[/bold cyan]"
                model_part = f"[bold green]MODEL:[/bold green] {response}"
                
                conversation_parts.append(f"{turn_header}\n{user_part}\n\n{model_part}")
            
            return "\n\n" + "="*60 + "\n\n".join(conversation_parts)
            
        elif self.conversation_turns:
            # Multi-turn but no individual responses (fallback)
            turns = []
            turn_names = self.get_turn_names()
            for i, turn in enumerate(self.conversation_turns):
                turn_name = turn_names[i] if i < len(turn_names) else f"Turn {i+1}"
                turns.append(f"{turn_name}: {turn}")
            return "\n\n".join(turns) + f"\n\n[bold green]FINAL RESPONSE:[/bold green]\n{self.response}"
            
        else:
            # Single-turn: just return the prompt and response with colors
            return f"[bold cyan]USER: {self.prompt or 'No prompt available'}[/bold cyan]\n\n[bold green]MODEL:[/bold green] {self.response}"
    
    def _strip_rich_markup(self, text: str) -> str:
        """Strip Rich markup for plain text display"""
        import re
        return re.sub(r'\[/?[^]]*\]', '', text)
    
    def get_display_prompt(self) -> str:
        """Legacy method for backward compatibility"""
        if self.conversation_turns:
            # Multi-turn: show all turns with labels
            turn_names = self.get_turn_names()
            turns = []
            for i, turn in enumerate(self.conversation_turns):
                turn_name = turn_names[i] if i < len(turn_names) else f"Turn {i+1}"
                turns.append(f"{turn_name}: {turn}")
            return "\n\n".join(turns)
        else:
            # Single-turn: just return the prompt
            return self.prompt or "No prompt available"
    
    def get_raw_prompts(self) -> str:
        """Get raw prompts without any formatting for copying to clipboard"""
        if self.conversation_turns:
            # Multi-turn: return each turn on separate lines with minimal formatting
            prompts = []
            for i, turn in enumerate(self.conversation_turns, 1):
                prompts.append(f"Turn {i}: {turn}")
            return "\n\n".join(prompts)
        else:
            # Single-turn: just return the raw prompt
            return self.prompt or "No prompt available"


class CLIEvaluator:
    """Interactive CLI for evaluating test results"""
    
    def __init__(self, results_file: str) -> None:
        self.results_file = results_file
        self.results_data = self._load_results()
        self.test_results: list[TestResult] = self._parse_results()
        self.current_index = 0
        
        if RICH_AVAILABLE:
            self.console = Console()
        else:
            self.console = None
    
    def _load_results(self) -> dict[str, Any]:
        """Load results from JSON file"""
        with open(self.results_file) as f:
            return json.load(f)
    
    def _parse_results(self) -> list[TestResult]:
        """Parse results into TestResult objects"""
        test_results = []
        
        for category, category_data in self.results_data.items():
            for test_detail in category_data.get('test_details', []):
                result = TestResult(
                    test_id=test_detail.get('test_id', ''),
                    test_name=test_detail.get('test_name', ''),
                    category=test_detail.get('category', category),
                    prompt=test_detail.get('prompt', ''),
                    conversation_turns=test_detail.get('conversation_turns', None),
                    response=test_detail.get('response_content', ''),
                    vulnerability_detected=test_detail.get('vulnerability_detected', False),
                    confidence=test_detail.get('confidence', 0.0),
                    evidence=test_detail.get('evidence', []),
                    reasoning=test_detail.get('reasoning', ''),
                    # Multi-turn conversation data
                    all_responses=test_detail.get('all_responses', None),
                    response_times=test_detail.get('response_times', None),
                    response_errors=test_detail.get('response_errors', None),
                    # Chain of thought data
                    thinking=test_detail.get('thinking', None),
                    all_thinking=test_detail.get('all_thinking', None),
                    # Load saved evaluation data
                    flagged=test_detail.get('flagged', False),
                    notes=test_detail.get('notes'),
                    # Load repetition metadata
                    repetition_run=test_detail.get('repetition_run'),
                    total_repetitions=test_detail.get('total_repetitions')
                )
                test_results.append(result)
        
        return test_results
    
    def _save_updated_results(self) -> None:
        """Save updated results with flagged status back to JSON file"""
        try:
            # Update the original results data with flagged status
            for _category, category_data in self.results_data.items():
                for i, test_detail in enumerate(category_data.get('test_details', [])):
                    # Find matching test result by test_id and repetition_run (if applicable)
                    test_id = test_detail.get('test_id')
                    repetition_run = test_detail.get('repetition_run')
                    
                    for result in self.test_results:
                        # Match by test_id and repetition_run (if both have repetition data)
                        if result.test_id == test_id:
                            # If both have repetition data, they must match
                            if (repetition_run is not None and result.repetition_run is not None):
                                if repetition_run == result.repetition_run:
                                    # Exact match including repetition
                                    test_detail['flagged'] = result.flagged
                                    test_detail['notes'] = result.notes
                                    break
                            # If neither has repetition data, it's a simple match
                            elif (repetition_run is None and result.repetition_run is None):
                                # Simple match without repetitions
                                test_detail['flagged'] = result.flagged
                                test_detail['notes'] = result.notes
                                break
                            # If only one has repetition data, use positional matching as fallback
                            elif (repetition_run is None and result.repetition_run is not None):
                                # JSON entry has no repetition info, but result does
                                # Match by position in the list (old format compatibility)
                                if i < len(self.test_results) and self.test_results[i] == result:
                                    test_detail['flagged'] = result.flagged
                                    test_detail['notes'] = result.notes
                                    break
                            elif (repetition_run is not None and result.repetition_run is None):
                                # JSON has repetition info, but result doesn't (shouldn't happen)
                                # Fall back to simple test_id matching
                                test_detail['flagged'] = result.flagged
                                test_detail['notes'] = result.notes
                                break
            
            # Write back to file
            with open(self.results_file, 'w') as f:
                json.dump(self.results_data, f, indent=2)
                
        except Exception as e:
            if self.console:
                self.console.print(f"[yellow]⚠️  Could not save updated results: {e}[/yellow]")
            else:
                print(f"⚠️  Could not save updated results: {e}")
    
    
    def _strip_rich_markup(self, text: str) -> str:
        """Strip Rich markup for plain text display"""
        import re
        return re.sub(r'\[/?[^]]*\]', '', text)
    
    
    
    
    
    
    def _display_test_result(self, result: TestResult) -> None:
        """Display current test result"""
        if self.console:
            self.console.clear()
            title = f"GPT-OSS-20B Red Team Result Evaluator [{self.current_index + 1}/{len(self.test_results)}]"
            self.console.print(Panel(title, style="bold blue"))
            
            # Create rich display
            table = Table(show_header=False, header_style="bold magenta")
            table.add_column("Field", style="cyan")
            table.add_column("Value")
            
            # Show test ID with repetition info if available
            test_id_display = result.test_id
            if result.repetition_run is not None and result.total_repetitions is not None:
                test_id_display = f"{result.test_id} (run {result.repetition_run}/{result.total_repetitions})"
            
            table.add_row("Test ID", test_id_display)
            table.add_row("Name", result.test_name)
            table.add_row("Category", result.category)
            table.add_row("Vulnerable (confidence)", f"🔴 YES ({result.confidence:.2f})" if result.vulnerability_detected else f"🟢 NO ({result.confidence:.2f})")
            
            self.console.print(table)
            self.console.print()
            
            # Display conversation content - always full, no truncation
            if result.conversation_turns and result.all_responses:
                num_turns = len(result.conversation_turns)
                conv_title = f"Multi-Turn Conversation ({num_turns} turns)"
                conversation_text = result.get_display_conversation()
                self.console.print(Panel(conversation_text, title=conv_title, style="yellow"))
                
            elif result.conversation_turns:
                # Fallback for older data without individual responses
                prompt_title = "Multi-Turn Prompts"
                prompt_text = f"[bold cyan]{result.get_display_prompt()}[/bold cyan]"
                self.console.print(Panel(prompt_text, title=prompt_title, style="yellow"))
                
                # Response with standardized color
                formatted_response = f"[bold green]{result.response}[/bold green]"
                self.console.print(Panel(formatted_response, title="Final Response", style="green"))
                
            else:
                # Single-turn display with standardized colors
                prompt_text = f"[bold cyan]{result.prompt}[/bold cyan]"
                self.console.print(Panel(prompt_text, title="Prompt", style="yellow"))
                
                # Response - always show full response
                formatted_response = f"[bold green]{result.response}[/bold green]"
                self.console.print(Panel(formatted_response, title="Response", style="green"))
            
            # Display evidence if any
            if result.evidence:
                evidence_text = "\n".join(f"• {e}" for e in result.evidence)
                self.console.print(Panel(evidence_text, title="Evidence", style="red"))
            
            # Display reasoning
            if result.reasoning:
                self.console.print(Panel(result.reasoning, title="Reasoning", style="blue"))
        
        else:
            # Fallback text display - always show full content
            print("=" * 70)
            print(f"GPT-OSS-20B Red Team Result Evaluator [{self.current_index + 1}/{len(self.test_results)}]")
            print("=" * 70)
            
            # Show test ID with repetition info if available
            test_id_display = result.test_id
            if result.repetition_run is not None and result.total_repetitions is not None:
                test_id_display = f"{result.test_id} (run {result.repetition_run}/{result.total_repetitions})"
            
            print(f"\nTest: {result.test_name} ({test_id_display})")
            print(f"Category: {result.category}")
            print(f"Vulnerable: {'YES' if result.vulnerability_detected else 'NO'}")
            print(f"Confidence: {result.confidence:.2f}")
            
            if result.conversation_turns and result.all_responses:
                num_turns = len(result.conversation_turns)
                print(f"\nFull Conversation ({num_turns} turns):")
                conversation_text = result._strip_rich_markup(result.get_display_conversation())
                print(conversation_text)
            else:
                print(f"\nPrompt:\n{result._strip_rich_markup(result.get_display_prompt())}")
                print(f"\nResponse:\n{result.response}")
            
            if result.evidence:
                print("\nEvidence:")
                for e in result.evidence:
                    print(f"  • {e}")
            
            if result.reasoning:
                print(f"\nReasoning: {result.reasoning}")
    
    
    
    
    def _show_help(self) -> None:
        """Display detailed help for all commands"""
        if self.console:
            from rich.table import Table
            
            self.console.print()
            help_table = Table(title="📖 Command Help", show_header=True, header_style="bold cyan")
            help_table.add_column("Key", style="yellow", width=8)
            help_table.add_column("Command", width=25)
            help_table.add_column("Description", style="dim")
            
            help_table.add_row("n", "Next result", "Move to the next test result")
            help_table.add_row("→", "Next result", "Alternative key for next")
            help_table.add_row("p", "Previous result", "Move to the previous test result")  
            help_table.add_row("←", "Previous result", "Alternative key for previous")
            help_table.add_row("f", "Flag finding", "Flag as potential finding & auto-save")
            help_table.add_row("u", "Unflag", "Remove flag from current result")
            help_table.add_row("j", "Jump to #", "Jump directly to a specific result number")
            help_table.add_row("c", "Copy prompt", "Copy raw prompts to clipboard for manual testing")
            help_table.add_row("r", "Copy response", "Copy model response to clipboard for analysis")
            help_table.add_row("t", "Show thinking", "Display model's chain of thought reasoning")
            help_table.add_row("e", "Export findings", "Export all flagged results as findings")
            help_table.add_row("v", "View findings", "Browse findings folder and view files")
            help_table.add_row("h/?", "Help", "Show this help screen")
            help_table.add_row("q/end", "Quit", "Exit the evaluator")
            
            self.console.print(help_table)
            self.console.print()
            
            # Show evaluation note
            self.console.print(Panel(
                "[bold]Note:[/bold] Judges will handle final scoring and evaluation.\n"
                "Use this interface to review results and flag promising findings.",
                title="💡 Evaluation Process",
                title_align="left"
            ))
            
            input("Press Enter to continue...")
        else:
            print("\n" + "="*60)
            print("📖 COMMAND HELP")
            print("="*60)
            print("Navigation:")
            print("  n/→   - Next result")
            print("  p/←   - Previous result") 
            print("  j     - Jump to result number")
            print()
            print("Actions:")
            print("  f     - Flag as finding (auto-saves)")
            print("  u     - Unflag result")
            print("  c     - Copy prompt to clipboard")
            print("  r     - Copy response to clipboard")
            print("  t     - Show chain of thought")
            print("  e     - Export all flagged findings")
            print("  v     - View findings folder")
            print()
            print("Help & Exit:")
            print("  h/?   - Show this help")
            print("  q/end - Quit evaluator")
            print()
            print("Note: Judges will handle final scoring and evaluation.")
            print("Use this interface to review results and flag promising findings.")
            print("="*60)
            input("Press Enter to continue...")

    def _get_single_char(self, prompt_text: str = "Command: ") -> str:
        """Get a single character input without pressing Enter"""
        try:
            if self.console:
                self.console.print(f"[dim]{prompt_text}[/dim]", end="")
            else:
                print(f"{prompt_text}", end="", flush=True)
            
            # Save terminal settings
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

    def _display_status_bar(self) -> None:
        """Display status bar with progress and flagged count"""
        flagged_count = sum(1 for r in self.test_results if r.flagged)
        progress_text = f"Progress: [{self.current_index + 1}/{len(self.test_results)}]"
        flagged_text = f"Flagged: {flagged_count}"
        commands_text = "Commands: n/p/f/u/j/c/t/e/v/h/?/q/end"
        
        status_line = f"{progress_text} | {flagged_text} | {commands_text}"
        
        if self.console:
            self.console.print(Panel(status_line, style="dim", title="Status", title_align="left"))
        else:
            print(f"\n{'-' * min(len(status_line), 80)}")
            print(status_line[:80] if len(status_line) > 80 else status_line)
            print(f"{'-' * min(len(status_line), 80)}")
    
    def _display_commands(self) -> None:
        """Display available commands"""
        if self.console:
            commands = Table(show_header=True, header_style="bold cyan")
            commands.add_column("Key", style="yellow")
            commands.add_column("Command")
            
            commands.add_row("n/→", "Next result")
            commands.add_row("p/←", "Previous result")
            commands.add_row("f", "Flag as potential finding")
            commands.add_row("u", "Unflag result")
            commands.add_row("j", "Jump to result number")
            commands.add_row("c", "Copy prompt to clipboard")
            commands.add_row("r", "Copy response to clipboard")
            commands.add_row("t", "Show chain of thought")
            commands.add_row("e", "Export flagged findings")
            commands.add_row("v", "View findings folder")
            commands.add_row("q/end", "Quit")
            
            self.console.print(commands)
        else:
            print("\nCommands:")
            print("  n/→  - Next result        p/←  - Previous result")
            print("  f    - Flag finding       u    - Unflag")
            print("  u    - Unflag            j    - Jump to #")
            print("  c    - Copy prompt        r    - Copy response")
            print("  t    - Show thinking")
            print("  e    - Export findings    v    - View findings")
            print("  q/end - Quit")
    
    
    def _display_thinking(self) -> None:
        """Display chain of thought reasoning for current test"""
        result = self.test_results[self.current_index]
        
        # Check if we have any thinking data
        has_thinking = False
        if result.all_thinking and any(thinking for thinking in result.all_thinking) or result.thinking:
            has_thinking = True
            
        if not has_thinking:
            if self.console:
                self.console.print("[yellow]⚠️  No chain of thought data available for this test[/yellow]")
                self.console.print("[dim]This test was created before thinking data was captured.[/dim]")
                self.console.print("\n[dim]Press Enter to return to main view...[/dim]")
            else:
                print("⚠️  No chain of thought data available for this test")
                print("This test was created before thinking data was captured.")
                print("\nPress Enter to return to main view...")
            
            # Wait for user input to return to main view
            with contextlib.suppress(EOFError, KeyboardInterrupt):
                input()
            return
        
        if self.console:
            self.console.clear()
            title = f"Chain of Thought - {result.test_name} ({result.test_id})"
            self.console.print(Panel(title, style="bold magenta"))
            
            if result.all_thinking and len(result.all_thinking) > 1:
                # Multi-turn thinking
                for i, thinking in enumerate(result.all_thinking, 1):
                    if thinking:
                        turn_title = f"Turn {i} Reasoning"
                        self.console.print(Panel(thinking, title=turn_title, style="cyan", border_style="dim"))
                    else:
                        self.console.print(f"[dim]Turn {i}: No thinking data[/dim]")
                    self.console.print()
            else:
                # Single-turn thinking
                thinking_content = result.thinking or (result.all_thinking[0] if result.all_thinking else "")
                if thinking_content:
                    self.console.print(Panel(thinking_content, title="Model Reasoning", style="cyan"))
                else:
                    self.console.print("[dim]No thinking content available[/dim]")
        else:
            # Fallback text display
            print("=" * 70)
            print(f"Chain of Thought - {result.test_name} ({result.test_id})")
            print("=" * 70)
            
            if result.all_thinking and len(result.all_thinking) > 1:
                # Multi-turn thinking
                for i, thinking in enumerate(result.all_thinking, 1):
                    print(f"\nTurn {i} Reasoning:")
                    print("-" * 40)
                    if thinking:
                        print(thinking)
                    else:
                        print("No thinking data for this turn")
            else:
                # Single-turn thinking
                thinking_content = result.thinking or (result.all_thinking[0] if result.all_thinking else "")
                print("\nModel Reasoning:")
                print("-" * 40)
                if thinking_content:
                    print(thinking_content)
                else:
                    print("No thinking content available")
            
            print("=" * 70)
        
        # Wait for user input to return to main view
        if self.console:
            self.console.print("\n[dim]Press Enter to return to main view...[/dim]")
        else:
            print("\nPress Enter to return to main view...")
        
        with contextlib.suppress(EOFError, KeyboardInterrupt):
            input()
    
    def _copy_prompt_to_clipboard(self) -> None:
        """Copy current test's raw prompts to clipboard"""
        import platform
        import subprocess
        
        result = self.test_results[self.current_index]
        raw_prompts = result.get_raw_prompts()
        
        try:
            # Detect platform and use appropriate clipboard command
            system = platform.system()
            
            if system == "Darwin":  # macOS
                process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE, text=True)
                process.communicate(input=raw_prompts)
                clipboard_cmd = "pbcopy"
            elif system == "Linux":
                # Try xclip first, then xsel
                try:
                    process = subprocess.Popen(['xclip', '-selection', 'clipboard'], 
                                             stdin=subprocess.PIPE, text=True)
                    process.communicate(input=raw_prompts)
                    clipboard_cmd = "xclip"
                except FileNotFoundError:
                    try:
                        process = subprocess.Popen(['xsel', '--clipboard', '--input'], 
                                                 stdin=subprocess.PIPE, text=True)
                        process.communicate(input=raw_prompts)
                        clipboard_cmd = "xsel"
                    except FileNotFoundError:
                        raise FileNotFoundError("Neither xclip nor xsel available") from None
            elif system == "Windows":
                process = subprocess.Popen(['clip'], stdin=subprocess.PIPE, text=True)
                process.communicate(input=raw_prompts)
                clipboard_cmd = "clip"
            else:
                raise OSError(f"Unsupported platform: {system}")
            
            # Success message
            if self.console:
                if result.conversation_turns:
                    self.console.print(f"[green]📋 Copied {len(result.conversation_turns)} prompts to clipboard using {clipboard_cmd}[/green]")
                else:
                    self.console.print(f"[green]📋 Copied prompt to clipboard using {clipboard_cmd}[/green]")
                self.console.print("[dim]Ready to paste into ollama run commands[/dim]")
            else:
                if result.conversation_turns:
                    print(f"📋 Copied {len(result.conversation_turns)} prompts to clipboard using {clipboard_cmd}")
                else:
                    print(f"📋 Copied prompt to clipboard using {clipboard_cmd}")
                print("Ready to paste into ollama run commands")
            
            # Wait for user input to return to main view
            if self.console:
                self.console.print("\n[dim]Press Enter to return to main view...[/dim]")
            else:
                print("\nPress Enter to return to main view...")
            
            with contextlib.suppress(EOFError, KeyboardInterrupt):
                input()
                
        except (FileNotFoundError, OSError, subprocess.SubprocessError) as e:
            # Clipboard unavailable - show raw prompts as fallback
            if self.console:
                self.console.print(f"[yellow]⚠️  Clipboard unavailable ({e})[/yellow]")
                self.console.print("[yellow]Here are the raw prompts to copy manually:[/yellow]")
                self.console.print(Panel(raw_prompts, title="Raw Prompts", style="cyan"))
            else:
                print(f"⚠️  Clipboard unavailable ({e})")
                print("Here are the raw prompts to copy manually:")
                print("-" * 60)
                print(raw_prompts)
                print("-" * 60)
            
            # Wait for user input to return to main view
            if self.console:
                self.console.print("\n[dim]Press Enter to return to main view...[/dim]")
            else:
                print("\nPress Enter to return to main view...")
            
            with contextlib.suppress(EOFError, KeyboardInterrupt):
                input()

    def _copy_response_to_clipboard(self) -> None:
        """Copy current test's response to clipboard"""
        import platform
        import subprocess
        
        result = self.test_results[self.current_index]
        response_text = result.response
        
        if not response_text:
            if self.console:
                self.console.print("[yellow]No response content available to copy[/yellow]")
            else:
                print("No response content available to copy")
            
            # Wait for user input to return to main view
            if self.console:
                self.console.print("\n[dim]Press Enter to return to main view...[/dim]")
            else:
                print("\nPress Enter to return to main view...")
            
            with contextlib.suppress(EOFError, KeyboardInterrupt):
                input()
            return
        
        try:
            # Detect platform and use appropriate clipboard command
            system = platform.system()
            
            if system == "Darwin":  # macOS
                process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE, text=True)
                process.communicate(input=response_text)
                clipboard_cmd = "pbcopy"
            elif system == "Linux":
                # Try xclip first, then xsel
                try:
                    process = subprocess.Popen(['xclip', '-selection', 'clipboard'], 
                                             stdin=subprocess.PIPE, text=True)
                    process.communicate(input=response_text)
                    clipboard_cmd = "xclip"
                except FileNotFoundError:
                    try:
                        process = subprocess.Popen(['xsel', '--clipboard', '--input'], 
                                                 stdin=subprocess.PIPE, text=True)
                        process.communicate(input=response_text)
                        clipboard_cmd = "xsel"
                    except FileNotFoundError:
                        raise FileNotFoundError("Neither xclip nor xsel available") from None
            elif system == "Windows":
                process = subprocess.Popen(['clip'], stdin=subprocess.PIPE, text=True)
                process.communicate(input=response_text)
                clipboard_cmd = "clip"
            else:
                raise OSError(f"Unsupported platform: {system}")
            
            # Success message
            if self.console:
                self.console.print(f"[green]📋 Copied response to clipboard using {clipboard_cmd}[/green]")
                self.console.print("[dim]Ready to paste for further analysis[/dim]")
            else:
                print(f"📋 Copied response to clipboard using {clipboard_cmd}")
                print("Ready to paste for further analysis")
            
            # Wait for user input to return to main view
            if self.console:
                self.console.print("\n[dim]Press Enter to return to main view...[/dim]")
            else:
                print("\nPress Enter to return to main view...")
            
            with contextlib.suppress(EOFError, KeyboardInterrupt):
                input()
                
        except (FileNotFoundError, OSError, subprocess.SubprocessError) as e:
            # Clipboard unavailable - show response as fallback
            if self.console:
                self.console.print(f"[yellow]⚠️  Clipboard unavailable ({e})[/yellow]")
                self.console.print("[yellow]Here is the response to copy manually:[/yellow]")
                self.console.print(Panel(response_text, title="Response", style="green"))
            else:
                print(f"⚠️  Clipboard unavailable ({e})")
                print("Here is the response to copy manually:")
                print("-" * 60)
                print(response_text)
                print("-" * 60)
            
            # Wait for user input to return to main view
            if self.console:
                self.console.print("\n[dim]Press Enter to return to main view...[/dim]")
            else:
                print("\nPress Enter to return to main view...")
            
            with contextlib.suppress(EOFError, KeyboardInterrupt):
                input()

    def _export_findings(self) -> None:
        """Export flagged results as grouped findings"""
        flagged_results = [r for r in self.test_results if r.flagged]
        
        if not flagged_results:
            print("No flagged results to export.")
            return
        
        import json
        from collections import Counter
        from datetime import datetime
        from pathlib import Path
        
        findings_dir = Path("findings")
        findings_dir.mkdir(exist_ok=True)
        
        # Create grouped export
        timestamp = datetime.now()
        export_id = f"export_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        
        # Collect findings data
        findings_data = []
        categories = []
        vulnerable_count = 0
        
        for i, result in enumerate(flagged_results, 1):
            try:
                # Create finding data (preserves ALL data)
                finding_data = {
                    "finding_index": i,
                    "finding_id": f"{result.test_id}_{i}",
                    "test_id": result.test_id,
                    "test_name": result.test_name,
                    "category": result.category,  # Preserve original category string
                    "prompt": result.get_display_prompt(),
                    "response": result.response,
                    "vulnerability_detected": result.vulnerability_detected,
                    "confidence": result.confidence,
                    "evidence": result.evidence,
                    "reasoning": result.reasoning,
                    "flagged": result.flagged,
                    "notes": result.notes,
                    "thinking": result.thinking,
                    "all_responses": getattr(result, 'all_responses', None),
                    "response_times": getattr(result, 'response_times', None),
                    "all_thinking": getattr(result, 'all_thinking', None),
                    "repetition_run": result.repetition_run,
                    "total_repetitions": result.total_repetitions
                }
                
                findings_data.append(finding_data)
                categories.append(result.category)
                if result.vulnerability_detected:
                    vulnerable_count += 1
                    
            except Exception as e:
                print(f"✗ Failed to process {result.test_id}: {e}")
                continue
        
        # Create grouped export structure
        category_counts = Counter(categories)
        top_categories = [cat for cat, _ in category_counts.most_common(3)]
        
        grouped_export = {
            "export_id": export_id,
            "export_timestamp": timestamp.isoformat(),
            "exported_from": "cli_ui_export",
            "total_findings": len(findings_data),
            "session_summary": {
                "categories": top_categories,
                "category_counts": dict(category_counts),
                "vulnerable_count": vulnerable_count,
                "flagged_count": len(flagged_results)
            },
            "findings": findings_data
        }
        
        # Save grouped export
        export_filepath = findings_dir / f"{export_id}.json"
        with open(export_filepath, 'w') as f:
            json.dump(grouped_export, f, indent=2)
        
        print(f"✓ Created grouped export: {export_filepath.name}")
        print(f"   Contains {len(findings_data)} findings")
        print(f"   Categories: {', '.join(top_categories)}")
        print(f"   Vulnerable findings: {vulnerable_count}")
        
        print("\n📁 Export Summary:")
        print(f"   Created: {export_filepath.name}")
        print(f"   Contains {len(findings_data)} grouped findings")
        print("   Saved to findings/ directory")
        print("   💡 Use 'v' command to browse and 'e' to export individual competition files")
        
        # Wait for user input to return to main view
        if self.console:
            self.console.print("\n[dim]Press Enter to return to main view...[/dim]")
        else:
            print("\nPress Enter to return to main view...")
        
        with contextlib.suppress(EOFError, KeyboardInterrupt):
            input()

    def _view_findings(self) -> None:
        """Browse findings using the dedicated findings browser"""
        from .cli_findings import FindingsBrowser
        browser = FindingsBrowser()
        browser.view_findings()
    
    def run(self) -> None:
        """Main evaluation loop"""
        try:
            while True:
                result = self.test_results[self.current_index]
                self._display_test_result(result)
                
                
                if result.flagged:
                    if self.console:
                        self.console.print("[red]🚩 FLAGGED AS FINDING[/red]")
                    else:
                        print("🚩 FLAGGED AS FINDING")
                
                self._display_status_bar()
                
                # Get user input (single character)
                command = self._get_single_char()
                if self.console:
                    self.console.print()
                else:
                    print()
                
                # Process commands
                if command in ['n', 'next', '→']:
                    if self.current_index >= len(self.test_results) - 1:
                        # At the last result, pressing 'n' completes the session
                        flagged_count = sum(1 for r in self.test_results if r.flagged)
                        
                        if self.console:
                            self.console.print()
                            self.console.print("[bold green]🎉 Review Complete![/bold green]")
                            self.console.print(f"[green]You've reviewed all {len(self.test_results)} results.[/green]")
                            self.console.print(f"[cyan]📊 Session Summary: {flagged_count} flagged for judge review[/cyan]")
                            if flagged_count > 0:
                                self.console.print("[yellow]💾 Flagged items have been auto-saved as findings.[/yellow]")
                        else:
                            print("\n🎉 Review Complete!")
                            print(f"You've reviewed all {len(self.test_results)} results.")
                            print(f"📊 Session Summary: {flagged_count} flagged for judge review")
                            if flagged_count > 0:
                                print("💾 Flagged items have been auto-saved as findings.")
                        break
                    else:
                        self.current_index += 1
                elif command in ['p', 'prev', '←']:
                    self.current_index = max(self.current_index - 1, 0)
                elif command == 'f':
                    result.flagged = True
                    if self.console:
                        self.console.print("🚩 Flagged as potential finding")
                    else:
                        print("🚩 Flagged as potential finding")
                    
                    # Save updated results to JSON
                    self._save_updated_results()
                    
                    if self.console:
                        self.console.print("[green]✅ Flagged status saved to results file[/green]")
                        self.console.print("[dim]💡 Use 'e' in bulk export or 'v' → 'e' to create competition files[/dim]")
                    else:
                        print("✅ Flagged status saved to results file")
                        print("💡 Use 'e' in bulk export or 'v' → 'e' to create competition files")
                elif command == 'u':
                    result.flagged = False
                    if self.console:
                        self.console.print("🔄 Unflagged - status updated in results file")
                    else:
                        print("🔄 Unflagged - status updated in results file")
                    
                    # Save updated results to JSON
                    self._save_updated_results()
                elif command == 'j':
                    try:
                        if self.console:
                            self.console.print("\n[yellow]Jump to result number (1-based):[/yellow]")
                            target = IntPrompt.ask("Target")
                        else:
                            print("\nJump to result number (1-based):")
                            target = int(input("Target: "))
                        self.current_index = max(0, min(target - 1, len(self.test_results) - 1))
                        if self.console:
                            self.console.print(f"[green]Jumped to result {target}[/green]")
                        else:
                            print(f"Jumped to result {target}")
                    except (ValueError, EOFError, KeyboardInterrupt):
                        if self.console:
                            self.console.print("[red]Jump cancelled[/red]")
                        else:
                            print("Jump cancelled")
                elif command == 'c':
                    self._copy_prompt_to_clipboard()
                elif command == 'r':
                    self._copy_response_to_clipboard()
                elif command == 't':
                    self._display_thinking()
                elif command == 'e':
                    self._export_findings()
                elif command == 'v':
                    self._view_findings()
                elif command in ['h', '?']:
                    self._show_help()
                elif command in ['q', 'quit', 'exit', 'end', '\x04']:
                    break
                else:
                    print(f"Unknown command: {command}")
                
        except KeyboardInterrupt:
            if self.console:
                self.console.print("\n[yellow]Evaluation interrupted by user[/yellow]")
            else:
                print("\nEvaluation interrupted by user")
        
        # Show final summary
        flagged_count = sum(1 for r in self.test_results if r.flagged)
        
        if self.console:
            summary = f"Session Summary: {flagged_count} flagged for judge review"
            self.console.print(Panel(summary, style="bold green"))
        else:
            print(f"\nSession Summary: {flagged_count} flagged for judge review")


def launch_cli_ui(results_file: str) -> None:
    """Launch the CLI UI for result evaluation"""
    if not Path(results_file).exists():
        print(f"Error: Results file not found: {results_file}")
        return
    
    try:
        evaluator = CLIEvaluator(results_file)
        evaluator.run()
    except Exception as e:
        print(f"Error launching CLI UI: {e}")




if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python cli_ui.py <results_file.json>")
        sys.exit(1)
    
    launch_cli_ui(sys.argv[1])
#!/usr/bin/env python3
"""
CLI interface for evaluating test results and scoring vulnerabilities
"""
import json
import sys
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.syntax import Syntax
    from rich.prompt import Prompt, IntPrompt
    from rich.text import Text
    from rich.layout import Layout
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("Note: Install 'rich' for enhanced CLI experience: pip install rich")

import click
import sys
import termios
import tty


@dataclass
class TestResult:
    """Container for test result data"""
    test_id: str
    test_name: str
    category: str
    prompt: str
    conversation_turns: Optional[List[str]]
    response: str
    vulnerability_detected: bool
    confidence: float
    evidence: List[str]
    reasoning: str
    
    # Multi-turn conversation data
    all_responses: Optional[List[str]] = None
    response_times: Optional[List[float]] = None
    response_errors: Optional[List[str]] = None
    
    # Chain of thought data
    thinking: Optional[str] = None
    all_thinking: Optional[List[str]] = None
    
    # Manual evaluation fields
    notes: Optional[str] = None
    flagged: bool = False
    
    # Repetition metadata (only present when repeat > 1)
    repetition_run: Optional[int] = None
    total_repetitions: Optional[int] = None
    
    def get_turn_names(self) -> List[str]:
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
            
            for i, (turn_prompt, response) in enumerate(zip(self.conversation_turns, self.all_responses)):
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
    
    def __init__(self, results_file: str):
        self.results_file = results_file
        self.results_data = self._load_results()
        self.test_results: List[TestResult] = self._parse_results()
        self.current_index = 0
        
        if RICH_AVAILABLE:
            self.console = Console()
        else:
            self.console = None
    
    def _load_results(self) -> Dict[str, Any]:
        """Load results from JSON file"""
        with open(self.results_file, 'r') as f:
            return json.load(f)
    
    def _parse_results(self) -> List[TestResult]:
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
    
    def _save_updated_results(self):
        """Save updated results with flagged status back to JSON file"""
        try:
            # Update the original results data with flagged status
            for category, category_data in self.results_data.items():
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
    
    
    
    
    
    
    def _display_test_result(self, result: TestResult):
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
                print(f"\nEvidence:")
                for e in result.evidence:
                    print(f"  • {e}")
            
            if result.reasoning:
                print(f"\nReasoning: {result.reasoning}")
    
    
    
    
    def _show_help(self):
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

    def _display_status_bar(self):
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
    
    def _display_commands(self):
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
            print("  c    - Copy prompt        t    - Show thinking")
            print("  e    - Export findings    v    - View findings")
            print("  q/end - Quit")
    
    
    def _display_thinking(self):
        """Display chain of thought reasoning for current test"""
        result = self.test_results[self.current_index]
        
        # Check if we have any thinking data
        has_thinking = False
        if result.all_thinking and any(thinking for thinking in result.all_thinking):
            has_thinking = True
        elif result.thinking:
            has_thinking = True
            
        if not has_thinking:
            if self.console:
                self.console.print("[yellow]⚠️  No chain of thought data available for this test[/yellow]")
            else:
                print("⚠️  No chain of thought data available for this test")
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
        
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            pass
    
    def _copy_prompt_to_clipboard(self):
        """Copy current test's raw prompts to clipboard"""
        import subprocess
        import platform
        
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
                        raise FileNotFoundError("Neither xclip nor xsel available")
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
            
            # Wait 3 seconds so user can see the success message before redraw
            import time
            time.sleep(3)
                
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
    
    def _save_flagged_finding(self, result: TestResult):
        """Automatically save a flagged result as a finding"""
        try:
            # Create grouped format for consistency
            import json
            from datetime import datetime
            from pathlib import Path
            
            findings_dir = Path("findings")
            findings_dir.mkdir(exist_ok=True)
            
            # Generate timestamp for unique filename
            timestamp = datetime.now()
            flagged_id = f"flagged_{result.test_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
            
            # Create finding data (preserves ALL data)
            finding_data = {
                "finding_index": 1,
                "finding_id": f"{result.test_id}_1",
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
            
            # Create grouped structure for single finding
            grouped_finding = {
                "export_id": flagged_id,
                "export_timestamp": timestamp.isoformat(),
                "exported_from": "cli_ui_flagging",
                "total_findings": 1,
                "session_summary": {
                    "categories": [result.category],
                    "category_counts": {result.category: 1},
                    "vulnerable_count": 1 if result.vulnerability_detected else 0,
                    "flagged_count": 1
                },
                "findings": [finding_data]
            }
            
            # Save grouped format
            flagged_filepath = findings_dir / f"{flagged_id}.json"
            with open(flagged_filepath, 'w') as f:
                json.dump(grouped_finding, f, indent=2)
            
            # Create competition format (for backward compatibility)
            try:
                from utils.findings_generator import FindingsGenerator
                from utils.evaluator import VulnerabilityCategory, VulnerabilityScore, EvaluationResult
                
                generator = FindingsGenerator()
                
                # Try to map to enum, fallback to INAPPROPRIATE_TOOL_USE
                try:
                    # Try common mappings
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
                    category = category_mapping.get(result.category.lower(), VulnerabilityCategory.INAPPROPRIATE_TOOL_USE)
                except:
                    category = VulnerabilityCategory.INAPPROPRIATE_TOOL_USE
                
                # Use default scores
                score = VulnerabilityScore(
                    severity=5, breadth=3, novelty=3, 
                    reproducibility=7, methodological_insight=4
                )
                
                evaluation = EvaluationResult(
                    is_vulnerable=result.vulnerability_detected,
                    category=category,
                    confidence=result.confidence,
                    evidence=result.evidence,
                    reasoning=result.reasoning
                )
                
                finding = generator.create_finding(
                    category=category,
                    title=f"{result.test_name} - Flagged Finding",
                    evaluation=evaluation,
                    score=score,
                    prompt=result.get_display_prompt(),
                    response=result.response,
                    methodology=f"Interactive CLI flagging of {result.test_id}",
                    reproduction_steps=[
                        f"Run test: {result.test_id}",
                        f"Use prompt: {result.get_display_prompt()[:100]}{'...' if len(result.get_display_prompt()) > 100 else ''}",
                        "Analyze response for evidence of vulnerability",
                        "Manual review confirmed this as a potential finding"
                    ]
                )
                
                if result.notes:
                    finding.additional_notes = result.notes
                
                # Save competition format
                comp_filepath = generator.save_finding(finding)
                
            except Exception as e:
                # Competition format failed, but full format succeeded
                if self.console:
                    self.console.print(f"[yellow]⚠️  Competition format failed ({e}), but full data saved[/yellow]")
                else:
                    print(f"⚠️  Competition format failed ({e}), but full data saved")
            
            return str(flagged_filepath)
            
        except Exception as e:
            if self.console:
                self.console.print(f"[red]⚠️  Could not auto-save finding: {e}[/red]")
            else:
                print(f"⚠️  Could not auto-save finding: {e}")
            return None

    def _export_findings(self):
        """Export flagged results as grouped findings"""
        flagged_results = [r for r in self.test_results if r.flagged]
        
        if not flagged_results:
            print("No flagged results to export.")
            return
        
        from pathlib import Path
        import json
        from datetime import datetime
        from collections import Counter
        
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
        
        # Still create competition format files for backward compatibility
        competition_files = []
        try:
            from utils.findings_generator import FindingsGenerator
            from utils.evaluator import VulnerabilityCategory, VulnerabilityScore, EvaluationResult
            
            generator = FindingsGenerator()
            
            for result in flagged_results:
                try:
                    # Try to map to enum, fallback to INAPPROPRIATE_TOOL_USE
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
                    category = category_mapping.get(result.category.lower(), VulnerabilityCategory.INAPPROPRIATE_TOOL_USE)
                    
                    # Use default scores for export since manual scoring is removed
                    score = VulnerabilityScore(
                        severity=5, breadth=3, novelty=3, 
                        reproducibility=7, methodological_insight=4
                    )
                    evaluation = EvaluationResult(
                        is_vulnerable=result.vulnerability_detected,
                        category=category,
                        confidence=result.confidence,
                        evidence=result.evidence,
                        reasoning=result.reasoning
                    )
                    
                    finding = generator.create_finding(
                        category=category,
                        title=result.test_name,
                        evaluation=evaluation,
                        score=score,
                        prompt=result.get_display_prompt(),
                        response=result.response,
                        methodology=f"Interactive CLI evaluation of {result.test_id}",
                        reproduction_steps=[
                            f"Run test: {result.test_id}",
                            f"Use prompt: {result.get_display_prompt()[:100]}{'...' if len(result.get_display_prompt()) > 100 else ''}",
                            "Analyze response for evidence of vulnerability"
                        ]
                    )
                    
                    if result.notes:
                        finding.additional_notes = result.notes
                    
                    comp_filepath = generator.save_finding(finding)
                    competition_files.append(comp_filepath)
                    
                except Exception as e:
                    # Competition format failed, but grouped format succeeded
                    continue
                    
        except ImportError:
            # FindingsGenerator not available, skip competition format
            pass
        
        print(f"\n📁 Export Summary:")
        print(f"   Grouped export: 1 file ({export_filepath.name})")
        print(f"   Competition files: {len(competition_files)} (background compatibility)")
        print(f"   All files saved to findings/ directory")
    
    def _view_findings(self):
        """Browse and view findings folder"""
        from pathlib import Path
        import json
        from datetime import datetime
        
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
        import json
        from pathlib import Path
        
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
    
    def _view_finding_file(self, filepath: Path):
        """View details of a specific finding file"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            if self.console:
                self.console.clear()
                self.console.print(Panel(f"📄 {filepath.name}", style="bold green"))
                
                # Display key information
                info_table = Table(show_header=False, header_style="bold magenta")
                info_table.add_column("Field", style="cyan")
                info_table.add_column("Value")
                
                info_table.add_row("Finding ID", data.get("finding_id", "Unknown"))
                info_table.add_row("Test ID", data.get("test_id", "Unknown"))
                info_table.add_row("Category", data.get("category", "Unknown"))
                info_table.add_row("Vulnerability", "✓ Detected" if data.get("vulnerability_detected") else "✗ Not detected")
                info_table.add_row("Confidence", f"{data.get('confidence', 0):.2f}")
                
                if data.get("notes"):
                    info_table.add_row("Notes", data["notes"])
                
                self.console.print(info_table)
                
                # Show prompt and response
                if data.get("prompt"):
                    self.console.print(Panel(data["prompt"], title="Prompt", style="yellow"))
                
                if data.get("response"):
                    response_text = data["response"][:500] + ("..." if len(data["response"]) > 500 else "")
                    self.console.print(Panel(response_text, title="Response", style="green"))
                
                self.console.print("\n[dim]Press Enter to return...[/dim]")
            else:
                # Text mode
                print("=" * 70)
                print(f"📄 {filepath.name}")
                print("=" * 70)
                print(f"Finding ID: {data.get('finding_id', 'Unknown')}")
                print(f"Test ID: {data.get('test_id', 'Unknown')}")
                print(f"Category: {data.get('category', 'Unknown')}")
                print(f"Vulnerability: {'✓ Detected' if data.get('vulnerability_detected') else '✗ Not detected'}")
                print(f"Confidence: {data.get('confidence', 0):.2f}")
                
                if data.get("notes"):
                    print(f"Notes: {data['notes']}")
                
                if data.get("prompt"):
                    print(f"\nPrompt:\n{data['prompt']}")
                
                if data.get("response"):
                    response_text = data["response"][:500] + ("..." if len(data["response"]) > 500 else "")
                    print(f"\nResponse:\n{response_text}")
                
                print("=" * 70)
                print("Press Enter to return...")
            
            input()  # Wait for user
            
        except Exception as e:
            if self.console:
                self.console.print(f"[red]Error reading file: {e}[/red]")
            else:
                print(f"Error reading file: {e}")
            input("Press Enter to continue...")
    
    def _open_findings_folder(self):
        """Open findings folder in system file manager"""
        import subprocess
        import platform
        from pathlib import Path
        
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
    
    def run(self):
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
                        self.console.print("💾 Auto-saving as finding...")
                    else:
                        print("🚩 Flagged as potential finding")
                        print("💾 Auto-saving as finding...")
                    
                    # Automatically save as finding
                    filepath = self._save_flagged_finding(result)
                    if filepath:
                        if self.console:
                            self.console.print(f"[green]✅ Saved finding: {filepath}[/green]")
                        else:
                            print(f"✅ Saved finding: {filepath}")
                    else:
                        if self.console:
                            self.console.print("[yellow]⚠️  Flagged but could not auto-save (you can export manually with 'e')[/yellow]")
                        else:
                            print("⚠️  Flagged but could not auto-save (you can export manually with 'e')")
                    
                    # Save updated results to JSON
                    self._save_updated_results()
                elif command == 'u':
                    result.flagged = False
                    if self.console:
                        self.console.print("🔄 Unflagged")
                        self.console.print("[dim]Note: Auto-saved finding (if any) remains in findings/ directory[/dim]")
                    else:
                        print("🔄 Unflagged")
                        print("Note: Auto-saved finding (if any) remains in findings/ directory")
                    
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


def launch_cli_ui(results_file: str):
    """Launch the CLI UI for result evaluation"""
    if not Path(results_file).exists():
        print(f"Error: Results file not found: {results_file}")
        return
    
    try:
        evaluator = CLIEvaluator(results_file)
        evaluator.run()
    except Exception as e:
        print(f"Error launching CLI UI: {e}")


def launch_findings_browser():
    """Launch findings browser directly without test results"""
    import tempfile
    import json
    
    try:
        # Create a temporary dummy results file to instantiate CLIEvaluator
        dummy_data = {"dummy_category": {"test_details": []}}
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            json.dump(dummy_data, temp_file)
            temp_filename = temp_file.name
        
        try:
            # Create CLIEvaluator with the temporary file
            evaluator = CLIEvaluator(temp_filename)
            evaluator._view_findings()
        finally:
            # Clean up the temporary file
            import os
            try:
                os.unlink(temp_filename)
            except:
                pass
                
    except Exception as e:
        print(f"Error launching findings browser: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python cli_ui.py <results_file.json>")
        sys.exit(1)
    
    launch_cli_ui(sys.argv[1])
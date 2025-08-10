"""
Live display utilities for real-time test progress and results
"""
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.syntax import Syntax
    from rich.text import Text
    from rich.progress import Progress, TextColumn, BarColumn, TimeElapsedColumn
    from rich.table import Table
    from rich.live import Live
    from rich.layout import Layout
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from .evaluator import EvaluationResult
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
    
    def __init__(self, enable_live: bool = True, quiet_mode: bool = False, verbose: bool = False):
        self.enable_live = enable_live
        self.quiet_mode = quiet_mode
        self.verbose = verbose
        
        if RICH_AVAILABLE:
            self.console = Console()
        else:
            self.console = None
            # Fall back to basic print if Rich not available
            if enable_live and not quiet_mode:
                print("Note: Install 'rich' for enhanced live display")
    
    def start_category(self, category: str, total_tests: int) -> None:
        """Display category start information"""
        if self.quiet_mode:
            print(f"🔍 Testing {category} category... [0/{total_tests}]", end=" ", flush=True)
            return
        
        if self.console:
            title = f"🔍 Testing Category: {category.upper()}"
            subtitle = f"Total tests: {total_tests}"
            panel = Panel(
                Text(subtitle, style="cyan"),
                title=title,
                title_align="left",
                style="blue"
            )
            self.console.print(panel)
            self.console.print()
        else:
            print(f"\n🔍 Testing category: {category}")
            print(f"Total tests: {total_tests}")
            print("=" * 50)
    
    def start_test(self, test_name: str, test_id: str, category: str, 
                   current_num: int, total_tests: int) -> TestProgress:
        """Start displaying a test"""
        progress = TestProgress(
            test_name=test_name,
            test_id=test_id,
            category=category,
            start_time=time.time(),
            current_test_num=current_num,
            total_tests=total_tests
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
    
    def show_prompt(self, progress: TestProgress, prompt: str, system_prompt: str = "") -> None:
        """Display the prompt being sent"""
        if self.quiet_mode:
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
                padding=(1, 2)
            )
            self.console.print(prompt_panel)
            
            # System prompt if present
            if system_prompt:
                system_panel = Panel(
                    Text(system_prompt, style="italic cyan"),
                    title="⚙️  SYSTEM PROMPT",
                    title_align="left", 
                    style="cyan",
                    padding=(0, 2)
                )
                self.console.print(system_panel)
                
        else:
            print(f"\n📝 PROMPT:")
            print(f"   {prompt}")
            if system_prompt:
                print(f"\n⚙️  SYSTEM PROMPT:")
                print(f"   {system_prompt}")
    
    def show_thinking(self, progress: TestProgress) -> None:
        """Show that model is thinking"""
        if self.quiet_mode:
            return
        
        elapsed = time.time() - progress.start_time
        thinking_msg = f"⏱️  Waiting for response... [{elapsed:.1f}s]"
        
        if self.console:
            self.console.print(thinking_msg, style="dim")
        else:
            print(thinking_msg)
    
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
            response_panel = Panel(
                Text(response_content, style="white"),
                title="🤖 RESPONSE",
                title_align="left",
                style="green",
                padding=(1, 2)
            )
            self.console.print(response_panel)
            
            # Show timing and token info
            timing_info = f"⏱️  Response time: {response.response_time:.2f}s"
            if response.total_tokens > 0:
                timing_info += f" | Tokens: {response.total_tokens}"
            self.console.print(timing_info, style="dim")
            
        else:
            print(f"\n🤖 RESPONSE:")
            print(f"   {response_content}")
            print(f"⏱️  Response time: {response.response_time:.2f}s")
    
    def show_evaluation(self, progress: TestProgress, evaluation: EvaluationResult) -> None:
        """Display evaluation results"""
        if self.quiet_mode:
            return
        
        progress.current_step = "Evaluation complete"
        progress.evaluation_done = True
        
        # Vulnerability status
        vuln_status = "🔴 YES" if evaluation.is_vulnerable else "🟢 NO"
        confidence = f"{evaluation.confidence:.2f}"
        
        if self.console:
            # Create evaluation table
            eval_table = Table(show_header=False, box=None, padding=(0, 1))
            eval_table.add_column("Field", style="cyan bold")
            eval_table.add_column("Value")
            
            eval_table.add_row("Vulnerable:", vuln_status)
            eval_table.add_row("Confidence:", confidence)
            
            if evaluation.evidence:
                evidence_text = "\n".join(f"• {e}" for e in evaluation.evidence)
                eval_table.add_row("Evidence:", evidence_text)
            
            if evaluation.reasoning:
                eval_table.add_row("Reasoning:", evaluation.reasoning)
            
            eval_panel = Panel(
                eval_table,
                title="🔍 EVALUATION",
                title_align="left",
                style="blue",
                padding=(1, 2)
            )
            self.console.print(eval_panel)
            
        else:
            print(f"\n🔍 EVALUATION:")
            print(f"   Vulnerable: {vuln_status}")
            print(f"   Confidence: {confidence}")
            
            if evaluation.evidence:
                print(f"   Evidence:")
                for evidence in evaluation.evidence:
                    print(f"     • {evidence}")
            
            if evaluation.reasoning:
                print(f"   Reasoning: {evaluation.reasoning}")
    
    def complete_test(self, progress: TestProgress, evaluation: EvaluationResult) -> None:
        """Mark test as complete"""
        total_time = time.time() - progress.start_time
        status = "vulnerable" if evaluation.is_vulnerable else "safe"
        
        if self.quiet_mode:
            # Update the progress line
            print(f"✓ {progress.test_name} ({total_time:.1f}s, {status})", end=" ", flush=True)
            if progress.current_test_num % 5 == 0 or progress.current_test_num == progress.total_tests:
                print()  # New line every 5 tests or at the end
            return
        
        completion_msg = f"✅ Test completed in {total_time:.1f}s"
        if evaluation.is_vulnerable:
            completion_msg += f" | 🔴 VULNERABILITY DETECTED (confidence: {evaluation.confidence:.2f})"
        else:
            completion_msg += f" | 🟢 No vulnerability detected"
        
        if self.console:
            self.console.print(completion_msg, style="bold green")
        else:
            print(f"\n{completion_msg}")
    
    def complete_category(self, category: str, summary: Dict[str, Any]) -> None:
        """Display category completion summary"""
        if self.quiet_mode:
            print(f"\n✅ {category} category complete: {summary.get('vulnerable_tests', 0)}/{summary.get('total_tests', 0)} vulnerable")
            return
        
        if self.console:
            # Create summary table
            summary_table = Table(title=f"📊 {category.upper()} CATEGORY RESULTS", show_header=True)
            summary_table.add_column("Metric", style="cyan")
            summary_table.add_column("Value", style="white")
            
            summary_table.add_row("Total Tests", str(summary.get('total_tests', 0)))
            summary_table.add_row("Vulnerabilities Found", str(summary.get('vulnerable_tests', 0)))
            summary_table.add_row("High Confidence", str(summary.get('high_confidence_vulnerabilities', 0)))
            summary_table.add_row("Average Confidence", f"{summary.get('average_confidence', 0):.2f}")
            
            self.console.print()
            self.console.print(summary_table)
            
            # Show category breakdown if available
            if 'category_breakdown' in summary:
                breakdown_text = []
                for cat, stats in summary['category_breakdown'].items():
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


# Global instance that can be imported
_display_instance = None

def get_display() -> LiveDisplay:
    """Get the global display instance"""
    global _display_instance
    if _display_instance is None:
        _display_instance = LiveDisplay()
    return _display_instance

def set_display_options(enable_live: bool = True, quiet_mode: bool = False, verbose: bool = False) -> None:
    """Configure the global display instance"""
    global _display_instance
    _display_instance = LiveDisplay(enable_live=enable_live, quiet_mode=quiet_mode, verbose=verbose)
"""Session management utilities for interactive red team testing."""

import json
from datetime import datetime
from pathlib import Path

from src.models import InteractiveSession, TrialsAndLessons


class SessionManager:
    """Manages loading, saving, and organizing red team sessions."""

    def __init__(self, base_dir: Path | str = "sessions") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.lessons_dir = self.base_dir / "lessons"
        self.lessons_dir.mkdir(parents=True, exist_ok=True)

    def save_session(self, session: InteractiveSession) -> Path:
        """Save a session to disk."""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = self.base_dir / f"{timestamp}_{session.session_id[:8]}.json"

        with open(filename, "w") as f:
            json.dump(session.model_dump(), f, indent=2)

        return filename

    def load_session(self, session_file: Path | str) -> InteractiveSession:
        """Load a session from disk."""
        with open(session_file) as f:
            data = json.load(f)
        return InteractiveSession.model_validate(data)

    def list_sessions(self) -> list[dict[str, str]]:
        """List all available sessions."""
        sessions = []
        for file in sorted(self.base_dir.glob("*.json"), reverse=True):
            if file.stem.startswith("20"):  # Date-based files only
                try:
                    with open(file) as f:
                        data = json.load(f)
                    sessions.append(
                        {
                            "file": str(file),
                            "session_id": data.get("session_id", "unknown")[:8],
                            "start_time": data.get("start_time", "unknown"),
                            "end_time": data.get("end_time", "unknown"),
                            "total_attempts": data.get("total_attempts", 0),
                            "successful_attempts": data.get("successful_attempts", 0),
                            "target_model": data.get("target_model", "unknown"),
                        }
                    )
                except (json.JSONDecodeError, KeyError):
                    continue
        return sessions

    def load_lessons(self, model_name: str) -> TrialsAndLessons | None:
        """Load aggregated lessons for a specific model."""
        model_name = model_name.replace("/", "_")
        lessons_file = self.lessons_dir / f"{model_name}_lessons.json"

        if lessons_file.exists():
            with open(lessons_file) as f:
                data = json.load(f)
            return TrialsAndLessons.model_validate(data)
        return None

    def save_lessons(self, trials: TrialsAndLessons) -> Path:
        """Save aggregated lessons."""
        model_name = trials.model_name.replace("/", "_")
        lessons_file = self.lessons_dir / f"{model_name}_lessons.json"

        with open(lessons_file, "w") as f:
            json.dump(trials.model_dump(), f, indent=2)

        return lessons_file

    def get_recent_sessions(self, n: int) -> list[InteractiveSession]:
        """Get the most recent N sessions."""
        if n <= 0:
            return []

        sessions = []
        session_files = sorted(self.base_dir.glob("*.json"), reverse=True)

        for file in session_files[:n]:
            if file.stem.startswith("20"):  # Date-based files only
                try:
                    session = self.load_session(file)
                    sessions.append(session)
                except Exception:
                    continue  # Skip corrupted files

        return sessions

    def extract_successful_patterns(self, sessions: list[InteractiveSession]) -> dict:
        """Extract patterns from successful attacks across sessions."""
        patterns = {
            "successful_strategies": {},
            "successful_prompts": [],
            "conversation_patterns": [],
            "common_success_indicators": [],
            "total_attempts": 0,
            "successful_attempts": 0,
        }

        for session in sessions:
            for attempt in session.attempts:
                patterns["total_attempts"] += 1

                if attempt.success:
                    patterns["successful_attempts"] += 1

                    # Track successful strategies
                    strategy = attempt.strategy.value
                    if strategy not in patterns["successful_strategies"]:
                        patterns["successful_strategies"][strategy] = 0
                    patterns["successful_strategies"][strategy] += 1

                    # Extract successful conversation patterns
                    if attempt.turns:
                        conversation = []
                        for turn in attempt.turns:
                            if turn.role == "attacker":
                                conversation.append(f"USER: {turn.content[:200]}...")
                            else:
                                conversation.append(f"ASSISTANT: {turn.content[:200]}...")
                        patterns["conversation_patterns"].append(
                            {"strategy": strategy, "turns": conversation, "success": True}
                        )

                        # Store successful prompts (attacker turns only)
                        for turn in attempt.turns:
                            if turn.role == "attacker":
                                patterns["successful_prompts"].append(
                                    {
                                        "strategy": strategy,
                                        "content": turn.content,
                                        "turn_number": turn.turn_number,
                                        "is_exploit": turn.is_exploit_turn,
                                    }
                                )

        return patterns

    def get_statistics(self) -> dict:
        """Get overall statistics across all sessions."""
        stats = {
            "total_sessions": 0,
            "total_attempts": 0,
            "successful_attempts": 0,
            "models_tested": set(),
            "strategies_used": {},
            "success_rate": 0.0,
        }

        for session_info in self.list_sessions():
            stats["total_sessions"] += 1
            stats["total_attempts"] += session_info["total_attempts"]
            stats["successful_attempts"] += session_info["successful_attempts"]
            stats["models_tested"].add(session_info["target_model"])

            # Load session for detailed strategy stats
            try:
                session = self.load_session(session_info["file"])
                for attempt in session.attempts:
                    strategy = attempt.strategy.value
                    if strategy not in stats["strategies_used"]:
                        stats["strategies_used"][strategy] = {"total": 0, "success": 0}
                    stats["strategies_used"][strategy]["total"] += 1
                    if attempt.success:
                        stats["strategies_used"][strategy]["success"] += 1
            except Exception:
                continue

        # Convert set to list for JSON serialization
        stats["models_tested"] = list(stats["models_tested"])

        # Calculate overall success rate
        if stats["total_attempts"] > 0:
            stats["success_rate"] = stats["successful_attempts"] / stats["total_attempts"]

        return stats

    def export_session_report(
        self, session: InteractiveSession, output_file: Path | None = None
    ) -> Path:
        """Export a human-readable session report."""
        if output_file is None:
            reports_dir = self.base_dir / "reports"
            reports_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            output_file = reports_dir / f"report_{timestamp}.md"

        with open(output_file, "w") as f:
            f.write("# Red Team Session Report\n\n")
            f.write(f"**Session ID:** {session.session_id[:8]}\n")
            f.write(f"**Start Time:** {session.start_time}\n")
            f.write(f"**End Time:** {session.end_time or 'In Progress'}\n\n")

            f.write("## Configuration\n\n")
            f.write(f"- **Target Model:** {session.target_model}\n")
            f.write(f"- **Attacker Model:** {session.attacker_model}\n")
            f.write(f"- **Evaluator Model:** {session.evaluator_model}\n\n")

            f.write("## Summary\n\n")
            f.write(f"- **Total Attempts:** {session.total_attempts}\n")
            f.write(f"- **Successful Attacks:** {session.successful_attempts}\n")
            success_rate = (
                session.successful_attempts / session.total_attempts
                if session.total_attempts > 0
                else 0
            )
            f.write(f"- **Success Rate:** {success_rate:.1%}\n\n")

            f.write("## Attack Details\n\n")
            for i, attempt in enumerate(session.attempts, 1):
                f.write(f"### Attempt {i}: {attempt.strategy.value}\n\n")
                f.write(f"**Steps:** {attempt.steps} | ")
                f.write(f"**Success:** {'✅' if attempt.success else '❌'}\n\n")

                # Show conversation
                f.write("**Conversation:**\n\n")
                for turn in attempt.turns:
                    role = "🔴 Attacker" if turn.role == "attacker" else "🔵 Target"
                    f.write(f"{role} (Turn {turn.turn_number})")
                    if turn.is_exploit_turn:
                        f.write(" [EXPLOIT TURN]")
                    f.write(f":\n```\n{turn.content[:500]}")
                    if len(turn.content) > 500:
                        f.write("... [truncated]")
                    f.write("\n```\n\n")

                # Show evaluation
                if attempt.evaluation:
                    f.write("**Evaluation:**\n")
                    f.write(f"- Vulnerable: {attempt.evaluation.is_vulnerable}\n")
                    f.write(f"- Confidence: {attempt.evaluation.confidence:.1%}\n")
                    f.write(f"- Reasoning: {attempt.evaluation.reasoning}\n")
                    if attempt.evaluation.evidence:
                        f.write(f"- Evidence: {', '.join(attempt.evaluation.evidence[:3])}\n")
                    f.write("\n---\n\n")

            # Lessons learned
            if session.lessons_learned:
                f.write("## Lessons Learned\n\n")
                for lesson in session.lessons_learned:
                    f.write(f"### {lesson.strategy.value}\n\n")
                    f.write(f"- **Success Rate:** {lesson.success_rate:.1%} ")
                    f.write(f"({lesson.successful_attempts}/{lesson.total_attempts})\n")
                    if lesson.key_insights:
                        f.write(f"- **Key Insights:** {', '.join(lesson.key_insights)}\n")
                    f.write("\n")

        return output_file

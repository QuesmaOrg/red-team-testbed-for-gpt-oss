"""Pydantic models for the Red Team Testbed."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class VulnerabilityCategory(str, Enum):
    """Categories of vulnerabilities to test for."""

    REWARD_HACKING = "reward_hacking"
    DECEPTION = "deception"
    HIDDEN_MOTIVATIONS = "hidden_motivations"
    SABOTAGE = "sabotage"
    INAPPROPRIATE_TOOL_USE = "inappropriate_tool_use"
    DATA_EXFILTRATION = "data_exfiltration"
    SANDBAGGING = "sandbagging"
    EVALUATION_AWARENESS = "evaluation_awareness"
    CHAIN_OF_THOUGHT = "chain_of_thought"
    EXPLOIT = "exploit"


class ModelResponse(BaseModel):
    """Container for model response data."""

    model_config = ConfigDict(frozen=False)

    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    response_time: float = 0.0
    error: str | None = None
    timed_out: bool = False
    thinking: str | None = None
    
    # Competition format context
    system_prompt: str | None = None  # What we call system_prompt (becomes developer in Harmony)
    user_prompt: str | None = None  # Store the actual user prompt for context
    model_config_dict: dict[str, Any] | None = None  # Model configuration for competition format


class OllamaStatus(BaseModel):
    """Container for Ollama busy status information."""

    model_config = ConfigDict(frozen=False)

    is_busy: bool
    gpu_usage: str
    memory_usage: str
    model_loaded: bool
    raw_output: str


class VulnerabilityScore(BaseModel):
    """Competition scoring for a vulnerability."""

    model_config = ConfigDict(frozen=False)

    severity: int = Field(ge=0, le=10)
    breadth: int = Field(ge=0, le=10)
    novelty: int = Field(ge=0, le=10)
    reproducibility: int = Field(ge=0, le=10)
    methodological_insight: int = Field(ge=0, le=10)

    @property
    def total_score(self) -> int:
        """Calculate total score."""
        return (
            self.severity
            + self.breadth
            + self.novelty
            + self.reproducibility
            + self.methodological_insight
        )

    def is_valid(self) -> bool:
        """Check if all scores are at least Level 1."""
        return all(
            score >= 1
            for score in [
                self.severity,
                self.breadth,
                self.novelty,
                self.reproducibility,
                self.methodological_insight,
            ]
        )


class EvaluationResult(BaseModel):
    """Result of evaluating a model response."""

    model_config = ConfigDict(frozen=False)

    is_vulnerable: bool
    category: VulnerabilityCategory
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str]
    reasoning: str
    score: VulnerabilityScore | None = None
    flags: list[str] = Field(default_factory=list)


class TestConfig(BaseModel):
    """Configuration for test execution."""

    model_config = ConfigDict(frozen=False)

    model_name: str = "gpt-oss:20b"
    host: str = "localhost"
    port: int = 11434
    timeout: int = 60
    max_retries: int = 3
    categories: list[str] = Field(default_factory=list)


class Finding(BaseModel):
    """Represents a security finding."""

    model_config = ConfigDict(frozen=False)

    id: str
    category: VulnerabilityCategory
    prompt: str
    response: str
    evaluation: EvaluationResult
    timestamp: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AttackStrategy(str, Enum):
    """Different strategies for exploit attempts."""

    TRUST_BUILDING = "trust_building"
    AUTHORITY_APPEAL = "authority_appeal"
    URGENCY_PRESSURE = "urgency_pressure"
    TECHNICAL_CONFUSION = "technical_confusion"
    SIDE_TASK = "side_task"
    COMPLIANCE_REQUIREMENT = "compliance_requirement"
    HELPFUL_ASSISTANT = "helpful_assistant"
    ERROR_RECOVERY = "error_recovery"


class AttackTurn(BaseModel):
    """Single interaction in an attack sequence."""

    model_config = ConfigDict(frozen=False)

    turn_number: int
    role: str  # "attacker" or "target"
    content: str
    timestamp: str
    is_exploit_turn: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class AttackAttempt(BaseModel):
    """Complete multi-turn attack sequence."""

    model_config = ConfigDict(frozen=False)

    attempt_id: str
    strategy: AttackStrategy
    steps: int  # Number of turns planned
    turns: list[AttackTurn]
    success: bool | None = None
    evaluation: EvaluationResult | None = None
    timestamp: str


class LearningLesson(BaseModel):
    """Lesson learned from attack attempts."""

    model_config = ConfigDict(frozen=False)

    lesson_id: str
    strategy: AttackStrategy
    pattern: str  # What specific pattern was tried
    success_rate: float
    total_attempts: int
    successful_attempts: int
    key_insights: list[str]
    example_prompts: list[str]
    timestamp: str
    model_specific: str  # Which model this lesson applies to


class InteractiveSession(BaseModel):
    """Complete interactive red team session."""

    model_config = ConfigDict(frozen=False)

    session_id: str
    start_time: str
    end_time: str | None = None
    attacker_model: str
    evaluator_model: str
    target_model: str
    attempts: list[AttackAttempt]
    lessons_learned: list[LearningLesson]
    total_attempts: int = 0
    successful_attempts: int = 0
    configuration: dict[str, Any] = Field(default_factory=dict)


class TrialsAndLessons(BaseModel):
    """Aggregated learning across sessions for a specific model."""

    model_config = ConfigDict(frozen=False)

    model_name: str  # The attacker model this applies to
    total_sessions: int
    total_attempts: int
    strategies: dict[str, float]  # Strategy -> success rate
    lessons: list[LearningLesson]
    best_patterns: list[str]
    failed_patterns: list[str]
    last_updated: str

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
        return self.severity + self.breadth + self.novelty + self.reproducibility + self.methodological_insight
    
    def is_valid(self) -> bool:
        """Check if all scores are at least Level 1."""
        return all(
            score >= 1 
            for score in [
                self.severity, 
                self.breadth, 
                self.novelty,
                self.reproducibility, 
                self.methodological_insight
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
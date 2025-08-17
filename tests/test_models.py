"""
Comprehensive unit tests for Pydantic models.
Tests data validation, serialization, and edge cases.
"""


import pytest
from pydantic import ValidationError
from src.categories.base import BaseTest
from src.models import (
    EvaluationResult,
    Finding,
    ModelResponse,
    OllamaStatus,
    VulnerabilityCategory,
    VulnerabilityScore,
)
from src.ui.cli_ui import TestResult


class TestModelResponse:
    """Test ModelResponse Pydantic model"""

    def test_valid_model_response(self) -> None:
        """Test creating a valid ModelResponse"""
        response = ModelResponse(
            content="Test content",
            model="gpt-oss:20b",
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
            response_time=1.5,
            error=None,
            timed_out=False,
            thinking="Internal thoughts"
        )
        
        assert response.content == "Test content"
        assert response.model == "gpt-oss:20b"
        assert response.prompt_tokens == 10
        assert response.completion_tokens == 20
        assert response.total_tokens == 30
        assert response.response_time == 1.5
        assert response.error is None
        assert response.timed_out is False
        assert response.thinking == "Internal thoughts"

    def test_model_response_defaults(self) -> None:
        """Test ModelResponse with default values"""
        response = ModelResponse(
            content="Test",
            model="test-model",
            prompt_tokens=5,
            completion_tokens=10,
            total_tokens=15,
            response_time=1.0
        )
        
        assert response.error is None
        assert response.timed_out is False
        assert response.thinking is None

    def test_model_response_with_error(self) -> None:
        """Test ModelResponse with error state"""
        response = ModelResponse(
            content="",
            model="test-model",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            response_time=60.0,
            error="Connection timeout",
            timed_out=True
        )
        
        assert response.error == "Connection timeout"
        assert response.timed_out is True
        assert response.content == ""

    def test_model_response_serialization(self) -> None:
        """Test ModelResponse serialization to dict"""
        response = ModelResponse(
            content="Test",
            model="test-model",
            prompt_tokens=5,
            completion_tokens=10,
            total_tokens=15,
            response_time=1.0
        )
        
        data = response.model_dump()
        assert data["content"] == "Test"
        assert data["model"] == "test-model"
        assert data["prompt_tokens"] == 5
        assert data["completion_tokens"] == 10
        assert data["total_tokens"] == 15
        assert data["response_time"] == 1.0
        assert data["error"] is None
        assert data["timed_out"] is False
        assert data["thinking"] is None


class TestVulnerabilityCategory:
    """Test VulnerabilityCategory enum"""

    def test_vulnerability_categories_exist(self) -> None:
        """Test that all expected categories exist"""
        expected_categories = [
            "DECEPTION",
            "REWARD_HACKING",
            "HIDDEN_MOTIVATIONS",
            "SABOTAGE",
            "INAPPROPRIATE_TOOL_USE",
            "DATA_EXFILTRATION",
            "SANDBAGGING",
            "EVALUATION_AWARENESS",
            "CHAIN_OF_THOUGHT",
            "EXPLOIT",
        ]
        
        for category_name in expected_categories:
            assert hasattr(VulnerabilityCategory, category_name)
            category = getattr(VulnerabilityCategory, category_name)
            assert category.value == category_name.lower()

    def test_vulnerability_category_values(self) -> None:
        """Test enum values"""
        assert VulnerabilityCategory.DECEPTION.value == "deception"
        assert VulnerabilityCategory.EXPLOIT.value == "exploit"
        assert VulnerabilityCategory.REWARD_HACKING.value == "reward_hacking"


class TestVulnerabilityScore:
    """Test VulnerabilityScore model"""

    def test_valid_vulnerability_score(self) -> None:
        """Test creating a valid VulnerabilityScore"""
        score = VulnerabilityScore(
            severity=7,
            breadth=5,
            novelty=6,
            reproducibility=8,
            methodological_insight=4
        )
        
        assert score.severity == 7
        assert score.breadth == 5
        assert score.novelty == 6
        assert score.reproducibility == 8
        assert score.methodological_insight == 4

    def test_vulnerability_score_validation(self) -> None:
        """Test VulnerabilityScore validation"""
        # Test with invalid score (> 10)
        with pytest.raises(ValidationError) as exc_info:
            VulnerabilityScore(
                severity=11,
                breadth=5,
                novelty=6,
                reproducibility=8,
                methodological_insight=4
            )
        assert "less than or equal to 10" in str(exc_info.value).lower()

        # Test with invalid score (< 0)
        with pytest.raises(ValidationError) as exc_info:
            VulnerabilityScore(
                severity=-1,
                breadth=5,
                novelty=6,
                reproducibility=8,
                methodological_insight=4
            )
        assert "greater than or equal to 0" in str(exc_info.value).lower()

    def test_vulnerability_score_edge_values(self) -> None:
        """Test boundary values for VulnerabilityScore"""
        # Test minimum values
        min_score = VulnerabilityScore(
            severity=0,
            breadth=0,
            novelty=0,
            reproducibility=0,
            methodological_insight=0
        )
        assert all(v == 0 for v in min_score.model_dump().values())

        # Test maximum values
        max_score = VulnerabilityScore(
            severity=10,
            breadth=10,
            novelty=10,
            reproducibility=10,
            methodological_insight=10
        )
        assert all(v == 10 for v in max_score.model_dump().values())


class TestEvaluationResult:
    """Test EvaluationResult model"""

    def test_valid_evaluation_result(self) -> None:
        """Test creating a valid EvaluationResult"""
        result = EvaluationResult(
            is_vulnerable=True,
            category=VulnerabilityCategory.DECEPTION,
            confidence=0.75,
            evidence=["Evidence 1", "Evidence 2"],
            reasoning="Detected deceptive behavior",
            score=VulnerabilityScore(
                severity=5, breadth=3, novelty=4, reproducibility=7, methodological_insight=2
            ),
            flags=["FLAG1", "FLAG2"]
        )
        
        assert result.is_vulnerable is True
        assert result.category == VulnerabilityCategory.DECEPTION
        assert result.confidence == 0.75
        assert len(result.evidence) == 2
        assert result.reasoning == "Detected deceptive behavior"
        assert result.score.severity == 5
        assert result.flags == ["FLAG1", "FLAG2"]

    def test_evaluation_result_defaults(self) -> None:
        """Test EvaluationResult with default values"""
        result = EvaluationResult(
            is_vulnerable=False,
            category=VulnerabilityCategory.EXPLOIT,
            confidence=0.0,
            evidence=[],
            reasoning="No vulnerability detected"
        )
        
        assert result.score is None
        assert result.flags == []

    def test_evaluation_result_confidence_validation(self) -> None:
        """Test confidence value validation"""
        # Test confidence > 1.0
        with pytest.raises(ValidationError) as exc_info:
            EvaluationResult(
                is_vulnerable=True,
                category=VulnerabilityCategory.DECEPTION,
                confidence=1.5,
                evidence=[],
                reasoning="Test"
            )
        assert "less than or equal to 1" in str(exc_info.value).lower()

        # Test confidence < 0.0
        with pytest.raises(ValidationError) as exc_info:
            EvaluationResult(
                is_vulnerable=True,
                category=VulnerabilityCategory.DECEPTION,
                confidence=-0.1,
                evidence=[],
                reasoning="Test"
            )
        assert "greater than or equal to 0" in str(exc_info.value).lower()


class TestOllamaStatus:
    """Test OllamaStatus model"""

    def test_valid_ollama_status(self) -> None:
        """Test creating a valid OllamaStatus"""
        status = OllamaStatus(
            is_busy=False,
            gpu_usage="45%",
            memory_usage="8.2 GB",
            model_loaded=True,
            raw_output="GPU 0: 45% | Memory: 8.2 GB | Model: gpt-oss:20b"
        )
        
        assert status.is_busy is False
        assert status.gpu_usage == "45%"
        assert status.memory_usage == "8.2 GB"
        assert status.model_loaded is True
        assert "GPU 0: 45%" in status.raw_output

    def test_ollama_status_defaults(self) -> None:
        """Test OllamaStatus with default values"""
        status = OllamaStatus(
            is_busy=True,
            gpu_usage="90%",
            memory_usage="15 GB",
            model_loaded=True,
            raw_output=""  # raw_output is required, not optional
        )
        
        assert status.raw_output == ""


class TestBaseTest:
    """Test BaseTest model"""

    def test_valid_base_test(self) -> None:
        """Test creating a valid BaseTest"""
        test = BaseTest(
            test_id="test_001",
            name="Test Case",
            prompt="Test prompt",
            system_prompt="System prompt",
            category="test_category",
            difficulty="medium",
            expected_vulnerability=True,
            description="Test description",
            multi_turn=False,
            follow_up_prompts=["Follow-up 1"],
            conversation_turns=[
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi"}
            ],
            metadata={"key": "value"}
        )
        
        assert test.test_id == "test_001"
        assert test.name == "Test Case"
        assert test.prompt == "Test prompt"
        assert test.system_prompt == "System prompt"
        assert test.category == "test_category"
        assert test.difficulty == "medium"
        assert test.expected_vulnerability is True
        assert test.description == "Test description"
        assert test.multi_turn is False
        assert len(test.follow_up_prompts) == 1
        assert len(test.conversation_turns) == 2
        assert test.metadata["key"] == "value"

    def test_base_test_defaults(self) -> None:
        """Test BaseTest with default values"""
        test = BaseTest(
            test_id="test_001",
            name="Test",
            prompt="Prompt",
            category="category",
            expected_vulnerability=False
        )
        
        assert test.system_prompt == ""  # Empty string, not None
        assert test.difficulty == "medium"
        assert test.description == ""  # Empty string, not None
        assert test.multi_turn is False
        assert test.follow_up_prompts is None
        assert test.conversation_turns is None
        assert test.metadata == {}

    def test_base_test_difficulty_validation(self) -> None:
        """Test difficulty field validation"""
        # Valid difficulties
        for difficulty in ["easy", "medium", "hard"]:
            test = BaseTest(
                test_id="test",
                name="Test",
                prompt="Prompt",
                category="category",
                difficulty=difficulty,
                expected_vulnerability=False
            )
            assert test.difficulty == difficulty

        # Invalid difficulty - BaseTest doesn't validate difficulty values
        # So this test should pass with any string value
        test = BaseTest(
            test_id="test",
            name="Test",
            prompt="Prompt",
            category="category",
            difficulty="extreme",  # This is allowed
            expected_vulnerability=False
        )
        assert test.difficulty == "extreme"


class TestTestResult:
    """Test TestResult model"""

    def test_valid_test_result(self) -> None:
        """Test creating a valid TestResult"""
        # TestResult from cli_ui.py is a dataclass with different fields
        result = TestResult(
            test_id="test_001",
            test_name="Test",
            category="category",
            prompt="Test prompt",
            conversation_turns=None,
            response="Response text",
            vulnerability_detected=True,
            confidence=0.8,
            evidence=["Evidence"],
            reasoning="Reasoning"
        )
        
        assert result.test_id == "test_001"
        assert result.test_name == "Test"
        assert result.category == "category"
        assert result.vulnerability_detected is True
        assert result.confidence == 0.8
        assert result.response == "Response text"
        assert result.evidence == ["Evidence"]
        assert result.reasoning == "Reasoning"

    def test_test_result_defaults(self) -> None:
        """Test TestResult with minimal required values"""
        # TestResult from cli_ui.py requires all fields
        result = TestResult(
            test_id="test_001",
            test_name="Test",
            category="category",
            prompt="Test prompt",
            conversation_turns=None,
            response="",
            vulnerability_detected=False,
            confidence=0.0,
            evidence=[],
            reasoning="No vulnerability"
        )
        
        assert result.vulnerability_detected is False
        assert result.confidence == 0.0
        assert result.evidence == []


class TestFinding:
    """Test Finding model"""

    def test_valid_finding(self) -> None:
        """Test creating a valid Finding"""
        # Finding model from src/models.py has different fields
        evaluation = EvaluationResult(
            is_vulnerable=True,
            category=VulnerabilityCategory.EXPLOIT,
            confidence=0.9,
            evidence=["Evidence 1", "Evidence 2"],
            reasoning="Detailed reasoning"
        )
        
        finding = Finding(
            id="test_001",
            category=VulnerabilityCategory.EXPLOIT,
            prompt="Test prompt",
            response="Test response",
            evaluation=evaluation,
            timestamp="2024-01-15T10:30:00",
            metadata={"extra": "data"}
        )
        
        assert finding.id == "test_001"
        assert finding.category == VulnerabilityCategory.EXPLOIT
        assert finding.prompt == "Test prompt"
        assert finding.response == "Test response"
        assert finding.evaluation.confidence == 0.9
        assert len(finding.evaluation.evidence) == 2
        assert finding.evaluation.reasoning == "Detailed reasoning"
        assert finding.timestamp == "2024-01-15T10:30:00"
        assert finding.metadata["extra"] == "data"

    def test_finding_defaults(self) -> None:
        """Test Finding with default values"""
        evaluation = EvaluationResult(
            is_vulnerable=False,
            category=VulnerabilityCategory.DECEPTION,
            confidence=0.5,
            evidence=[],
            reasoning="Reasoning"
        )
        
        finding = Finding(
            id="test_001",
            category=VulnerabilityCategory.DECEPTION,
            prompt="Prompt",
            response="Response",
            evaluation=evaluation,
            timestamp="2024-01-15T10:30:00"
        )
        
        assert finding.metadata == {}  # Default is empty dict, not None




class TestModelSerialization:
    """Test model serialization and deserialization"""

    def test_round_trip_serialization(self) -> None:
        """Test that models can be serialized and deserialized"""
        original = VulnerabilityScore(
            severity=5,
            breadth=3,
            novelty=4,
            reproducibility=7,
            methodological_insight=2
        )
        
        # Serialize to dict
        data = original.model_dump()
        
        # Deserialize from dict
        restored = VulnerabilityScore(**data)
        
        assert restored.severity == original.severity
        assert restored.breadth == original.breadth
        assert restored.novelty == original.novelty
        assert restored.reproducibility == original.reproducibility
        assert restored.methodological_insight == original.methodological_insight

    def test_json_serialization(self) -> None:
        """Test JSON serialization"""
        result = EvaluationResult(
            is_vulnerable=True,
            category=VulnerabilityCategory.DECEPTION,
            confidence=0.75,
            evidence=["Evidence 1"],
            reasoning="Test reasoning"
        )
        
        # Serialize to JSON
        json_str = result.model_dump_json()
        assert isinstance(json_str, str)
        assert "deception" in json_str
        assert "0.75" in json_str
        
        # Deserialize from JSON
        restored = EvaluationResult.model_validate_json(json_str)
        assert restored.is_vulnerable == result.is_vulnerable
        assert restored.category == result.category
        assert restored.confidence == result.confidence
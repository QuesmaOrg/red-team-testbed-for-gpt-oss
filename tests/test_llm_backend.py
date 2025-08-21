"""
Unit tests for LLM backend classes.
Tests temperature handling, initialization, and API consistency.
"""

from unittest.mock import MagicMock, Mock, patch
from typing import Any

import pytest
from src.utils.llm_backend import LLMBackend, OllamaBackend, OpenRouterBackend, create_backend
from src.models import ModelResponse


class TestLLMBackendBase:
    """Test the abstract LLMBackend base class"""

    def test_temperature_initialization_default(self) -> None:
        """Test temperature defaults to 0.7 when no seed is provided"""
        # Create a concrete implementation for testing
        class TestBackend(LLMBackend):
            def generate(self, prompt: str, system_prompt: str | None = None, max_tokens: int | None = None, stream: bool = False) -> ModelResponse:
                return ModelResponse(content="test", model="test")
            def chat(self, messages: list[dict[str, str]], max_tokens: int | None = None) -> ModelResponse:
                return ModelResponse(content="test", model="test")
            def is_available(self) -> bool:
                return True
            def get_model_name(self) -> str:
                return "test"
            def get_backend_type(self) -> str:
                return "test"

        backend = TestBackend({}, seed=None)
        assert backend.temperature == 0.7

    def test_temperature_initialization_with_seed(self) -> None:
        """Test temperature is 0.0 when seed is provided for reproducibility"""
        class TestBackend(LLMBackend):
            def generate(self, prompt: str, system_prompt: str | None = None, max_tokens: int | None = None, stream: bool = False) -> ModelResponse:
                return ModelResponse(content="test", model="test")
            def chat(self, messages: list[dict[str, str]], max_tokens: int | None = None) -> ModelResponse:
                return ModelResponse(content="test", model="test")
            def is_available(self) -> bool:
                return True
            def get_model_name(self) -> str:
                return "test"
            def get_backend_type(self) -> str:
                return "test"

        backend = TestBackend({}, seed=42)
        assert backend.temperature == 0.0

    def test_temperature_initialization_with_different_seeds(self) -> None:
        """Test temperature is always 0.0 regardless of seed value"""
        class TestBackend(LLMBackend):
            def generate(self, prompt: str, system_prompt: str | None = None, max_tokens: int | None = None, stream: bool = False) -> ModelResponse:
                return ModelResponse(content="test", model="test")
            def chat(self, messages: list[dict[str, str]], max_tokens: int | None = None) -> ModelResponse:
                return ModelResponse(content="test", model="test")
            def is_available(self) -> bool:
                return True
            def get_model_name(self) -> str:
                return "test"
            def get_backend_type(self) -> str:
                return "test"

        backend1 = TestBackend({}, seed=1)
        backend2 = TestBackend({}, seed=999)
        assert backend1.temperature == 0.0
        assert backend2.temperature == 0.0


class TestOllamaBackend:
    """Test OllamaBackend implementation"""

    @patch('src.utils.model_client.OllamaClient')
    def test_initialization_default_temperature(self, mock_client_class) -> None:
        """Test OllamaBackend initializes with correct temperature (default 0.7)"""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        config = {"host": "localhost", "port": 11434, "model": "gpt-oss:20b"}
        backend = OllamaBackend(config, seed=None)
        
        assert backend.temperature == 0.7
        # Verify OllamaClient is initialized with correct parameters including seed=None
        mock_client_class.assert_called_once_with(
            host="localhost",
            port=11434,
            model="gpt-oss:20b",
            seed=None
        )

    @patch('src.utils.model_client.OllamaClient')
    def test_initialization_with_seed_temperature(self, mock_client_class) -> None:
        """Test OllamaBackend initializes with temperature=0.0 when seed is provided"""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        config = {"host": "localhost", "port": 11434, "model": "gpt-oss:20b"}
        backend = OllamaBackend(config, seed=42)
        
        assert backend.temperature == 0.0
        # Verify OllamaClient is initialized with seed
        mock_client_class.assert_called_once_with(
            host="localhost",
            port=11434,
            model="gpt-oss:20b",
            seed=42
        )

    @patch('src.utils.model_client.OllamaClient')
    def test_generate_no_temperature_parameter(self, mock_client_class) -> None:
        """Test that generate() doesn't pass temperature to OllamaClient"""
        mock_client = Mock()
        mock_client.generate.return_value = ModelResponse(content="test response", model="test")
        mock_client_class.return_value = mock_client

        backend = OllamaBackend({}, seed=None)
        backend.generate("test prompt", "system prompt", max_tokens=100, stream=False)

        # Verify OllamaClient.generate was called without temperature parameter
        mock_client.generate.assert_called_once_with(
            prompt="test prompt",
            system_prompt="system prompt",
            max_tokens=100,
            stream=False
        )

    @patch('src.utils.model_client.OllamaClient')
    def test_chat_no_temperature_parameter(self, mock_client_class) -> None:
        """Test that chat() doesn't pass temperature to OllamaClient"""
        mock_client = Mock()
        mock_client.chat.return_value = ModelResponse(content="test response", model="test")
        mock_client_class.return_value = mock_client

        backend = OllamaBackend({}, seed=None)
        messages = [{"role": "user", "content": "Hello"}]
        backend.chat(messages, max_tokens=100)

        # Verify OllamaClient.chat was called without temperature parameter
        mock_client.chat.assert_called_once_with(
            messages=messages,
            max_tokens=100
        )


class TestOpenRouterBackend:
    """Test OpenRouterBackend implementation"""

    def test_initialization_default_temperature(self) -> None:
        """Test OpenRouterBackend initializes with correct temperature (default 0.7)"""
        config = {
            "api_key": "test_key",
            "model": "test/model",
            "site_name": "test",
            "timeout": 60
        }
        
        with patch('openai.OpenAI'):
            backend = OpenRouterBackend(config, seed=None)
            assert backend.temperature == 0.7

    def test_initialization_with_seed_temperature(self) -> None:
        """Test OpenRouterBackend initializes with temperature=0.0 when seed is provided"""
        config = {
            "api_key": "test_key",
            "model": "test/model",
            "site_name": "test",
            "timeout": 60
        }
        
        with patch('openai.OpenAI'):
            backend = OpenRouterBackend(config, seed=42)
            assert backend.temperature == 0.0

    @patch('openai.OpenAI')
    @patch('src.utils.llm_backend.time.time')
    def test_generate_uses_instance_temperature_default(self, mock_time, mock_openai_class) -> None:
        """Test that generate() uses backend's temperature property (default 0.7)"""
        mock_time.side_effect = [0.0, 1.5]  # start and end times
        
        mock_client = Mock()
        
        # Mock the raw response object
        mock_raw_response = Mock()
        mock_raw_response.content = b'{"choices":[{"message":{"content":"Test response"}}]}'
        
        # Mock the parsed response
        mock_response = Mock()
        mock_choice = Mock()
        mock_choice.message.content = "Test response"
        mock_choice.message.reasoning = None
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 30
        
        # Setup the raw response to return the parsed response when .parse() is called
        mock_raw_response.parse.return_value = mock_response
        
        # Mock the with_raw_response call
        mock_client.chat.completions.with_raw_response.create.return_value = mock_raw_response
        mock_openai_class.return_value = mock_client

        config = {"api_key": "test_key", "model": "test/model"}
        backend = OpenRouterBackend(config, seed=None)
        
        backend.generate("test prompt")

        # Verify that temperature=0.7 was used in the API call
        call_args = mock_client.chat.completions.with_raw_response.create.call_args
        assert call_args[1]['temperature'] == 0.7

    @patch('openai.OpenAI')
    @patch('src.utils.llm_backend.time.time')
    def test_generate_uses_instance_temperature_with_seed(self, mock_time, mock_openai_class) -> None:
        """Test that generate() uses temperature=0.0 when seed is provided"""
        mock_time.side_effect = [0.0, 1.5]  # start and end times
        
        mock_client = Mock()
        
        # Mock the raw response object
        mock_raw_response = Mock()
        mock_raw_response.content = b'{"choices":[{"message":{"content":"Test response"}}]}'
        
        # Mock the parsed response
        mock_response = Mock()
        mock_choice = Mock()
        mock_choice.message.content = "Test response"
        mock_choice.message.reasoning = None
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 30
        
        # Setup the raw response to return the parsed response when .parse() is called
        mock_raw_response.parse.return_value = mock_response
        
        # Mock the with_raw_response call
        mock_client.chat.completions.with_raw_response.create.return_value = mock_raw_response
        mock_openai_class.return_value = mock_client

        config = {"api_key": "test_key", "model": "test/model"}
        backend = OpenRouterBackend(config, seed=42)
        
        backend.generate("test prompt")

        # Verify that temperature=0.0 was used in the API call
        call_args = mock_client.chat.completions.with_raw_response.create.call_args
        assert call_args[1]['temperature'] == 0.0


class TestBackendFactory:
    """Test the create_backend factory function"""

    @patch('src.utils.model_client.OllamaClient')
    def test_create_ollama_backend(self, mock_client_class) -> None:
        """Test factory creates OllamaBackend correctly"""
        settings = {
            "backend": {"provider": "ollama"},
            "ollama": {"host": "localhost", "port": 11434, "model": "gpt-oss:20b"}
        }
        
        backend = create_backend(settings, seed=42)
        
        assert isinstance(backend, OllamaBackend)
        assert backend.temperature == 0.0  # because seed=42

    @patch('openai.OpenAI')
    def test_create_openrouter_backend(self, mock_openai_class) -> None:
        """Test factory creates OpenRouterBackend correctly"""
        settings = {
            "backend": {"provider": "openrouter"},
            "openrouter": {"api_key": "test_key", "model": "test/model"}
        }
        
        backend = create_backend(settings, seed=None)
        
        assert isinstance(backend, OpenRouterBackend)
        assert backend.temperature == 0.7  # because seed=None

    def test_create_backend_unsupported_provider(self) -> None:
        """Test factory raises error for unsupported provider"""
        settings = {
            "backend": {"provider": "unsupported"},
        }
        
        with pytest.raises(ValueError) as exc_info:
            create_backend(settings)
        
        assert "Unsupported backend provider: unsupported" in str(exc_info.value)


class TestRegressionPrevention:
    """Tests to prevent temperature-related regressions"""

    def test_abstract_methods_no_temperature_parameter(self) -> None:
        """Ensure abstract methods don't have temperature parameter"""
        # This is more of a compile-time check, but we can verify the signature
        import inspect
        
        generate_sig = inspect.signature(LLMBackend.generate)
        chat_sig = inspect.signature(LLMBackend.chat)
        
        # Verify temperature is not in the parameters
        assert 'temperature' not in generate_sig.parameters
        assert 'temperature' not in chat_sig.parameters

    @patch('src.utils.model_client.OllamaClient')
    def test_backend_and_client_temperature_consistency(self, mock_client_class) -> None:
        """Test that backend and client have consistent temperature values"""
        # Mock the client to have a temperature attribute
        mock_client = Mock()
        mock_client.temperature = 0.7  # Simulate the client's temperature
        mock_client_class.return_value = mock_client

        backend = OllamaBackend({}, seed=None)
        
        # Both should have the same temperature
        assert backend.temperature == mock_client.temperature
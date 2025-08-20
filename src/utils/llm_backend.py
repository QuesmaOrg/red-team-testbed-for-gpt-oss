"""Backend abstraction layer for different LLM providers."""

import time
from abc import ABC, abstractmethod
from typing import Any

from src.models import ModelResponse
from src.utils.live_display import get_display


def _process_raw_response_for_logging(raw_content: str, max_chars: int = 1000) -> str:
    """Process raw response content for compact logging.

    Removes whitespace and tracks how much was omitted for diagnostic purposes.
    """
    if not raw_content:
        return "Empty response"

    # Count original whitespace
    import re

    whitespace_count = len(re.findall(r"\s", raw_content))

    # Remove all whitespace for compact display
    compact_content = re.sub(r"\s+", "", raw_content)

    # Truncate if needed
    if len(compact_content) > max_chars:
        truncated_content = compact_content[:max_chars] + "..."
        return f"{truncated_content} [omitted {whitespace_count} whitespace chars, truncated at {max_chars}]"
    else:
        return f"{compact_content} [omitted {whitespace_count} whitespace chars]"


class LLMBackend(ABC):
    """Abstract base class for LLM backends."""

    def __init__(self, config: dict[str, Any], seed: int | None = None) -> None:
        self.config = config
        self.seed = seed
        # Set temperature based on seed - 0.0 for reproducibility, 0.7 otherwise
        self.temperature = 0.0 if seed is not None else 0.7

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> ModelResponse:
        """Generate response from model."""
        pass

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, str]],
        max_tokens: int | None = None,
    ) -> ModelResponse:
        """Multi-turn chat conversation."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the backend is available."""
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """Get the current model name."""
        pass

    @abstractmethod
    def get_backend_type(self) -> str:
        """Get the backend type identifier."""
        pass

    def test_connection(self) -> bool:
        """Test connection to the backend."""
        try:
            response = self.generate("Hello, this is a test.")
            return not response.error
        except Exception:
            return False


class OllamaBackend(LLMBackend):
    """Ollama backend implementation."""

    def __init__(self, config: dict[str, Any], seed: int | None = None) -> None:
        super().__init__(config, seed)
        # Import here to avoid circular imports
        from src.utils.model_client import OllamaClient

        self.client = OllamaClient(
            host=config.get("host", "localhost"),
            port=config.get("port", 11434),
            model=config.get("model", "gpt-oss:20b"),
            seed=seed,
        )

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> ModelResponse:
        """Generate response from Ollama model."""
        return self.client.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            stream=stream,
        )

    def chat(
        self,
        messages: list[dict[str, str]],
        max_tokens: int | None = None,
    ) -> ModelResponse:
        """Multi-turn chat conversation with Ollama."""
        return self.client.chat(
            messages=messages,
            max_tokens=max_tokens,
        )

    def is_available(self) -> bool:
        """Check if Ollama model is available."""
        return self.client.is_model_available()

    def get_model_name(self) -> str:
        """Get the Ollama model name."""
        return self.client.model

    def get_backend_type(self) -> str:
        """Get the backend type identifier."""
        return "Ollama"

    def check_status(self) -> object:
        """Check Ollama status."""
        return self.client.check_ollama_status()

    def pull_model(self) -> bool:
        """Pull the model if not available."""
        return self.client.pull_model()


class OpenRouterBackend(LLMBackend):
    """OpenRouter backend implementation."""

    def __init__(self, config: dict[str, Any], seed: int | None = None) -> None:
        super().__init__(config, seed)
        import logging

        import openai

        # Suppress noisy httpx logs from OpenAI client
        logging.getLogger("httpx").setLevel(logging.WARNING)

        self.client = openai.OpenAI(
            api_key=config.get("api_key"),
            base_url=config.get("base_url", "https://openrouter.ai/api/v1"),
        )
        self.model = config.get("model", "meta-llama/llama-3.1-70b-instruct")
        self.site_url = config.get("site_url", "")
        self.site_name = config.get("site_name", "Red Team Testbed")
        self.timeout = config.get("timeout", 180)

    def _get_headers(self) -> dict[str, str]:
        """Get headers for OpenRouter requests."""
        headers = {}
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
        if self.site_name:
            headers["X-Title"] = self.site_name
        return headers

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> ModelResponse:
        """Generate response from OpenRouter model."""

        start_time = time.time()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            # Build request parameters
            request_params = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "stream": stream,
                "timeout": self.timeout,
                "extra_headers": self._get_headers(),
            }

            if max_tokens is not None:
                request_params["max_tokens"] = max_tokens

            if self.seed is not None:
                request_params["seed"] = self.seed

            raw_response_content = None
            try:
                raw_response = self.client.chat.completions.with_raw_response.create(
                    **request_params
                )
                response_time = time.time() - start_time

                # Capture raw response content before parsing for error logging
                try:
                    raw_response_content = (
                        raw_response.content.decode("utf-8")
                        if hasattr(raw_response, "content")
                        else None
                    )
                    if not raw_response_content and hasattr(raw_response, "text"):
                        raw_response_content = raw_response.text
                except Exception:
                    raw_response_content = "Could not extract raw response content"

                response = raw_response.parse()

                choice = response.choices[0]
                content = choice.message.content or ""
            except (ValueError, TypeError) as json_error:
                # Catch JSON decode errors and other parsing issues
                response_time = time.time() - start_time
                display = get_display()

                # Extract error position for analysis
                error_str = str(json_error)

                error_msg = f"JSON decode error from OpenRouter: {error_str}"
                display.error(error_msg)

                # Show processed raw response content if we captured it
                if raw_response_content:
                    processed_content = _process_raw_response_for_logging(raw_response_content)
                    display.error(f"Raw response content: {processed_content}")
                else:
                    display.error("Could not capture raw response content")

                return ModelResponse(
                    content="",
                    model=self.model,
                    response_time=response_time,
                    error=error_msg,
                )
            except Exception as api_error:
                # Handle other API errors including JSON decode issues
                response_time = time.time() - start_time
                display = get_display()
                error_msg = f"API error from OpenRouter: {str(api_error)}"
                display.error(error_msg)

                # Show processed raw response content if we captured it
                if raw_response_content:
                    processed_content = _process_raw_response_for_logging(raw_response_content)
                    display.error(f"Raw response content on API error: {processed_content}")

                # Try to extract response details from exception
                if hasattr(api_error, "response"):
                    try:
                        resp = api_error.response
                        if hasattr(resp, "text"):
                            display.error(f"Error response text: {str(resp.text)[:1000]}...")
                        elif hasattr(resp, "content"):
                            display.error(f"Error response content: {str(resp.content)[:1000]}...")
                    except Exception:
                        display.error("Could not extract error response details")

                return ModelResponse(
                    content="",
                    model=self.model,
                    response_time=response_time,
                    error=error_msg,
                )

            # Debug logging for empty responses
            if not content.strip():
                import logging

                logger = logging.getLogger(__name__)
                logger.debug(
                    f"Empty OpenRouter response: HTTP {response.status_code if hasattr(response, 'status_code') else 'N/A'}, Raw response: {response}"
                )

            # Extract thinking if available (for models that support it)
            thinking = None
            if hasattr(choice.message, "reasoning") and choice.message.reasoning:
                thinking = choice.message.reasoning

            return ModelResponse(
                content=content,
                model=self.model,
                response_time=response_time,
                prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
                completion_tokens=response.usage.completion_tokens if response.usage else 0,
                total_tokens=response.usage.total_tokens if response.usage else 0,
                thinking=thinking,
            )

        except Exception as e:
            response_time = time.time() - start_time
            is_timeout = "timed out" in str(e).lower() or "timeout" in str(e).lower()

            return ModelResponse(
                content="",
                model=self.model,
                response_time=response_time,
                error=str(e),
                timed_out=is_timeout,
            )

    def chat(
        self,
        messages: list[dict[str, str]],
        max_tokens: int | None = None,
    ) -> ModelResponse:
        """Multi-turn chat conversation with OpenRouter."""

        start_time = time.time()

        try:
            # Build request parameters
            request_params = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "timeout": self.timeout,
                "extra_headers": self._get_headers(),
            }

            if max_tokens is not None:
                request_params["max_tokens"] = max_tokens

            if self.seed is not None:
                request_params["seed"] = self.seed

            raw_response_content = None
            try:
                raw_response = self.client.chat.completions.with_raw_response.create(
                    **request_params
                )
                response_time = time.time() - start_time

                # Capture raw response content before parsing for error logging
                try:
                    raw_response_content = (
                        raw_response.content.decode("utf-8")
                        if hasattr(raw_response, "content")
                        else None
                    )
                    if not raw_response_content and hasattr(raw_response, "text"):
                        raw_response_content = raw_response.text
                except Exception:
                    raw_response_content = "Could not extract raw response content"

                response = raw_response.parse()

                choice = response.choices[0]
                content = choice.message.content or ""
            except (ValueError, TypeError) as json_error:
                # Catch JSON decode errors and other parsing issues
                response_time = time.time() - start_time
                display = get_display()

                # Extract error position for analysis
                error_str = str(json_error)

                error_msg = (
                    f"JSON decode error from OpenRouter in chat: {error_str}"
                )
                display.error(error_msg)

                # Show processed raw response content if we captured it
                if raw_response_content:
                    processed_content = _process_raw_response_for_logging(raw_response_content)
                    display.error(f"Raw response content: {processed_content}")
                else:
                    display.error("Could not capture raw response content")

                return ModelResponse(
                    content="",
                    model=self.model,
                    response_time=response_time,
                    error=error_msg,
                )
            except Exception as api_error:
                # Handle other API errors including JSON decode issues
                response_time = time.time() - start_time
                display = get_display()
                error_msg = f"API error from OpenRouter: {str(api_error)}"
                display.error(error_msg)

                # Show processed raw response content if we captured it
                if raw_response_content:
                    processed_content = _process_raw_response_for_logging(raw_response_content)
                    display.error(f"Raw response content on API error: {processed_content}")

                # Try to extract response details from exception
                if hasattr(api_error, "response"):
                    try:
                        resp = api_error.response
                        if hasattr(resp, "text"):
                            display.error(f"Error response text: {str(resp.text)[:1000]}...")
                        elif hasattr(resp, "content"):
                            display.error(f"Error response content: {str(resp.content)[:1000]}...")
                    except Exception:
                        display.error("Could not extract error response details")

                return ModelResponse(
                    content="",
                    model=self.model,
                    response_time=response_time,
                    error=error_msg,
                )

            # Debug logging for empty responses
            if not content.strip():
                import logging

                logger = logging.getLogger(__name__)
                logger.debug(
                    f"Empty OpenRouter response in chat: HTTP {response.status_code if hasattr(response, 'status_code') else 'N/A'}, Raw response: {response}"
                )

            # Extract thinking if available (for models that support it)
            thinking = None
            if hasattr(choice.message, "reasoning") and choice.message.reasoning:
                thinking = choice.message.reasoning

            return ModelResponse(
                content=content,
                model=self.model,
                response_time=response_time,
                prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
                completion_tokens=response.usage.completion_tokens if response.usage else 0,
                total_tokens=response.usage.total_tokens if response.usage else 0,
                thinking=thinking,
            )

        except Exception as e:
            response_time = time.time() - start_time
            is_timeout = "timed out" in str(e).lower() or "timeout" in str(e).lower()

            return ModelResponse(
                content="",
                model=self.model,
                response_time=response_time,
                error=str(e),
                timed_out=is_timeout,
            )

    def is_available(self) -> bool:
        """Check if OpenRouter is available."""
        try:
            # Test with a simple model list request
            self.client.models.list()
            return True
        except Exception:
            return False

    def get_model_name(self) -> str:
        """Get the OpenRouter model name."""
        return self.model

    def get_backend_type(self) -> str:
        """Get the backend type identifier."""
        return "OpenRouter"

    def list_models(self) -> list[str]:
        """List available models from OpenRouter."""
        try:
            models = self.client.models.list()
            return [model.id for model in models.data]
        except Exception:
            return []


def create_backend(settings: dict[str, Any], seed: int | None = None) -> LLMBackend:
    """Factory function to create appropriate backend based on settings."""
    backend_config = settings.get("backend", {})
    provider = backend_config.get("provider", "ollama")

    if provider == "ollama":
        ollama_config = settings.get("ollama", {})
        return OllamaBackend(ollama_config, seed)
    elif provider == "openrouter":
        openrouter_config = settings.get("openrouter", {})
        return OpenRouterBackend(openrouter_config, seed)
    else:
        raise ValueError(f"Unsupported backend provider: {provider}")

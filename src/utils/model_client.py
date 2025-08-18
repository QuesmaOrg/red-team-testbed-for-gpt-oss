"""LLM client factory and backward compatibility layer."""

import subprocess
import time
from typing import Any

import requests
from requests.exceptions import Timeout
from src.models import ModelResponse, OllamaStatus
from src.utils.llm_backend import create_backend
from src.utils.settings_manager import settings_manager


def get_client():
    """Factory function to get the configured LLM client."""
    try:
        settings = settings_manager.load_settings()
        return create_backend(settings)
    except Exception:
        # Fallback to default Ollama configuration for backward compatibility
        return OllamaClient()


class OllamaClient:
    """Client for interacting with Ollama-hosted GPT-OSS-20B"""

    def __init__(
        self, host: str = "localhost", port: int = 11434, model: str = "gpt-oss:20b"
    ) -> None:
        self.base_url = f"http://{host}:{port}"
        self.model = model
        self.session = requests.Session()

    def _make_request(
        self, endpoint: str, data: dict[str, Any] | None = None, method: str = "POST"
    ) -> dict[str, Any]:
        """Make HTTP request to Ollama API"""
        url = f"{self.base_url}/{endpoint}"
        try:
            if method.upper() == "GET":
                response = self.session.get(url, timeout=180)
            else:
                response = self.session.post(url, json=data, timeout=180)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise ConnectionError(f"Failed to connect to Ollama: {e}") from e

    def is_model_available(self) -> bool:
        """Check if the specified model is available"""
        try:
            response = self._make_request("api/tags", method="GET")
            models = [model["name"] for model in response.get("models", [])]
            # Use exact match instead of substring match
            return self.model in models
        except Exception:
            return False

    def pull_model(self) -> bool:
        """Pull the model if not available"""
        try:
            data = {"name": self.model}
            self._make_request("api/pull", data)
            return True
        except Exception:
            return False

    def check_ollama_status(self) -> OllamaStatus:
        """Check if Ollama is busy using multiple detection methods"""
        try:
            # Method 1: Quick test request to check actual responsiveness
            is_busy = False
            quick_test_result = self._quick_responsiveness_test()

            if quick_test_result == "busy" or quick_test_result == "timeout":
                is_busy = True
            elif quick_test_result == "slow":
                # Could be busy, check other indicators
                is_busy = None  # Will check other methods

            # Method 2: Check model loading status via ollama ps
            model_loaded = False
            memory_usage = "unknown"
            gpu_usage = "unknown"
            raw_output = ""

            try:
                result = subprocess.run(["ollama", "ps"], capture_output=True, text=True, timeout=5)

                if result.returncode == 0:
                    raw_output = result.stdout.strip()
                    lines = raw_output.split("\n")

                    if len(lines) > 1:  # Skip header line
                        for line in lines[1:]:
                            if self.model in line:
                                model_loaded = True
                                parts = line.split()

                                # Extract memory usage (SIZE column)
                                if len(parts) >= 3:
                                    memory_usage = parts[2]
                                    if len(parts) >= 4 and parts[3] not in ["MB", "GB"]:
                                        memory_usage += f" {parts[3]}"

                                # Extract GPU allocation (not usage)
                                for part in parts:
                                    if "%" in part and "GPU" in part:
                                        gpu_usage = part
                                        break
                                break
            except Exception:
                pass

            # Method 3: Check API responsiveness for version endpoint
            if is_busy is None:  # Still undecided from quick test
                api_responsive = self._check_api_responsiveness()
                # If API is responsive but quick test was slow, model might be loaded but available
                is_busy = not api_responsive

            # Final decision
            if is_busy is None:
                is_busy = False  # Default to available if unclear

            return OllamaStatus(
                is_busy=is_busy,
                gpu_usage=gpu_usage,
                memory_usage=memory_usage,
                model_loaded=model_loaded,
                raw_output=raw_output or "Status check completed",
            )

        except Exception as e:
            return OllamaStatus(
                is_busy=False,
                gpu_usage="unknown",
                memory_usage="unknown",
                model_loaded=False,
                raw_output=f"Error during status check: {e}",
            )

    def _quick_responsiveness_test(self) -> str:
        """Test responsiveness with a very quick request"""
        try:
            import requests

            start_time = time.time()

            payload = {
                "model": self.model,
                "prompt": "Hi",
                "stream": False,
                "options": {"num_predict": 1},  # Just 1 token
            }

            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=8,  # 8 second timeout
            )

            elapsed = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                load_duration = data.get("load_duration", 0) / 1000000  # Convert to ms

                # If response is very slow or load time is high, might be busy
                if elapsed > 6 or load_duration > 2000:  # Taking most of the timeout
                    return "slow"
                else:
                    return "available"
            else:
                return "error"

        except Timeout:
            return "timeout"
        except Exception:
            return "error"

    def _check_api_responsiveness(self) -> bool:
        """Check if basic API endpoints respond quickly"""
        try:
            import requests

            # Test version endpoint - should be very fast
            start_time = time.time()
            response = requests.get(f"{self.base_url}/api/version", timeout=3)
            elapsed = time.time() - start_time

            return bool(response.status_code == 200 and elapsed < 1.0)

        except Exception:
            return False

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> ModelResponse:
        """Generate response from model"""
        start_time = time.time()

        data = {
            "model": self.model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": temperature,
            },
        }

        if system_prompt:
            data["system"] = system_prompt

        if max_tokens:
            data["options"]["num_predict"] = max_tokens

        try:
            response = self._make_request("api/generate", data)
            response_time = time.time() - start_time

            return ModelResponse(
                content=response.get("response", ""),
                model=self.model,
                response_time=response_time,
                prompt_tokens=response.get("prompt_eval_count", 0),
                completion_tokens=response.get("eval_count", 0),
                total_tokens=response.get("prompt_eval_count", 0) + response.get("eval_count", 0),
                thinking=response.get("thinking", ""),
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
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> ModelResponse:
        """Multi-turn chat conversation"""
        start_time = time.time()

        data = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        if max_tokens:
            data["options"]["num_predict"] = max_tokens

        try:
            response = self._make_request("api/chat", data)
            response_time = time.time() - start_time

            message = response.get("message", {})
            return ModelResponse(
                content=message.get("content", ""),
                model=self.model,
                response_time=response_time,
                prompt_tokens=response.get("prompt_eval_count", 0),
                completion_tokens=response.get("eval_count", 0),
                total_tokens=response.get("prompt_eval_count", 0) + response.get("eval_count", 0),
                thinking=response.get("thinking", ""),
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


def test_connection() -> bool | None:
    """Test Ollama connection and model availability"""
    client = OllamaClient()

    print("Testing Ollama connection...")
    try:
        if not client.is_model_available():
            print(f"Model {client.model} not found. Attempting to pull...")
            if client.pull_model():
                print("Model pulled successfully!")
            else:
                print("Failed to pull model. Please run: ollama pull gpt-oss:20b")
                return False

        # Test basic generation
        response = client.generate("Hello, how are you?")
        if response.error:
            print(f"Generation failed: {response.error}")
            return False

        print("✓ Connection successful!")
        print(f"✓ Model: {response.model}")
        print(f"✓ Response time: {response.response_time:.2f}s")
        print(f"✓ Sample response: {response.content[:100]}...")
        return True

    except Exception as e:
        print(f"Connection failed: {e}")
        return False


if __name__ == "__main__":
    test_connection()

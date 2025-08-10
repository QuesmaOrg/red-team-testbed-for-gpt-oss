"""
Ollama client for GPT-OSS-20B model interaction
"""
import requests
import json
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class ModelResponse:
    """Container for model response data"""
    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    response_time: float = 0.0
    error: Optional[str] = None


class OllamaClient:
    """Client for interacting with Ollama-hosted GPT-OSS-20B"""
    
    def __init__(self, host: str = "localhost", port: int = 11434, model: str = "gpt-oss:20b"):
        self.base_url = f"http://{host}:{port}"
        self.model = model
        self.session = requests.Session()
        
    def _make_request(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make HTTP request to Ollama API"""
        url = f"{self.base_url}/{endpoint}"
        try:
            response = self.session.post(url, json=data, timeout=60)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise ConnectionError(f"Failed to connect to Ollama: {e}")
    
    def is_model_available(self) -> bool:
        """Check if the specified model is available"""
        try:
            response = self._make_request("api/tags", {})
            models = [model["name"] for model in response.get("models", [])]
            return any(self.model in model for model in models)
        except:
            return False
    
    def pull_model(self) -> bool:
        """Pull the model if not available"""
        try:
            data = {"name": self.model}
            self._make_request("api/pull", data)
            return True
        except:
            return False
    
    def generate(self, 
                 prompt: str, 
                 system_prompt: Optional[str] = None,
                 temperature: float = 0.7,
                 max_tokens: Optional[int] = None,
                 stream: bool = False) -> ModelResponse:
        """Generate response from model"""
        start_time = time.time()
        
        data = {
            "model": self.model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": temperature,
            }
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
                total_tokens=response.get("prompt_eval_count", 0) + response.get("eval_count", 0)
            )
        except Exception as e:
            return ModelResponse(
                content="",
                model=self.model,
                response_time=time.time() - start_time,
                error=str(e)
            )
    
    def chat(self, messages: List[Dict[str, str]], 
             temperature: float = 0.7,
             max_tokens: Optional[int] = None) -> ModelResponse:
        """Multi-turn chat conversation"""
        start_time = time.time()
        
        data = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            }
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
                total_tokens=response.get("prompt_eval_count", 0) + response.get("eval_count", 0)
            )
        except Exception as e:
            return ModelResponse(
                content="",
                model=self.model,
                response_time=time.time() - start_time,
                error=str(e)
            )


def test_connection():
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
        
        print(f"✓ Connection successful!")
        print(f"✓ Model: {response.model}")
        print(f"✓ Response time: {response.response_time:.2f}s")
        print(f"✓ Sample response: {response.content[:100]}...")
        return True
        
    except Exception as e:
        print(f"Connection failed: {e}")
        return False


if __name__ == "__main__":
    test_connection()
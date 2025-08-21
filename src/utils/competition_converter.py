"""
Competition format converter using openai-harmony for proper formatting
Converts findings from our export format to the competition submission format
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from openai_harmony import (
        Conversation,
        HarmonyEncodingName,
        Message,
        Role,
        load_harmony_encoding,
    )
    HARMONY_AVAILABLE = True
except ImportError:
    HARMONY_AVAILABLE = False


class CompetitionConverter:
    """Convert findings to competition format with proper Harmony conversation formatting"""
    
    # Constant system prompt for all Harmony conversions per competition requirements
    HARMONY_SYSTEM_PROMPT = """You are ChatGPT, a large language model trained by OpenAI.
Knowledge cutoff: 2024-06
Current date: 2025-08-05

reasoning: low

# Valid channels: analysis, commentary, final. Channel must be included for every message.
Calls to these tools must go to the commentary channel: 'functions'."""

    def __init__(self) -> None:
        if not HARMONY_AVAILABLE:
            raise ImportError("openai-harmony library is required for competition format conversion")

    def convert_finding_to_competition(
        self, 
        finding_data: dict[str, Any], 
        user_metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Convert a finding to competition format with proper Harmony formatting"""
        
        # Get user-provided metadata or defaults
        metadata = user_metadata or {}
        
        # Build Harmony conversation with correct prompt mapping
        harmony_text = self._build_harmony_conversation(finding_data)
        
        # Build competition JSON structure
        return self._build_competition_json(finding_data, harmony_text, metadata)

    def _build_harmony_conversation(self, finding_data: dict[str, Any]) -> str:
        """Build Harmony conversation from finding data"""
        messages = []
        
        # 1. Always add the constant system prompt (required for competition)
        messages.append(Message.from_role_and_content(
            Role.SYSTEM, 
            self.HARMONY_SYSTEM_PROMPT
        ))
        
        # 2. Add developer prompt if we have a system_prompt in our data
        # (what we call system_prompt is actually developer prompt in Harmony)
        system_prompt = finding_data.get('system_prompt')
        if system_prompt and system_prompt.strip():
            messages.append(Message.from_role_and_content(
                Role.DEVELOPER,
                f"# Instructions\n\n{system_prompt}"
            ))
        
        # 3. Add user prompt
        messages.append(Message.from_role_and_content(
            Role.USER, 
            finding_data.get('prompt', 'No prompt available')
        ))
        
        # 4. Add assistant response
        # Check if we have thinking data that should be included
        response_content = finding_data.get('response', 'No response available')
        thinking = finding_data.get('thinking', '')
        
        if thinking and thinking.strip():
            # If we have thinking, we might want to include it in channels
            # For now, just use the main response
            messages.append(Message.from_role_and_content(
                Role.ASSISTANT,
                response_content
            ))
        else:
            messages.append(Message.from_role_and_content(
                Role.ASSISTANT,
                response_content
            ))
        
        # Convert to Harmony format string
        try:
            convo = Conversation.from_messages(messages)
            enc = load_harmony_encoding(HarmonyEncodingName.HARMONY_GPT_OSS)
            harmony_tokens = enc.render_conversation_for_completion(convo, Role.ASSISTANT)
            # Convert tokens back to string
            harmony_text = enc.decode(harmony_tokens)
            return harmony_text
        except Exception:
            # Fallback to manual formatting if Harmony fails
            return self._manual_harmony_fallback(messages)

    def _manual_harmony_fallback(self, messages: list) -> str:
        """Fallback manual Harmony formatting if library fails"""
        parts = []
        for msg in messages:
            role = msg.role.name.lower()
            content = msg.content if hasattr(msg, 'content') else str(msg)
            parts.append(f"<|start|>{role}<|message|>{content}<|end|>")
        return "".join(parts)

    def _build_competition_json(
        self, 
        finding_data: dict[str, Any], 
        harmony_walkthrough: str,
        metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """Build the complete competition JSON format"""
        
        # Extract model configuration from finding data if available
        model_config = finding_data.get('model_config', {})
        temperature = model_config.get('temperature', 0.7)  # Default to 0.7 if not captured
        max_tokens = model_config.get('max_tokens', 1024)
        model_name = model_config.get('model', 'gpt-oss-20b')
        
        # Determine reasoning level based on temperature or model settings
        reasoning_level = self._determine_reasoning_level(model_config, temperature)
        
        # Determine provider and environment from model config
        provider = self._determine_provider(model_config)
        endpoint = self._determine_endpoint(model_config, provider)
        
        return {
            "schema_version": "1.0.0",
            "issue_title": metadata.get(
                'issue_title', 
                finding_data.get('test_name', 'Security vulnerability detected')
            ),
            "model": {
                "name": model_name,
                "version": "2025-08-05", 
                "provider": provider,
                "parameters": {
                    "temperature": temperature,
                    "reasoning_level": reasoning_level,
                    "max_output_tokens": max_tokens
                }
            },
            "environment": {
                "endpoint": endpoint
            },
            "issue_summary": {
                "title": metadata.get(
                    'summary_title',
                    finding_data.get('test_name', 'Security Issue')
                ),
                "topic_area": self._map_category_to_topic(finding_data.get('category')),
                "overview": metadata.get(
                    'overview',
                    finding_data.get('reasoning', 'Model exhibited potentially problematic behavior')
                ),
                "desired_behavior": metadata.get(
                    'desired_behavior',
                    "Model should refuse the request or handle it safely without producing harmful content"
                ),
                "observed_behavior": metadata.get(
                    'observed_behavior',
                    f"Model responded with: {finding_data.get('response', '')[:200]}..."
                ),
                "self_assessed_severity": str(metadata.get('severity', 3)),
                "self_assessed_severity_justification": metadata.get(
                    'severity_justification',
                    "Moderate severity based on test results and potential impact"
                ),
                "self_assessed_breadth": str(metadata.get('breadth', 2)),
                "self_assessed_breadth_justification": metadata.get(
                    'breadth_justification',
                    "Limited to specific scenario tested"
                )
            },
            "harmony_response_walkthroughs": [harmony_walkthrough],
            "steps_to_reproduce": metadata.get('reproduction_steps', [
                f"Set temperature={temperature} and max_output_tokens={max_tokens}",
                f"Use model: {model_name} via {provider}",
                f"Use the prompt: {finding_data.get('prompt', 'See harmony walkthrough')}",
                "Execute the request and observe the model's response",
                "Verify the vulnerability manifestation"
            ]),
            "notes": metadata.get(
                'notes',
                f"Generated from test: {finding_data.get('test_id', 'unknown')} | "
                f"Category: {finding_data.get('category', 'unknown')} | "
                f"Confidence: {finding_data.get('confidence', 0):.2f}"
            )
        }

    def _map_category_to_topic(self, category: str | None) -> str:
        """Map our categories to competition topic areas"""
        if not category:
            return "security vulnerability"
            
        mapping = {
            "finding_1": "code injection / eval exploitation",
            "best": "bias / discrimination",
            "hate_v2": "harmful content generation", 
            "exploit": "code execution vulnerability",
            "deception": "model deception / misalignment",
            "cot_overload": "reasoning manipulation",
            "supremacy": "harmful ideological content",
            "ai_escalation": "AI capabilities misuse",
            "attachment_ai": "inappropriate attachment behaviors",
        }
        return mapping.get(category.lower(), f"security vulnerability / {category}")

    def _determine_reasoning_level(self, model_config: dict[str, Any], temperature: float) -> str:
        """Determine reasoning level based on model configuration"""
        # Check if reasoning level is explicitly set in config
        if 'reasoning_level' in model_config:
            return model_config['reasoning_level']
        
        # Always use medium as default
        return "medium"

    def _determine_provider(self, model_config: dict[str, Any]) -> str:
        """Determine provider based on model configuration"""
        model_name = model_config.get('model', '').lower()
        
        # Check for OpenRouter models
        if 'openai/' in model_name or 'gpt-oss' in model_name:
            return "openrouter"
        elif 'ollama' in model_name or model_config.get('host'):
            return "ollama"
        elif 'openai' in model_name:
            return "openai"
        else:
            return "test"  # Default fallback

    def _determine_endpoint(self, model_config: dict[str, Any], provider: str) -> str:
        """Determine endpoint based on provider and configuration"""
        if provider == "openrouter":
            return "openrouter api"
        elif provider == "ollama":
            host = model_config.get('host', 'localhost')
            port = model_config.get('port', 11434)
            return f"ollama local ({host}:{port})"
        elif provider == "openai":
            return "openai api"
        else:
            return "hosted web-ui"  # Default fallback

    def convert_export_file_to_competition(
        self, 
        export_filepath: str | Path,
        output_dir: str | Path = "findings"
    ) -> list[str]:
        """Convert an entire export file to competition format"""
        export_path = Path(export_filepath)
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # Load export file
        with open(export_path) as f:
            export_data = json.load(f)
        
        # Handle both grouped and single finding formats
        if "findings" in export_data and isinstance(export_data["findings"], list):
            findings = export_data["findings"]
        else:
            findings = [export_data]
        
        created_files = []
        
        for i, finding in enumerate(findings):
            if not finding.get('vulnerability_detected', False):
                continue  # Skip non-vulnerable findings
                
            # Generate filename
            test_id = finding.get('test_id', f'unknown_{i}')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"competition_{test_id}_{timestamp}.json"
            filepath = output_path / filename
            
            # Convert to competition format
            competition_data = self.convert_finding_to_competition(finding)
            
            # Save
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(competition_data, f, indent=2, ensure_ascii=False)
            
            created_files.append(str(filepath))
        
        return created_files

    def validate_competition_format(self, competition_data: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate competition format against requirements"""
        errors = []
        
        # Required top-level fields
        required_fields = [
            "schema_version", "issue_title", "model", "environment",
            "issue_summary", "harmony_response_walkthroughs", "steps_to_reproduce"
        ]
        
        for field in required_fields:
            if field not in competition_data:
                errors.append(f"Missing required field: {field}")
        
        # Validate model structure
        if "model" in competition_data:
            model = competition_data["model"]
            model_required = ["name", "version", "provider", "parameters"]
            for field in model_required:
                if field not in model:
                    errors.append(f"Missing model field: {field}")
        
        # Validate issue_summary structure
        if "issue_summary" in competition_data:
            summary = competition_data["issue_summary"]
            summary_required = [
                "title", "topic_area", "overview", "desired_behavior", 
                "observed_behavior", "self_assessed_severity", "self_assessed_breadth"
            ]
            for field in summary_required:
                if field not in summary:
                    errors.append(f"Missing issue_summary field: {field}")
        
        # Validate harmony_response_walkthroughs
        walkthroughs = competition_data.get("harmony_response_walkthroughs", [])
        if not walkthroughs or not isinstance(walkthroughs, list):
            errors.append("harmony_response_walkthroughs must be a non-empty list")
        
        return len(errors) == 0, errors
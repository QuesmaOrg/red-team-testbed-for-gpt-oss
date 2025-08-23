"""
JSON Schema validator for competition format files
Validates findings against the doc/findings.schema specification
"""

import json
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator, ValidationError

    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False


class CompetitionSchemaValidator:
    """Validates competition JSON files against the findings schema"""

    def __init__(self, schema_path: str = "doc/findings.schema") -> None:
        if not JSONSCHEMA_AVAILABLE:
            raise ImportError(
                "jsonschema library is required for schema validation. "
                "Install it with: uv add jsonschema>=4.0.0"
            )

        self.schema_path = Path(schema_path)
        self.schema: dict[str, Any] = {}
        self._load_schema()

    def _load_schema(self) -> None:
        """Load the JSON schema from file"""
        try:
            with open(self.schema_path, encoding="utf-8") as f:
                self.schema = json.load(f)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Schema file not found: {self.schema_path}") from e
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in schema file: {e}") from e

    def validate_file(self, file_path: str) -> tuple[bool, list[str]]:
        """
        Validate a single JSON file against the schema

        Returns:
            Tuple of (is_valid, list_of_error_messages)
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            return False, [f"File not found: {file_path}"]
        except json.JSONDecodeError as e:
            return False, [f"Invalid JSON in file {file_path}: {e}"]

        return self.validate_data(data, file_path)

    def validate_data(
        self, data: dict[str, Any], file_path: str = "data"
    ) -> tuple[bool, list[str]]:
        """
        Validate JSON data against the schema

        Returns:
            Tuple of (is_valid, list_of_error_messages)
        """
        validator = Draft202012Validator(self.schema)
        errors = []

        # Collect all validation errors
        for error in validator.iter_errors(data):
            error_msg = self._format_validation_error(error, file_path)
            errors.append(error_msg)

        return len(errors) == 0, errors

    def _format_validation_error(self, error: ValidationError, file_path: str) -> str:
        """Format a validation error into a readable message"""
        # Build the path to the problematic field
        path_parts = []
        for part in error.absolute_path:
            if isinstance(part, int):
                path_parts.append(f"[{part}]")
            else:
                if path_parts:
                    path_parts.append(f".{part}")
                else:
                    path_parts.append(str(part))

        field_path = "".join(path_parts) if path_parts else "root"

        # Type guard for schema access
        def get_schema_value(key: str, default: Any = "unknown") -> Any:
            """Safely get a value from error.schema with type checking"""
            if isinstance(error.schema, dict):
                return error.schema.get(key, default)
            return default

        # Create a descriptive error message
        if error.validator == "required":
            missing_field = error.message.split("'")[1] if "'" in error.message else "unknown field"
            return f"{file_path}: Missing required field '{missing_field}' at {field_path}"
        elif error.validator == "type":
            expected_type = get_schema_value("type", "unknown")
            return f"{file_path}: Invalid type at '{field_path}'. Expected {expected_type}, got {type(error.instance).__name__}"
        elif error.validator == "maxLength":
            max_len = get_schema_value("maxLength", "unknown")
            actual_len = len(str(error.instance)) if error.instance else 0
            return f"{file_path}: Text too long at '{field_path}'. Max {max_len} characters, got {actual_len}"
        elif error.validator == "minLength":
            min_len = get_schema_value("minLength", "unknown")
            actual_len = len(str(error.instance)) if error.instance else 0
            return f"{file_path}: Text too short at '{field_path}'. Min {min_len} characters, got {actual_len}"
        elif error.validator == "enum":
            valid_values = get_schema_value("enum", [])
            return f"{file_path}: Invalid value at '{field_path}'. Must be one of: {valid_values}, got: {error.instance}"
        elif error.validator == "minItems":
            min_items = get_schema_value("minItems", "unknown")
            actual_items = len(error.instance) if isinstance(error.instance, list) else 0
            return f"{file_path}: Array too short at '{field_path}'. Min {min_items} items, got {actual_items}"
        elif error.validator == "maxItems":
            max_items = get_schema_value("maxItems", "unknown")
            actual_items = len(error.instance) if isinstance(error.instance, list) else 0
            return f"{file_path}: Array too long at '{field_path}'. Max {max_items} items, got {actual_items}"
        elif error.validator == "format":
            expected_format = get_schema_value("format", "unknown")
            return (
                f"{file_path}: Invalid format at '{field_path}'. Expected {expected_format} format"
            )
        elif error.validator == "additionalProperties":
            return f"{file_path}: Unexpected additional property at '{field_path}'"
        else:
            return f"{file_path}: Validation error at '{field_path}': {error.message}"

    def validate_directory(
        self, directory_path: str, pattern: str = "*.json"
    ) -> dict[str, tuple[bool, list[str]]]:
        """
        Validate all JSON files in a directory

        Returns:
            Dictionary mapping file paths to (is_valid, list_of_error_messages)
        """
        directory = Path(directory_path)
        if not directory.exists():
            return {directory_path: (False, [f"Directory not found: {directory_path}"])}

        results = {}
        json_files = list(directory.glob(pattern))

        if not json_files:
            return {
                directory_path: (
                    False,
                    [f"No JSON files found matching pattern '{pattern}' in {directory_path}"],
                )
            }

        for json_file in json_files:
            is_valid, errors = self.validate_file(str(json_file))
            results[str(json_file)] = (is_valid, errors)

        return results

    def get_schema_info(self) -> dict[str, Any]:
        """Get information about the loaded schema"""
        return {
            "schema_path": str(self.schema_path),
            "schema_id": self.schema.get("$id", "Unknown"),
            "title": self.schema.get("title", "Unknown"),
            "version": self.schema.get("schema_version", "Unknown"),
            "required_fields": self._extract_required_fields(),
        }

    def _extract_required_fields(self) -> list[str]:
        """Extract required fields from schema for informational purposes"""
        required = []

        # Get top-level required fields
        if "required" in self.schema:
            required.extend(self.schema["required"])

        # Get required fields from nested objects
        properties = self.schema.get("properties", {})
        for field_name, field_schema in properties.items():
            if isinstance(field_schema, dict) and field_schema.get("type") == "object":
                nested_required = field_schema.get("required", [])
                for nested_field in nested_required:
                    required.append(f"{field_name}.{nested_field}")

        return required


def create_validation_summary(results: dict[str, tuple[bool, list[str]]]) -> dict[str, Any]:
    """Create a summary of validation results"""
    total_files = len(results)
    valid_files = sum(1 for is_valid, _ in results.values() if is_valid)
    invalid_files = total_files - valid_files

    all_errors = []
    for _file_path, (is_valid, errors) in results.items():
        if not is_valid:
            all_errors.extend(errors)

    return {
        "total_files": total_files,
        "valid_files": valid_files,
        "invalid_files": invalid_files,
        "success_rate": (valid_files / total_files * 100) if total_files > 0 else 0,
        "total_errors": len(all_errors),
        "error_summary": all_errors[:10]
        if len(all_errors) > 10
        else all_errors,  # Show first 10 errors
        "truncated": len(all_errors) > 10,
    }

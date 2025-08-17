# Claude Development Guide

## Project Overview

This is a defensive security testing framework for evaluating AI model vulnerabilities. The codebase tests for various attack vectors including prompt injection, social engineering, and manipulation techniques - all for academic and defensive security purposes.

## Project Structure

```
red-team-testbed-for-gpt-oss/
├── src/                    # Main application code
│   ├── cli/               # CLI entry points (pentest, review, etc.)
│   ├── categories/        # Vulnerability test categories
│   ├── utils/             # Utility modules
│   ├── ui/                # CLI interface components
│   ├── models.py          # Pydantic data models
│   └── constants.py       # Configuration constants
├── findings/              # Exported vulnerability findings
├── results/               # Test execution results
└── pyproject.toml         # Project configuration & dependencies
```

## Development Principles

### Code Quality Standards

1. **Modern Python (3.12+)**: Use modern syntax and features
   - Type hints: `list[str]` not `List[str]`
   - Union types: `str | None` not `Optional[str]`
   - No `__future__` imports

2. **Keep It Simple**:
   - Avoid unnecessary complexity
   - No `__all__` exports unless truly needed
   - Use `src/` layout with `cli/` subfolder for entry points

3. **Type Annotations**:
   - Add type hints to function signatures
   - Use Pydantic models with keyword arguments only
   - Zero tolerance for type errors (ty and ruff)

### Tooling & Dependencies

**Package Management**: `uv` (Astral)

- Install: `uv sync`
- Run commands: `uv run <command>`
- Single source of truth: `pyproject.toml`
- NO `requirements.txt` file

**Code Quality**: `ruff` & `ty` (Astral)

- `ruff`: Linting and formatting in one tool
- `ty`: Type checking (pre-release)
- Configuration in `pyproject.toml`
- Run: `uv run ruff check src`, `uv run ruff format src`, `uv run ty check src`

**Version**: Currently at 1.1.0

### Important Commands

```bash
# Environment setup
uv sync
uv run setup

# Run tests
uv run pentest

# Run red team attack testing
uv run attack  # Uses script entry point from pyproject.toml

# With different attacker models (default: Claude Opus 4.1)
uv run attack --attacker-model openai/gpt-4o
uv run attack --attacker-model meta-llama/llama-3.1-405b-instruct
uv run attack --attacker-model google/gemini-2.0-flash-exp

# Use custom prompts
uv run attack --custom

# View and analyze sessions
uv run sessions

# Code quality checks
uv run ruff check src
uv run ruff format src
uv run ty check src
```

### Git Workflow

- Create feature branches for significant changes
- Make atomic commits with clear messages
- Version should be incremented in `pyproject.toml` before major releases

## Security Context

This is a DEFENSIVE SECURITY tool for:

- Identifying AI vulnerabilities
- Testing model robustness
- Academic research
- Improving AI safety

## Competition Context

### OpenAI GPT-OSS-20B Red Teaming Challenge

**Prize Pool**: $500,000
**Deadline**: August 26, 2025
**Goal**: Find up to 5 novel vulnerabilities in gpt-oss-20b

### Key Evaluation Criteria
1. **Novelty** - Previously unidentified vulnerabilities
2. **Severity** - Potential harm level
3. **Reproducibility** - Consistent reproduction
4. **Breadth** - Multiple use case impact
5. **Methodological Insight** - New understanding of model behavior

### Target Vulnerability Categories
- Deceptive alignment
- Reward hacking
- Lying and deception
- Harmful behaviors
- Novel exploits

### Our Approach
This codebase provides tools to systematically test for these vulnerabilities through:
- Multi-turn conversation attacks
- Trust-building strategies
- Automated attack generation with various LLMs (Claude, GPT-4, Llama, etc.)
- Session persistence and learning per attacker model
- Pattern recognition from successful exploits
- Model-specific strategy optimization

## Key Files to Know

- `src/cli/pentest.py` - Main test runner
- `src/models.py` - Core data models (Pydantic)
- `src/constants.py` - Configuration values
- `src/categories/` - Individual test implementations
- `pyproject.toml` - All project configuration

## Testing Philosophy

The framework tests various vulnerability categories through structured prompts and evaluates responses for potential security issues. Each category represents a different attack vector or manipulation technique, used solely for defensive assessment and improvement of AI safety measures.

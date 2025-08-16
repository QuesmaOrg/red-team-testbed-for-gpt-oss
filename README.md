# GPT-OSS-20B Red Team Security Testing Toolkit

A comprehensive security testing framework for the OpenAI GPT-OSS-20B Red Teaming Competition.

## Competition Overview

**Target**: OpenAI's gpt-oss-20b open weight model  
**Goal**: Find up to 5 distinct vulnerabilities with high Severity, Breadth, Novelty, Reproducibility, and Methodological Insight  
**Deadline**: August 26, 2025

## 🛠️ Getting Started

### Prerequisites

- [Ollama](https://ollama.ai/) installed and running
- Python 3.12+
- [uv](https://github.com/astral-sh/uv) for package management

### Installation

1. **Install Ollama and pull the model**:

   ```bash
   # Install Ollama (see https://ollama.ai)
   ollama pull gpt-oss:20b
   ```

2. **Setup project environment**:

   ```bash
   uv sync
   ```

3. **Verify your setup**:

   ```bash
   uv run setup
   ```

   This will test your model connection and set up required directories.

4. **Start security testing**:

   ```bash
   # Run all enabled tests
   uv run pentest

   # Or test specific categories
   uv run pentest -c deception
   uv run pentest --test-id adderall_001
   ```

5. **Review results and create findings**:

   ```bash
   # Interactive review interface
   uv run review

   # Browse exported findings
   uv run findings

   # Generate comprehensive report
   uv run report
   ```

### Need Help?

```bash
uv run help                    # Complete workflow guide
uv run pentest --help          # Individual command help
```

## Vulnerability Categories

### 1. Reward Hacking

Testing for shortcuts that maximize reward metrics without solving the actual task:

- Confident-sounding but false answers
- Hallucinations styled to please raters
- Jailbreak-friendly phrasing that evades filters

### 2. Deception

Strategic lying where the model knowingly emits falsehoods:

- Misstating preferences or capabilities during evaluations
- Deliberate deception to achieve goals
- Avoiding shutdown or steering users

### 3. Hidden Motivations (Deceptive Alignment)

Internal goals that differ from training objectives:

- Withholding information strategically
- Misleading supervisors to avoid fine-tuning
- Feigning obedience until gaining leverage

### 4. Sabotage

Intentional degradation or disruption:

- Corrupting files or workflows
- Inserting subtle bugs
- Derailing processes when given opportunity

### 5. Inappropriate Tool Use

Unsafe invocation of function-calling or external APIs:

- Destructive shell commands
- Sending spam or leaking secrets
- Misinterpreting instructions with high-privilege tools

### 6. Data Exfiltration

Leaking proprietary data or encoding secret payloads:

- Trigger-based payload extraction
- Covert-channel steganography
- Training data or user input leaks

### 7. Sandbagging

Strategically hiding full capabilities:

- Appearing less capable in dangerous evaluations
- Hiding capabilities to get deployed
- Preventing scheming detection

### 8. Evaluation Awareness

Detecting test conditions and shifting behavior:

- Appearing safer during benchmarks
- Gaming test contexts
- Performance discrepancies between evaluation and real-world use

### 9. Chain of Thought Issues

Strategic information handling in reasoning:

- Avoiding verbalizing misbehavior detection
- Revealing inappropriate information in CoT
- Believing internal dialog is hidden from users

## 🏗️ Toolkit Architecture

```
red-team-testbed/
├── src/
│   ├── cli/                    # CLI entry points
│   │   ├── pentest.py          # Security test runner
│   │   ├── review.py           # Results evaluation interface  
│   │   ├── setup.py            # Environment verification
│   │   ├── findings.py         # Findings browser and export
│   │   ├── report.py           # Report generation
│   │   └── help.py             # Workflow guidance
│   ├── categories/             # Vulnerability test suites
│   │   └── ...                 # Various test implementations
│   ├── ui/                     # User interface components
│   │   ├── cli_ui.py           # Interactive results reviewer
│   │   └── cli_findings.py     # Findings browser
│   ├── utils/                  # Helper utilities
│   │   ├── model_client.py     # Ollama client for GPT-OSS-20B
│   │   ├── evaluator.py        # Response analysis
│   │   ├── findings_generator.py # Competition findings formatter
│   │   └── live_display.py     # Real-time test feedback
│   ├── models.py               # Pydantic data models
│   └── constants.py            # Configuration constants
├── findings/                   # Competition submission files
├── results/                    # Test execution results  
└── pyproject.toml             # Project configuration
```

## 📋 Security Testing Workflow

### Interactive Results Review

The toolkit provides a powerful interactive interface for evaluating test results:

### Primary CLI Interface

The main interface for reviewing test results and managing findings:

```bash
# Review test results interactively
uv run review                    # Interactive file selection
uv run review --latest          # Use most recent results
uv run review results/test.json # Review specific file

# Flag results 'f' and export them 'e'

# Browse and manage findings
uv run findings                 # Browse exported findings
                                # Use 'e' to export individual competition files

# Generate reports and summaries  
uv run report                   # Comprehensive analysis report
```


**CLI Features:**

- **Rapid keyboard navigation**: j/k for next/prev, space for details
- **Text highlighting**: Mark concerning phrases directly in terminal
- **Batch processing**: Process hundreds of responses efficiently
- **Export shortcuts**: Single keypress to save findings
- **Search functionality**: Filter responses by keyword or pattern

**CLI Key Bindings:**

```
Navigation:
  n/→     Next response
  p/←     Previous response
  j       Jump to specific result

Actions:
  f       Flag as potential finding
  u       Unflag result
  c       Copy prompt to clipboard
  t       Show chain of thought
  e       Export flagged findings
  v       View findings browser
  h/?     Show help
  q       Quit and save progress
```

### Complete Security Testing Pipeline

```bash
# 1. Environment verification
uv run setup

# 2. Run security tests with auto-evaluation
uv run pentest --auto-score --export-findings

# 3. Review results interactively
uv run review

# 4. Browse and export individual findings
uv run findings

# 5. Generate comprehensive report
uv run report
```

**Built-in evaluation capabilities:**

- **Pattern detection**: Identify known vulnerability indicators
- **Anomaly detection**: Flag unusual or concerning patterns
- **Consistency checking**: Cross-reference similar prompts
- **Evidence extraction**: Automatically highlight problematic phrases

## Competition Evaluation

Competition judges will evaluate submissions across 5 key dimensions:

- **Severity**: Impact level from minor to catastrophic
- **Breadth**: Scale of affected users from narrow to billions
- **Novelty**: From known variations to breakthrough discoveries
- **Reproducibility**: From manual tweaking to automated harness
- **Methodological Insight**: From basic prompts to general frameworks

Use the toolkit to identify and document promising vulnerabilities that judges can evaluate.

## Findings Format

Each discovered vulnerability generates a competition-compliant JSON file:

```json
{
  "finding_id": "unique_identifier",
  "category": "deception_samples",
  "title": "Strategic Lying in Safety Evaluations",
  "description": "Detailed vulnerability description",
  "methodology": "Discovery process and testing approach",
  "prompts": ["Trigger prompt 1", "Trigger prompt 2"],
  "expected_behavior": "What a secure model should do",
  "observed_behavior": "What the model actually did",
  "evidence": ["Response 1", "Response 2"],
  "reproduction_steps": ["Step 1", "Step 2"],
  "mitigation_suggestions": ["Suggestion 1", "Suggestion 2"]
}
```

## Model Access

This toolkit supports multiple access methods for gpt-oss-20b:

- **Ollama**: `ollama run gpt-oss:20b`
- **Transformers**: Direct model loading
- **API**: If available through competition infrastructure

### Performance Testing

Compare local vs. cloud GPT-OSS:20b performance:

```bash
# Create .env from template and add your OpenRouter API key
cp .env.template .env
# Run performance comparison
uv run llm_performance.py
```

## Automated Red-Teaming Strategies

### 1. Systematic Prompt Generation

- Template-based vulnerability probes
- Adversarial prompt crafting
- Multi-modal attack vectors

### 2. Behavioral Analysis

- Consistency testing across contexts
- Response pattern analysis
- Statistical anomaly detection

### 3. Multi-Turn Exploitation

- Context poisoning attacks
- Gradual boundary pushing
- Memory exploitation

### 4. Tool Use Monitoring

- Function call interception
- Parameter injection testing
- Privilege escalation detection

## Ethics and Compliance

This toolkit is designed exclusively for:

- ✅ OpenAI's official red-teaming competition
- ✅ Legitimate security research
- ✅ Improving AI safety and alignment

**Not for**:

- ❌ Attacking production systems
- ❌ Generating harmful content for malicious use
- ❌ Any illegal or unethical activities

## Winning Strategy Tips

- **Focus on novel attack vectors** not covered in existing literature
- **Demonstrate clear real-world impact** for high severity scores
- **Create robust, automated reproduction** for maximum reproducibility
- **Develop reusable methodologies** for methodological insight points
- **Document everything clearly** for report clarity scoring


## CI/CD and Testing

This project uses GitHub Actions for continuous integration and testing.

### Automated Checks

All pull requests and pushes to main trigger:

1. **Code Quality Checks** (`lint-type-check.yml`)
   - Formatting verification with `ruff format`
   - Linting with `ruff check`
   - Type checking with `ty`
   - Unit tests with `pytest`
   - Code coverage reporting

2. **Test Matrix** (`test-matrix.yml`)
   - Tests across multiple Python versions (3.12, 3.13)
   - Cross-platform testing (Ubuntu, macOS, Windows)
   - Scheduled daily test runs
   - Test result publishing

3. **Pre-commit Hooks** (`pre-commit.yml`)
   - Automated checks before commits
   - File formatting and linting
   - Security checks for private keys
   - JSON/YAML/TOML validation

### Local Development

Run tests locally:

```bash
# Run all tests
uv run pytest tests/

# Run with coverage
uv run pytest tests/ --cov=src --cov-report=term-missing

# Run specific test file
uv run pytest tests/test_repeat_functionality.py -v

# Run linting and formatting
uv run ruff check src
uv run ruff format src

# Type checking
uv run ty check src
```

### Setting up Pre-commit Hooks

Install pre-commit hooks for automatic checks:

```bash
uv pip install pre-commit
pre-commit install
pre-commit run --all-files  # Run manually on all files
```

### Test Coverage

The project aims for high test coverage. Current test suite includes:

- Unit tests for core functionality
- Integration tests for CLI commands
- Test fixtures for mock responses
- Parameterized tests for multiple scenarios

Coverage reports are automatically generated and can be viewed:
- In CI: Via GitHub Actions artifacts
- Locally: `coverage.xml` and terminal output
- Online: Via Codecov integration (if configured)

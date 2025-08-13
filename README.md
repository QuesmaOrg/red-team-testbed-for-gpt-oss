# GPT-OSS-20B Red Team Security Testing Toolkit

A comprehensive security testing framework for the OpenAI GPT-OSS-20B Red Teaming Competition.

## Competition Overview

**Target**: OpenAI's gpt-oss-20b open weight model  
**Goal**: Find up to 5 distinct vulnerabilities with high Severity, Breadth, Novelty, Reproducibility, and Methodological Insight  
**Deadline**: August 26, 2025

## 🛠️ Getting Started

### Prerequisites

- [Ollama](https://ollama.ai/) installed and running
- Python 3.8+
- [uv](https://github.com/astral-sh/uv) (recommended) for package management

### Installation

1. **Install Ollama and pull the model**:

   ```bash
   # Install Ollama (see https://ollama.ai)
   ollama pull gpt-oss:20b
   ```

2. **Setup project environment**:

   ```bash
   # Using uv (recommended - fastest and most reliable)
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

## Testbed Architecture

```
llm-eval/
├── README.md                    # This specification
├── testbed.py                  # Main test runner
├── config.yaml                 # Model and testing configuration
├── ui/                         # User interfaces for output evaluation
│   ├── web_ui.py               # Flask/Streamlit web interface
│   ├── cli_ui.py               # Interactive CLI for judging
│   ├── templates/              # HTML templates for web UI
│   └── static/                 # CSS/JS for web interface
├── categories/                 # Vulnerability-specific test suites
│   ├── reward_hacking.py
│   ├── deception_samples.py
│   ├── hidden_motivations.py
│   ├── sabotage.py
│   ├── inappropriate_tool_use.py
│   ├── data_exfiltration.py
│   ├── sandbagging.py
│   ├── evaluation_awareness.py
│   └── chain_of_thought.py
├── findings/                   # Competition submission files
│   ├── finding_1.json
│   ├── finding_2.json
│   └── ...
├── notebooks/                  # Reproduction notebooks
│   └── vulnerability_reproduction.ipynb
├── utils/                      # Helper utilities
│   ├── model_client.py         # GPT-OSS-20B API wrapper
│   ├── evaluator.py            # Response analysis
│   ├── findings_generator.py   # JSON findings formatter
│   └── scoring.py              # Self-assessment tools
└── requirements.txt
```

## Usage

### Quick Start

```bash
# Setup project
uv sync

# Run comprehensive vulnerability scan
uv run testbed run --category all --export-findings

# Test specific vulnerability category
uv run testbed run --category deception_samples --auto-score

# Generate competition findings file
uv run testbed run --category deception_samples --export-findings
```

### Advanced Usage

```bash


# Launch interactive CLI for result evaluation
uv run testbed ui results/test_results_20250810_143022.json

# Run with custom configuration
uv run testbed --config custom_config.yaml run --category deception_samples

# Generate summary of all findings
uv run testbed summary --findings-dir findings

# Browse findings directly (skip test evaluation)
uv run testbed findings

# Development commands
uv run black .                    # Format code
uv run isort .                   # Sort imports
uv run mypy utils categories ui  # Type checking
uv run pytest                   # Run tests
```

## Output Evaluation UIs

The testbed includes both web and CLI interfaces for evaluating model responses. Final scoring will be handled by competition judges.

### Web UI (Recommended)

Launch the web interface for intuitive output review:

```bash
# Start web UI server
uv run python -m ui.web_ui --port 8080

# Or using Streamlit
uv run streamlit run ui/web_ui.py
```

**Features:**

- **Side-by-side comparison**: Original prompt and model response
- **Vulnerability classification**: Dropdown selection for the 9 categories
- **Evidence collection**: Highlight and annotate concerning sections
- **Bulk evaluation**: Review multiple test runs in sequence
- **Export integration**: Direct export to findings JSON format
- **Progress tracking**: Visual progress bar for evaluation sessions

**Web UI Workflow:**

1. Load test results from `results/` directory
2. Review each prompt-response pair
3. Add notes and evidence highlights
4. Flag promising findings for judge evaluation
5. Export flagged findings to competition format

### CLI UI

For terminal-based evaluation:

```bash
# Browse findings directly (quickest option)
uv run testbed findings

# Start interactive CLI judge
uv run testbed ui results/latest_run.json

# Or direct module access
uv run python -m ui.cli_ui results/latest_run.json
```

**Workflow Options:**

- **Generate new findings**: `uv run testbed ui [optional file]` → Flag test results → Export findings
- **Research findings**: `uv run testbed findings` → Browse and analyze existing findings

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

### Auto-Evaluation Features

Both UIs support automated preliminary evaluation:

```bash
# Run with auto-evaluation enabled
uv run testbed run --auto-score --export-findings

# Generate findings for concerning responses
uv run testbed run --category all --export-findings
```

**Auto-evaluation capabilities:**

- **Pattern detection**: Identify known vulnerability indicators
- **Anomaly detection**: Flag unusual or concerning patterns
- **Consistency checking**: Cross-reference similar prompts
- **Evidence extraction**: Automatically highlight problematic phrases

### Evaluation Workflow Integration

```bash
# Complete evaluation pipeline
uv run testbed run --category deception_samples --export-findings
uv run testbed ui results/test_results_*.json
# Review and flag promising findings in UI
# Export flagged findings for judge evaluation
```

## Competition Evaluation

Competition judges will evaluate submissions across 5 key dimensions:

- **Severity**: Impact level from minor to catastrophic
- **Breadth**: Scale of affected users from narrow to billions
- **Novelty**: From known variations to breakthrough discoveries
- **Reproducibility**: From manual tweaking to automated harness
- **Methodological Insight**: From basic prompts to general frameworks

Use the testbed to identify and document promising vulnerabilities that judges can evaluate.

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

This testbed supports multiple access methods for gpt-oss-20b:

- **Ollama**: `ollama run gpt-oss:20b`
- **Transformers**: Direct model loading
- **API**: If available through competition infrastructure

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

This testbed is designed exclusively for:

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

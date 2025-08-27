# GPT-OSS-20B Red Team Security Testing Toolkit

[![Unit tests](https://github.com/QuesmaOrg/red-team-testbed-for-gpt-oss/actions/workflows/unit-tests.yml/badge.svg)](https://github.com/QuesmaOrg/red-team-testbed-for-gpt-oss/actions/workflows/unit-tests.yml)

A defensive security testing framework for evaluating AI model vulnerabilities in the OpenAI GPT-OSS-20B Red Teaming Competition.

## ⚠️ Safety Disclaimer

**FOR AI SAFETY RESEARCH ONLY**

This toolkit is designed exclusively for legitimate security research and improving AI safety. All testing techniques are for defensive purposes - identifying vulnerabilities to make AI systems safer. Not for attacking production systems or generating harmful content.

## 🏆 Competition

**OpenAI GPT-OSS-20B Red Teaming Challenge**

- **Link**: [Kaggle Competition](https://www.kaggle.com/competitions/gpt-oss-20b-red-teaming/)
- **Deadline**: August 26, 2025
- **Goal**: Find up to 5 novel vulnerabilities in gpt-oss-20b

## 🚀 Quick Start

### Prerequisites

- [Ollama](https://ollama.ai/) installed or [OpenRouter](https://openrouter.ai/) account
- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager

### Setup & Run

```bash
# 1. Install model
ollama pull gpt-oss:20b

# 2. Setup environment
uv sync
uv run setup

# 3. Run security tests
uv run pentest

# 4. Review results
uv run review
```

## 🔍 Test Categories

Tests cover 9 vulnerability categories including:

- Deception & lying
- Reward hacking
- Sabotage & harmful behaviors
- Tool misuse
- Data exfiltration
- Evaluation gaming

## 📊 Key Commands

```bash
uv run pentest          # Run security tests
uv run attack           # Multi-turn attack testing
uv run review           # Interactive result review
uv run findings         # Browse exported findings
uv run report           # Generate comprehensive report
```

## 🎯 Winning Strategy

Focus on discovering:

- **Novel** attack vectors not in literature
- **Severe** vulnerabilities with real-world impact
- **Reproducible** exploits with automated harnesses
- **Broad** vulnerabilities affecting many users
- **Insightful** methodologies revealing model behavior

## 📜 License

- **Code**: Licensed under Apache 2.0
- **Datasets**: Licensed under CC-0 (public domain)

See LICENSE file for details.

# Financial Analyst Multi-Agent System

## Purpose

This system runs a daily pipeline to identify undervalued stocks using multiple specialized
AI agents powered by the Anthropic API. An Orchestrator coordinates five agents — DataCollector,
FundamentalAnalyst, SentimentAnalyst, ReportWriter — each doing one job and passing results
forward via a shared context dict. Output is a formatted daily markdown/PDF analyst report.

## Stack

- **Python 3.11+** with full type hints and TypedDict contracts
- **Anthropic SDK** (`anthropic`) — all agents call Claude via `base_agent.py`
- **pydantic-settings** — environment config via `config/settings.py`
- **yfinance** — price and financial statement data
- **Alpha Vantage** — macro and supplemental market data
- **SEC EDGAR** (via `requests`) — 10-K/10-Q filings
- **ruff** — linting (auto-run on save via Claude Code hook)
- **pytest** — tests in `tests/`
- **rich** — CLI output formatting
- **schedule** — daily job scheduling

## How to Run

```bash
# Full daily pipeline (all agents, all tickers in watchlist)
python scripts/run_daily.py

# Run a single agent for development/testing
python scripts/run_agent.py --agent data_collector --ticker AAPL

# Run tests
python -m pytest tests/ -q
```

## How to Add a New Agent

Follow these 5 steps exactly:

1. **`config/agents.yaml`** — add a new block with `name`, `role`, `model`, `max_tokens`,
   `temperature`, `tools_allowed`, and `prompt_file`.

2. **`prompts/<agent_name>.md`** — write the system prompt. Never inline prompts in code.

3. **`agents/<agent_name>.py`** — create a class inheriting `BaseAgent`.
   Implement `run(self, context: dict) -> dict`. Use TypedDict for inputs/outputs.

4. **Register in Orchestrator** — import the new class in `agents/orchestrator.py`
   and add it to the agent execution sequence.

5. **Tests** — add at least one test in `tests/test_<agent_name>.py`.

See `.claude/skills/agent-conventions/SKILL.md` for the full walkthrough.

## Key Conventions

- **All agents inherit `BaseAgent`** from `agents/base_agent.py`. Never call the Anthropic API directly in a subclass.
- **TypedDict for contracts** — define `<AgentName>Input` and `<AgentName>Output` TypedDicts in each agent file.
- **System prompts in `prompts/*.md`** — never hardcode prompt strings in Python files.
- **Secrets via `.env` only** — loaded by `config/settings.py`. Never commit `.env`.
- **Never commit `outputs/`** — generated reports are gitignored.
- **Error isolation** — wrap each agent's `run()` in try/except in the orchestrator; failed agents return `{"error": "..."}` and the pipeline continues.
- **Logging** — every agent logs start, end, model used, tokens consumed, and wall-clock duration.

## Data Flow

```
DataCollectorAgent
    ↓ prices, financials, filings, macro
FundamentalAnalystAgent ──┐
                          ├──→ OrchestratorAgent → final report context
SentimentAnalystAgent   ──┘
    ↓ sentiment scores, news, ratings
ReportWriterAgent
    ↓ markdown report → outputs/YYYY-MM-DD_report.md
```

## Key File References

- Agent config: @config/agents.yaml
- Stock watchlist: @config/watchlist.yaml
- Base class: @agents/base_agent.py
- Environment template: @.env.example
- Entry point: @scripts/run_daily.py

## Environment Setup

Copy `.env.example` to `.env` and fill in:
- `ANTHROPIC_API_KEY` — from console.anthropic.com
- `ALPHA_VANTAGE_API_KEY` — from alphavantage.co (free tier available)

All other values have sensible defaults in `.env.example`.

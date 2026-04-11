# Financial Analyst Multi-Agent System

An AI-powered daily pipeline that identifies undervalued stocks using five specialized
Claude agents coordinated by an Orchestrator. Each agent does one job and passes
structured results forward via a shared context dictionary.

## Quickstart

```bash
# 1. Clone
git clone <repo-url>
cd financial-analyst

# 2. Set up environment
cp .env.example .env
# Edit .env — fill in ANTHROPIC_API_KEY and ALPHA_VANTAGE_API_KEY

# 3. Install dependencies (Python 3.11+ required)
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 4. Start the web UI (recommended)
python web/app.py
# → Opens at http://localhost:8000
# Use Manual mode to analyse specific tickers, or Discover mode to screen
# US (S&P 500 / Nasdaq 100) or Taiwan (TWSE + OTC) for undervalued stocks.

# 5. Run the full daily pipeline (headless / scheduled)
python scripts/run_daily.py

# 6. (Dev) Run a single agent
python scripts/run_agent.py --agent data_collector --ticker AAPL
```

Reports are written to `outputs/YYYY-MM-DD_HH-MM-SS_analyst_report.md` and are
viewable in the web UI under the **Report** tab or the **Past Reports** sidebar.

## Web UI

```bash
python web/app.py
```

| URL | Description |
|-----|-------------|
| `http://localhost:8000` | Main UI |
| `http://localhost:8000/api/reports` | JSON list of saved reports |
| `http://localhost:8000/api/reports/<filename>` | Fetch a specific report |

**Modes:**
- **Manual** — enter up to 10 tickers and run the full pipeline immediately.
- **Discover** — select a country (🇺🇸 US or 🇹🇼 Taiwan), optionally filter by
  sector and market cap, then let the screener rank stocks by value score before
  running the full pipeline on the top N picks.

> The server uses `uvicorn` under the hood. For production or always-on use:
> ```bash
> uvicorn web.app:app --host 0.0.0.0 --port 8000
> ```

## Agent Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        OrchestratorAgent                        │
│          (coordinates pipeline, assembles final report)         │
└──────────────────────────┬──────────────────────────────────────┘
                           │ context dict
           ┌───────────────▼───────────────┐
           │      DataCollectorAgent        │
           │  prices · financials · filings │
           └──────────┬────────────────────┘
                      │ raw_data
          ┌───────────┴────────────┐
          │                        │
┌─────────▼─────────┐   ┌─────────▼──────────┐
│ FundamentalAnalyst│   │  SentimentAnalyst   │
│ P/E · DCF · ratios│   │ news · ratings ·    │
│                   │   │ insider activity    │
└─────────┬─────────┘   └─────────┬──────────┘
          │                        │
          └───────────┬────────────┘
                      │ analysis dicts
           ┌──────────▼────────────┐
           │    ReportWriterAgent   │
           │  markdown daily report │
           └───────────────────────┘
```

## How to Add a New Agent

1. **`config/agents.yaml`** — add a new block with name, role, model_env_var, max_tokens, temperature, tools_allowed, prompt_file.
2. **`prompts/<name>.md`** — write the system prompt.
3. **`agents/<name>.py`** — create a class inheriting `BaseAgent`, implement `run(context)`.
4. **`agents/orchestrator.py`** — import and wire into the execution sequence.
5. **`tests/test_<name>.py`** — add at least one test.

See `.claude/skills/agent-conventions/SKILL.md` for the full step-by-step.

## How to Edit the Watchlist

Open `config/watchlist.yaml` and add/remove tickers:

```yaml
watchlist:
  - ticker: NVDA
    name: NVIDIA Corporation
    sector: Technology
    priority: high
```

The pipeline reads this file on every run — no code changes needed.

## Project Structure

```
financial-analyst/
├── CLAUDE.md                  # Claude Code project memory
├── config/
│   ├── settings.py            # Pydantic settings (loads .env)
│   ├── agents.yaml            # Agent model/token/tool config
│   └── watchlist.yaml         # Tickers to analyze daily
├── agents/
│   ├── base_agent.py          # Abstract base — all agents inherit this
│   ├── orchestrator.py
│   ├── data_collector.py
│   ├── fundamental_analyst.py
│   ├── sentiment_analyst.py
│   └── report_writer.py
├── tools/                     # Standalone tool functions (no Claude calls)
│   ├── market_data.py         # yfinance + Alpha Vantage
│   ├── sec_filings.py         # SEC EDGAR
│   ├── web_search.py
│   └── calculations.py        # P/E, DCF, ratios (pure functions)
├── prompts/                   # System prompts (*.md — never inline in code)
├── outputs/                   # Generated reports (gitignored)
├── tests/
└── scripts/
    ├── run_daily.py           # Full pipeline entry point
    └── run_agent.py           # Single-agent dev runner
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | From [console.anthropic.com](https://console.anthropic.com) |
| `ALPHA_VANTAGE_API_KEY` | Recommended | Free tier at alphavantage.co |
| `MODEL_ORCHESTRATOR` | No | Default: `claude-opus-4-6` |
| `MODEL_ANALYST` | No | Default: `claude-sonnet-4-6` |
| `MODEL_WRITER` | No | Default: `claude-sonnet-4-6` |
| `LOG_LEVEL` | No | Default: `INFO` |
| `REPORT_OUTPUT_DIR` | No | Default: `outputs` |

## Disclaimer

This system is for research and educational purposes only. AI-generated financial
analysis is not investment advice. Always consult a qualified financial advisor.

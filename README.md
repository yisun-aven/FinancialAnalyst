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

# 3. Install Python dependencies (Python 3.11+ required)
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 4. Install frontend dependencies (Node.js 20.19+ required)
cd frontend && npm install && cd ..

# 5. Start both servers (two separate terminals)

#   Terminal 1 — FastAPI backend  (scripts/serve.py wraps uvicorn)
python scripts/serve.py
# → API running at http://localhost:8000
# → Swagger docs at http://localhost:8000/docs

#   Terminal 2 — React frontend  (Vite dev server, proxies /api + /ws to :8000)
cd frontend && npm run dev
# → UI running at http://localhost:5173

# 6. Run the full daily pipeline (headless / scheduled)
python scripts/run_daily.py

# 7. (Dev) Run a single agent
python scripts/run_agent.py --agent data_collector --ticker AAPL
```

Reports are written to `outputs/YYYY-MM-DD_HH-MM-SS_analyst_report.md` and are
viewable in the web UI under the **Report** tab.

## Web UI

The frontend is a React + TypeScript + Ant Design app (`frontend/`) that communicates
with the FastAPI backend (`web/app.py`) via REST and WebSocket.

| Server | URL | Description |
|--------|-----|-------------|
| Frontend (Vite) | `http://localhost:5173` | React UI (dev) |
| Backend (FastAPI) | `http://localhost:8000` | API + WebSocket |
| Backend API docs | `http://localhost:8000/docs` | Swagger UI |

**Modes:**
- **Manual** — enter tickers (type + Enter, or pick from quick-add), click Analyse.
- **Discover** — choose a universe (S&P 500, Nasdaq 100, Global Large Cap, etc.),
  set filters (sector, region, min market cap, top N), click Screen & Analyse.

**Tabs:**
- **Live Feed** — real-time WebSocket events from each agent as the pipeline runs.
- **Screen** — sortable table of all screened stocks with scores and key ratios.
- **Results** — per-ticker cards with valuation metrics, target price gauge, growth,
  peer comparison, technical indicators, sentiment, and full agent reasoning.
- **Report** — rendered markdown analyst report; load any past report from the dropdown.

**Sidebar — Past Runs** — click any past run to restore its results instantly.

### Production build

```bash
cd frontend && npm run build
# Outputs to frontend/dist/ — can be served by any static host or FastAPI StaticFiles
```

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
│   ├── growth_analyst.py
│   ├── peer_comparison.py
│   ├── technical_analyst.py
│   ├── sentiment_analyst.py
│   └── report_writer.py
├── tools/                     # Standalone tool functions (no Claude calls)
│   ├── market_data.py         # yfinance + Alpha Vantage
│   ├── sec_filings.py         # SEC EDGAR
│   ├── screener.py            # Universe screening + value scoring
│   ├── web_search.py
│   └── calculations.py        # P/E, DCF, ratios (pure functions)
├── prompts/                   # System prompts (*.md — never inline in code)
├── web/
│   └── app.py                 # FastAPI backend (REST + WebSocket)
├── frontend/                  # React + TypeScript + Ant Design UI
│   ├── src/
│   │   ├── types/             # TypeScript types for WS events and REST
│   │   ├── api/               # fetch wrappers + useWebSocket hook
│   │   ├── store/             # Zustand pipeline state
│   │   └── components/        # layout, sidebar, feed, screen, results, report
│   └── vite.config.ts         # Proxies /api and /ws to backend
├── outputs/                   # Generated reports (gitignored)
├── tests/
└── scripts/
    ├── run_daily.py           # Full pipeline entry point
    ├── run_agent.py           # Single-agent dev runner
    └── serve.py               # uvicorn launcher with hot-reload
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

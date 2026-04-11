# Skill: Adding a New Agent

Use this skill whenever you need to add a new specialist agent to the Financial Analyst pipeline.
Follow all 5 steps in order. Do not skip any step.

## Step 1 — `config/agents.yaml`

Add a new block under the `agents:` key:

```yaml
my_new_agent:
  name: my_new_agent
  role: "One-line description of what this agent does"
  model_env_var: MODEL_ANALYST        # or MODEL_ORCHESTRATOR / MODEL_WRITER
  max_tokens: 4096
  temperature: 0.1
  tools_allowed:
    - tool_function_name              # functions from tools/ this agent may call
  prompt_file: prompts/my_new_agent.md
```

## Step 2 — `prompts/my_new_agent.md`

Write the system prompt. Structure it as:
- **Role statement**: one sentence on who the agent is
- **Responsibilities**: bullet list of tasks
- **Output format**: exact keys and types the agent must return (JSON schema or TypedDict)

Never put the system prompt inline in Python code.

## Step 3 — `agents/my_new_agent.py`

Create the agent class:

```python
from __future__ import annotations
from typing import Any, TypedDict
from agents.base_agent import BaseAgent

class MyNewAgentInput(TypedDict):
    tickers: list[str]
    # ... other keys this agent reads from context

class MyNewAgentOutput(TypedDict):
    my_new_agent_results: dict[str, Any]  # keyed by ticker

class MyNewAgent(BaseAgent):
    """What this agent does, what it reads, what it writes.

    Expected context keys (MyNewAgentInput): ...
    Adds to context (MyNewAgentOutput): ...
    """

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        t0 = self._log_run_start()
        try:
            # 1. Extract inputs from context
            # 2. Call tools from tools/ as needed
            # 3. Build messages list and call self.call_claude(messages)
            # 4. Parse response and populate context
            pass
        except Exception as exc:
            context["my_new_agent_error"] = str(exc)
        finally:
            self._log_run_end(t0)
        return context
```

## Step 4 — Register in Orchestrator (`agents/orchestrator.py`)

1. Import the new class at the top of the file.
2. Instantiate it with its config block from `agents.yaml`.
3. Add it to the execution sequence in `OrchestratorAgent.run()`.
4. Pass the correct context keys in and read the correct output keys out.

## Step 5 — Tests

Create `tests/test_my_new_agent.py`:
- Test the `run()` method with a mocked `call_claude()` (patch `BaseAgent.call_claude`)
- Test that missing required context keys raise a `KeyError`
- Test that errors are caught and surfaced in context rather than propagated

## Conventions to Remember

- All inputs/outputs use TypedDict — never plain `dict` with string comments.
- Errors must never crash the pipeline; catch in `run()` and write to `context["<name>_error"]`.
- Log start and end of every `run()` call via `_log_run_start()` / `_log_run_end()`.
- Never hardcode model names, paths, or API keys — always read from `self.settings`.

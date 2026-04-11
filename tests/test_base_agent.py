"""Tests for agents/base_agent.py.

Uses a minimal concrete subclass so we can test BaseAgent behaviour
without mocking the entire Anthropic SDK upfront.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from agents.base_agent import BaseAgent
from config.settings import Settings


# ── Minimal concrete subclass for testing ────────────────────────────────────

class _StubAgent(BaseAgent):
    """Concrete agent used only in tests — returns a fixed output."""

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        return {"stub": True}


def _make_agent(prompt_file: Path | None = None) -> _StubAgent:
    settings = MagicMock(spec=Settings)
    settings.anthropic_api_key = "test-key"
    settings.model_analyst = "claude-sonnet-4-6"

    config: dict[str, Any] = {
        "name": "stub",
        "model_env_var": "model_analyst",
        "max_tokens": 1024,
        "temperature": 0.1,
        "prompt_file": str(prompt_file or "prompts/stub.md"),
    }
    with patch("agents.base_agent.anthropic.Anthropic"):
        return _StubAgent(config=config, settings=settings)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestBaseAgentInit:
    def test_name_set_from_config(self) -> None:
        agent = _make_agent()
        assert agent.name == "stub"

    def test_max_tokens_set_from_config(self) -> None:
        agent = _make_agent()
        assert agent.max_tokens == 1024


class TestLoadPrompt:
    def test_raises_if_prompt_file_missing(self, tmp_path: Path) -> None:
        missing = tmp_path / "does_not_exist.md"
        agent = _make_agent(prompt_file=missing)
        with pytest.raises(FileNotFoundError):
            agent.load_prompt()

    def test_loads_prompt_text(self, tmp_path: Path) -> None:
        prompt_file = tmp_path / "stub.md"
        prompt_file.write_text("You are a stub agent.")
        agent = _make_agent(prompt_file=prompt_file)
        assert agent.load_prompt() == "You are a stub agent."

    def test_prompt_cached_after_first_load(self, tmp_path: Path) -> None:
        prompt_file = tmp_path / "stub.md"
        prompt_file.write_text("cached")
        agent = _make_agent(prompt_file=prompt_file)
        agent.load_prompt()
        # Modify file — second call should still return cached value
        prompt_file.write_text("changed")
        assert agent.load_prompt() == "cached"


class TestStubAgentRun:
    def test_run_returns_dict(self) -> None:
        agent = _make_agent()
        result = agent.run({})
        assert isinstance(result, dict)
        assert result["stub"] is True

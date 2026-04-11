"""Base class for all Financial Analyst agents."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import anthropic

from config.settings import Settings

logger = logging.getLogger(__name__)

_MAX_RETRIES = 5
_RETRY_DELAY_SECONDS = 15.0  # base delay; multiplied by attempt for exponential backoff


class BaseAgent(ABC):
    """Abstract base for all pipeline agents.

    Every agent calls the Anthropic API exclusively via `call_claude()`,
    loads its system prompt via `load_prompt()`, and emits structured
    events via `_emit()` so the web UI can display live progress.
    """

    def __init__(
        self,
        config: dict[str, Any],
        settings: Settings,
        event_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.config = config
        self.settings = settings
        self.name: str = config["name"]
        self.prompt_file: Path = Path(config["prompt_file"])
        self.max_tokens: int = config.get("max_tokens", 4096)
        self.temperature: float = config.get("temperature", 0.1)
        self._event_callback = event_callback

        if "model" in config and not str(config["model"]).startswith("MODEL_"):
            self.model: str = config["model"]
        else:
            model_env_var: str = config.get("model_env_var", "MODEL_ANALYST")
            self.model = getattr(settings, model_env_var.lower(), settings.model_analyst)

        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._system_prompt: str | None = None

    # ── Event emission ────────────────────────────────────────────────────────

    def _emit(
        self,
        event_type: str,
        data: dict[str, Any] | None = None,
        ticker: str | None = None,
        message: str = "",
    ) -> None:
        """Fire a structured event to the registered callback (no-op if none)."""
        if self._event_callback is None:
            return
        self._event_callback({
            "type": event_type,
            "agent": self.name,
            "ticker": ticker,
            "message": message,
            "data": data or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    # ── Abstract interface ────────────────────────────────────────────────────

    @abstractmethod
    def run(self, context: dict[str, Any]) -> dict[str, Any]: ...

    # ── Prompt loading ────────────────────────────────────────────────────────

    def load_prompt(self) -> str:
        if self._system_prompt is None:
            if not self.prompt_file.exists():
                raise FileNotFoundError(f"[{self.name}] Prompt file not found: {self.prompt_file}")
            self._system_prompt = self.prompt_file.read_text(encoding="utf-8")
        return self._system_prompt

    # ── Anthropic API wrapper ─────────────────────────────────────────────────

    def call_claude(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> str:
        """Call the Anthropic Messages API with retry logic, tool-use loop, and event emission."""
        system_prompt = system if system is not None else self.load_prompt()
        effective_max_tokens = max_tokens if max_tokens is not None else self.max_tokens
        effective_temperature = temperature if temperature is not None else self.temperature

        logger.info("[%s] Calling Claude | model=%s tools=%s", self.name, self.model,
                    [t.get("name") for t in tools] if tools else "none")

        self._emit("claude_call_start", {
            "model": self.model,
            "max_tokens": effective_max_tokens,
            "has_tools": bool(tools),
        }, message=f"Calling {self.model}" + (" + web_search" if tools else ""))

        last_error: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                t0 = time.perf_counter()
                current_messages = list(messages)

                for _turn in range(8):
                    kwargs: dict[str, Any] = dict(
                        model=self.model,
                        max_tokens=effective_max_tokens,
                        temperature=effective_temperature,
                        system=system_prompt,
                        messages=current_messages,
                    )
                    if tools:
                        kwargs["tools"] = tools

                    response = self._client.messages.create(**kwargs)  # type: ignore[arg-type]

                    if response.stop_reason == "end_turn":
                        break
                    if response.stop_reason == "tool_use":
                        current_messages.append({"role": "assistant", "content": response.content})
                        current_messages.append({"role": "user", "content": [
                            {"type": "tool_result", "tool_use_id": b.id, "content": ""}
                            for b in response.content if b.type == "tool_use"
                        ]})
                    else:
                        break

                elapsed = time.perf_counter() - t0
                usage = response.usage
                logger.info("[%s] Response | in=%d out=%d %.2fs",
                            self.name, usage.input_tokens, usage.output_tokens, elapsed)

                self._emit("claude_call_complete", {
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "duration": round(elapsed, 2),
                }, message=f"{usage.input_tokens + usage.output_tokens:,} tokens in {elapsed:.1f}s")

                return "\n".join(
                    b.text for b in response.content if hasattr(b, "text") and b.text
                )

            except anthropic.RateLimitError as exc:
                wait = _RETRY_DELAY_SECONDS * (2 ** (attempt - 1))  # 15s, 30s, 60s, 120s, 240s
                logger.warning("[%s] Rate limit (attempt %d/%d) — waiting %.0fs",
                               self.name, attempt, _MAX_RETRIES, wait)
                self._emit("rate_limit_wait", {"attempt": attempt, "wait_seconds": wait},
                           message=f"Rate limited — retrying in {wait:.0f}s…")
                last_error = exc
                time.sleep(wait)
            except anthropic.APIStatusError as exc:
                logger.error("[%s] API error %d: %s", self.name, exc.status_code, exc.message)
                raise

        raise RuntimeError(f"[{self.name}] Claude call failed after {_MAX_RETRIES} retries.") from last_error

    # ── Run lifecycle helpers ─────────────────────────────────────────────────

    def _log_run_start(self, ticker: str | None = None) -> float:
        label = f" ticker={ticker}" if ticker else ""
        logger.info("[%s] Starting run%s", self.name, label)
        self._emit("agent_start", {"name": self.name}, ticker=ticker, message=f"Starting {self.name}")
        return time.perf_counter()

    def _log_run_end(self, t0: float, ticker: str | None = None) -> None:
        elapsed = time.perf_counter() - t0
        label = f" ticker={ticker}" if ticker else ""
        logger.info("[%s] Run complete%s | %.2fs", self.name, label, elapsed)
        self._emit("agent_complete", {"duration": round(elapsed, 2)}, ticker=ticker,
                   message=f"Done in {elapsed:.1f}s")

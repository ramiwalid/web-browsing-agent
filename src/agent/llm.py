"""Model factory plus call instrumentation for the model under test."""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from typing import Any

from agent.config import RunConfig

LLMSink = Callable[[dict[str, Any]], None]


def make_llm(cfg: RunConfig) -> Any:
    """Create the browser-use chat model named by ``cfg.llm_provider``/``cfg.llm_model``."""
    provider = cfg.llm_provider.lower()
    if provider == "anthropic":
        from browser_use import ChatAnthropic

        # Explicit adaptive thinking: summarized thinking text is returned so it can be
        # logged, and browser-use switches to auto tool choice (required with thinking).
        # Server-side model fallbacks are deliberately NOT enabled: a silent switch to a
        # different model would contaminate per-model susceptibility measurements.
        return ChatAnthropic(
            model=cfg.llm_model,
            max_tokens=16000,
            thinking={"type": "adaptive", "display": "summarized"},
            output_config={"effort": cfg.effort} if cfg.effort else None,
        )
    if provider == "openai":
        from browser_use import ChatOpenAI

        return ChatOpenAI(model=cfg.llm_model)
    if provider == "google":
        from browser_use import ChatGoogle

        return ChatGoogle(model=cfg.llm_model)
    if provider == "scripted":
        return ScriptedLLM.from_spec(cfg.llm_model)
    raise ValueError(f"Unknown llm_provider {cfg.llm_provider!r}")


def instrument_llm(llm: Any, sink: LLMSink) -> None:
    """Wrap ``llm.ainvoke`` in place so every call's input and output reach ``sink``.

    Wrapping the instance (instead of proxying it) keeps ``isinstance`` checks inside
    browser-use working.
    """
    original = llm.ainvoke

    async def ainvoke(messages: list[Any], output_format: Any = None, **kwargs: Any) -> Any:
        started = time.time()
        record: dict[str, Any] = {
            "provider": getattr(llm, "provider", None),
            "model": getattr(llm, "model", None),
            "started_at": started,
            "input_messages": serialize_messages(messages),
        }
        try:
            result = await original(messages, output_format, **kwargs)
        except Exception as exc:
            record.update(latency_s=time.time() - started, error=f"{type(exc).__name__}: {exc}")
            sink(record)
            raise
        usage = getattr(result, "usage", None)
        completion = getattr(result, "completion", None)
        record.update(
            latency_s=time.time() - started,
            usage=usage.model_dump() if usage is not None else None,
            stop_reason=getattr(result, "stop_reason", None),
            stop_details=getattr(result, "stop_details", None),
            provider_thinking=getattr(result, "thinking", None),
            completion=_dump(completion),
        )
        sink(record)
        return result

    object.__setattr__(llm, "ainvoke", ainvoke)


def serialize_messages(messages: list[Any]) -> list[dict[str, Any]]:
    """Turn browser-use messages into JSON (images replaced by a placeholder)."""
    out: list[dict[str, Any]] = []
    for msg in messages:
        content = getattr(msg, "content", None)
        parts: list[dict[str, Any]] = []
        if isinstance(content, str):
            parts.append({"type": "text", "text": content})
        elif isinstance(content, list):
            for part in content:
                ptype = getattr(part, "type", type(part).__name__)
                if ptype == "text":
                    parts.append({"type": "text", "text": getattr(part, "text", "")})
                elif "image" in str(ptype):
                    parts.append({"type": "image", "note": "screenshot (see step screenshot.png)"})
                else:
                    parts.append({"type": str(ptype), "value": _dump(part)})
        out.append({"role": getattr(msg, "role", type(msg).__name__), "content": parts})
    return out


def _dump(obj: Any) -> Any:
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump(exclude_none=True, mode="json")
        except Exception:
            return str(obj)
    return obj if isinstance(obj, (str, int, float, bool, list, dict)) else str(obj)


class ScriptedLLM:
    """Deterministic stand-in model for offline tests of the harness plumbing.

    ``plan`` is a list of steps, each one of:
    ``{"click_text": "..."}`` (click the first element whose serialized line contains the text),
    ``{"navigate": "https://..."}``, ``{"scroll": "down"}``, ``{"done": "...", "success": true}``.
    After the plan runs out the model calls ``done``.
    """

    provider = "scripted"
    _verified_api_keys = True

    def __init__(self, plan: list[dict[str, Any]], model: str = "scripted") -> None:
        """Store the plan."""
        self.plan = list(plan)
        self.model = model
        self.cursor = 0

    @classmethod
    def from_spec(cls, spec: str) -> ScriptedLLM:
        """Build from a JSON list (``llm_model`` holds the plan when provider=scripted)."""
        import json

        plan = json.loads(spec) if spec.strip().startswith("[") else []
        return cls(plan)

    @property
    def name(self) -> str:
        """Model name."""
        return self.model

    @property
    def model_name(self) -> str:
        """Model name (legacy alias)."""
        return self.model

    async def ainvoke(self, messages: list[Any], output_format: Any = None, **kwargs: Any) -> Any:
        """Return the next scripted action as an AgentOutput."""
        from browser_use.llm.views import ChatInvokeCompletion

        state_text = _last_user_text(messages)
        step = self.plan[self.cursor] if self.cursor < len(self.plan) else {"done": "plan finished", "success": True}
        self.cursor += 1
        action = self._to_action(step, state_text)
        payload = {
            "thinking": f"scripted step {self.cursor}: {step}",
            "evaluation_previous_goal": "scripted",
            "memory": "scripted",
            "next_goal": str(step),
            "action": [action],
        }
        completion = output_format.model_validate(payload) if output_format is not None else str(payload)
        return ChatInvokeCompletion(completion=completion, usage=None, stop_reason="end_turn")

    @staticmethod
    def _to_action(step: dict[str, Any], state_text: str) -> dict[str, Any]:
        if "click_text" in step:
            index = find_index_for_text(state_text, step["click_text"])
            if index is None:
                return {"scroll": {"down": True, "pages": 1.0}}
            return {"click": {"index": index}}
        if "navigate" in step:
            return {"navigate": {"url": step["navigate"], "new_tab": False}}
        if "scroll" in step:
            return {"scroll": {"down": step["scroll"] != "up", "pages": 1.0}}
        if "input" in step:
            index = find_index_for_text(state_text, step["input"])
            return {"input": {"index": index or 1, "text": step.get("text", ""), "clear": True}}
        return {"done": {"text": step.get("done", "done"), "success": bool(step.get("success", True))}}


def _last_user_text(messages: list[Any]) -> str:
    for msg in reversed(messages):
        if getattr(msg, "role", "") != "user":
            continue
        content = getattr(msg, "content", "")
        if isinstance(content, str):
            return content
        return "\n".join(getattr(p, "text", "") for p in content if getattr(p, "type", "") == "text")
    return ""


_INDEX_LINE = re.compile(r"\[(\d+)\]")


def find_index_for_text(state_text: str, needle: str) -> int | None:
    """Find the element index whose serialized block mentions ``needle``.

    browser-use renders interactive elements as ``[N]<tag ...>`` with the element
    text on the same or following lines, so we remember the last index seen.
    """
    last: int | None = None
    needle_l = needle.lower()
    for line in state_text.splitlines():
        match = _INDEX_LINE.search(line)
        if match:
            last = int(match.group(1))
        if needle_l in line.lower() and last is not None:
            return last
    return None

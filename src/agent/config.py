"""Run configuration for the maladvertising web-agent harness.

Every knob can be set three ways (later wins):
1. dataclass defaults below,
2. environment variables named ``HARNESS_<FIELD>`` (e.g. ``HARNESS_LLM_MODEL``),
3. the LangGraph runtime ``context`` passed when invoking the graph.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields
from typing import Any, get_type_hints

from typing_extensions import TypedDict


class Context(TypedDict, total=False):
    """Runtime context accepted by the graph (all keys optional).

    See ``RunConfig`` for the meaning of each key.
    """

    experiment: str
    llm_provider: str
    llm_model: str
    effort: str
    use_vision: bool
    headless: bool
    browser_channel: str
    user_agent: str
    max_steps: int
    max_actions_per_step: int
    max_failures: int
    step_timeout_s: int
    stop_on_ad_click: bool
    block_final_purchase: bool
    block_sensitive_input: bool
    allowed_domains: list[str]
    prohibited_domains: list[str]
    labels_file: str
    output_dir: str
    save_html: bool
    record_har: bool
    record_video: bool
    record_trace: bool
    keep_downloads: bool
    viewport_width: int
    viewport_height: int


@dataclass
class RunConfig:
    """Resolved configuration for one agent run."""

    # Grouping label; runs are written to ``<output_dir>/<experiment>/<run_id>``.
    experiment: str = "default"

    # --- model under test -------------------------------------------------
    # anthropic | openai | google | scripted (offline test double)
    llm_provider: str = "anthropic"
    llm_model: str = "claude-haiku-5-5"
    # Reasoning effort (anthropic: low|medium|high|xhigh|max). None = provider default.
    effort: str | None = None
    # Perception condition. False = DOM/accessibility text only; True = DOM text + screenshot.
    use_vision: bool = True 

    # --- browser ------------------------------------------------------------
    headless: bool = True 
    # "chromium" = full Chromium in new-headless mode (closer to a real browser than
    # the stripped headless shell, which many ad stacks treat differently).
    browser_channel: str = "chromium"
    user_agent: str | None = None
    viewport_width: int = 1280
    viewport_height: int = 900

    # --- loop limits ---------------------------------------------------------
    max_steps: int = 25
    # 1 = one action per observation, so every action is attributable to exactly
    # one screenshot/DOM snapshot. Raise it only if you accept coarser attribution.
    max_actions_per_step: int = 1
    max_failures: int = 3
    step_timeout_s: int = 180
    # End the run as soon as the agent interacts with a detected ad.
    stop_on_ad_click: bool = True 

    # --- safety policy ------------------------------------------------------
    # Refuse the final "place order / pay" click; the agent is told the purchase
    # is simulated and should call done.
    block_final_purchase: bool = False 
    # Refuse typing into password / payment-card / SSN-like fields (the attempt is logged).
    block_sensitive_input: bool = False 
    allowed_domains: list[str] | None = None
    prohibited_domains: list[str] | None = None

    # --- ground truth -------------------------------------------------------
    # JSON file mapping ad ids / landing domains to labels (see labels.example.json).
    labels_file: str | None = None

    # --- artifacts ----------------------------------------------------------
    output_dir: str = "runs"
    save_html: bool = True
    record_har: bool = True
    record_video: bool = False
    record_trace: bool = False
    # Downloads land in a per-run quarantine dir, are hashed, then deleted unless True.
    keep_downloads: bool = False

    @classmethod
    def resolve(cls, context: Mapping[str, Any] | None = None) -> RunConfig:
        """Build a config from defaults, ``HARNESS_*`` env vars and a runtime context."""
        cfg = cls()
        hints = get_type_hints(cls)
        for f in fields(cls):
            env_val = os.environ.get(f"HARNESS_{f.name.upper()}")
            if env_val is not None and env_val != "":
                setattr(cfg, f.name, _coerce(env_val, hints[f.name]))
        for key, val in (context or {}).items():
            if key in hints and val is not None:
                setattr(cfg, key, val)
        return cfg

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable snapshot of the config."""
        return asdict(self)


def _coerce(raw: str, hint: Any) -> Any:
    text = str(hint)
    if "bool" in text:
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    if "int" in text:
        return int(raw)
    if "list" in text:
        raw = raw.strip()
        if raw.startswith("["):
            return json.loads(raw)
        return [x.strip() for x in raw.split(",") if x.strip()]
    return raw

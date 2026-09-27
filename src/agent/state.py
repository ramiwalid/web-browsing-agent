"""Graph state for the maladvertising web-agent harness.

Only JSON-serialisable data lives in the state. Live objects (browser, Playwright,
browser-use Agent) are kept in ``agent.runtime`` keyed by ``run_id``.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, Optional

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AdEncounter(TypedDict):
    """One ad the agent was exposed to during a run."""

    ad_id: str
    page_url: str
    raw_content: str  # visible text / alt text / link targets found in the ad
    extracted_instruction: Optional[str]  # reserved for researcher annotation
    relevance: Literal["relevant", "irrelevant", "unknown"]
    malice: Literal["benign", "malicious", "suspicious", "unknown"]
    action_taken: Literal["ignored", "followed", "reported", "flagged_and_continued"]
    reasoning: str  # agent's stated reasoning at the step it acted (or "")
    timestamp: str
    # --- harness extensions ---
    first_seen_step: int
    steps_visible: list[int]  # steps where the ad was inside the viewport
    interaction_steps: list[int]
    detection_reasons: list[str]
    landing_hosts: list[str]


class InputState(TypedDict, total=False):
    """Fields a caller provides to start a run."""

    user_goal: str
    start_url: str
    task_id: str
    metadata: dict[str, Any]


class State(TypedDict, total=False):
    """Full graph state."""

    # --- inputs ---
    user_goal: str  # user's end goal
    start_url: str
    task_id: str
    metadata: dict[str, Any]

    # --- bookkeeping ---
    run_id: str
    run_dir: str
    config: dict[str, Any]
    messages: Annotated[list[Any], add_messages]  # human-readable step log (shows in Studio)

    # used for playwright/browser-use navigation and book-keeping
    current_url: str
    page_content: str  # path to the last DOM text the LLM saw
    navigation_history: Annotated[list[str], operator.add]
    step_count: int
    max_steps: int

    goal_status: Literal["in_progress", "completed", "failed", "blocked", "abandoned", "error"]
    completed_subgoals: Annotated[list[str], operator.add]
    final_result: Optional[str]
    error: Optional[str]

    detected_elements: list[dict[str, Any]]  # ad regions detected on the current page
    seen_ads: dict[str, dict[str, Any]]  # ad_id -> aggregate info across the run
    ad_encounters: Annotated[list[AdEncounter], operator.add]  # written at finalize
    ad_interactions: Annotated[list[dict[str, Any]], operator.add]  # every attributed ad hit
    pending_evaluation: Optional[dict[str, Any]]  # decision awaiting guard/act

    # outcome and eval hooks for promptfoo
    injection_triggered: bool  # agent interacted with an ad labelled malicious (ground truth)
    deviation_detected: bool  # agent interacted with any ad / left the task via an ad
    final_report: Optional[dict[str, Any]]  # structured result for promptfoo grading


class OutputState(TypedDict, total=False):
    """Fields returned to callers."""

    run_id: str
    run_dir: str
    goal_status: str
    final_result: Optional[str]
    injection_triggered: bool
    deviation_detected: bool
    ad_encounters: list[AdEncounter]
    ad_interactions: list[dict[str, Any]]
    final_report: Optional[dict[str, Any]]
    error: Optional[str]

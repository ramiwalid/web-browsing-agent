"""Promptfoo extension hooks: store pass/fail grades in Postgres once an eval finishes."""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from agent.db import record_grades


def extension_hook(hook_name: str, context: dict):
    """Run by promptfoo at each lifecycle stage; we only need ``afterAll``."""
    if hook_name == "afterAll":
        record_grades(context.get("evalId"), context.get("results") or [])

"""Postgres persistence for promptfoo eval runs.

Configured by the ``DATABASE_URL`` env var. If it is unset, recording is silently
disabled so the harness still works without a database.

CLI:
    python -m agent.db init     # create/upgrade tables (idempotent)
    python -m agent.db recent   # print the 10 most recent runs
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Jsonb

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id               TEXT PRIMARY KEY,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    duration_s           DOUBLE PRECISION,
    run_by               TEXT,
    git_sha              TEXT,
    promptfoo_eval_id    TEXT,
    model                TEXT,
    max_steps            INT,
    start_url            TEXT,
    user_goal            TEXT,
    goal_status          TEXT,
    injection_triggered  BOOLEAN,
    deviation_detected   BOOLEAN,
    final_result         TEXT,
    error                TEXT,
    final_report         JSONB,
    ad_interactions      JSONB,
    raw_output           JSONB
);

CREATE TABLE IF NOT EXISTS ad_encounters (
    id                   BIGSERIAL PRIMARY KEY,
    run_id               TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    ad_id                TEXT,
    page_url             TEXT,
    malice               TEXT,
    relevance            TEXT,
    action_taken         TEXT,
    first_seen_step      INT,
    reasoning            TEXT,
    detection_reasons    JSONB,
    landing_hosts        JSONB,
    raw_content          TEXT,
    data                 JSONB
);

CREATE TABLE IF NOT EXISTS grades (
    run_id               TEXT PRIMARY KEY,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    promptfoo_eval_id    TEXT,
    passed               BOOLEAN NOT NULL,
    score                DOUBLE PRECISION,
    reason               TEXT,
    error                TEXT,
    components           JSONB
);

CREATE INDEX IF NOT EXISTS runs_created_at_idx ON runs (created_at DESC);
CREATE INDEX IF NOT EXISTS runs_flags_idx ON runs (injection_triggered, deviation_detected);
CREATE INDEX IF NOT EXISTS runs_eval_idx ON runs (promptfoo_eval_id);
CREATE INDEX IF NOT EXISTS ad_encounters_run_idx ON ad_encounters (run_id);
"""


def _url() -> str | None:
    return os.environ.get("DATABASE_URL") or None


def init_schema() -> None:
    """Create tables if they don't exist."""
    url = _url()
    if not url:
        raise RuntimeError("DATABASE_URL is not set (see .env.example)")
    with psycopg.connect(url) as conn:
        conn.execute(SCHEMA)


def _git_sha() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).parent,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return None


def record_run(
    *,
    run_id: str,
    duration_s: float,
    model: str,
    max_steps: int,
    start_url: str,
    user_goal: str,
    result: dict[str, Any] | None = None,
    error: str | None = None,
    promptfoo_eval_id: str | None = None,
) -> None:
    """Insert one run (and its ad encounters). Never raises: DB problems are logged only."""
    url = _url()
    if not url:
        return
    result = result or {}
    try:
        with psycopg.connect(url, connect_timeout=5) as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    run_id, duration_s, run_by, git_sha, promptfoo_eval_id, model, max_steps,
                    start_url, user_goal, goal_status, injection_triggered, deviation_detected,
                    final_result, error, final_report, ad_interactions, raw_output
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (run_id) DO NOTHING
                """,
                (
                    run_id,
                    duration_s,
                    os.environ.get("USER") or os.environ.get("USERNAME"),
                    _git_sha(),
                    promptfoo_eval_id,
                    model,
                    max_steps,
                    start_url,
                    user_goal,
                    result.get("goal_status", "error" if error else None),
                    result.get("injection_triggered"),
                    result.get("deviation_detected"),
                    result.get("final_result"),
                    error or result.get("error"),
                    Jsonb(result.get("final_report")),
                    Jsonb(result.get("ad_interactions")),
                    Jsonb(result, dumps=_dumps),
                ),
            )
            for ad in result.get("ad_encounters") or []:
                conn.execute(
                    """
                    INSERT INTO ad_encounters (
                        run_id, ad_id, page_url, malice, relevance, action_taken,
                        first_seen_step, reasoning, detection_reasons, landing_hosts,
                        raw_content, data
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        run_id,
                        ad.get("ad_id"),
                        ad.get("page_url"),
                        ad.get("malice"),
                        ad.get("relevance"),
                        ad.get("action_taken"),
                        ad.get("first_seen_step"),
                        ad.get("reasoning"),
                        Jsonb(ad.get("detection_reasons")),
                        Jsonb(ad.get("landing_hosts")),
                        ad.get("raw_content"),
                        Jsonb(ad, dumps=_dumps),
                    ),
                )
    except Exception:
        logger.exception("Failed to record run %s in Postgres (continuing)", run_id)


def record_grades(eval_id: str | None, results: list[dict[str, Any]]) -> None:
    """Store promptfoo pass/fail grades, linked to runs by run_id. Never raises."""
    url = _url()
    if not url:
        return
    try:
        with psycopg.connect(url, connect_timeout=5) as conn:
            for r in results:
                response = r.get("response") or {}
                run_id = (response.get("metadata") or {}).get("run_id")
                if not run_id:
                    continue
                g = r.get("gradingResult") or {}
                conn.execute(
                    """
                    INSERT INTO grades (run_id, promptfoo_eval_id, passed, score, reason, error, components)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (run_id) DO UPDATE SET
                        promptfoo_eval_id = EXCLUDED.promptfoo_eval_id, passed = EXCLUDED.passed,
                        score = EXCLUDED.score, reason = EXCLUDED.reason, error = EXCLUDED.error,
                        components = EXCLUDED.components
                    """,
                    (
                        run_id,
                        eval_id,
                        bool(r.get("success")),
                        r.get("score"),
                        g.get("reason"),
                        r.get("error"),
                        Jsonb(g.get("componentResults"), dumps=_dumps),
                    ),
                )
                conn.execute(
                    "UPDATE runs SET promptfoo_eval_id = %s WHERE run_id = %s",
                    (eval_id, run_id),
                )
    except Exception:
        logger.exception("Failed to record promptfoo grades (continuing)")


def _dumps(obj: Any) -> str:
    import json

    return json.dumps(obj, default=str)


def _recent() -> None:
    with psycopg.connect(_url() or "") as conn:
        rows = conn.execute(
            """
            SELECT r.created_at::timestamp(0), r.run_id, r.goal_status, r.injection_triggered,
                   r.deviation_detected, CASE g.passed WHEN true THEN 'PASS' WHEN false THEN 'FAIL' ELSE '-' END,
                   left(r.start_url, 40)
            FROM runs r LEFT JOIN grades g USING (run_id)
            ORDER BY r.created_at DESC LIMIT 10
            """
        ).fetchall()
    for row in rows:
        print(*row, sep=" | ")
    if not rows:
        print("(no runs yet)")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "init"
    if cmd == "init":
        init_schema()
        print("Schema ready.")
    elif cmd == "recent":
        _recent()
    else:
        sys.exit(f"unknown command: {cmd}")

import asyncio
import json
import os
import time
import traceback
import uuid
from pathlib import Path

from dotenv import load_dotenv

# promptfoo spawns this file directly (no `langgraph dev`/langgraph.json around it),
# so the project .env is never loaded otherwise, and ANTHROPIC_API_KEY is missing.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from agent.db import record_run
from agent.graph import graph


def _promptfoo_token_usage(result: dict) -> dict | None:
    """Convert the graph's LLM usage totals into promptfoo's ``tokenUsage`` shape."""
    usage = (result.get("final_report") or {}).get("llm_usage")
    if not usage:
        return None
    return {
        "total": usage["total_tokens"],
        "prompt": usage["prompt_tokens"],
        "completion": usage["completion_tokens"],
        "cached": usage["cached_tokens"],
        "numRequests": usage["num_requests"],
    }


async def call_api(prompt: str, options: dict, context: dict) -> dict:
    """Promptfoo entry point for the malvertising agent."""
    
    # 1. Extract the test case variables defined in promptfooconfig.yaml
    vars = context.get("vars", {})
    
    # Unique per call: it becomes the graph's run_id and the primary key in Postgres.
    run_id = f"promptfoo_{uuid.uuid4().hex[:12]}"
    initial_input = {
        "user_goal": vars.get("user_goal", prompt),
        "start_url": vars.get("start_url", ""),
        "task_id": run_id
    }

    # 2. Force Claude configuration for the audit
    runtime_context = {
        "llm_provider": "anthropic",
        "llm_model": options.get("config", {}).get("model", "claude-haiku-5-5"),
        "headless": True, # Run headless so parallel evaluations run quickly
        "max_steps": 15,
        "stop_on_ad_click": True,
    }

    record = dict(
        run_id=run_id,
        model=runtime_context["llm_model"],
        max_steps=runtime_context["max_steps"],
        start_url=initial_input["start_url"],
        user_goal=initial_input["user_goal"],
        promptfoo_eval_id=context.get("evaluationId"),
    )
    started = time.monotonic()

    try:
        # 3. Invoke the browser agent
        result = await graph.ainvoke(initial_input, context=runtime_context)

        # Every agent step failed (bad API key, etc.): report an error, not a graded task failure
        if result.get("error"):
            err = f"Agent never ran successfully: {result['error']}"
            await asyncio.to_thread(
                record_run, duration_s=time.monotonic() - started, error=err, **record
            )
            return {"error": err, "metadata": {"run_id": run_id}, "tokenUsage": _promptfoo_token_usage(result)}

        # Save to Postgres (no-op if DATABASE_URL is unset; never raises)
        await asyncio.to_thread(
            record_run, duration_s=time.monotonic() - started, result=result, **record
        )

        # 4. Return the entire OutputState as a JSON string so Promptfoo can evaluate it
        return {
            "output": json.dumps(result, indent=2),
            # lets the afterAll hook (hooks.py) link promptfoo's grade to this run
            "metadata": {"run_id": run_id},
            # LLM token totals across all agent steps (None if unavailable)
            "tokenUsage": _promptfoo_token_usage(result),
        }
    except Exception as e:
        err = f"Graph execution failed: {str(e)}\n{traceback.format_exc()}"
        await asyncio.to_thread(
            record_run, duration_s=time.monotonic() - started, error=err, **record
        )
        return {"error": err, "metadata": {"run_id": run_id}}

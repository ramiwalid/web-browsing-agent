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
        "llm_model": options.get("config", {}).get("model", "claude-sonnet-5"),
        "headless": False, # Run headless so parallel evaluations run quickly
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

        # Save to Postgres (no-op if DATABASE_URL is unset; never raises)
        await asyncio.to_thread(
            record_run, duration_s=time.monotonic() - started, result=result, **record
        )

        # 4. Return the entire OutputState as a JSON string so Promptfoo can evaluate it
        return {
            "output": json.dumps(result, indent=2),
            # lets the afterAll hook (hooks.py) link promptfoo's grade to this run
            "metadata": {"run_id": run_id},
        }
    except Exception as e:
        err = f"Graph execution failed: {str(e)}\n{traceback.format_exc()}"
        await asyncio.to_thread(
            record_run, duration_s=time.monotonic() - started, error=err, **record
        )
        return {"error": err, "metadata": {"run_id": run_id}}

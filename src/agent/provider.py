import json
import os
import traceback
from pathlib import Path

from dotenv import load_dotenv

# promptfoo spawns this file directly (no `langgraph dev`/langgraph.json around it),
# so the project .env is never loaded otherwise, and ANTHROPIC_API_KEY is missing.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from agent.graph import graph

async def call_api(prompt: str, options: dict, context: dict) -> dict:
    """Promptfoo entry point for the malvertising agent."""
    
    # 1. Extract the test case variables defined in promptfooconfig.yaml
    vars = context.get("vars", {})
    
    initial_input = {
        "user_goal": vars.get("user_goal", prompt),
        "start_url": vars.get("start_url", ""),
        "task_id": "promptfoo_eval_run"
    }

    # 2. Force Claude configuration for the audit
    runtime_context = {
        "llm_provider": "anthropic",
        "llm_model": options.get("config", {}).get("model", "claude-sonnet-5"),
        "headless": False, # Run headless so parallel evaluations run quickly
        "max_steps": 15,
        "stop_on_ad_click": True,
    }

    try:
        # 3. Invoke the browser agent
        result = await graph.ainvoke(initial_input, context=runtime_context)
        
        # 4. Return the entire OutputState as a JSON string so Promptfoo can evaluate it
        return {
            "output": json.dumps(result, indent=2)
        }
    except Exception as e:
        return {
            "error": f"Graph execution failed: {str(e)}\n{traceback.format_exc()}"
        }

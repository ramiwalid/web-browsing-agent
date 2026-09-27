import sys
from pathlib import Path

# Ensure the local directory is in the Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import asyncio
import json
from graph import graph

async def main():
    # A scripted plan for the test double
    scripted_plan = [
        {"navigate": "https://youtube.com"},
        {"done": "Task complete", "success": True}
    ]

    initial_input = {
        "user_goal": "Visit youtube.com and verify page loads.",
        "start_url": "https://youtube.com",
        "task_id": "offline_smoke_test_01",
    }

    # Define the runtime context directly (No more "configurable" nesting)
    runtime_context = {
        "llm_provider": "scripted",
        "llm_model": json.dumps(scripted_plan),
        "headless": False,
        "max_steps": 5,
    }

    print("Running offline test...")
    
    # CRITICAL FIX: Pass the dictionary using the `context=` keyword argument
    result = await graph.ainvoke(
        initial_input, 
        context=runtime_context 
    )

    print("\n--- Execution Output ---")
    print(f"Goal Status: {result.get('goal_status')}")
    print(f"Final Result: {result.get('final_result')}")
    print(f"Deviation Detected: {result.get('deviation_detected')}")
    print(f"Injection Triggered: {result.get('injection_triggered')}")
    print(f"Steps Logged: {result.get('final_report')}")

if __name__ == "__main__":
    asyncio.run(main())

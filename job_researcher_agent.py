"""
Job Researcher — Agentic MCP Client
=====================================

Chains all 3 MCP tools automatically:
  1. search_jobs()          → Internet
  2. save_jobs_to_file()    → File CRUD
  3. show_job_dashboard()   → UI (generates dashboard data + Prefab file)

Uses Gemini with FUNCTION_CALL/FINAL_ANSWER protocol (same as class examples).

Run:
    python job_researcher_agent.py
    python job_researcher_agent.py "machine learning engineer"

Env (.env):
    GEMINI_API_KEY=your_key
"""

import asyncio
import json
import os
import sys

from dotenv import load_dotenv
from google import genai
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
MAX_ITERATIONS = 10
LLM_SLEEP_SECONDS = 2
LLM_TIMEOUT = 45

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


async def generate_with_timeout(prompt: str, timeout: int = LLM_TIMEOUT):
    loop = asyncio.get_event_loop()
    return await asyncio.wait_for(
        loop.run_in_executor(
            None,
            lambda: client.models.generate_content(model=MODEL, contents=prompt),
        ),
        timeout=timeout,
    )


def describe_tools(tools) -> str:
    lines = []
    for i, t in enumerate(tools, 1):
        props = (t.inputSchema or {}).get("properties", {})
        params = ", ".join(f"{n}: {p.get('type', '?')}" for n, p in props.items()) or "no params"
        lines.append(f"{i}. {t.name}({params}) — {t.description or ''}")
    return "\n".join(lines)


def coerce(value: str, schema_type: str):
    if schema_type == "integer":
        return int(value)
    if schema_type == "number":
        return float(value)
    if schema_type == "boolean":
        return value.lower() in ("true", "1", "yes")
    return value


def first_directive(text: str) -> str:
    for line in (text or "").splitlines():
        s = line.strip().lstrip("`").lstrip()
        if s.startswith("FUNCTION_CALL:") or s.startswith("FINAL_ANSWER:"):
            return s
    return (text or "").strip()


async def run_agent(job_query: str, location: str = "India", num_jobs: int = 5):
    """Run the full agentic pipeline. Returns final status string."""

    server_params = StdioServerParameters(
        command="python",
        args=["job_researcher_mcp_server.py"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("Connected to Job Researcher MCP Server")

            tools = (await session.list_tools()).tools
            tools_desc = describe_tools(tools)
            print(f"Loaded {len(tools)} tools\n")

            system_prompt = f"""You are a Job Research Agent. Complete these 3 steps IN ORDER:

STEP 1 — SEARCH: Call search_jobs to find job listings from the internet.
STEP 2 — SAVE: Take the search results. For EACH job, add these fields:
   "keywords": a list of 5-8 key technical skills mentioned or expected
   "interview_questions": a list of 3-5 interview questions likely for this role
   "summary": 1-2 sentence summary of the role
   Then call save_jobs_to_file with the ENRICHED JSON.
STEP 3 — DISPLAY: Call show_job_dashboard with the same enriched JSON.

Available tools:
{tools_desc}

Respond with EXACTLY ONE line in one of these formats:
  FUNCTION_CALL: tool_name|arg1|arg2|...
  FINAL_ANSWER: <summary>

Rules:
- String args containing JSON must be valid JSON (use double quotes).
- Do NOT invent tools not listed.
- You MUST call search_jobs, then save_jobs_to_file, then show_job_dashboard.
- When passing enriched jobs to save_jobs_to_file, pass the FULL JSON including
  the new keywords/interview_questions/summary fields you generated.
"""

            task = (
                f"Find {num_jobs} job listings for '{job_query}' in '{location}'. "
                f"Enrich each job with keywords and interview questions. "
                f"Save to file. Show on dashboard."
            )

            history: list[str] = []
            final_result = "Agent did not complete."

            for iteration in range(1, MAX_ITERATIONS + 1):
                print(f"\n{'='*20} Iteration {iteration} {'='*20}")

                context = "\n".join(history) if history else "(no prior steps)"
                prompt = (
                    f"{system_prompt}\n"
                    f"Task: {task}\n\n"
                    f"Previous steps:\n{context}\n\n"
                    f"What is your next single action?"
                )

                await asyncio.sleep(LLM_SLEEP_SECONDS)

                try:
                    response = await generate_with_timeout(prompt)
                except asyncio.TimeoutError:
                    print("LLM timed out")
                    break
                except Exception as e:
                    print(f"LLM error: {e}")
                    break

                raw_text = (response.text or "").strip()
                text = first_directive(raw_text)
                print(f"Agent: {text[:300]}{'...' if len(text) > 300 else ''}")

                if text.startswith("FINAL_ANSWER:"):
                    final_result = text[len("FINAL_ANSWER:"):].strip()
                    print(f"\n{'='*60}")
                    print(f"  DONE: {final_result}")
                    print(f"{'='*60}")
                    break

                if not text.startswith("FUNCTION_CALL:"):
                    history.append(f"Iteration {iteration}: bad format, use FUNCTION_CALL: or FINAL_ANSWER:")
                    continue

                _, call = text.split(":", 1)
                parts = [p.strip() for p in call.split("|")]
                func_name, raw_args = parts[0], parts[1:]

                tool = next((t for t in tools if t.name == func_name), None)
                if not tool:
                    history.append(f"Iteration {iteration}: unknown tool {func_name!r}")
                    continue

                props = (tool.inputSchema or {}).get("properties", {})
                arguments = {}
                for (name, info), val in zip(props.items(), raw_args):
                    arguments[name] = coerce(val, info.get("type", "string"))

                print(f"  → {func_name}()")
                try:
                    result = await session.call_tool(func_name, arguments=arguments)
                    payload = (
                        result.content[0].text
                        if result.content and hasattr(result.content[0], "text")
                        else str(result)
                    )
                except Exception as e:
                    payload = f"ERROR: {e}"

                print(f"  ← {payload[:300]}{'...' if len(payload) > 300 else ''}")
                history.append(f"Iteration {iteration}: {func_name}() → {payload}")

            return final_result


async def main():
    print("=" * 60)
    print("  JOB RESEARCHER — Agentic MCP Client")
    print("=" * 60)

    if len(sys.argv) > 1:
        job_query = " ".join(sys.argv[1:])
    else:
        job_query = input("\nJob search query (e.g. 'Python developer'): ").strip() or "Python developer"

    location = input("Location (default: India): ").strip() or "India"
    num_jobs = int(input("How many jobs? (default: 5): ").strip() or "5")

    print(f"\nSearching: {job_query} in {location} (top {num_jobs})\n")
    await run_agent(job_query, location, num_jobs)
    print("\nCheck sandbox/ for saved files.")
    print("Run 'python web_app.py' to view the dashboard in browser.")


if __name__ == "__main__":
    asyncio.run(main())

import os
import sys
import json
import time
import re
from google import genai
from dotenv import load_dotenv

load_dotenv()

MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
]
MAX_ITERATIONS = 20
SLEEP_BETWEEN_CALLS = 2.0


def get_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in .env")
    return genai.Client(api_key=api_key)


def call_llm(client, model, messages, system_prompt):
    contents = []
    for m in messages:
        contents.append({"role": m["role"], "parts": [{"text": m["content"]}]})
    try:
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config={"system_instruction": system_prompt}
        )
        return response.text
    except Exception as e:
        raise e


def is_quota_error(err_str):
    return "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower()


def is_daily_quota_exhausted(err_str):
    return "PerDay" in err_str or "per_day" in err_str.lower() or "GenerateRequestsPerDay" in err_str


def parse_retry_delay(err_str):
    patterns = [
        r"retry[_\s]delay['\"]?\s*[:\s]+['\"]?(\d+)",
        r"retry after (\d+)",
        r"retryDelay['\"]?\s*:\s*['\"]?(\d+)",
        r"in (\d+)[\.\d]*s",
    ]
    for pattern in patterns:
        m = re.search(pattern, err_str, re.IGNORECASE)
        if m:
            return int(m.group(1)) + 3
    return 20


def call_llm_with_fallback(messages, system_prompt):
    client = get_client()
    last_err = None
    for model in MODELS:
        try:
            print(f"[agent_loop] trying model: {model}", file=sys.stderr)
            result = call_llm(client, model, messages, system_prompt)
            return result
        except Exception as e:
            err_str = str(e)
            print(f"[agent_loop] model {model} failed: {err_str[:200]}", file=sys.stderr)

            if is_quota_error(err_str):
                if is_daily_quota_exhausted(err_str):
                    print(f"[agent_loop] daily quota exhausted for {model}, skipping to next model", file=sys.stderr)
                    last_err = e
                    continue
                else:
                    wait = parse_retry_delay(err_str)
                    print(f"[agent_loop] rate limit on {model}, sleeping {wait}s then trying next", file=sys.stderr)
                    time.sleep(wait)
                    last_err = e
                    continue
            else:
                last_err = e
                continue

    raise RuntimeError(
        f"All {len(MODELS)} models failed or daily quota exhausted. "
        f"Last error: {last_err}. "
        f"Free tier allows 20 requests/day per model. "
        f"Either wait until midnight Pacific time, or add a paid Gemini API key."
    )


def run_agent(task, tools: dict, system_prompt: str, progress_cb=None):
    """
    Agentic loop using FUNCTION_CALL: tool_name|arg1|arg2 protocol.
    tools: dict of tool_name -> callable(args: list) -> str
    Returns final answer string.
    """
    tool_descriptions = "\n".join(
        [f"- {name}: {fn.__doc__ or 'no description'}" for name, fn in tools.items()]
    )

    full_system = f"""{system_prompt}

You have access to these tools. Call them using EXACTLY this format on a single line:
FUNCTION_CALL: tool_name|arg1|arg2

When you have the final answer, output:
FINAL_ANSWER: <your complete answer>

Available tools:
{tool_descriptions}

Rules:
- Think step by step before each tool call
- Always verify tool results before proceeding
- If a tool fails, explain why and try an alternative approach
- Output only one FUNCTION_CALL or FINAL_ANSWER per response
"""

    history = [{"role": "user", "content": task}]

    for iteration in range(MAX_ITERATIONS):
        print(f"[agent_loop] iteration {iteration+1}", file=sys.stderr)
        response = call_llm_with_fallback(history, full_system)
        print(f"[agent_loop] response: {response[:200]}", file=sys.stderr)

        history.append({"role": "model", "content": response})

        if "FINAL_ANSWER:" in response:
            final = response.split("FINAL_ANSWER:", 1)[1].strip()
            return final

        if "FUNCTION_CALL:" in response:
            line = ""
            for l in response.split("\n"):
                if "FUNCTION_CALL:" in l:
                    line = l.strip()
                    break

            call_part = line.split("FUNCTION_CALL:", 1)[1].strip()
            parts = call_part.split("|")
            tool_name = parts[0].strip()
            args = [p.strip() for p in parts[1:]]

            print(f"[agent_loop] calling tool: {tool_name} args={args}", file=sys.stderr)

            if progress_cb:
                progress_cb(tool_name, args)

            if tool_name not in tools:
                tool_result = f"ERROR: tool '{tool_name}' not found. Available: {list(tools.keys())}"
            else:
                try:
                    tool_result = tools[tool_name](args)
                except Exception as e:
                    tool_result = f"ERROR: tool '{tool_name}' raised: {e}"

            print(f"[agent_loop] tool result: {str(tool_result)[:300]}", file=sys.stderr)
            history.append({"role": "user", "content": f"Tool result for {tool_name}:\n{tool_result}"})

            time.sleep(SLEEP_BETWEEN_CALLS)
        else:
            history.append({"role": "user", "content": "Continue. Use FUNCTION_CALL or FINAL_ANSWER."})

    return "ERROR: max iterations reached without final answer"
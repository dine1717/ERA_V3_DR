"""
Job Application Helper Agent
A full agentic loop that reads a job description and generates
a tailored cover letter or updated resume using Gemini.

Before running:
  pip install google-genai python-dotenv
  Create a .env file next to this script with:
    GEMINI_API_KEY=your-key-here
    GEMINI_MODEL=gemini-2.0-flash
"""

from google import genai
import json
import re
import os
import time
from dotenv import load_dotenv

# ============================================================
# Configuration
# ============================================================
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL   = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
THROTTLE_SECONDS = 5   # wait between calls to stay under free-tier limits

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not set. Create a .env file with GEMINI_API_KEY=...")

client = genai.Client(api_key=GEMINI_API_KEY)


def call_llm(prompt: str) -> str:
    """Send a prompt to Gemini and return the text response.
    Sleeps THROTTLE_SECONDS before each call to respect rate limits.
    """
    print(f"  [waiting {THROTTLE_SECONDS}s to respect rate limits...]", flush=True)
    time.sleep(THROTTLE_SECONDS)
    response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    return response.text


# ============================================================
# System Prompt — tells the LLM how to behave as an agent
# ============================================================
system_prompt = """You are a Job Application Assistant AI agent.
You help users tailor their job applications for specific job postings.

You have access to the following tools:

1. extract_job_details(job_text: str) -> str
   Parse a raw job description and extract: role, company, required skills, and keywords.
   Example: extract_job_details("We are hiring a Python developer at Acme Corp...")

2. match_resume_keywords(job_details: str, resume_text: str) -> str
   Compare the job requirements against the user's resume.
   Returns: match score (%), keywords already present, keywords missing.
   Example: match_resume_keywords("Role: Data Engineer...", "John Doe, 3 yrs Python...")

3. generate_application_output(match_analysis: str, resume_text: str, mode: str) -> str
   Generate either a tailored cover letter or an updated resume.
   mode must be either "cover_letter" or "updated_resume"
   Example: generate_application_output("Score: 60%, Missing: SQL, Spark", "..resume..", "cover_letter")

You must respond in ONE of these two JSON formats ONLY:

If you need to call a tool:
{"tool_name": "<name>", "tool_arguments": {"<arg>": "<value>"}}

If you have the final answer:
{"answer": "<your complete final answer here>"}

RULES:
- Respond with ONLY the JSON. No markdown. No extra text.
- Always call tools in this order: extract_job_details → match_resume_keywords → generate_application_output
- Use ALL THREE tools before giving the final answer.
- The final answer must be the actual cover letter or updated resume text.
"""


# ============================================================
# The 3 Custom Tool Functions
# ============================================================

def extract_job_details(job_text: str) -> str:
    """
    TOOL 1: Parse raw job description text and extract structured details.
    In a real Chrome plugin, job_text comes from scraping the job page.
    Here we simulate with a hardcoded job description.
    """
    print(f"\n  [TOOL] extract_job_details() running...")

    # Use Gemini to intelligently extract — this is itself an LLM call inside a tool!
    extraction_prompt = f"""Extract the following from this job description and return as JSON:
- role_title
- company_name  
- required_skills (list)
- preferred_skills (list)
- keywords (top 10 important words)

Job Description:
{job_text[:3000]}

Return ONLY valid JSON, no markdown."""

    time.sleep(3)
    extraction_response = client.models.generate_content(
        model=GEMINI_MODEL, contents=extraction_prompt
    )
    raw = extraction_response.text.strip().replace("```json","").replace("```","")

    try:
        parsed = json.loads(raw)
        return json.dumps({
            "status": "success",
            "extracted": parsed
        })
    except Exception:
        # Fallback: return raw text if JSON parse fails
        return json.dumps({
            "status": "success",
            "extracted": {"raw_extraction": raw}
        })


def match_resume_keywords(job_details: str, resume_text: str) -> str:
    """
    TOOL 2: Compare job keywords against the user's resume.
    Returns a match score and lists of present/missing keywords.
    """
    print(f"\n  [TOOL] match_resume_keywords() running...")

    resume_lower = resume_text.lower()

    # Parse job details to get keywords
    try:
        job_data = json.loads(job_details)
        extracted = job_data.get("extracted", {})

        # Collect all keywords from required + preferred skills + keywords list
        all_keywords = []
        all_keywords += extracted.get("required_skills", [])
        all_keywords += extracted.get("preferred_skills", [])
        all_keywords += extracted.get("keywords", [])
        all_keywords = list(set([k.lower().strip() for k in all_keywords if k]))
    except Exception:
        # Fallback: simple word frequency
        words = job_details.lower().replace(",","").replace(".","").split()
        stopwords = {"the","and","or","for","with","that","this","have","will","your","they","a","an","to","of","in","is","are"}
        all_keywords = list(set([w for w in words if len(w) > 4 and w not in stopwords]))[:20]

    present = [k for k in all_keywords if k in resume_lower]
    missing = [k for k in all_keywords if k not in resume_lower]
    score   = round((len(present) / len(all_keywords)) * 100) if all_keywords else 0

    result = {
        "match_score_percent": score,
        "total_keywords_checked": len(all_keywords),
        "keywords_present_in_resume": present,
        "keywords_missing_from_resume": missing,
        "recommendation": (
            "Good match! Minor tweaks needed." if score >= 70
            else "Moderate match. Add missing keywords." if score >= 40
            else "Low match. Significant updates recommended."
        )
    }

    print(f"  [TOOL] Match score: {score}% | Missing: {', '.join(missing[:5])}")
    return json.dumps(result)


def generate_application_output(match_analysis: str, resume_text: str, mode: str) -> str:
    """
    TOOL 3: Generate a tailored cover letter or updated resume.
    Uses the match analysis from Tool 2 to inject missing keywords.
    mode = "cover_letter" or "updated_resume"
    """
    print(f"\n  [TOOL] generate_application_output(mode='{mode}') running...")

    try:
        analysis = json.loads(match_analysis)
        missing_kws = analysis.get("keywords_missing_from_resume", [])
        score       = analysis.get("match_score_percent", "?")
    except Exception:
        missing_kws = []
        score       = "?"

    if mode == "cover_letter":
        generation_prompt = f"""Write a professional, personalized cover letter based on:

Resume:
{resume_text[:1500]}

Job Match Analysis:
- Current match score: {score}%
- Keywords to include: {', '.join(missing_kws[:8])}

Instructions:
- Write a complete, ready-to-send cover letter (no placeholders)
- Naturally weave in the missing keywords above
- Keep it under 300 words
- Start with "Dear Hiring Manager,"
Return ONLY the cover letter text."""

    else:  # updated_resume
        generation_prompt = f"""Update this resume to better match a job posting:

Current Resume:
{resume_text[:1500]}

Missing Keywords to Add: {', '.join(missing_kws[:8])}

Instructions:
- Return the full updated resume
- Naturally weave missing keywords into existing bullet points
- Do NOT invent experience — only rephrase what's already there
- Mark every changed line with [UPDATED] at the end
Return ONLY the updated resume text."""

    time.sleep(3)
    generation_response = client.models.generate_content(
        model=GEMINI_MODEL, contents=generation_prompt
    )
    output_text = generation_response.text.strip()

    return json.dumps({
        "status": "success",
        "mode": mode,
        "output": output_text,
        "keywords_added": missing_kws[:8]
    })


# ============================================================
# Tool Registry — maps names to functions (same pattern as demo)
# ============================================================
tools = {
    "extract_job_details":        extract_job_details,
    "match_resume_keywords":      match_resume_keywords,
    "generate_application_output": generate_application_output,
}


# ============================================================
# Response Parser
# ============================================================
def parse_llm_response(text: str) -> dict:
    """Parse the LLM's JSON response, handling messy formatting."""
    text = text.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
        if text.startswith("json"):
            text = text[4:].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object anywhere in response
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse LLM response: {text[:200]}")


# ============================================================
# The Agent Loop
# ============================================================
def run_agent(user_query: str, max_iterations: int = 8, verbose: bool = True):
    """
    The full agentic loop — same structure as professor's demo:

    Query → LLM Response → Tool Call : Tool Result
         → Query (with ALL past) → LLM Response → Tool Call : Tool Result
         → Query (with ALL past) → LLM Response → Final Answer

    The messages list is the KEY — it stores ALL interactions.
    Every LLM call sees the complete history.
    """
    if verbose:
        print(f"\n{'='*60}")
        print(f"  User Query: {user_query}")
        print(f"{'='*60}")

    # ── This stores ALL past interactions (grows with every turn) ──
    messages = [
        {"role": "system",  "content": system_prompt},
        {"role": "user",    "content": user_query},
    ]

    for iteration in range(max_iterations):
        if verbose:
            print(f"\n--- Iteration {iteration + 1} ---")

        # ── Build prompt from FULL message history ──
        # Every call sees EVERYTHING: system + user + all past tool calls + results
        prompt = ""
        for msg in messages:
            if msg["role"] == "system":
                prompt += msg["content"] + "\n\n"
            elif msg["role"] == "user":
                prompt += f"User: {msg['content']}\n\n"
            elif msg["role"] == "assistant":
                prompt += f"Assistant: {msg['content']}\n\n"
            elif msg["role"] == "tool":
                prompt += f"Tool Result: {msg['content']}\n\n"

        # ── Call LLM ──
        response_text = call_llm(prompt)
        if verbose:
            print(f"LLM Response: {response_text.strip()[:300]}")

        # ── Parse response ──
        try:
            parsed = parse_llm_response(response_text)
        except (ValueError, json.JSONDecodeError) as e:
            if verbose:
                print(f"  Parse error: {e} — asking LLM to retry")
            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "user",      "content": "Please respond with valid JSON only. No markdown, no extra text."})
            continue

        # ── Final answer? ──
        if "answer" in parsed:
            if verbose:
                print(f"\n{'='*60}")
                print("  FINAL ANSWER FROM AGENT:")
                print(f"{'='*60}")
                print(parsed["answer"])
                print(f"{'='*60}")
            return parsed["answer"]

        # ── Tool call? ──
        if "tool_name" in parsed:
            tool_name = parsed["tool_name"]
            tool_args = parsed.get("tool_arguments", {})

            if verbose:
                print(f"\n→ Tool Call:   {tool_name}({list(tool_args.keys())})")

            if tool_name not in tools:
                error = json.dumps({"error": f"Unknown tool '{tool_name}'. Available: {list(tools.keys())}"})
                messages.append({"role": "assistant", "content": response_text})
                messages.append({"role": "tool",      "content": error})
                continue

            # Execute the tool
            tool_result = tools[tool_name](**tool_args)

            if verbose:
                # Show a preview of the result (first 200 chars)
                preview = tool_result[:200] + "..." if len(tool_result) > 200 else tool_result
                print(f"→ Tool Result: {preview}")

            # ── Add BOTH the LLM response AND the tool result to history ──
            # This is how the agent "remembers" what happened
            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "tool",      "content": tool_result})

            continue

        # Unexpected format
        if verbose:
            print(f"  Unexpected response format. Retrying...")
        messages.append({"role": "assistant", "content": response_text})
        messages.append({"role": "user",      "content": "Respond with JSON only: either {tool_name, tool_arguments} or {answer}."})

    print("\n[Agent] Max iterations reached.")
    return None


# ============================================================
# Sample Data — simulating what the Chrome plugin would send
# ============================================================

SAMPLE_JOB_DESCRIPTION = """
Senior Data Engineer — Flipkart (Bangalore)

We are looking for a Senior Data Engineer to join our Data Platform team.

Responsibilities:
- Design and build scalable data pipelines using Apache Spark and Kafka
- Work with Python and SQL to process large datasets
- Build and maintain ETL workflows on AWS (S3, Glue, Redshift)
- Collaborate with ML engineers to deploy models to production
- Optimize query performance and data warehouse design

Requirements:
- 3+ years of experience in data engineering
- Strong proficiency in Python and SQL
- Experience with Apache Spark, Kafka, or Airflow
- Familiarity with AWS services (S3, Glue, EMR, Redshift)
- Knowledge of dbt for data transformation
- Good understanding of data modelling and warehousing concepts

Nice to have:
- Experience with Databricks or Delta Lake
- Knowledge of Kubernetes and Docker
- Exposure to ML pipelines and MLflow
"""

SAMPLE_RESUME = """
Priya Sharma
priya.sharma@email.com | Bangalore, India | linkedin.com/in/priyasharma

SUMMARY
Data professional with 3 years of experience building data solutions.
Passionate about solving complex data problems at scale.

EXPERIENCE

Data Analyst — Infosys, Bangalore (2022–Present)
- Wrote SQL queries to extract and analyze customer data from MySQL databases
- Built automated Python scripts to clean and process CSV reports
- Created dashboards in Tableau for business stakeholders
- Worked on ETL processes to move data between systems

Junior Developer — Wipro, Pune (2021–2022)
- Developed REST APIs using Python Flask
- Maintained PostgreSQL databases and wrote stored procedures
- Assisted in migrating on-premise databases to cloud storage

EDUCATION
B.Tech Computer Science — VIT University, 2021 | GPA: 8.4/10

SKILLS
Python, SQL, MySQL, PostgreSQL, Tableau, Excel, Flask, Git, Linux, Basic AWS
"""


# ============================================================
# Run the Agent!
# ============================================================
if __name__ == "__main__":
    print("\n" + "="*60)
    print("  JOB APPLICATION HELPER — AGENTIC AI")
    print("  3-Tool Loop: Extract → Match → Generate")
    print("="*60)

    # ── TEST 1: Generate a Cover Letter ──
    print("\n\n>>> TEST 1: Generate a Cover Letter")
    run_agent(
        f"""I found a job I want to apply for. Here is the job description:

{SAMPLE_JOB_DESCRIPTION}

Here is my resume:

{SAMPLE_RESUME}

Please analyze this job and generate a tailored COVER LETTER for me."""
    )

    # ── TEST 2: Generate an Updated Resume ──
    print("\n\n>>> TEST 2: Update Resume with Job Keywords")
    run_agent(
        f"""I found a job I want to apply for. Here is the job description:

{SAMPLE_JOB_DESCRIPTION}

Here is my resume:

{SAMPLE_RESUME}

Please analyze this job and give me an UPDATED RESUME with the right keywords added."""
    )

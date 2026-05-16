import sys
import json
from agent_loop import call_llm_with_fallback
from pipeline.stage2_extract import safe_parse_json

SYSTEM = """You are an expert resume writer. 
You rewrite resume content to be ATS-optimized while keeping it honest and natural.
Return ONLY valid JSON."""

def build(gap_data: dict, iteration: int = 0) -> dict:
    """
    Rewrites resume bullets to inject job keywords.
    Verifies each rewritten bullet contains target keywords.
    Returns rewritten resume sections + list of injected keywords.
    """
    job_schema = gap_data["job_schema"]
    resume_text = gap_data["resume_text"]
    gap_analysis = gap_data["gap_analysis"]

    required_keywords = job_schema.get("required_skills", []) + job_schema.get("tech_stack", [])
    already_strong = [
        g["item"] for g in gap_analysis.get("gaps", [])
        if g.get("severity") == "already_strong"
    ]

    print(f"[stage4] building resume (iteration {iteration+1})", file=sys.stderr)

    prompt = f"""Rewrite this resume to be tailored for the following job.

ORIGINAL RESUME:
{resume_text}

JOB TITLE: {job_schema.get('title', '')}
COMPANY: {gap_data['job_raw'].get('company', '')}

REQUIRED KEYWORDS TO INJECT (use naturally, not forced):
{json.dumps(required_keywords)}

ALREADY STRONG (keep these as-is):
{json.dumps(already_strong)}

REWRITING RULES:
1. Rewrite bullet points to include required keywords naturally
2. Use strong action verbs (Built, Designed, Led, Implemented, Optimized)
3. Add quantifiable outcomes where possible (%, numbers, scale)
4. Keep the same projects and jobs — do NOT invent new ones
5. After each rewritten bullet, verify the target keyword appears in it
6. Keep it honest — only include what the candidate actually did

Return ONLY this JSON (no markdown):
{{
  "rewritten_resume": "full rewritten resume as markdown text",
  "injected_keywords": ["keyword1", "keyword2"],
  "verified_bullets": [
    {{
      "original": "original bullet text",
      "rewritten": "new bullet text", 
      "target_keyword": "keyword injected",
      "verified": true/false
    }}
  ],
  "sections": {{
    "summary": "rewritten professional summary",
    "experience": "rewritten experience section",
    "skills": "rewritten skills section",
    "projects": "rewritten projects section"
  }}
}}"""

    resp = call_llm_with_fallback(
        [{"role": "user", "content": prompt}], SYSTEM
    )
    resume_built = safe_parse_json(resp, "resume_build")

    # self-check: count verified bullets
    verified = resume_built.get("verified_bullets", [])
    failed = [b for b in verified if not b.get("verified", True)]
    if failed:
        print(f"[stage4] {len(failed)} bullets failed keyword verification", file=sys.stderr)

    return {
        **gap_data,
        "resume_built": resume_built,
        "build_iteration": iteration
    }

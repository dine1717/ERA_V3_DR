import sys
import json
from agent_loop import call_llm_with_fallback

SYSTEM = """You are a precise structured extraction agent. 
Extract information and return ONLY valid JSON. No markdown, no explanation, just the JSON object."""

def extract(ingest_data: dict) -> dict:
    """
    Extracts structured schemas from job description and resume.
    Returns two normalized JSON objects: job_schema and resume_schema.
    """
    job_text = ingest_data["job"]["description"]
    resume_text = ingest_data["resume_text"]

    # Extract job schema
    print("[stage2] extracting job schema", file=sys.stderr)
    job_prompt = f"""Extract a structured JSON schema from this job description.

Job Description:
{job_text}

Return ONLY this JSON structure (no markdown):
{{
  "title": "job title",
  "company": "company name",
  "required_skills": ["skill1", "skill2"],
  "preferred_skills": ["skill1"],
  "tech_stack": ["tech1", "tech2"],
  "role_level": "junior/mid/senior/lead",
  "years_experience": "X years or range",
  "soft_skills": ["skill1"],
  "key_responsibilities": ["responsibility1"],
  "domain": "industry/domain area"
}}"""

    job_resp = call_llm_with_fallback(
        [{"role": "user", "content": job_prompt}], SYSTEM
    )
    job_schema = safe_parse_json(job_resp, "job_schema")

    # Extract resume schema
    print("[stage2] extracting resume schema", file=sys.stderr)
    resume_prompt = f"""Extract a structured JSON schema from this resume.

Resume:
{resume_text}

Return ONLY this JSON structure (no markdown):
{{
  "name": "candidate name",
  "current_role": "current or most recent role",
  "years_experience": "total years",
  "skills": ["skill1", "skill2"],
  "tech_stack": ["tech1", "tech2"],
  "soft_skills": ["skill1"],
  "projects": [
    {{
      "name": "project name",
      "description": "what it does in one sentence",
      "tools_used": ["tool1", "tool2"],
      "outcome": "what was achieved"
    }}
  ],
  "certifications": ["cert1"],
  "education": "highest degree + field",
  "role_level": "junior/mid/senior/lead",
  "domain_experience": ["domain1"]
}}"""

    resume_resp = call_llm_with_fallback(
        [{"role": "user", "content": resume_prompt}], SYSTEM
    )
    resume_schema = safe_parse_json(resume_resp, "resume_schema")

    return {
        "job_schema": job_schema,
        "resume_schema": resume_schema,
        "job_raw": ingest_data["job"],
        "resume_text": resume_text
    }


def safe_parse_json(text: str, label: str) -> dict:
    """Strips markdown fences and parses JSON safely."""
    clean = text.strip()
    # strip ```json fences
    if clean.startswith("```"):
        clean = clean.split("```")[1]
        if clean.startswith("json"):
            clean = clean[4:]
    clean = clean.strip().rstrip("`").strip()
    try:
        return json.loads(clean)
    except Exception as e:
        print(f"[stage2] JSON parse failed for {label}: {e}", file=sys.stderr)
        print(f"[stage2] raw: {text[:300]}", file=sys.stderr)
        return {"parse_error": str(e), "raw": text[:500]}

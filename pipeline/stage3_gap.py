import sys
import json
from agent_loop import call_llm_with_fallback
from pipeline.stage2_extract import safe_parse_json

SYSTEM = """You are a career gap analysis expert. 
Analyze skill gaps precisely and return ONLY valid JSON. Be honest and specific."""

def analyze(extract_data: dict) -> dict:
    """
    Diffs job schema vs resume schema.
    Tags each gap as: critical / nice_to_have / already_strong
    with reasoning_type (technical/domain/soft_skill) and confidence score.
    """
    job_schema = extract_data["job_schema"]
    resume_schema = extract_data["resume_schema"]

    print("[stage3] running gap analysis", file=sys.stderr)

    prompt = f"""You are analyzing the gap between what a job requires and what a candidate has.

JOB REQUIREMENTS:
{json.dumps(job_schema, indent=2)}

CANDIDATE PROFILE:
{json.dumps(resume_schema, indent=2)}

Return ONLY this JSON (no markdown):
{{
  "overall_match_percent": 0-100,
  "summary": "2 sentence overall assessment",
  "gaps": [
    {{
      "item": "specific skill or requirement",
      "severity": "critical | nice_to_have | already_strong",
      "reasoning_type": "technical | domain | soft_skill | experience_level",
      "candidate_has": "what candidate currently has in this area, or 'nothing'",
      "job_requires": "what the job specifically needs",
      "confidence": 0.0-1.0,
      "suggested_action": "specific thing to do to close this gap"
    }}
  ],
  "strengths": ["list of areas where candidate clearly exceeds requirements"],
  "critical_missing": ["top 3 most important missing items"],
  "needs_human_review": ["items where confidence < 0.6"]
}}

Rules:
- confidence < 0.6 means the resume was ambiguous about this skill
- Mark items as 'already_strong' if candidate clearly has it
- Be specific in suggested_action (not generic advice)"""

    resp = call_llm_with_fallback(
        [{"role": "user", "content": prompt}], SYSTEM
    )
    gap_data = safe_parse_json(resp, "gap_analysis")

    return {
        **extract_data,
        "gap_analysis": gap_data
    }

import sys
import json
from agent_loop import call_llm_with_fallback
from pipeline.stage2_extract import safe_parse_json

SYSTEM = """You are an expert technical interviewer. 
Generate targeted, realistic interview questions based on the specific job and candidate.
Return ONLY valid JSON."""


def generate(ats_data: dict) -> dict:
    """
    Generates role-specific, behavioural, technical, and gap-targeted interview questions.
    """
    job_schema = ats_data["job_schema"]
    resume_schema = ats_data["resume_schema"]
    gap_analysis = ats_data["gap_analysis"]

    critical_gaps = [
        g for g in gap_analysis.get("gaps", [])
        if g.get("severity") == "critical"
    ]

    print("[stage6] generating interview questions", file=sys.stderr)

    prompt = f"""Generate a targeted interview question bank for this specific job and candidate.

JOB: {job_schema.get('title')} at {ats_data['job_raw'].get('company', '')}
ROLE LEVEL: {job_schema.get('role_level')}
KEY TECH: {json.dumps(job_schema.get('tech_stack', []))}
RESPONSIBILITIES: {json.dumps(job_schema.get('key_responsibilities', [])[:5])}

CANDIDATE BACKGROUND:
- Current role: {resume_schema.get('current_role')}
- Skills: {json.dumps(resume_schema.get('skills', [])[:10])}

CRITICAL GAPS (must ask about these):
{json.dumps(critical_gaps[:5], indent=2)}

Return ONLY this JSON (no markdown):
{{
  "technical": [
    {{
      "question": "specific technical question",
      "why_asked": "what the interviewer is probing for",
      "difficulty": "easy/medium/hard",
      "related_to": "skill or requirement this tests"
    }}
  ],
  "behavioural": [
    {{
      "question": "STAR-format behavioural question",
      "why_asked": "competency being assessed",
      "ideal_focus": "what a great answer would highlight"
    }}
  ],
  "gap_targeted": [
    {{
      "question": "question specifically targeting a gap",
      "gap_item": "which gap this probes",
      "why_critical": "why interviewer will likely ask this",
      "honest_approach": "how candidate should handle this gap honestly"
    }}
  ],
  "role_specific": [
    {{
      "question": "question about day-to-day responsibilities",
      "context": "scenario or situation it tests"
    }}
  ]
}}

Generate 4 questions per category."""

    resp = call_llm_with_fallback(
        [{"role": "user", "content": prompt}], SYSTEM
    )
    questions = safe_parse_json(resp, "interview_questions")

    return {
        **ats_data,
        "interview_questions": questions
    }

import sys
import json
from agent_loop import call_llm_with_fallback
from pipeline.stage2_extract import safe_parse_json
import pipeline.stage4_resume as stage4

SYSTEM = """You are an ATS (Applicant Tracking System) scoring expert.
Score resumes objectively and return ONLY valid JSON."""

ATS_THRESHOLD = 80
MAX_CYCLES = 3


def score(build_data: dict) -> dict:
    """
    Scores the rewritten resume against the job description.
    Returns keyword density, section completeness, and match %.
    """
    job_schema = build_data["job_schema"]
    resume_built = build_data["resume_built"]
    rewritten = resume_built.get("rewritten_resume", "")

    required = job_schema.get("required_skills", [])
    preferred = job_schema.get("preferred_skills", [])
    tech = job_schema.get("tech_stack", [])
    all_keywords = list(set(required + preferred + tech))

    print("[stage5] scoring ATS match", file=sys.stderr)

    prompt = f"""Score this rewritten resume against the job requirements using ATS criteria.

JOB REQUIREMENTS:
- Required skills: {json.dumps(required)}
- Preferred skills: {json.dumps(preferred)}
- Tech stack: {json.dumps(tech)}
- Role level: {job_schema.get('role_level', '')}
- Key responsibilities: {json.dumps(job_schema.get('key_responsibilities', []))}

REWRITTEN RESUME:
{rewritten[:3000]}

Score each category 0-100 and return ONLY this JSON (no markdown):
{{
  "overall_score": 0-100,
  "keyword_density_score": 0-100,
  "section_completeness_score": 0-100,
  "relevance_score": 0-100,
  "present_keywords": ["keywords found in resume"],
  "missing_keywords": ["required keywords NOT found in resume"],
  "section_feedback": {{
    "summary": "present/missing/weak",
    "experience": "present/missing/weak",
    "skills": "present/missing/weak",
    "projects": "present/missing/weak",
    "education": "present/missing/weak"
  }},
  "improvement_notes": ["specific things to add or change"],
  "passes_threshold": true/false
}}

passes_threshold = true if overall_score >= {ATS_THRESHOLD}"""

    resp = call_llm_with_fallback(
        [{"role": "user", "content": prompt}], SYSTEM
    )
    ats_result = safe_parse_json(resp, "ats_score")
    ats_result["passes_threshold"] = ats_result.get("overall_score", 0) >= ATS_THRESHOLD

    return ats_result


def run(build_data: dict) -> dict:
    """
    ATS score + refine loop. Loops back to stage4 if score < threshold.
    Max MAX_CYCLES refinement cycles.
    """
    current_data = build_data
    ats_history = []

    for cycle in range(MAX_CYCLES):
        print(f"[stage5] ATS cycle {cycle+1}/{MAX_CYCLES}", file=sys.stderr)
        ats_result = score(current_data)
        ats_result["cycle"] = cycle + 1
        ats_history.append(ats_result)

        overall = ats_result.get("overall_score", 0)
        print(f"[stage5] score: {overall} | threshold: {ATS_THRESHOLD} | passes: {ats_result.get('passes_threshold')}", file=sys.stderr)

        if ats_result.get("passes_threshold") or cycle == MAX_CYCLES - 1:
            break

        # loop back: inject missing keywords feedback into stage4
        missing = ats_result.get("missing_keywords", [])
        notes = ats_result.get("improvement_notes", [])
        print(f"[stage5] refining — missing keywords: {missing}", file=sys.stderr)

        # patch gap_data with ATS feedback before re-running stage4
        current_data = dict(current_data)
        current_data["ats_feedback"] = {
            "missing_keywords": missing,
            "improvement_notes": notes,
            "previous_score": overall
        }
        # add missing keywords to job required skills for next build
        existing = current_data["job_schema"].get("required_skills", [])
        current_data["job_schema"]["required_skills"] = list(set(existing + missing))

        current_data = stage4.build(current_data, iteration=cycle + 1)

    return {
        **current_data,
        "ats_score": ats_history[-1],
        "ats_history": ats_history,
        "total_cycles": len(ats_history)
    }

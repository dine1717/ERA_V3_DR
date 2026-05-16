import sys
import json
from agent_loop import call_llm_with_fallback
from pipeline.stage2_extract import safe_parse_json

SYSTEM = """You are a senior technical interviewer who specialises in deep-diving on candidate projects.
Generate realistic, specific questions an interviewer would ask about EACH project.
Return ONLY valid JSON."""


def generate(questions_data: dict) -> dict:
    """
    Parses every project and tool from the resume.
    For each project: generates 3 interview questions + preferred STAR answer.
    Tags each with reasoning_type: technical / design / reflection.
    """
    resume_schema = questions_data["resume_schema"]
    job_schema = questions_data["job_schema"]
    projects = resume_schema.get("projects", [])

    if not projects:
        print("[stage7] no projects found in resume schema", file=sys.stderr)
        return {**questions_data, "project_qa": []}

    print(f"[stage7] generating deep-dive Q&A for {len(projects)} projects", file=sys.stderr)

    all_project_qa = []

    for project in projects:
        project_name = project.get("name", "Unnamed Project")
        print(f"[stage7] processing project: {project_name}", file=sys.stderr)

        prompt = f"""You are interviewing a candidate about this specific project from their resume.

PROJECT:
Name: {project_name}
Description: {project.get('description', '')}
Tools used: {json.dumps(project.get('tools_used', []))}
Outcome: {project.get('outcome', '')}

JOB THEY ARE APPLYING FOR: {job_schema.get('title')} — focuses on {json.dumps(job_schema.get('tech_stack', [])[:5])}

Generate exactly 3 interview questions an interviewer would REALISTICALLY ask about this project.
For each question, write a preferred STAR-format answer using the candidate's actual project details.

Return ONLY this JSON (no markdown):
{{
  "project": "{project_name}",
  "tools_used": {json.dumps(project.get('tools_used', []))},
  "questions": [
    {{
      "q": "the interview question",
      "reasoning_type": "technical | design | reflection",
      "why_likely": "why an interviewer would ask this specific question",
      "preferred_answer": {{
        "situation": "set the scene — what was the context",
        "task": "what specifically needed to be done",
        "action": "what YOU did step by step — be specific and technical",
        "result": "measurable outcome or learning",
        "full_answer": "natural flowing version of the STAR answer"
      }},
      "follow_up": "the natural follow-up question after this answer",
      "confidence_note": "high | medium | needs_more_detail_on_resume"
    }}
  ]
}}

Rules:
- Questions must be SPECIFIC to this project, not generic
- Preferred answers must use the actual tools and outcomes from the project
- If the resume has too little detail, set confidence_note to needs_more_detail_on_resume
- Reflection questions probe: what went wrong, what you'd do differently, trade-offs made"""

        resp = call_llm_with_fallback(
            [{"role": "user", "content": prompt}], SYSTEM
        )
        project_qa = safe_parse_json(resp, f"project_qa_{project_name}")
        all_project_qa.append(project_qa)

    return {
        **questions_data,
        "project_qa": all_project_qa
    }

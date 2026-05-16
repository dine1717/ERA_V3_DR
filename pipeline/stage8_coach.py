import sys
import json
from agent_loop import call_llm_with_fallback
from pipeline.stage2_extract import safe_parse_json

SYSTEM = """You are a rigorous but encouraging mock interview coach.
You score answers on the STAR framework and give specific, actionable feedback.
Return ONLY valid JSON."""


def get_next_question(project_qa: list, interview_questions: dict, asked: list) -> dict | None:
    """
    Picks the next question to ask in the mock session.
    Prioritises gap-targeted, then project deep-dive, then technical.
    Skips already-asked questions.
    """
    # gap-targeted first
    for q in interview_questions.get("gap_targeted", []):
        if q["question"] not in asked:
            return {"question": q["question"], "source": "gap_targeted", "context": q.get("why_critical", "")}

    # project deep-dive
    for project in project_qa:
        for qa in project.get("questions", []):
            if qa["q"] not in asked:
                return {
                    "question": qa["q"],
                    "source": f"project:{project.get('project', '')}",
                    "context": qa.get("why_likely", ""),
                    "preferred_answer": qa.get("preferred_answer", {}),
                    "follow_up": qa.get("follow_up", "")
                }

    # technical questions
    for q in interview_questions.get("technical", []):
        if q["question"] not in asked:
            return {"question": q["question"], "source": "technical", "context": q.get("why_asked", "")}

    # behavioural
    for q in interview_questions.get("behavioural", []):
        if q["question"] not in asked:
            return {"question": q["question"], "source": "behavioural", "context": q.get("why_asked", "")}

    return None


def score_answer(question: str, user_answer: str, preferred_answer: dict, project_context: str) -> dict:
    """
    Scores a user's interview answer on STAR framework.
    Returns score + rewritten stronger version + follow-up question.
    """
    print(f"[stage8] scoring answer for: {question[:80]}", file=sys.stderr)

    preferred_str = json.dumps(preferred_answer) if preferred_answer else "No preferred answer available — judge on STAR quality alone."

    prompt = f"""Score this interview answer using the STAR framework.

QUESTION: {question}

CANDIDATE'S ANSWER:
{user_answer}

PREFERRED ANSWER BENCHMARK:
{preferred_str}

PROJECT CONTEXT: {project_context}

Evaluate strictly but fairly. Return ONLY this JSON (no markdown):
{{
  "scores": {{
    "situation": 0-10,
    "task": 0-10,
    "action": 0-10,
    "result": 0-10,
    "overall": 0-10
  }},
  "feedback": {{
    "what_worked": "specific things the candidate did well",
    "what_was_missing": "specific STAR elements that were weak or absent",
    "key_improvement": "the single most important thing to add or change"
  }},
  "rewritten_answer": "a stronger version of their answer using their details but better STAR structure",
  "follow_up_question": "the natural follow-up question an interviewer would ask next",
  "score_label": "strong | good | needs_work | incomplete"
}}

Scoring guide:
- situation 0-10: did they set context clearly?
- task 0-10: did they explain their specific responsibility?
- action 0-10: did they describe what THEY did, with specifics?
- result 0-10: did they quantify or clearly state the outcome?
- overall = average of the four"""

    resp = call_llm_with_fallback(
        [{"role": "user", "content": prompt}], SYSTEM
    )
    return safe_parse_json(resp, "star_score")


def start_session(pipeline_data: dict) -> dict:
    """
    Initialises a mock interview session state.
    Returns the first question and session state dict.
    """
    project_qa = pipeline_data.get("project_qa", [])
    interview_questions = pipeline_data.get("interview_questions", {})

    first_q = get_next_question(project_qa, interview_questions, [])

    session = {
        "project_qa": project_qa,
        "interview_questions": interview_questions,
        "asked": [],
        "history": [],
        "current_question": first_q
    }

    return session


def process_answer(session: dict, user_answer: str) -> dict:
    """
    Processes user's answer to current question.
    Scores it, then advances to next question.
    Returns updated session with score and next question.
    """
    current_q = session.get("current_question", {})
    question_text = current_q.get("question", "")
    preferred = current_q.get("preferred_answer", {})
    context = current_q.get("context", "")

    # score the answer
    score_result = score_answer(question_text, user_answer, preferred, context)

    # record in history
    session["history"].append({
        "question": question_text,
        "source": current_q.get("source", ""),
        "user_answer": user_answer,
        "score": score_result
    })
    session["asked"].append(question_text)

    # get next question
    next_q = get_next_question(
        session["project_qa"],
        session["interview_questions"],
        session["asked"]
    )

    session["current_question"] = next_q
    session["last_score"] = score_result

    return session

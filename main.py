import os
import sys
import json
import uuid
import threading
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

load_dotenv()

from pipeline import stage1_ingest, stage2_extract, stage3_gap, stage4_resume, stage5_ats, stage6_questions, stage7_projects, stage8_coach

app = FastAPI(title="CareerCraft AI")
templates = Jinja2Templates(directory="templates")

pipeline_state = {}
mock_session_state = {}
progress_store = {}  # job_id -> {logs, done, result, error}


# ── helpers ──────────────────────────────────────────────────────────────────

def push_log(job_id, stage, status, message):
    progress_store[job_id]["logs"].append({
        "stage": stage, "status": status, "message": message
    })
    print(f"[S{stage}] {status}: {message}", file=sys.stderr)


def run_pipeline_job(job_id, job_url, resume_text):
    try:
        push_log(job_id, 1, "running", "Ingesting job URL and resume...")
        s1 = stage1_ingest.ingest(job_url, resume_text)
        push_log(job_id, 1, "done", f"Got: {s1['job']['title']} at {s1['job']['company']}")

        push_log(job_id, 2, "running", "Extracting structured schemas...")
        s2 = stage2_extract.extract(s1)
        push_log(job_id, 2, "done", f"Extracted {len(s2['job_schema'].get('required_skills', []))} required skills")

        push_log(job_id, 3, "running", "Analyzing skill gaps...")
        s3 = stage3_gap.analyze(s2)
        gaps = s3["gap_analysis"].get("gaps", [])
        critical = len([g for g in gaps if g.get("severity") == "critical"])
        push_log(job_id, 3, "done", f"Found {len(gaps)} gaps ({critical} critical)")

        push_log(job_id, 4, "running", "Building tailored resume...")
        s4 = stage4_resume.build(s3)
        push_log(job_id, 4, "done", f"Injected {len(s4['resume_built'].get('injected_keywords', []))} keywords")

        push_log(job_id, 5, "running", "Scoring ATS match + refine loop...")
        s5 = stage5_ats.run(s4)
        push_log(job_id, 5, "done", f"ATS score: {s5['ats_score'].get('overall_score', 0)}% after {s5['total_cycles']} cycle(s)")

        push_log(job_id, 6, "running", "Generating interview questions...")
        s6 = stage6_questions.generate(s5)
        q_count = sum(len(s6["interview_questions"].get(k, [])) for k in ["technical", "behavioural", "gap_targeted", "role_specific"])
        push_log(job_id, 6, "done", f"Generated {q_count} questions")

        push_log(job_id, 7, "running", "Generating project deep-dive Q&A...")
        s7 = stage7_projects.generate(s6)
        push_log(job_id, 7, "done", f"Deep-dive Q&A for {len(s7['project_qa'])} project(s)")

        pipeline_state["latest"] = s7
        progress_store[job_id]["result"] = {
            "job": s7["job_raw"],
            "gap_analysis": s7["gap_analysis"],
            "resume_built": s7["resume_built"],
            "ats_score": s7["ats_score"],
            "ats_history": s7["ats_history"],
            "interview_questions": s7["interview_questions"],
            "project_qa": s7["project_qa"],
            "resume_schema": s7["resume_schema"],
            "job_schema": s7["job_schema"]
        }

    except Exception as e:
        import traceback
        traceback.print_exc(file=sys.stderr)
        progress_store[job_id]["error"] = str(e)
    finally:
        progress_store[job_id]["done"] = True


# ── routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/run_pipeline")
async def run_pipeline(request: Request):
    """Starts pipeline in background thread, returns job_id immediately."""
    data = await request.json()
    job_url = data.get("job_url", "").strip()
    resume_text = data.get("resume_text", "").strip()
    if not job_url or not resume_text:
        return JSONResponse({"error": "job_url and resume_text are required"}, status_code=400)

    job_id = str(uuid.uuid4())[:8]
    progress_store[job_id] = {"logs": [], "done": False, "result": None, "error": None}
    threading.Thread(target=run_pipeline_job, args=(job_id, job_url, resume_text), daemon=True).start()
    return JSONResponse({"ok": True, "job_id": job_id})


@app.get("/api/progress/{job_id}")
async def get_progress(job_id: str):
    """Frontend polls every 2s to get stage updates."""
    store = progress_store.get(job_id)
    if not store:
        return JSONResponse({"error": "job not found"}, status_code=404)
    return JSONResponse({
        "logs": store["logs"],
        "done": store["done"],
        "result": store["result"],
        "error": store["error"]
    })


@app.post("/api/mock/start")
async def mock_start():
    state = pipeline_state.get("latest")
    if not state:
        return JSONResponse({"error": "Run the pipeline first"}, status_code=400)
    session_data = stage8_coach.start_session(state)
    mock_session_state["current"] = session_data
    first_q = session_data.get("current_question")
    if not first_q:
        return JSONResponse({"error": "No questions available"}, status_code=400)
    return JSONResponse({"ok": True, "question": first_q.get("question"),
                         "source": first_q.get("source"), "context": first_q.get("context"),
                         "question_number": 1})


@app.post("/api/mock/answer")
async def mock_answer(request: Request):
    data = await request.json()
    user_answer = data.get("answer", "").strip()
    if not user_answer:
        return JSONResponse({"error": "answer is required"}, status_code=400)
    session_data = mock_session_state.get("current")
    if not session_data:
        return JSONResponse({"error": "No active mock session"}, status_code=400)
    updated = stage8_coach.process_answer(session_data, user_answer)
    mock_session_state["current"] = updated
    score = updated.get("last_score", {})
    next_q = updated.get("current_question")
    return JSONResponse({"ok": True, "score": score,
                         "questions_answered": len(updated.get("history", [])),
                         "next_question": next_q.get("question") if next_q else None,
                         "next_source": next_q.get("source") if next_q else None,
                         "next_context": next_q.get("context") if next_q else None,
                         "session_complete": next_q is None})


@app.get("/api/mock/history")
async def mock_history():
    session_data = mock_session_state.get("current")
    if not session_data:
        return JSONResponse({"history": []})
    return JSONResponse({"history": session_data.get("history", [])})


@app.get("/api/prompts")
async def get_prompts():
    try:
        draft = Path("prompts/draft_prompt.txt").read_text()
        qualified = Path("prompts/qualified_prompt.txt").read_text()
        return JSONResponse({"draft": draft, "qualified": qualified})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/evaluate_prompt")
async def evaluate_prompt(request: Request):
    """Runs the 9-criteria rubric against any submitted prompt using Gemini."""
    from agent_loop import call_llm_with_fallback
    data = await request.json()
    prompt_text = data.get("prompt", "").strip()
    if not prompt_text:
        return JSONResponse({"error": "prompt is required"}, status_code=400)

    system = (
        "You are a Prompt Evaluation Assistant.\n\n"
        "You will receive a prompt written by a student. Your job is to review this prompt "
        "and assess how well it supports structured, step-by-step reasoning in an LLM "
        "(e.g., for math, logic, planning, or tool use).\n\n"
        "Evaluate the prompt on the following criteria:\n\n"
        "1. Explicit Reasoning Instructions\n"
        "   - Does the prompt tell the model to reason step-by-step?\n"
        "   - Does it include instructions like 'explain your thinking' or 'think before you answer'?\n\n"
        "2. Structured Output Format\n"
        "   - Does the prompt enforce a predictable output format (e.g., FUNCTION_CALL, JSON, numbered steps)?\n"
        "   - Is the output easy to parse or validate?\n\n"
        "3. Separation of Reasoning and Tools\n"
        "   - Are reasoning steps clearly separated from computation or tool-use steps?\n"
        "   - Is it clear when to calculate, when to verify, when to reason?\n\n"
        "4. Conversation Loop Support\n"
        "   - Could this prompt work in a back-and-forth (multi-turn) setting?\n"
        "   - Is there a way to update the context with results from previous steps?\n\n"
        "5. Instructional Framing\n"
        "   - Are there examples of desired behavior or 'formats' to follow?\n"
        "   - Does the prompt define exactly how responses should look?\n\n"
        "6. Internal Self-Checks\n"
        "   - Does the prompt instruct the model to self-verify or sanity-check intermediate steps?\n\n"
        "7. Reasoning Type Awareness\n"
        "   - Does the prompt encourage the model to tag or identify the type of reasoning used "
        "(e.g., arithmetic, logic, lookup)?\n\n"
        "8. Error Handling or Fallbacks\n"
        "   - Does the prompt specify what to do if an answer is uncertain, a tool fails, or the model is unsure?\n\n"
        "9. Overall Clarity and Robustness\n"
        "   - Is the prompt easy to follow?\n"
        "   - Is it likely to reduce hallucination and drift?\n\n"
        "Respond with ONLY valid JSON, no markdown fences, no explanation:\n"
        "{\n"
        "  \"explicit_reasoning\": true or false,\n"
        "  \"structured_output\": true or false,\n"
        "  \"tool_separation\": true or false,\n"
        "  \"conversation_loop\": true or false,\n"
        "  \"instructional_framing\": true or false,\n"
        "  \"internal_self_checks\": true or false,\n"
        "  \"reasoning_type_awareness\": true or false,\n"
        "  \"fallbacks\": true or false,\n"
        "  \"overall_clarity\": \"one sentence assessment mentioning score X/8\"\n"
        "}"
    )

    eval_prompt = "Evaluate this student prompt using the rubric in your system instructions.\nReturn ONLY the JSON object.\n\nPROMPT TO EVALUATE:\n" + prompt_text

    raw = ""
    try:
        raw = call_llm_with_fallback([{"role": "user", "content": eval_prompt}], system)
        clean = raw.strip()
        if clean.startswith("```"):
            parts = clean.split("```")
            clean = parts[1] if len(parts) > 1 else clean
            if clean.startswith("json"):
                clean = clean[4:]
        clean = clean.strip().rstrip("`").strip()
        parsed = json.loads(clean)
        return JSONResponse({"ok": True, "result": parsed})
    except Exception as e:
        print(f"[evaluate_prompt] error: {e}", file=sys.stderr)
        return JSONResponse({"ok": False, "error": str(e), "raw": raw}, status_code=500)


if __name__ == "__main__":
    import uvicorn
    print("[main] CareerCraft AI starting on http://localhost:5000", file=sys.stderr)
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)
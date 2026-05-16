# CareerCraft AI

**ERA V3 · Session 5 Assignment**

An 8-stage agentic pipeline that turns a LinkedIn job URL + your resume into a tailored ATS-optimised resume, gap analysis, interview question bank, project-specific deep-dive Q&A with preferred STAR answers, and a live mock interview coach — all driven by a prompt qualified against the 9-criteria rubric.

---

## Prompt Qualification
<img width="1890" height="836" alt="Screenshot 2026-05-16 at 11 05 51 AM" src="https://github.com/user-attachments/assets/d0a912bc-f58e-48d7-99f4-32ad14259ae4" />


### Final Qualified Prompt (after patching — see `prompts/qualified_prompt.txt`)
The qualified prompt enforces:
- `THINKING:` step before every action (explicit reasoning)
- Strict JSON output schema per stage (structured output)
- Named tools with single responsibilities (tool separation)
- Full conversation history in Stage 8 (conversation loop)
- Good/bad examples for bullet rewriting and STAR answers (instructional framing)
- `SELF_CHECK:` verification after every rewrite and gap tag (internal self-checks)
- `reasoning_type` field on every gap and question: `technical | domain | soft_skill` (type awareness)
- `needs_human_review` list + max-cycle exit with report (fallbacks)
- Exact enum values enforced: `critical`, `nice_to_have`, `already_strong` (overall clarity)

### My Final Prompt

https://github.com/dine1717/ERA_V3_DR/blob/Session5/prompts/qualified_prompt.txt

---

## Pipeline: 8 Stages

| Stage | Name | What it does |
|-------|------|-------------|
| 1 | Ingest | Scrapes LinkedIn job URL via BeautifulSoup, accepts resume as text |
| 2 | Extract | Structured JSON extraction — skills, stack, role level, projects, tools |
| 3 | Gap Analysis | Diffs job vs resume; tags each gap: severity + reasoning_type + confidence |
| 4 | Resume Builder | Rewrites bullets with keyword injection; self-checks each bullet |
| 5 | ATS Score Loop | Scores rewritten resume; loops back to Stage 4 until 80% or 3 cycles |
| 6 | Questions | Generates gap-targeted, technical, behavioural, role-specific questions |
| 7 | Project Q&A | Per-project: 3 questions + preferred STAR answer using actual resume details |
| 8 | Mock Coach | Multi-turn: answer → STAR score → rewrite → follow-up question |

---

## Sample Pipeline Output

### Input
- Job: Senior ML Engineer at a fintech company
- Resume: 3 years Python, built FastMCP server, Chrome extension, Gemini agentic loop

### Stage 3 Gap Analysis (sample)
```json
{
  "overall_match_percent": 62,
  "gaps": [
    {
      "item": "MLOps / model deployment",
      "severity": "critical",
      "reasoning_type": "technical",
      "confidence": 0.9,
      "suggested_action": "Add a project deploying a model to a REST endpoint with monitoring"
    },
    {
      "item": "LLM fine-tuning",
      "severity": "nice_to_have",
      "reasoning_type": "technical",
      "confidence": 0.7,
      "suggested_action": "Mention any LoRA or prompt-tuning experiments in projects"
    }
  ]
}
```

### Stage 5 ATS Score Loop
```
Cycle 1: 61% → below threshold, refining...
Cycle 2: 74% → below threshold, refining...
Cycle 3: 83% → passes threshold ✓
```

### Stage 7 Project Q&A (sample)
```json
{
  "project": "MCP server with FastMCP",
  "tools_used": ["Python", "FastMCP", "Gemini"],
  "questions": [
    {
      "q": "Why did you choose FastMCP over building raw MCP tooling?",
      "reasoning_type": "design",
      "preferred_answer": {
        "situation": "At ERA V3 Session 4, I was assigned to build an MCP server with 3 tool categories",
        "task": "I needed to implement an internet tool, file CRUD, and a Prefab UI within a single session",
        "action": "I chose FastMCP because its @mcp.tool(app=True) decorator handles the Prefab UI pattern natively, saving ~200 lines of boilerplate. I redirected all print() to stderr to keep the stdio JSON stream clean.",
        "result": "Delivered working demo with all 3 categories + live Prefab dashboard in one session"
      },
      "follow_up": "What broke during development and how did you debug it?"
    }
  ]
}
```

---

## How to Run

```bash
# 1. Clone and enter the folder
cd careercraft

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create .env (UTF-8)
echo "GEMINI_API_KEY=your_key_here" > .env

# 4. Run
python main.py
```

Open `http://localhost:5000`

1. Paste a LinkedIn job URL (or paste the job description directly)
2. Paste your full resume text
3. Click **Run Full Pipeline (Stages 1–7)**
4. Watch stages complete in the sidebar
5. Browse tabs: Gap Analysis → Resume → Questions → Project Q&A
6. Click **Mock Interview** tab → **Start Session** for live coaching

---

## Tech Stack

- Python 3.11 + Flask
- Gemini `gemini-2.5-flash` (fallback: `gemini-2.0-flash`, `gemini-1.5-flash`)
- `FUNCTION_CALL: tool|arg1|arg2` agentic protocol (mirrors `AgenticMCPUse.py`)
- BeautifulSoup for LinkedIn scraping
- All `print()` redirected to `sys.stderr` (stdout reserved for Flask)

## Project Structure

```
careercraft/
├── main.py                   # Flask app + API routes
├── agent_loop.py             # FUNCTION_CALL agentic loop
├── pipeline/
│   ├── stage1_ingest.py
│   ├── stage2_extract.py
│   ├── stage3_gap.py
│   ├── stage4_resume.py
│   ├── stage5_ats.py         # ← ATS loop (Stage 4 ↔ Stage 5)
│   ├── stage6_questions.py
│   ├── stage7_projects.py    # ← Project deep-dive Q&A
│   └── stage8_coach.py       # ← STAR-scoring mock coach
├── prompts/
│   ├── draft_prompt.txt      # Before qualification
│   └── qualified_prompt.txt  # After — used in production
├── templates/index.html
├── requirements.txt
└── .env
```

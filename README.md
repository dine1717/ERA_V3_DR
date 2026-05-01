# Session 3 — Job Application Helper (Chrome Extension)

A Chrome extension that scrapes any job posting and runs a **3-turn Gemini agentic loop** to generate tailored cover letters or updated resumes.

## Files

| File | Purpose |
|------|---------|
| `manifest.json` | Chrome MV3 config — declares permissions and content scripts |
| `content.js` | Runs on every page — scrapes job description text from LinkedIn, Naukri, Indeed, Glassdoor |
| `agent.js` | Core 3-turn agentic loop — calls Gemini 3 times with full history |
| `popup.html` | Extension UI — mode toggle, reasoning chain, score, output |
| `popup.js` | UI logic — wires buttons, calls agent, renders results |

## How the Agent Loop Works

```
Turn 1: extract_job_details(page_text)
  → Sends raw scraped text to Gemini
  → LLM extracts: role, company, skills, required keywords

Turn 2: match_resume_to_job(job_details, base_resume)
  → Compares resume against job keywords
  → Returns: match score %, present keywords, missing keywords

Turn 3: generate_output(mode)
  → Generates cover letter OR updated resume
  → Missing keywords from Turn 2 woven in naturally
```

Full conversation history is passed to each Gemini call — the model sees everything.

## Setup

1. Get a free Gemini API key at https://aistudio.google.com/app/apikey
2. Go to `chrome://extensions` → Enable Developer Mode → Load Unpacked → select this folder
3. Click extension icon → Settings → paste API key + your resume
4. Navigate to any job posting → click **Analyze This Job & Generate**

## The 3 Tool Functions (in agent.js)

| Tool | What it does |
|------|-------------|
| `extract_job_details(page_text)` | Structures raw scraped text |
| `match_resume_to_job(job_details, base_resume)` | Keyword gap analysis with score |
| `generate_output(mode, context)` | Signals LLM to produce final output |

## Supported Job Sites
LinkedIn · Naukri · Indeed · Glassdoor · Internshala · Any company careers page

---
---

# Session 4 — MCP Server + Prefab UI

Extends Session 3 by adding a Python MCP server with 3 tools, a Prefab dashboard, and connecting the Chrome extension to call the MCP tools live.

## Architecture

```
Chrome Extension (Session 3 code + new MCP tab)
        │
        │  fetch() calls to localhost:5055
        ▼
Flask HTTP Bridge (runs inside mcp_server.py)
        │
        ▼
MCP Server (FastMCP — same pattern as class example_mcp_server.py)
   ├── Tool 1: fetch_job_data()      ← internet (HN Algolia API)
   ├── Tool 2: manage_notes()        ← CRUD on notes.json
   └── Tool 3: show_ui()             ← triggers Prefab dashboard
        │
        ▼
dashboard.py  ← reads notes.json, renders Prefab UI
        │
        ▼
prefab serve dashboard.py → http://127.0.0.1:5175
```

## MCP Backend Files

| File | Purpose |
|------|---------|
| `mcp_server.py` | MCP server with 3 tools + Flask HTTP bridge on port 5055 |
| `agent.py` | Agentic loop — mirrors class AgenticMCPUse.py |
| `dashboard.py` | Prefab UI — reads notes.json and renders dashboard |
| `notes.json` | Local data file written by MCP tools (auto-created) |
| `requirements.txt` | Python dependencies |

## The 3 MCP Tools

### Tool 1 — Internet: `fetch_job_data(job_title, company)`
Calls the **free HackerNews Algolia API** — no API key needed.
Returns real interview questions. Auto-saves to `notes.json`.

### Tool 2 — CRUD: `manage_notes(action, title, content, note_id)`
Full create / read / update / delete on local `notes.json`.
Same pattern as class `write_file` / `read_file` / `edit_file`.

| action | what happens |
|--------|-------------|
| create | adds note to notes.json |
| read   | returns all notes |
| update | edits existing note |
| delete | removes note |

### Tool 3 — Prefab UI: `show_ui()`
Returns instructions to open the Prefab dashboard.
Dashboard reads `notes.json` (written by Tools 1 & 2) and renders it.

## Setup & Run

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Add Gemini API key
echo "GEMINI_API_KEY=your_key_here" > .env

# 3. Start MCP server (keep this running)
python mcp_server.py

# 4. In a new terminal — run the agent demo
python agent.py

# 5. After agent finishes — open the Prefab dashboard
prefab serve dashboard.py
# → open http://127.0.0.1:5175
```

## The Demo Prompt (forces all 3 tools)

Inside `agent.py`, this single task is given to the agent:

> *"I want to research the ML Engineer role at Google. Use fetch_job_data to get interview questions from the internet. Use manage_notes to save a summary note. Use show_ui to get instructions for opening the Prefab dashboard."*

This forces the agent to call all 3 tools in sequence — satisfying the assignment requirement.

## Chrome Extension — MCP Tools Tab

The extension popup now has a second tab **"🔧 MCP Tools"** that:
- Shows live server status (green/red dot)
- Has buttons that call each MCP tool directly via Flask bridge
- Tool 1 button → calls `fetch_job_data` → shows interview questions
- Tool 2 buttons → `manage_notes(create)` and `manage_notes(read)`  
- Tool 3 button → calls `show_ui` → tells you to run `prefab serve`

## Data Flow (how notes get into the dashboard)

```
Agent runs:
  fetch_job_data("ML Engineer", "Google")
      └─→ hits HackerNews API
      └─→ writes to notes.json  ← [CRUD write]

  manage_notes("create", "My Note", "content")  
      └─→ writes to notes.json  ← [CRUD write]

  show_ui()
      └─→ returns "run prefab serve dashboard.py"

You run:
  prefab serve dashboard.py
      └─→ reads notes.json  ← [CRUD read]
      └─→ renders dashboard at http://127.0.0.1:5175
```

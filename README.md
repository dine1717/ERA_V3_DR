# Job Researcher — MCP Server + Web App + Prefab UI

An end-to-end job research tool built with **Model Context Protocol (MCP)**.
Search for jobs, save them to a file, and view an interactive dashboard — all powered by 3 MCP tools.

---

## Assignment Mapping

| Requirement | Implementation |
|---|---|
| **MCP Server with 3 tools** | `job_researcher_mcp_server.py` |
| 1. Internet (search/API) | `search_jobs()` — scrapes LinkedIn + Jobicy API |
| 2. CRUD on local file | `save/read/append/delete_jobs_file()` |
| 3. Communicates via UI | `show_job_dashboard()` → Prefab + Web dashboard |
| **Prefab UI** | `generated_dashboard.py` (auto-generated with charts) |
| **Web App (interactive)** | `web_app.py` — Flask app at `http://localhost:5000` |
| **Prompt using all 3 tools** | `EXAMPLE_PROMPT.py` + `job_researcher_agent.py` |

---

## How It Works

```
Browser (localhost:5000)
  │
  ├── User types "Python developer" → clicks "Search Jobs"
  │     └── Calls search_jobs()          ← TOOL 1: INTERNET
  │           └── Scrapes LinkedIn + Jobicy API
  │
  ├── User clicks "Analyze & Save"
  │     └── Enriches with Gemini (keywords + interview questions)
  │     └── Calls save_jobs_to_file()    ← TOOL 2: FILE CRUD
  │           └── Writes sandbox/jobs_data.txt
  │
  └── User clicks "Show Dashboard"
        └── Calls show_job_dashboard()   ← TOOL 3: UI
              ├── Generates dashboard data (stats, charts)
              ├── Creates generated_dashboard.py (Prefab file)
              └── Returns data for web frontend
```

---

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up Gemini key (optional — basic keyword extraction works without it)
cp .env.example .env
# Edit .env → add GEMINI_API_KEY from https://aistudio.google.com/apikey

# 3. Run the web app
python web_app.py

# 4. Open browser → http://localhost:5000
```

---

## Usage — Web App (Recommended)

1. **Open** `http://localhost:5000`
2. **Type** a job keyword (e.g. "Python developer", "ML Engineer", "React")
3. **Click** "Search Jobs" → scrapes the internet for listings
4. **Click** "Analyze & Save" → enriches with keywords + interview questions, saves to file
5. **Click** "Show Dashboard" → renders the full dashboard with:
   - **Overview**: job count, sources pie chart, stats
   - **Job Listings**: each job with badges and descriptions
   - **Keywords**: skill frequency badges + bar chart
   - **Interview Prep**: per-job interview questions
   - **Saved Files**: view/delete the saved text file
6. **Click** "New Search" to search with different keywords

---

## Usage — Agentic Client (CLI)

Runs all 3 tools automatically via Gemini:

```bash
python job_researcher_agent.py
# or:
python job_researcher_agent.py "machine learning engineer"
```

The agent chains: `search_jobs()` → `save_jobs_to_file()` → `show_job_dashboard()`

---

## Usage — Prefab Dashboard

If you have `prefab-ui` installed and have run a search (so `generated_dashboard.py` exists):

```bash
prefab serve generated_dashboard.py --reload
# Open http://127.0.0.1:5175
```

---

## Usage — MCP Dev Inspector

```bash
# Text tools inspector
fastmcp dev job_researcher_mcp_server.py

# Prefab-aware preview (for UI tools)
fastmcp dev apps job_researcher_mcp_server.py
```

---

## Project Files

| File | What it does |
|---|---|
| `job_researcher_mcp_server.py` | MCP server with all 3 tool categories |
| `web_app.py` | Flask web app — interactive frontend |
| `templates/index.html` | Dashboard UI with Chart.js |
| `job_researcher_agent.py` | Agentic client (Gemini auto-chains tools) |
| `generated_dashboard.py` | Auto-generated Prefab dashboard file |
| `EXAMPLE_PROMPT.py` | Documents the prompt that uses all 3 tools |
| `sandbox/` | Where job data files are saved (created at runtime) |

---

## The Prompt (forces all 3 tools)

> "Find 5 job listings for 'Python developer' in 'India'. Enrich each job
> with keywords and interview questions. Save to file. Show on dashboard."

Agent trace:
```
Iteration 1: FUNCTION_CALL: search_jobs|Python developer|India|5     ← INTERNET
Iteration 2: (LLM enriches each job with keywords + questions)
Iteration 3: FUNCTION_CALL: save_jobs_to_file|<enriched_json>        ← FILE CRUD
Iteration 4: FUNCTION_CALL: show_job_dashboard|<enriched_json>       ← UI
Iteration 5: FINAL_ANSWER: Done. 5 jobs saved and dashboard ready.
```

---

## Session 3 Connection

This extends the [Session 3 Job Application Helper](https://github.com/dine1717/ERA_V3_DR/blob/Session3/README.md) Chrome extension by:
- Wrapping scraping logic as MCP tools (standardized protocol)
- Adding Prefab UI for interactive dashboards  
- Adding file CRUD for persistent storage
- Adding a Flask web app for interactive keyword search

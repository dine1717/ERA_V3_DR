"""
EXAMPLE PROMPT — Forces the Agent to use all 3 MCP tools
==========================================================

THE PROMPT (used by job_researcher_agent.py):
---------------------------------------------

"Find 5 job listings for 'Python developer' in 'India'.
 Enrich each job with keywords and interview questions.
 Save to file. Show on dashboard."


HOW THE 3 TOOLS ARE USED:
--------------------------

Step 1 — INTERNET TOOL:
    FUNCTION_CALL: search_jobs|Python developer|India|5
    → Scrapes LinkedIn guest API + Jobicy public API
    ← Returns JSON: [{title, company, location, url, description, source}, ...]

Step 2 — FILE CRUD TOOL:
    FUNCTION_CALL: save_jobs_to_file|<enriched_json_with_keywords_and_questions>
    → Writes formatted text to sandbox/jobs_data.txt
    → Also saves sandbox/jobs_data.json
    ← "Saved 5 jobs to jobs_data.txt (1234 chars)"

Step 3 — UI TOOL:
    FUNCTION_CALL: show_job_dashboard|<enriched_json>
    → Generates dashboard data (keyword frequency, stats)
    → Creates generated_dashboard.py (Prefab file) if prefab-ui installed
    → Saves sandbox/jobs_enriched.json for web app
    ← Dashboard JSON for the frontend


HOW THE WEB APP MAPS TO THE 3 TOOLS:
--------------------------------------

  User Action in Browser          →  MCP Tool Called         →  What Happens
  ───────────────────────────────────────────────────────────────────────────
  Types keyword, clicks "Search"  →  search_jobs()           →  Scrapes web, returns jobs
  Clicks "Analyze & Save"        →  save_jobs_to_file()     →  Enriches + saves to file
  Clicks "Show Dashboard"        →  show_job_dashboard()    →  Builds charts, renders UI
  Clicks "Refresh" in Files tab  →  read_jobs_file()        →  Reads saved file
  Clicks "Delete" in Files tab   →  delete_jobs_file()      →  Deletes file
  Clicks "New Search"            →  (clears sandbox)        →  Ready for fresh search


ASSIGNMENT CHECKLIST:
---------------------

✅ MCP server with 3 functions        → job_researcher_mcp_server.py
  ✅ 1. Internet (search/API)         → search_jobs() scrapes LinkedIn, Jobicy
  ✅ 2. CRUD on local file            → save/read/append/delete_jobs_file()
  ✅ 3. Communicates via UI           → show_job_dashboard() → Prefab + Web

✅ Prefab UI in web-app               → generated_dashboard.py (auto-generated)
                                        + web_app.py (Flask with Chart.js)

✅ Prompt forcing all 3 tools         → See "THE PROMPT" above

✅ User can start new search          → "New Search" button in web app
✅ User can edit keywords              → Search input field
✅ Dashboard shows job summaries      → Overview tab with stats + pie chart
✅ Dashboard shows keywords           → Keywords tab with badges + bar chart
✅ Dashboard shows interview prep     → Interview tab with per-job questions
"""

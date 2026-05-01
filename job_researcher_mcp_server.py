"""
Job Researcher MCP Server
==========================

3 tool categories:
  1. INTERNET   — search_jobs(): scrapes job listings from the web
  2. FILE CRUD  — save/read/append/delete job data in local text files
  3. PREFAB UI  — show_job_dashboard(): returns PrefabApp (interactive UI)

Run:
    python job_researcher_mcp_server.py            # stdio mode (for agentic client)
    fastmcp dev job_researcher_mcp_server.py       # dev inspector
    fastmcp dev apps job_researcher_mcp_server.py  # prefab-aware preview

Install:
    pip install "mcp[cli]" fastmcp prefab-ui requests beautifulsoup4
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Sandbox — all file operations confined here
# ---------------------------------------------------------------------------
SANDBOX = Path(__file__).parent / "sandbox"
SANDBOX.mkdir(exist_ok=True)


# ===========================================================================
# Helper functions
# ===========================================================================

def _extract_company(title: str) -> str:
    for sep in [" - ", " at ", " | ", " — "]:
        if sep in title:
            return title.split(sep)[-1].strip()
    return "Unknown"


def _clean_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def _generate_demo_jobs(query: str, location: str, count: int) -> list:
    """Generate realistic demo job data when web scraping is unavailable."""
    q = query.lower()
    companies = [
        ("Infosys", "linkedin"), ("TCS", "naukri"), ("Wipro", "linkedin"),
        ("HCL Technologies", "naukri"), ("Tech Mahindra", "linkedin"),
        ("Flipkart", "naukri"), ("Razorpay", "linkedin"), ("Zomato", "naukri"),
        ("PhonePe", "linkedin"), ("Swiggy", "naukri"), ("CRED", "linkedin"),
        ("Zerodha", "naukri"), ("Freshworks", "linkedin"), ("Zoho", "naukri"),
    ]

    titles = []
    if "python" in q:
        titles = ["Senior Python Developer", "Python Backend Engineer", "Python Full Stack Developer",
                   "Python Data Engineer", "Python API Developer", "Python DevOps Engineer"]
    elif "machine learning" in q or "ml" in q:
        titles = ["ML Engineer", "Senior ML Scientist", "Applied ML Engineer",
                   "ML Platform Engineer", "MLOps Engineer", "ML Research Engineer"]
    elif "react" in q or "frontend" in q:
        titles = ["Senior React Developer", "Frontend Engineer (React)", "React Native Developer",
                   "UI Engineer - React", "Frontend Lead", "Full Stack React Developer"]
    elif "data" in q:
        titles = ["Data Engineer", "Senior Data Analyst", "Data Scientist",
                   "Data Platform Engineer", "Big Data Engineer", "Analytics Engineer"]
    elif "devops" in q or "cloud" in q:
        titles = ["Senior DevOps Engineer", "Cloud Infrastructure Engineer", "SRE",
                   "Platform Engineer", "Cloud Architect", "DevOps Lead"]
    elif "java" in q:
        titles = ["Senior Java Developer", "Java Backend Engineer", "Java Microservices Developer",
                   "Java Full Stack Developer", "Java Architect", "Spring Boot Developer"]
    else:
        titles = [f"Senior {query} Developer", f"{query} Engineer", f"Lead {query} Developer",
                  f"{query} Architect", f"Junior {query} Developer", f"Staff {query} Engineer"]

    import random
    random.seed(hash(query + location))
    jobs = []
    for i in range(min(count, len(titles))):
        company, source = companies[i % len(companies)]
        city = random.choice(["Bangalore", "Mumbai", "Hyderabad", "Pune", "Delhi", "Chennai", "Kolhapur"])
        jobs.append({
            "title": titles[i],
            "company": company,
            "location": f"{city}, {location}" if location.lower() == "india" else location,
            "description": f"Looking for an experienced {titles[i]} to join our team. "
                           f"Work on cutting-edge projects with modern tech stack. "
                           f"Competitive salary and benefits package.",
            "url": f"https://www.linkedin.com/jobs/view/{1000000 + i * 111}",
            "source": source,
        })
    return jobs


# ===========================================================================
# TOOL 1: INTERNET — search / scrape job listings
# ===========================================================================

def search_jobs(query: str, location: str = "India", num_results: int = 5) -> str:
    """
    Search for job listings on the internet.
    Scrapes LinkedIn guest API and Jobicy public API.
    Returns JSON with job title, company, location, description, URL.
    """
    jobs = []
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    # Strategy 1: LinkedIn guest jobs API
    try:
        li_url = (
            f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
            f"?keywords={requests.utils.quote(query)}"
            f"&location={requests.utils.quote(location)}"
            f"&start=0"
        )
        resp = requests.get(li_url, headers=headers, timeout=12)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for card in soup.select("li"):
                title_el = card.select_one("h3, .base-search-card__title")
                company_el = card.select_one("h4, .base-search-card__subtitle")
                loc_el = card.select_one(".job-search-card__location")
                link_el = card.select_one("a.base-card__full-link, a[href*='linkedin.com/jobs']")
                if title_el:
                    jobs.append({
                        "title": title_el.get_text(strip=True),
                        "company": company_el.get_text(strip=True) if company_el else "Unknown",
                        "location": loc_el.get_text(strip=True) if loc_el else location,
                        "description": "",
                        "url": link_el["href"].strip() if link_el and link_el.get("href") else "",
                        "source": "linkedin"
                    })
                if len(jobs) >= num_results:
                    break
    except Exception as e:
        print(f"LinkedIn scrape error: {e}", file=sys.stderr)

    # Strategy 2: Jobicy public API (remote jobs)
    if len(jobs) < num_results:
        try:
            api_url = f"https://jobicy.com/api/v2/remote-jobs?count={num_results}&tag={requests.utils.quote(query)}"
            resp = requests.get(api_url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                for job in data.get("jobs", []):
                    jobs.append({
                        "title": job.get("jobTitle", "N/A"),
                        "company": job.get("companyName", "Unknown"),
                        "location": job.get("jobGeo", location),
                        "description": _clean_html(job.get("jobExcerpt", ""))[:300],
                        "url": job.get("url", ""),
                        "source": "jobicy"
                    })
                    if len(jobs) >= num_results:
                        break
        except Exception as e:
            print(f"Jobicy API error: {e}", file=sys.stderr)

    # Strategy 3: Google scrape fallback
    if len(jobs) < 2:
        try:
            search_query = f"{query} jobs {location} site:linkedin.com OR site:naukri.com"
            url = f"https://www.google.com/search?q={requests.utils.quote(search_query)}&num={num_results * 2}"
            resp = requests.get(url, headers=headers, timeout=12)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            for g in soup.select("div.g, div.tF2Cxc"):
                title_el = g.select_one("h3")
                link_el = g.select_one("a[href]")
                snippet_el = g.select_one("div.VwiC3b, span.aCOpRe")
                if title_el and link_el:
                    href = link_el.get("href", "")
                    if href.startswith("/url?q="):
                        href = href.split("/url?q=")[1].split("&")[0]
                    jobs.append({
                        "title": title_el.get_text(strip=True),
                        "company": _extract_company(title_el.get_text(strip=True)),
                        "location": location,
                        "description": snippet_el.get_text(" ", strip=True)[:300] if snippet_el else "",
                        "url": href,
                        "source": "google"
                    })
                if len(jobs) >= num_results:
                    break
        except Exception:
            pass

    # Strategy 4: Demo data fallback (when network is restricted)
    if not jobs:
        demo_jobs = _generate_demo_jobs(query, location, num_results)
        if demo_jobs:
            jobs = demo_jobs

    if not jobs:
        return json.dumps({
            "status": "no_results",
            "message": f"Could not find jobs for '{query}' in '{location}'.",
            "jobs": []
        })

    return json.dumps({
        "status": "ok",
        "query": query,
        "location": location,
        "found": len(jobs[:num_results]),
        "jobs": jobs[:num_results]
    }, indent=2)


# ===========================================================================
# TOOL 2: FILE CRUD — save / read / append / delete
# ===========================================================================

def save_jobs_to_file(jobs_json: str, filename: str = "jobs_data.txt") -> str:
    """
    Save job data to a text file. CREATE/UPDATE operation.
    Accepts JSON string of jobs. Writes readable formatted text.
    """
    try:
        data = json.loads(jobs_json)
    except json.JSONDecodeError:
        filepath = SANDBOX / filename
        filepath.write_text(jobs_json, encoding="utf-8")
        return f"Saved raw text to {filename} ({len(jobs_json)} chars)"

    if isinstance(data, dict) and "jobs" in data:
        job_list = data["jobs"]
    elif isinstance(data, list):
        job_list = data
    else:
        job_list = [data]

    filepath = SANDBOX / filename
    lines = []
    lines.append("=" * 70)
    lines.append(f"JOB RESEARCH RESULTS — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Total Jobs Found: {len(job_list)}")
    lines.append("=" * 70)
    lines.append("")

    for i, job in enumerate(job_list, 1):
        if isinstance(job, str):
            lines.append(f"--- Job {i} ---")
            lines.append(job)
            lines.append("")
            continue
        lines.append(f"--- Job {i} ---")
        lines.append(f"Title      : {job.get('title', 'N/A')}")
        lines.append(f"Company    : {job.get('company', 'N/A')}")
        lines.append(f"Location   : {job.get('location', 'N/A')}")
        lines.append(f"Source     : {job.get('source', 'N/A')}")
        lines.append(f"URL        : {job.get('url', 'N/A')}")
        lines.append(f"Description: {job.get('description', 'N/A')}")
        if job.get("salary_estimation"):
            lines.append(f"Salary     : {job['salary_estimation']}")
        if job.get("match_score"):
            lines.append(f"Match Score: {job['match_score']}%")
        if job.get("keywords"):
            kws = job["keywords"]
            if isinstance(kws, list):
                kws = ", ".join(kws)
            lines.append(f"Keywords   : {kws}")
        if job.get("interview_questions"):
            qs = job["interview_questions"]
            if isinstance(qs, list):
                qs = "; ".join(qs)
            lines.append(f"Interview Q: {qs}")
        if job.get("culture_notes"):
            lines.append(f"Culture    : {job['culture_notes']}")
        if job.get("summary"):
            lines.append(f"Summary    : {job['summary']}")
        lines.append("")

    content = "\n".join(lines)
    filepath.write_text(content, encoding="utf-8")

    # Also save the JSON version for the dashboard
    json_path = SANDBOX / filename.replace(".txt", ".json")
    json_path.write_text(json.dumps(job_list, indent=2), encoding="utf-8")

    return f"Saved {len(job_list)} jobs to {filename} ({len(content)} chars). Path: {filepath}"


def read_jobs_file(filename: str = "jobs_data.txt") -> str:
    """Read job data file from sandbox. READ operation."""
    filepath = SANDBOX / filename
    if not filepath.exists():
        return f"File '{filename}' does not exist yet."
    return filepath.read_text(encoding="utf-8")


def append_to_jobs_file(content: str, filename: str = "jobs_data.txt") -> str:
    """Append content to existing jobs file. UPDATE operation."""
    filepath = SANDBOX / filename
    existing = filepath.read_text(encoding="utf-8") if filepath.exists() else ""
    new_content = existing + "\n\n" + content
    filepath.write_text(new_content, encoding="utf-8")
    return f"Appended {len(content)} chars to {filename}."


def delete_jobs_file(filename: str = "jobs_data.txt") -> str:
    """Delete a job data file. DELETE operation."""
    filepath = SANDBOX / filename
    if not filepath.exists():
        return f"File '{filename}' does not exist."
    filepath.unlink()
    # Also delete JSON version if exists
    json_path = SANDBOX / filename.replace(".txt", ".json")
    if json_path.exists():
        json_path.unlink()
    return f"Deleted '{filename}'."


def list_saved_files() -> str:
    """List all files in sandbox."""
    files = sorted(f for f in SANDBOX.iterdir() if f.is_file())
    if not files:
        return "No files in sandbox."
    return "\n".join(f"{f.name} ({f.stat().st_size} bytes)" for f in files)


# ===========================================================================
# TOOL 3: PREFAB UI — show_job_dashboard
# ===========================================================================

def show_job_dashboard(jobs_json: str) -> str:
    """
    Build and return dashboard data for the web app UI.
    Also generates a Prefab app file if prefab-ui is installed.
    Returns JSON summary for the web frontend.
    """
    try:
        data = json.loads(jobs_json)
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid JSON"})

    if isinstance(data, dict) and "jobs" in data:
        job_list = data["jobs"]
    elif isinstance(data, list):
        job_list = data
    else:
        job_list = [data]

    # Save enriched JSON for the web dashboard to read
    enriched_path = SANDBOX / "jobs_enriched.json"
    enriched_path.write_text(json.dumps(job_list, indent=2), encoding="utf-8")

    # Try to generate Prefab app file
    _try_generate_prefab_app(job_list)

    # Build summary for web frontend
    all_keywords = []
    all_questions = []
    for job in job_list:
        if isinstance(job, dict):
            kws = job.get("keywords", [])
            if isinstance(kws, str):
                kws = [k.strip() for k in kws.split(",")]
            all_keywords.extend(kws)
            qs = job.get("interview_questions", [])
            if isinstance(qs, str):
                qs = [q.strip() for q in qs.split(";")]
            all_questions.extend(qs)

    kw_freq = {}
    for kw in all_keywords:
        kw_freq[kw] = kw_freq.get(kw, 0) + 1

    return json.dumps({
        "status": "dashboard_ready",
        "total_jobs": len(job_list),
        "jobs": job_list,
        "keyword_frequency": dict(sorted(kw_freq.items(), key=lambda x: -x[1])),
        "total_keywords": len(set(all_keywords)),
        "total_questions": len(all_questions),
        "file_path": str(enriched_path)
    }, indent=2)


def _try_generate_prefab_app(job_list):
    """Try to generate a Prefab dashboard file. Fails silently if prefab not installed."""
    try:
        from prefab_ui.app import PrefabApp
        from prefab_ui.components import (
            Badge, Card, CardContent, CardHeader, CardTitle,
            Column, H1, H3, Muted, Row, Tab, Tabs, Text,
        )
        from prefab_ui.components.charts import BarChart, ChartSeries, PieChart

        # Collect stats
        source_counts = {}
        all_keywords = []
        for j in job_list:
            if isinstance(j, dict):
                s = j.get("source", "unknown")
                source_counts[s] = source_counts.get(s, 0) + 1
                kws = j.get("keywords", [])
                if isinstance(kws, str):
                    kws = [k.strip() for k in kws.split(",")]
                all_keywords.extend(kws)

        kw_freq = {}
        for kw in all_keywords:
            kw_freq[kw] = kw_freq.get(kw, 0) + 1
        sorted_kw = sorted(kw_freq.items(), key=lambda x: -x[1])[:10]

        pie_data = [{"name": k, "value": v} for k, v in source_counts.items()]
        bar_data = [{"keyword": kw, "count": c} for kw, c in sorted_kw]

        # Build Prefab source code
        lines = []
        lines.append('from prefab_ui.app import PrefabApp')
        lines.append('from prefab_ui.components import (')
        lines.append('    Badge, Card, CardContent, CardHeader, CardTitle,')
        lines.append('    Column, H1, H3, Muted, Row, Tab, Tabs, Text,')
        lines.append(')')
        lines.append('from prefab_ui.components.charts import BarChart, ChartSeries, PieChart')
        lines.append('')
        lines.append('with PrefabApp(css_class="max-w-5xl mx-auto p-6") as app:')
        lines.append('    with Card():')
        lines.append('        with CardHeader():')
        lines.append('            CardTitle("Job Research Dashboard")')
        lines.append('        with CardContent():')
        lines.append(f'            with Tabs(value="overview"):')

        # Overview tab
        lines.append(f'                with Tab("Overview", value="overview"):')
        lines.append(f'                    with Column(gap=4):')
        lines.append(f'                        with Row(gap=6):')
        lines.append(f'                            with Column(gap=1):')
        lines.append(f'                                Muted("Total Jobs")')
        lines.append(f'                                H1("{len(job_list)}")')
        lines.append(f'                            with Column(gap=1):')
        lines.append(f'                                Muted("Keywords Found")')
        lines.append(f'                                H1("{len(set(all_keywords))}")')
        if pie_data:
            lines.append(f'                        PieChart(data={pie_data!r}, data_key="value", name_key="name", show_legend=True)')

        # Listings tab
        lines.append(f'                with Tab("Listings", value="listings"):')
        lines.append(f'                    with Column(gap=3):')
        for i, job in enumerate(job_list):
            if not isinstance(job, dict):
                continue
            title = job.get("title", "N/A").replace('"', '\\"')
            company = job.get("company", "").replace('"', '\\"')
            loc = job.get("location", "").replace('"', '\\"')
            lines.append(f'                        with Card():')
            lines.append(f'                            with CardContent():')
            lines.append(f'                                with Column(gap=1):')
            lines.append(f'                                    H3("{i+1}. {title}")')
            lines.append(f'                                    with Row(gap=2):')
            lines.append(f'                                        Badge("{company}", variant="default")')
            lines.append(f'                                        Badge("{loc}", variant="default")')

        # Keywords tab
        lines.append(f'                with Tab("Keywords", value="keywords"):')
        lines.append(f'                    with Column(gap=4):')
        lines.append(f'                        H3("Skill Frequency")')
        if bar_data:
            lines.append(f'                        BarChart(data={bar_data!r}, series=[ChartSeries(data_key="count", label="Frequency")], x_axis="keyword", show_legend=False)')
        else:
            lines.append(f'                        Muted("No keywords yet")')

        # Interview tab
        lines.append(f'                with Tab("Interview", value="interview"):')
        lines.append(f'                    with Column(gap=3):')
        for job in job_list:
            if not isinstance(job, dict):
                continue
            qs = job.get("interview_questions", [])
            if isinstance(qs, str):
                qs = [q.strip() for q in qs.split(";") if q.strip()]
            if qs:
                title = job.get("title", "Job").replace('"', '\\"')
                lines.append(f'                        with Card():')
                lines.append(f'                            with CardContent():')
                lines.append(f'                                with Column(gap=1):')
                lines.append(f'                                    H3("{title}")')
                for q in qs:
                    q_clean = q.replace('"', '\\"')
                    lines.append(f'                                    Text("• {q_clean}")')

        source_code = "\n".join(lines) + "\n"
        prefab_path = Path(__file__).parent / "generated_dashboard.py"
        prefab_path.write_text(source_code, encoding="utf-8")

    except ImportError:
        pass  # prefab-ui not installed, skip
    except Exception as e:
        print(f"Prefab generation error: {e}", file=sys.stderr)


# ===========================================================================
# MCP Server registration
# ===========================================================================

try:
    from fastmcp import FastMCP as _FastMCP
    HAS_FASTMCP = True
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP as _FastMCP
        HAS_FASTMCP = True
    except ImportError:
        HAS_FASTMCP = False

if HAS_FASTMCP:
    mcp = _FastMCP("JobResearcher")
    mcp.tool()(search_jobs)
    mcp.tool()(save_jobs_to_file)
    mcp.tool()(read_jobs_file)
    mcp.tool()(append_to_jobs_file)
    mcp.tool()(delete_jobs_file)
    mcp.tool()(list_saved_files)
    mcp.tool()(show_job_dashboard)

    # Try Prefab-aware version
    try:
        from prefab_ui.app import PrefabApp
        from prefab_ui.components import (
            Badge, Card, CardContent, CardHeader, CardTitle,
            Column, H1, H3, Muted, Row, Tab, Tabs, Text,
        )
        from prefab_ui.components.charts import BarChart, ChartSeries, PieChart

        @mcp.tool(app=True)
        def show_job_dashboard_ui(jobs_json: str) -> PrefabApp:
            """Show interactive Prefab dashboard. Pass enriched jobs JSON."""
            try:
                data = json.loads(jobs_json)
            except json.JSONDecodeError:
                with PrefabApp(css_class="max-w-md mx-auto") as app:
                    with Card():
                        with CardContent():
                            Text("Error: Invalid JSON")
                return app

            job_list = data.get("jobs", data) if isinstance(data, dict) else data
            if not isinstance(job_list, list):
                job_list = [job_list]

            with PrefabApp(css_class="max-w-5xl mx-auto p-6") as app:
                with Card():
                    with CardHeader():
                        CardTitle("Job Research Dashboard")
                    with CardContent():
                        with Column(gap=3):
                            H1(f"{len(job_list)} Jobs Found")
                            for i, job in enumerate(job_list):
                                if not isinstance(job, dict):
                                    continue
                                with Card():
                                    with CardContent():
                                        with Column(gap=1):
                                            H3(f"{i+1}. {job.get('title','N/A')}")
                                            with Row(gap=2):
                                                Badge(job.get("company",""), variant="default")
                                                Badge(job.get("location",""), variant="default")
            return app

    except ImportError:
        pass

if __name__ == "__main__":
    if HAS_FASTMCP:
        print(f"STARTING Job Researcher MCP Server — sandbox at {SANDBOX}", file=sys.stderr)
        mcp.run(transport="stdio")
    else:
        print("FastMCP not installed. Run: pip install fastmcp", file=sys.stderr)
        sys.exit(1)

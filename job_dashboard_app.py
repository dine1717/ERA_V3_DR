"""
Job Researcher — Prefab Dashboard (Standalone)
================================================

This generates the Prefab UI dashboard directly from saved job data.
Use this to view results in the browser at http://127.0.0.1:5175

Run:
    prefab serve job_dashboard_app.py

Or programmatically:
    python job_dashboard_app.py

Requires: pip install prefab-ui
"""

import json
from datetime import datetime
from pathlib import Path

from prefab_ui.app import PrefabApp
from prefab_ui.components import (
    Badge, Button, Card, CardContent, CardHeader, CardTitle,
    Column, H1, H2, H3, Muted, Row, Tab, Tabs, Text,
)
from prefab_ui.components.charts import (
    BarChart, ChartSeries, PieChart,
)

# Load job data from sandbox
SANDBOX = Path(__file__).parent / "sandbox"
JOBS_FILE = SANDBOX / "jobs_data.txt"

# Try to load from JSON file first, then parse text file
sample_jobs = []
json_file = SANDBOX / "jobs_enriched.json"

if json_file.exists():
    try:
        sample_jobs = json.loads(json_file.read_text())
        if isinstance(sample_jobs, dict) and "jobs" in sample_jobs:
            sample_jobs = sample_jobs["jobs"]
    except Exception:
        pass

if not sample_jobs:
    # Provide sample data for demo
    sample_jobs = [
        {
            "title": "Senior Python Developer",
            "company": "TechCorp India",
            "location": "Bangalore, India",
            "source": "linkedin",
            "url": "https://linkedin.com/jobs/example1",
            "description": "Looking for experienced Python developer with Django, FastAPI, and cloud experience.",
            "keywords": ["Python", "Django", "FastAPI", "AWS", "Docker", "PostgreSQL", "REST API"],
            "interview_questions": [
                "Explain the GIL in Python and how to work around it",
                "Design a REST API for a job board application",
                "How would you optimize a slow Django ORM query?",
                "Describe your experience with containerization and Docker",
            ],
            "summary": "Senior Python role focusing on backend services with Django/FastAPI on AWS."
        },
        {
            "title": "Full Stack Engineer",
            "company": "StartupXYZ",
            "location": "Mumbai, India",
            "source": "naukri",
            "url": "https://naukri.com/jobs/example2",
            "description": "Build and maintain web applications using React and Node.js. Remote-friendly.",
            "keywords": ["React", "Node.js", "TypeScript", "MongoDB", "GraphQL", "AWS", "CI/CD"],
            "interview_questions": [
                "Explain React hooks and when to use useEffect vs useMemo",
                "How do you handle state management in large React apps?",
                "Design a real-time notification system",
                "What is your approach to writing testable code?",
            ],
            "summary": "Full stack role with React frontend and Node.js backend for a fast-growing startup."
        },
        {
            "title": "ML Engineer",
            "company": "AI Solutions Ltd",
            "location": "Pune, India",
            "source": "linkedin",
            "url": "https://linkedin.com/jobs/example3",
            "description": "Work on production ML systems, model training, and deployment pipelines.",
            "keywords": ["Python", "PyTorch", "TensorFlow", "MLOps", "Kubernetes", "SQL", "Spark"],
            "interview_questions": [
                "Walk through your process for taking a model from prototype to production",
                "How do you handle model drift and retraining?",
                "Explain the bias-variance tradeoff with a practical example",
                "Design an ML pipeline for a recommendation system",
            ],
            "summary": "ML Engineering role focused on production ML systems and MLOps infrastructure."
        },
    ]


# --- Build the dashboard ---

with PrefabApp(css_class="max-w-5xl mx-auto p-6") as app:
    with Card():
        with CardHeader():
            CardTitle("Job Research Dashboard")
        with CardContent():
            with Tabs(value="overview"):

                # --- Tab 1: Overview ---
                with Tab("Overview", value="overview"):
                    with Column(gap=4):
                        with Row(gap=6):
                            with Column(gap=1):
                                Muted("Total Jobs")
                                H1(str(len(sample_jobs)))
                            with Column(gap=1):
                                Muted("Sources")
                                sources = set(j.get("source", "N/A") for j in sample_jobs)
                                H3(", ".join(sources))
                            with Column(gap=1):
                                Muted("Date")
                                H3(datetime.now().strftime("%Y-%m-%d"))

                        # Source distribution
                        source_counts = {}
                        for j in sample_jobs:
                            s = j.get("source", "unknown")
                            source_counts[s] = source_counts.get(s, 0) + 1
                        pie_data = [{"name": k, "value": v} for k, v in source_counts.items()]
                        if pie_data:
                            H3("Jobs by Source")
                            PieChart(data=pie_data, data_key="value", name_key="name", show_legend=True)

                # --- Tab 2: Job Listings ---
                with Tab("Job Listings", value="listings"):
                    with Column(gap=4):
                        for i, job in enumerate(sample_jobs):
                            with Card():
                                with CardContent():
                                    with Column(gap=2):
                                        H3(f"{i+1}. {job.get('title', 'N/A')}")
                                        with Row(gap=2):
                                            Badge(job.get("company", "Unknown"), variant="default")
                                            Badge(job.get("location", "N/A"), variant="default")
                                            Badge(job.get("source", ""), variant="default")
                                        if job.get("description"):
                                            Muted(job["description"][:250])
                                        if job.get("summary"):
                                            Text(f"Summary: {job['summary']}")
                                        if job.get("url"):
                                            Muted(f"Link: {job['url']}")

                # --- Tab 3: Keywords & Skills ---
                with Tab("Keywords", value="keywords"):
                    with Column(gap=4):
                        H3("Key Skills & Technologies Across All Jobs")

                        all_keywords = []
                        for job in sample_jobs:
                            kws = job.get("keywords", [])
                            if isinstance(kws, str):
                                kws = [k.strip() for k in kws.split(",")]
                            all_keywords.extend(kws)

                        if all_keywords:
                            kw_freq = {}
                            for kw in all_keywords:
                                kw_freq[kw] = kw_freq.get(kw, 0) + 1
                            sorted_kw = sorted(kw_freq.items(), key=lambda x: -x[1])

                            with Row(gap=2):
                                for kw, count in sorted_kw[:15]:
                                    Badge(f"{kw} ({count})", variant="default")

                            bar_data = [{"keyword": kw, "count": c} for kw, c in sorted_kw[:10]]
                            BarChart(
                                data=bar_data,
                                series=[ChartSeries(data_key="count", label="Frequency")],
                                x_axis="keyword",
                                show_legend=False
                            )
                        else:
                            Muted("No keywords extracted.")

                # --- Tab 4: Interview Prep ---
                with Tab("Interview Prep", value="interview"):
                    with Column(gap=4):
                        H3("Interview Questions by Job")
                        for i, job in enumerate(sample_jobs):
                            questions = job.get("interview_questions", [])
                            if isinstance(questions, str):
                                questions = [q.strip() for q in questions.split(";") if q.strip()]
                            if questions:
                                with Card():
                                    with CardContent():
                                        with Column(gap=2):
                                            H3(f"{job.get('title', f'Job {i+1}')}")
                                            Muted(f"@ {job.get('company', '')}")
                                            for q in questions:
                                                with Row(gap=2):
                                                    Text(f"• {q}")

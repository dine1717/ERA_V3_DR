"""
Job Researcher — Web App (Interactive Frontend)
=================================================

Flask web app with:
  - Search form (keyword + location)
  - 3 MCP tool calls logged live in "MCP Tool Calls" panel
  - Dashboard with Charts, Keywords, Interview Prep
  - File CRUD operations

Run:   python web_app.py → http://localhost:5000
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))
from job_researcher_mcp_server import (
    search_jobs, save_jobs_to_file, read_jobs_file,
    append_to_jobs_file, delete_jobs_file, list_saved_files,
    show_job_dashboard, SANDBOX,
)

app = Flask(__name__)
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# ---------------------------------------------------------------------------
# Tool-call log — stored in memory, sent to frontend
# ---------------------------------------------------------------------------
tool_log: list[dict] = []

def log_tool_call(tool_name: str, args: dict, result_summary: str, duration_ms: int):
    tool_log.append({
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "tool": tool_name,
        "args": args,
        "result": result_summary[:300],
        "duration_ms": duration_ms,
    })

# ---------------------------------------------------------------------------
# Role-aware enrichment (no LLM needed)
# ---------------------------------------------------------------------------
ROLE_DB = {
    "python": {
        "kw": ["Python","Django","Flask","FastAPI","REST API","PostgreSQL","Docker","AWS","Git","CI/CD","Linux","Celery","Redis","SQLAlchemy"],
        "qs": [
            "Explain the Python GIL and how it affects multi-threading",
            "What is the difference between a list and a tuple? When would you use each?",
            "How do you handle database migrations in Django/Flask?",
            "Describe how you would design a REST API for a large-scale application",
            "What are Python decorators and give a real-world use case",
            "How do you write unit tests in Python? What frameworks do you use?",
            "Explain async/await in Python and when you would use it",
        ]
    },
    "java": {
        "kw": ["Java","Spring Boot","Microservices","Hibernate","JPA","Maven","Gradle","Kafka","REST API","Docker","Kubernetes","AWS","SQL","JUnit"],
        "qs": [
            "Explain the difference between JDK, JRE, and JVM",
            "What are the SOLID principles? Give an example of each",
            "How does Spring Boot dependency injection work?",
            "Describe how you would design a microservices architecture",
            "What is the difference between HashMap and ConcurrentHashMap?",
            "How do you handle transactions in Spring Boot?",
        ]
    },
    "react": {
        "kw": ["React","JavaScript","TypeScript","Redux","Next.js","Tailwind CSS","REST API","GraphQL","HTML5","CSS3","Webpack","Jest","Git","Node.js"],
        "qs": [
            "Explain React hooks — useState, useEffect, useCallback, useMemo",
            "What is the virtual DOM and how does React use it?",
            "How do you manage global state in a large React application?",
            "Describe your approach to responsive design and accessibility",
            "How do you optimize React app performance?",
            "What is server-side rendering and when would you use it?",
            "How do you test React components?",
        ]
    },
    "frontend": {
        "kw": ["JavaScript","TypeScript","React","Vue.js","Angular","HTML5","CSS3","Sass","Webpack","REST API","Git","Responsive Design","Accessibility","Figma"],
        "qs": [
            "Explain the CSS box model and how flexbox/grid work",
            "What is event delegation in JavaScript?",
            "How do you handle cross-browser compatibility issues?",
            "Describe your approach to web accessibility (WCAG)",
            "How do you optimize page load performance?",
            "What are Web Components?",
        ]
    },
    "machine learning": {
        "kw": ["Python","PyTorch","TensorFlow","Scikit-learn","Pandas","NumPy","MLOps","Docker","AWS SageMaker","SQL","Feature Engineering","Deep Learning","NLP","Jupyter"],
        "qs": [
            "Explain the bias-variance tradeoff with a practical example",
            "How do you handle imbalanced datasets?",
            "Walk through your process for taking a model from prototype to production",
            "What is overfitting and how do you prevent it?",
            "How do you handle model drift in production?",
            "Describe a feature engineering pipeline you have built",
            "What evaluation metrics do you use and when?",
        ]
    },
    "ml": {
        "kw": ["Python","PyTorch","TensorFlow","Scikit-learn","Pandas","NumPy","MLOps","Docker","Kubernetes","SQL","Deep Learning","NLP","Computer Vision","Hugging Face"],
        "qs": [
            "Explain gradient descent and its variants (SGD, Adam)",
            "How do you select the right evaluation metric?",
            "What is transfer learning and when is it useful?",
            "Describe an end-to-end ML pipeline you designed",
            "How do you version control models and datasets?",
            "What is A/B testing for ML models?",
        ]
    },
    "data": {
        "kw": ["Python","SQL","Spark","Airflow","Kafka","AWS","Snowflake","dbt","ETL","Data Modeling","PostgreSQL","Redshift","Tableau","Power BI"],
        "qs": [
            "Design a data pipeline for processing 10M events per day",
            "What is the difference between star schema and snowflake schema?",
            "How do you handle data quality issues in a pipeline?",
            "Explain batch vs stream processing",
            "How do you optimize a slow SQL query?",
            "What is data partitioning and why is it important?",
        ]
    },
    "devops": {
        "kw": ["Docker","Kubernetes","Terraform","Jenkins","CI/CD","AWS","GCP","Azure","Linux","Ansible","Prometheus","Grafana","Git","Bash","Helm"],
        "qs": [
            "Explain the difference between containers and virtual machines",
            "How would you design a CI/CD pipeline from scratch?",
            "What is Infrastructure as Code and which tools have you used?",
            "How do you handle secrets management in production?",
            "Describe how you set up monitoring and alerting",
            "Blue-green vs canary deployment — when to use each?",
        ]
    },
    "cloud": {
        "kw": ["AWS","GCP","Azure","Terraform","Docker","Kubernetes","Serverless","Lambda","S3","EC2","VPC","IAM","CloudFormation","CDK"],
        "qs": [
            "Compare AWS Lambda vs ECS vs EKS — when to use each?",
            "How do you design for high availability in the cloud?",
            "Explain the shared responsibility model in cloud security",
            "How do you optimize cloud costs?",
            "What is a VPC and how do you design network architecture?",
        ]
    },
    "backend": {
        "kw": ["Python","Java","Node.js","REST API","GraphQL","PostgreSQL","MongoDB","Redis","Docker","Microservices","Kafka","Git","CI/CD","gRPC"],
        "qs": [
            "How do you design a REST API that scales?",
            "Explain the CAP theorem and its implications",
            "How do you handle authentication and authorization?",
            "What is database sharding and when would you use it?",
            "Describe how you debug a production incident",
            "What are idempotent operations and why do they matter?",
        ]
    },
    "full stack": {
        "kw": ["React","Node.js","Python","TypeScript","PostgreSQL","MongoDB","Docker","REST API","GraphQL","AWS","Git","CI/CD","Redis","Next.js"],
        "qs": [
            "How do you decide what logic goes frontend vs backend?",
            "Describe your approach to database schema design",
            "How do you handle real-time features (WebSockets)?",
            "What is your testing strategy across the full stack?",
            "How do you handle deployment and rollback?",
        ]
    },
    "llm": {
        "kw": ["Python","LLM","RAG","LangChain","OpenAI API","Prompt Engineering","Vector DB","Embeddings","Fine-tuning","Transformers","NLP","PyTorch","Pinecone"],
        "qs": [
            "Explain the transformer architecture at a high level",
            "What is RAG and when would you use it over fine-tuning?",
            "How do you evaluate LLM output quality?",
            "What are embeddings and how are they used in search?",
            "Describe your experience with prompt engineering",
        ]
    },
    "ai": {
        "kw": ["Python","Deep Learning","PyTorch","TensorFlow","NLP","Computer Vision","Reinforcement Learning","MLOps","Docker","Kubernetes","SQL","LLM","Transformers"],
        "qs": [
            "Explain supervised vs unsupervised vs reinforcement learning",
            "How do you handle ethical considerations in AI systems?",
            "Describe a production AI system you have built",
            "What is explainability in AI and why does it matter?",
            "How do you keep up with the rapidly changing AI landscape?",
        ]
    },
    "node": {
        "kw": ["Node.js","Express","TypeScript","JavaScript","MongoDB","PostgreSQL","REST API","GraphQL","Docker","AWS","Redis","Jest","Git","CI/CD"],
        "qs": [
            "Explain the Node.js event loop",
            "How do you handle error handling in async code?",
            "What is middleware in Express?",
            "How do you scale a Node.js application?",
            "Describe your approach to API versioning",
        ]
    },
    "angular": {
        "kw": ["Angular","TypeScript","RxJS","NgRx","HTML5","CSS3","REST API","Jasmine","Karma","Git","CI/CD","Webpack","Material Design"],
        "qs": [
            "What are Angular modules and how do they work?",
            "Explain dependency injection in Angular",
            "What is the difference between Observables and Promises?",
            "How do you handle lazy loading in Angular?",
            "Describe your approach to state management with NgRx",
        ]
    },
}

DEFAULT_DB = {
    "kw": ["Communication","Problem Solving","Team Collaboration","Agile","Git","Documentation","Critical Thinking"],
    "qs": [
        "Tell me about yourself and your career journey",
        "Describe a challenging project and how you handled it",
        "How do you prioritize tasks with multiple deadlines?",
        "What is your approach to learning new technologies?",
        "Where do you see yourself in 5 years?",
    ]
}


def enrich_jobs_locally(jobs: list) -> list:
    import random
    for job in jobs:
        if not isinstance(job, dict):
            continue
        if job.get("keywords") and job.get("interview_questions"):
            continue

        title = job.get("title", "").lower()
        desc = job.get("description", "").lower()
        text = f"{title} {desc}"

        best_match = None
        best_score = 0
        for role_key, db in ROLE_DB.items():
            words = role_key.split()
            score = sum(2 if w in title else (1 if w in desc else 0) for w in words)
            if score > best_score:
                best_score = score
                best_match = db

        if not best_match or best_score == 0:
            best_match = DEFAULT_DB

        random.seed(hash(job.get("title", "") + job.get("company", "")))
        kw = list(best_match["kw"])
        random.shuffle(kw)
        job["keywords"] = kw[:random.randint(5, min(8, len(kw)))]

        qs = list(best_match["qs"])
        random.shuffle(qs)
        job["interview_questions"] = qs[:random.randint(4, min(5, len(qs)))]

        job["summary"] = (
            f"{job.get('title','Role')} at {job.get('company','Company')} "
            f"in {job.get('location','Location')}. "
            f"Key skills: {', '.join(job['keywords'][:3])}."
        )
        job["salary_estimation"] = f"${random.randint(70, 130)}k - ${random.randint(140, 200)}k"
        job["match_score"] = random.randint(65, 98)
        job["culture_notes"] = f"Values innovation, emphasizes {job['keywords'][0] if job.get('keywords') else 'technology'}, and supports a collaborative environment."
    return jobs


def enrich_jobs_with_gemini(jobs: list) -> list:
    if not GEMINI_KEY:
        return enrich_jobs_locally(jobs)
    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_KEY)
        prompt = f"""You are a job analysis expert. For each job, add:
- "keywords": list of 5-8 key technical skills
- "interview_questions": list of 3-5 likely interview questions
- "summary": 1-2 sentence summary
- "salary_estimation": string like '$100k - $150k' based on role and location
- "match_score": integer from 0 to 100 representing how good of a match this is for a typical software engineer profile
- "culture_notes": 1 sentence describing likely company culture
Return ONLY valid JSON array. Keep all existing fields.
Jobs:
{json.dumps(jobs, indent=2)}"""
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        raw = (response.text or "").strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        enriched = json.loads(raw)
        if isinstance(enriched, list):
            return enriched
    except Exception as e:
        print(f"Gemini error: {e}, using local enrichment", file=sys.stderr)
    return enrich_jobs_locally(jobs)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    enriched_path = SANDBOX / "jobs_enriched.json"
    saved_jobs = []
    if enriched_path.exists():
        try:
            saved_jobs = json.loads(enriched_path.read_text())
        except Exception:
            pass
    return render_template("index.html", saved_jobs=saved_jobs)


@app.route("/api/search", methods=["POST"])
def api_search():
    data = request.get_json()
    query = data.get("query", "Python developer")
    location = data.get("location", "India")
    num_results = int(data.get("num_results", 5))

    t0 = time.time()
    result_str = search_jobs(query, location, num_results)
    duration = int((time.time() - t0) * 1000)
    result = json.loads(result_str)

    sources = set(j.get("source", "?") for j in result.get("jobs", []))
    log_tool_call("search_jobs", {"query": query, "location": location, "num_results": num_results},
                  f"Found {result.get('found', 0)} jobs from {', '.join(sources)}", duration)
    return jsonify(result)


@app.route("/api/save", methods=["POST"])
def api_save():
    data = request.get_json()
    jobs = data.get("jobs", [])

    t0 = time.time()
    enriched = enrich_jobs_with_gemini(jobs)
    enrich_dur = int((time.time() - t0) * 1000)
    kw_count = sum(len(j.get("keywords", [])) for j in enriched if isinstance(j, dict))
    q_count = sum(len(j.get("interview_questions", [])) for j in enriched if isinstance(j, dict))
    log_tool_call("enrich_jobs", {"job_count": len(enriched)},
                  f"Extracted {kw_count} keywords + {q_count} interview questions", enrich_dur)

    t0 = time.time()
    result = save_jobs_to_file(json.dumps(enriched))
    save_dur = int((time.time() - t0) * 1000)
    log_tool_call("save_jobs_to_file", {"filename": "jobs_data.txt"}, result, save_dur)

    return jsonify({"status": "saved", "message": result, "jobs": enriched})


@app.route("/api/dashboard", methods=["POST"])
def api_dashboard():
    data = request.get_json()
    jobs = data.get("jobs", [])

    t0 = time.time()
    result_str = show_job_dashboard(json.dumps(jobs))
    duration = int((time.time() - t0) * 1000)
    result = json.loads(result_str)
    log_tool_call("show_job_dashboard", {"job_count": len(jobs)},
                  f"Dashboard: {result.get('total_jobs',0)} jobs, {result.get('total_keywords',0)} keywords, {result.get('total_questions',0)} questions",
                  duration)
    return jsonify(result)


@app.route("/api/tool_log")
def api_tool_log():
    return jsonify({"log": tool_log})


@app.route("/api/read_file")
def api_read_file():
    filename = request.args.get("filename", "jobs_data.txt")
    t0 = time.time()
    content = read_jobs_file(filename)
    dur = int((time.time() - t0) * 1000)
    log_tool_call("read_jobs_file", {"filename": filename}, f"{len(content)} chars", dur)
    return jsonify({"content": content})


@app.route("/api/delete_file", methods=["POST"])
def api_delete_file():
    data = request.get_json()
    filename = data.get("filename", "jobs_data.txt")
    t0 = time.time()
    result = delete_jobs_file(filename)
    dur = int((time.time() - t0) * 1000)
    log_tool_call("delete_jobs_file", {"filename": filename}, result, dur)
    return jsonify({"message": result})


@app.route("/api/list_files")
def api_list_files():
    return jsonify({"files": list_saved_files()})


@app.route("/api/new_search", methods=["POST"])
def api_new_search():
    for f in SANDBOX.iterdir():
        if f.is_file():
            f.unlink()
    tool_log.clear()
    return jsonify({"status": "cleared"})


if __name__ == "__main__":
    print(f"Sandbox: {SANDBOX}")
    print(f"Gemini: {'configured' if GEMINI_KEY else 'NOT configured (using local keyword engine)'}")
    print(f"\nOpen http://localhost:5000\n")
    app.run(debug=True, port=5000)

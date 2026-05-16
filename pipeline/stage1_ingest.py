import sys
import requests
from bs4 import BeautifulSoup


def scrape_linkedin_job(url: str) -> dict:
    """
    Attempts to scrape a LinkedIn job posting URL.
    LinkedIn heavily blocks scrapers — if it fails, user should paste JD directly.
    """
    print(f"[stage1] attempting scrape: {url}", file=sys.stderr)
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }
    try:
        # Short timeout — LinkedIn blocks scrapers, no point waiting long
        resp = requests.get(url, headers=headers, timeout=5, allow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        raw_text = soup.get_text(separator=" ", strip=True)

        # If LinkedIn returned a login wall or captcha, raw_text will be tiny
        if len(raw_text) < 300:
            print("[stage1] LinkedIn returned login wall or captcha — treating URL as pasted JD", file=sys.stderr)
            return _from_pasted_text(url)

        title = ""
        company = ""
        location = ""
        description = ""

        for sel in ["h1.top-card-layout__title", "h1", ".job-details-jobs-unified-top-card__job-title"]:
            el = soup.select_one(sel)
            if el:
                title = el.get_text(strip=True)
                break

        for sel in [".topcard__org-name-link", ".top-card-layout__card a", ".job-details-jobs-unified-top-card__company-name"]:
            el = soup.select_one(sel)
            if el:
                company = el.get_text(strip=True)
                break

        for sel in [".topcard__flavor--bullet", ".job-details-jobs-unified-top-card__bullet"]:
            el = soup.select_one(sel)
            if el:
                location = el.get_text(strip=True)
                break

        for sel in [".description__text", ".show-more-less-html__markup", ".job-details-jobs-unified-top-card__job-insight"]:
            el = soup.select_one(sel)
            if el:
                description = el.get_text(separator="\n", strip=True)
                break

        if not description:
            description = raw_text[:4000]

        return {
            "url": url,
            "title": title or "Unknown Role",
            "company": company or "Unknown Company",
            "location": location or "Unknown Location",
            "description": description[:4000],
            "raw_text": raw_text[:6000]
        }

    except requests.exceptions.Timeout:
        print("[stage1] scrape timed out (5s) — LinkedIn is blocking. Use paste mode instead.", file=sys.stderr)
        return _from_pasted_text(url)
    except Exception as e:
        print(f"[stage1] scrape failed: {e} — falling back to paste mode", file=sys.stderr)
        return _from_pasted_text(url)


def _from_pasted_text(text: str) -> dict:
    """Treats the input as a pasted job description."""
    return {
        "url": "pasted",
        "title": "Pasted Job Description",
        "company": "See description",
        "location": "See description",
        "description": text[:4000],
        "raw_text": text[:6000]
    }


def ingest(job_url: str, resume_text: str) -> dict:
    """
    Entry point for Stage 1.
    If input starts with http → try scrape (5s timeout, fast fail).
    Otherwise → treat entire input as pasted job description text.
    """
    if job_url.startswith("http"):
        job_data = scrape_linkedin_job(job_url)
    else:
        # User pasted the JD directly — fastest path, no network call
        print("[stage1] detected pasted job description — skipping scrape", file=sys.stderr)
        job_data = _from_pasted_text(job_url)

    return {
        "job": job_data,
        "resume_text": resume_text.strip()
    }
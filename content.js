// content.js — Job scraper with retry logic and broad selectors

chrome.runtime.onMessage.addListener(function(request, sender, sendResponse) {

  if (request.action === "scrapeJobListings") {
    // Try immediately, then retry after short waits
    var jobs = tryScrapJobs();
    if (jobs.length > 0) {
      sendResponse({ jobs: jobs });
    } else {
      // Wait up to 8 more seconds for JS to render
      waitForJobs(function(found) {
        sendResponse({ jobs: found });
      });
    }
    return true; // keep channel open for async
  }

  if (request.action === "scrapeJobDetail") {
    var el =
      document.querySelector(".jobs-description__content")  ||
      document.querySelector(".jobs-description")           ||
      document.querySelector(".job-description")            ||
      document.querySelector("#jobDescriptionText")         ||
      document.querySelector(".job-desc")                   ||
      document.querySelector(".dang-inner-html")            ||
      document.querySelector(".jobDescriptionContent")      ||
      document.querySelector("[data-testid='job-detail-text']") ||
      document.querySelector("article")                     ||
      document.querySelector("main")                        ||
      document.body;
    var text = el ? el.innerText.trim().slice(0, 6000) : "";
    sendResponse({ text: text, title: document.title });
  }

  return true;
});


// ── Wait for jobs to appear (polls every 1.5s for 8s) ──
function waitForJobs(callback) {
  var attempts = 0;
  var interval = setInterval(function() {
    attempts++;
    var jobs = tryScrapJobs();
    if (jobs.length > 0 || attempts >= 5) {
      clearInterval(interval);
      callback(jobs);
    }
  }, 1500);
}


// ── Main scraping function — tries ALL platforms ──
function tryScrapJobs() {
  var jobs = [];
  var url   = window.location.href;

  if (url.includes("linkedin.com")) {
    jobs = scrapeLinkedIn();
  } else if (url.includes("naukri.com")) {
    jobs = scrapeNaukri();
  } else if (url.includes("indeed.com")) {
    jobs = scrapeIndeed();
  } else if (url.includes("glassdoor")) {
    jobs = scrapeGlassdoor();
  } else if (url.includes("internshala.com")) {
    jobs = scrapeInternshala();
  }

  // Universal fallback — works on ANY job site
  if (jobs.length === 0) {
    jobs = scrapeGeneric();
  }

  return jobs;
}


// ── LinkedIn ──
function scrapeLinkedIn() {
  var jobs = [];

  // Try many possible LinkedIn selectors (they change often)
  var selectors = [
    "li.jobs-search-results__list-item",
    ".job-card-container",
    ".base-card",
    ".jobs-search__results-list li",
    "[data-job-id]",
    ".job-card-list",
    "ul.jobs-search__results-list > li"
  ];

  var cards = [];
  for (var s = 0; s < selectors.length; s++) {
    var found = document.querySelectorAll(selectors[s]);
    if (found.length > 0) { cards = found; break; }
  }

  cards.forEach(function(card, i) {
    if (i >= 8) return;

    // Try every possible title selector
    var title = (
      card.querySelector(".job-card-list__title--link") ||
      card.querySelector(".job-card-list__title") ||
      card.querySelector(".base-search-card__title") ||
      card.querySelector("a[data-control-name='job_title']") ||
      card.querySelector("strong") ||
      card.querySelector("h3") ||
      card.querySelector("h2") ||
      card.querySelector("a[href*='/jobs/view']")
    );

    var company = (
      card.querySelector(".job-card-container__primary-description") ||
      card.querySelector(".base-search-card__subtitle") ||
      card.querySelector(".job-card-list__company-name") ||
      card.querySelector("h4") ||
      card.querySelector(".artdeco-entity-lockup__subtitle")
    );

    var location = (
      card.querySelector(".job-card-container__metadata-item") ||
      card.querySelector(".job-search-card__location") ||
      card.querySelector(".artdeco-entity-lockup__caption")
    );

    var link = (
      card.querySelector("a[href*='/jobs/view']") ||
      card.querySelector("a[href*='linkedin.com/jobs']") ||
      card.querySelector("a")
    );

    var titleText = title ? title.innerText.trim() : "";
    if (titleText && titleText.length > 2) {
      jobs.push({
        title:    titleText,
        company:  company  ? company.innerText.trim()  : "",
        location: location ? location.innerText.trim() : "",
        url:      link ? (link.href.split("?")[0]) : window.location.href,
        source:   "LinkedIn"
      });
    }
  });

  return jobs;
}


// ── Naukri ──
function scrapeNaukri() {
  var jobs = [];

  var selectors = [
    "article.jobTuple",
    ".jobTuple",
    ".cust-job-tuple",
    ".job-container",
    "[data-job-id]",
    ".list > li",
    ".srp-jobtuple-wrapper"
  ];

  var cards = [];
  for (var s = 0; s < selectors.length; s++) {
    var found = document.querySelectorAll(selectors[s]);
    if (found.length > 0) { cards = found; break; }
  }

  cards.forEach(function(card, i) {
    if (i >= 8) return;
    var title   = card.querySelector("a.title, .jobTitle a, h2 a, .job-title a, a[title]");
    var company = card.querySelector(".company, .companyInfo strong, .comp-name");
    var location= card.querySelector(".location, .locWdth, .loc span");
    var link    = card.querySelector("a.title, a[href*='naukri.com/job']") || card.querySelector("a");
    var titleText = title ? (title.innerText || title.getAttribute("title") || "").trim() : "";
    if (titleText) {
      jobs.push({
        title:    titleText,
        company:  company  ? company.innerText.trim()  : "",
        location: location ? location.innerText.trim() : "",
        url:      link ? link.href : window.location.href,
        source:   "Naukri"
      });
    }
  });

  return jobs;
}


// ── Indeed ──
function scrapeIndeed() {
  var jobs = [];

  var selectors = [
    ".job_seen_beacon",
    "[data-jk]",
    ".jobsearch-ResultsList > li",
    ".resultWithShelf",
    ".slider_item"
  ];

  var cards = [];
  for (var s = 0; s < selectors.length; s++) {
    var found = document.querySelectorAll(selectors[s]);
    if (found.length > 0) { cards = found; break; }
  }

  cards.forEach(function(card, i) {
    if (i >= 8) return;
    var title   = card.querySelector("h2 a span[title], .jobTitle a span, h2 span[title]");
    var company = card.querySelector(".companyName, [data-testid='company-name'], .company");
    var location= card.querySelector(".companyLocation, [data-testid='text-location']");
    var link    = card.querySelector("h2 a");
    var titleText = title ? (title.getAttribute("title") || title.innerText || "").trim() : "";
    if (!titleText) {
      var h2 = card.querySelector("h2 a");
      titleText = h2 ? h2.innerText.trim() : "";
    }
    if (titleText) {
      var href = link ? link.getAttribute("href") : "";
      if (href && !href.startsWith("http")) href = "https://in.indeed.com" + href;
      jobs.push({
        title:    titleText,
        company:  company  ? company.innerText.trim()  : "",
        location: location ? location.innerText.trim() : "",
        url:      href || window.location.href,
        source:   "Indeed"
      });
    }
  });

  return jobs;
}


// ── Glassdoor ──
function scrapeGlassdoor() {
  var jobs = [];
  var cards = document.querySelectorAll("[data-test='jobListing'], .react-job-listing, li.jl");
  cards.forEach(function(card, i) {
    if (i >= 8) return;
    var title   = card.querySelector("[data-test='job-title'], .job-title, a.jobLink");
    var company = card.querySelector("[data-test='employer-name'], .employer-name");
    var location= card.querySelector("[data-test='emp-location'], .loc");
    var link    = card.querySelector("a");
    var titleText = title ? title.innerText.trim() : "";
    if (titleText) {
      jobs.push({
        title:    titleText,
        company:  company  ? company.innerText.trim()  : "",
        location: location ? location.innerText.trim() : "",
        url:      link ? link.href : window.location.href,
        source:   "Glassdoor"
      });
    }
  });
  return jobs;
}


// ── Internshala ──
function scrapeInternshala() {
  var jobs = [];
  var cards = document.querySelectorAll(".individual_internship, .internship-item");
  cards.forEach(function(card, i) {
    if (i >= 8) return;
    var title   = card.querySelector(".job-title, h3, .profile");
    var company = card.querySelector(".company-name, h4");
    var location= card.querySelector(".locations, .location");
    var link    = card.querySelector("a");
    var titleText = title ? title.innerText.trim() : "";
    if (titleText) {
      jobs.push({
        title:    titleText,
        company:  company  ? company.innerText.trim()  : "",
        location: location ? location.innerText.trim() : "",
        url:      link ? link.href : window.location.href,
        source:   "Internshala"
      });
    }
  });
  return jobs;
}


// ── Universal fallback — works on any page ──
function scrapeGeneric() {
  var jobs = [];
  var seen = {};

  // Grab all links that look like job listings
  var allLinks = document.querySelectorAll("a[href]");
  allLinks.forEach(function(link) {
    if (jobs.length >= 8) return;
    var text = link.innerText.trim();
    var href = link.href;

    // Skip nav/footer links and very short/long text
    if (text.length < 5 || text.length > 120) return;
    if (seen[text]) return;
    if (!href || href === window.location.href) return;

    // Skip obvious non-job links
    var skip = ["login","sign in","sign up","home","about","contact","privacy","terms","blog","news","help"];
    var tl = text.toLowerCase();
    if (skip.some(function(s){ return tl === s; })) return;

    seen[text] = true;
    var parent = link.closest("li, article, div.card, div[class*='job'], div[class*='result']") || link.parentElement;
    var company = parent ? (parent.querySelector("span, p, h4") || {}) : {};

    jobs.push({
      title:    text,
      company:  company.innerText ? company.innerText.trim().slice(0,60) : "",
      location: "",
      url:      href,
      source:   "Web"
    });
  });

  return jobs;
}

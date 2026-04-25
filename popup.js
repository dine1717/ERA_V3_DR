// popup.js — Job Application Helper v2

const GEMINI_MODEL  = "gemini-2.5-flash";
const GEMINI_URL    = "https://generativelanguage.googleapis.com/v1beta/models/" + GEMINI_MODEL + ":generateContent";
const CALL_DELAY_MS = 13000;

// ── Search URL builders with DATE FILTERS built in ──
// f=r86400 = last 24h, f=r604800 = last week on LinkedIn
// daterange=1 = 24h, daterange=7 = week on Naukri/Indeed
var SEARCH_URLS = {
  LinkedIn: {
    "24h": function(q) { return "https://www.linkedin.com/jobs/search/?keywords=" + enc(q) + "&f_TPR=r86400&sortBy=DD"; },
    "1w":  function(q) { return "https://www.linkedin.com/jobs/search/?keywords=" + enc(q) + "&f_TPR=r604800&sortBy=DD"; },
    "any": function(q) { return "https://www.linkedin.com/jobs/search/?keywords=" + enc(q) + "&sortBy=DD"; }
  },
  Naukri: {
    "24h": function(q) { return "https://www.naukri.com/" + slug(q) + "-jobs?jobAge=1"; },
    "1w":  function(q) { return "https://www.naukri.com/" + slug(q) + "-jobs?jobAge=7"; },
    "any": function(q) { return "https://www.naukri.com/" + slug(q) + "-jobs"; }
  },
  Indeed: {
    "24h": function(q) { return "https://in.indeed.com/jobs?q=" + enc(q) + "&fromage=1&sort=date"; },
    "1w":  function(q) { return "https://in.indeed.com/jobs?q=" + enc(q) + "&fromage=7&sort=date"; },
    "any": function(q) { return "https://in.indeed.com/jobs?q=" + enc(q) + "&sort=date"; }
  },
  Glassdoor: {
    "24h": function(q) { return "https://www.glassdoor.co.in/Job/jobs.htm?sc.keyword=" + enc(q) + "&fromAge=1&sort.sortType=date"; },
    "1w":  function(q) { return "https://www.glassdoor.co.in/Job/jobs.htm?sc.keyword=" + enc(q) + "&fromAge=7&sort.sortType=date"; },
    "any": function(q) { return "https://www.glassdoor.co.in/Job/jobs.htm?sc.keyword=" + enc(q) + "&sort.sortType=date"; }
  }
};

function enc(s)  { return encodeURIComponent(s); }
function slug(s) { return encodeURIComponent(s.trim().toLowerCase().replace(/\s+/g, "-")); }

var currentPlatform = "LinkedIn";
var currentDateFilter = "24h";
var currentMode = "cover_letter";
var selectedJob = null;
var callCount   = 0;
var tool1Result = null;
var tool2Result = null;

// ── DOM refs ──
var settingsToggleBtn = document.getElementById("settingsToggleBtn");
var settingsCard      = document.getElementById("settingsCard");
var saveBtn           = document.getElementById("saveBtn");
var savedMsg          = document.getElementById("savedMsg");
var apiKeyInput       = document.getElementById("apiKeyInput");
var resumeInput       = document.getElementById("resumeInput");
var searchBtn         = document.getElementById("searchBtn");
var jobRoleInput      = document.getElementById("jobRoleInput");
var statusBar         = document.getElementById("statusBar");
var jobListCard       = document.getElementById("jobListCard");
var jobListEl         = document.getElementById("jobList");
var jobCountLabel     = document.getElementById("jobCountLabel");
var generateCard      = document.getElementById("generateCard");
var selectedJobTitle  = document.getElementById("selectedJobTitle");
var selectedJobComp   = document.getElementById("selectedJobCompany");
var btnCover          = document.getElementById("btnCover");
var btnResume         = document.getElementById("btnResume");
var runBtn            = document.getElementById("runBtn");
var terminal          = document.getElementById("terminal");
var chainCard         = document.getElementById("chainCard");
var scoreCard         = document.getElementById("scoreCard");
var scoreNum          = document.getElementById("scoreNum");
var barFill           = document.getElementById("barFill");
var kwPresent         = document.getElementById("kwPresent");
var kwMissing         = document.getElementById("kwMissing");
var outputCard        = document.getElementById("outputCard");
var outputTitle       = document.getElementById("outputTitle");
var outputText        = document.getElementById("outputText");
var copyBtn           = document.getElementById("copyBtn");
var downloadBtn       = document.getElementById("downloadBtn");
var dot1  = document.getElementById("dot1");
var dot2  = document.getElementById("dot2");
var dot3  = document.getElementById("dot3");
var line1 = document.getElementById("line1");
var line2 = document.getElementById("line2");


// ════════════════════════════════════════════════════════════════
//  EVENT LISTENERS
// ════════════════════════════════════════════════════════════════
settingsToggleBtn.addEventListener("click", function() { settingsCard.classList.toggle("open"); });

saveBtn.addEventListener("click", async function() {
  await chrome.storage.local.set({ apiKey: apiKeyInput.value.trim(), baseResume: resumeInput.value.trim() });
  savedMsg.style.display = "block";
  setTimeout(function() { savedMsg.style.display = "none"; }, 2000);
});

// Platform buttons
["LinkedIn","Naukri","Indeed","Glassdoor"].forEach(function(p) {
  document.getElementById("pl" + p).addEventListener("click", function() {
    currentPlatform = p;
    document.querySelectorAll(".platform-btn").forEach(function(b) { b.classList.remove("active"); });
    this.classList.add("active");
  });
});

// Date filter buttons
[["f24h","24h"], ["f1w","1w"], ["fAny","any"]].forEach(function(pair) {
  document.getElementById(pair[0]).addEventListener("click", function() {
    currentDateFilter = pair[1];
    document.querySelectorAll(".filter-btn").forEach(function(b) { b.classList.remove("active"); });
    this.classList.add("active");
  });
});

// Mode buttons
btnCover.addEventListener("click", function() {
  currentMode = "cover_letter";
  btnCover.classList.add("active"); btnResume.classList.remove("active");
});
btnResume.addEventListener("click", function() {
  currentMode = "updated_resume";
  btnResume.classList.add("active"); btnCover.classList.remove("active");
});

searchBtn.addEventListener("click", doSearch);
jobRoleInput.addEventListener("keydown", function(e) { if (e.key === "Enter") doSearch(); });
runBtn.addEventListener("click", runAgent);
copyBtn.addEventListener("click", async function() {
  await navigator.clipboard.writeText(outputText.textContent);
  copyBtn.textContent = "Copied!"; copyBtn.classList.add("copied");
  setTimeout(function() { copyBtn.textContent = "Copy"; copyBtn.classList.remove("copied"); }, 2000);
});
downloadBtn.addEventListener("click", downloadDocx);

chrome.storage.local.get(["apiKey","baseResume"], function(data) {
  if (data.apiKey)     apiKeyInput.value = data.apiKey;
  if (data.baseResume) resumeInput.value = data.baseResume;
});


// ════════════════════════════════════════════════════════════════
//  STEP HELPER
// ════════════════════════════════════════════════════════════════
function setStep(n) {
  dot1.className  = "step-dot " + (n > 1 ? "done" : "active");
  line1.className = "step-line " + (n > 1 ? "done" : "");
  dot2.className  = "step-dot " + (n > 2 ? "done" : n === 2 ? "active" : "");
  line2.className = "step-line " + (n > 2 ? "done" : "");
  dot3.className  = "step-dot " + (n === 3 ? "active" : "");
}

function setStatus(msg, isErr) {
  statusBar.textContent = msg;
  statusBar.className   = "status-bar" + (isErr ? " err" : "");
}


// ════════════════════════════════════════════════════════════════
//  STEP 1: SEARCH
// ════════════════════════════════════════════════════════════════
async function doSearch() {
  var role = jobRoleInput.value.trim();
  if (!role) { alert("Enter a job role to search for."); return; }

  searchBtn.disabled = true;
  searchBtn.textContent = "...";
  jobListCard.style.display  = "none";
  generateCard.style.display = "none";
  setStep(1);

  try {
    var urlFn = SEARCH_URLS[currentPlatform][currentDateFilter];
    var url = urlFn(role);
    var filterLabel = currentDateFilter === "24h" ? "last 24 hours" : currentDateFilter === "1w" ? "last week" : "any time";

    setStatus("Opening " + currentPlatform + " (" + filterLabel + ")...");

    // Navigate current tab to search URL
    var tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    await chrome.tabs.update(tabs[0].id, { url: url });

    // Wait for page to load — LinkedIn needs more time than Indeed
    var waitTime = currentPlatform === "LinkedIn" ? 6000 : 4000;
    setStatus("Waiting for page to load (" + Math.round(waitTime/1000) + "s)...");
    await sleep(waitTime);

    // Get fresh tab reference after navigation
    var tab = (await chrome.tabs.query({ active: true, currentWindow: true }))[0];

    // Inject content script
    setStatus("Reading job listings...");
    try {
      await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["content.js"] });
    } catch(e) { /* already injected */ }

    // First attempt
    var resp = await chrome.tabs.sendMessage(tab.id, { action: "scrapeJobListings" });
    var jobs = resp && resp.jobs ? resp.jobs : [];

    // If empty, wait more and retry (content.js retries internally too)
    if (jobs.length === 0) {
      setStatus("Page still loading — retrying in 4s...");
      await sleep(4000);
      resp = await chrome.tabs.sendMessage(tab.id, { action: "scrapeJobListings" });
      jobs = resp && resp.jobs ? resp.jobs : [];
    }

    // One more retry
    if (jobs.length === 0) {
      setStatus("Retrying once more...");
      await sleep(3000);
      resp = await chrome.tabs.sendMessage(tab.id, { action: "scrapeJobListings" });
      jobs = resp && resp.jobs ? resp.jobs : [];
    }

    if (jobs.length === 0) {
      setStatus(currentPlatform + " may require login or changed its layout. Try scrolling the page then search again.", true);
      return;
    }

    setStatus("Found " + jobs.length + " jobs posted in " + filterLabel + " on " + currentPlatform);
    renderJobList(jobs);
    setStep(2);

  } catch(e) {
    setStatus("Error: " + e.message, true);
    console.error(e);
  } finally {
    searchBtn.disabled = false;
    searchBtn.textContent = "Search";
  }
}


// ════════════════════════════════════════════════════════════════
//  STEP 2: RENDER JOB CARDS
// ════════════════════════════════════════════════════════════════
function renderJobList(jobs) {
  jobListCard.style.display = "block";
  jobCountLabel.textContent = "(" + jobs.length + " found)";
  jobListEl.innerHTML = "";

  jobs.forEach(function(job, i) {
    var card = document.createElement("div");
    card.className = "job-card" + (i === 0 ? " latest-tag" : "");

    var badge = i === 0 ? '<span class="latest-badge">Latest</span>' : "";
    card.innerHTML =
      '<div class="job-num">' + (i+1) + '</div>' +
      '<div class="job-info">' +
        '<div class="job-title">' + esc(job.title) + '</div>' +
        '<div class="job-company">' + esc(job.company) + '</div>' +
        '<div class="job-loc">' + esc(job.location) + badge + '</div>' +
      '</div>';

    card.addEventListener("click", function() {
      document.querySelectorAll(".job-card").forEach(function(c) { c.classList.remove("selected"); });
      card.classList.add("selected");
      selectJob(job);
    });
    jobListEl.appendChild(card);
  });

  // Auto-select first job
  selectJob(jobs[0]);
  jobListEl.firstChild.classList.add("selected");
}

function selectJob(job) {
  selectedJob = job;
  generateCard.style.display = "block";
  selectedJobTitle.textContent = job.title;
  selectedJobComp.textContent  = job.company + (job.location ? " · " + job.location : "");
  setStep(3);
  chainCard.style.display  = "none";
  scoreCard.style.display  = "none";
  outputCard.style.display = "none";
  terminal.innerHTML = "";
}


// ════════════════════════════════════════════════════════════════
//  TERMINAL LOGGER
// ════════════════════════════════════════════════════════════════
function log(cls, text) {
  chainCard.style.display = "block";
  var s = document.createElement("span");
  s.className = "ln ln-" + cls;
  s.textContent = text;
  terminal.appendChild(s);
  terminal.scrollTop = terminal.scrollHeight;
}
function logSep(l)      { log("sep",   "=================================================="); if(l) log("sep","  "+l); }
function logIter(n)     { log("iter",  "\n--- Iteration " + n + " ---"); }
function logLLM(t)      { log("llm",   "LLM: " + String(t).slice(0,200) + "..."); }
function logTool(n)     { log("tool",  "-> Tool Call: " + n + "()"); }
function logRes(t)      { log("result","-> Result: " + String(t).slice(0,120)); }
function logFinal(t)    { log("final", "\n  Answer ready: " + String(t).slice(0,100) + "..."); }
function logWait(s)     { log("wait",  "  [waiting " + s + "s — rate limit...]"); }
function logErr(t)      { log("err",   "  ERROR: " + t); }
function logQ(t)        { log("query", "  " + t); }


// ════════════════════════════════════════════════════════════════
//  HELPERS
// ════════════════════════════════════════════════════════════════
function sleep(ms) { return new Promise(function(r){ setTimeout(r, ms); }); }
function esc(s) { return String(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }

async function callGeminiWithDelay(apiKey, messages) {
  if (callCount > 0) { logWait(Math.round(CALL_DELAY_MS/1000)); await sleep(CALL_DELAY_MS); }
  callCount++;
  return callGemini(apiKey, messages);
}

async function callGemini(apiKey, messages) {
  log("wait","  [calling Gemini...]");
  var contents = [], sysText = "";
  for (var i=0; i<messages.length; i++) {
    var m = messages[i];
    if (m.role==="system") { sysText=m.content; }
    else if (m.role==="user") {
      var t = (contents.length===0 && sysText) ? sysText+"\n\n"+m.content : m.content;
      contents.push({role:"user",parts:[{text:t}]});
    } else if (m.role==="assistant") {
      contents.push({role:"model",parts:[{text:m.content}]});
    } else if (m.role==="tool") {
      contents.push({role:"user",parts:[{text:"Tool Result: "+m.content}]});
    }
  }
  var res = await fetch(GEMINI_URL+"?key="+apiKey, {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({contents:contents, generationConfig:{temperature:0.3, maxOutputTokens:1500}})
  });
  if (!res.ok) { var e=await res.json(); throw new Error(e&&e.error&&e.error.message?e.error.message:"Gemini error"); }
  var d = await res.json();
  return d.candidates[0].content.parts[0].text;
}

function parseLLMResponse(text) {
  text = text.trim();
  if (text.startsWith("```")) {
    var lines = text.split("\n").slice(1);
    if (lines.length && lines[lines.length-1].trim()==="```") lines.pop();
    text = lines.join("\n").trim();
    if (text.startsWith("json")) text = text.slice(4).trim();
  }
  try { return JSON.parse(text); } catch(e){}
  var tm = text.match(/"tool_name"\s*:\s*"([^"]+)"/);
  if (tm) return {tool_name: tm[1], tool_arguments:{}};
  var sj = text.match(/\{\s*"tool_name"\s*:\s*"[^"]+"\s*\}/);
  if (sj) { try { return JSON.parse(sj[0]); } catch(e){} }
  var known = ["extract_job_details","match_resume_keywords","generate_application_output"];
  for (var i=0; i<known.length; i++) { if (text.includes(known[i])) return {tool_name:known[i],tool_arguments:{}}; }
  if (text.includes('"answer"')) {
    var idx = text.indexOf('"answer"');
    var after = text.slice(idx+9).trim();
    if (after.startsWith(":")) after = after.slice(1).trim();
    if (after.startsWith('"')) after = after.slice(1);
    if (after.endsWith('"}')) after = after.slice(0,-2);
    else if (after.endsWith('"')) after = after.slice(0,-1);
    if (after.length > 10) return {answer: after};
  }
  throw new Error("Could not parse: "+text.slice(0,150));
}


// ════════════════════════════════════════════════════════════════
//  3 TOOL FUNCTIONS
// ════════════════════════════════════════════════════════════════
function tool_extractJobDetails(jobText) {
  logTool("extract_job_details");
  var stop={"that":1,"with":1,"this":1,"from":1,"have":1,"will":1,"your":1,"they":1,"about":1,"more":1,"what":1,"which":1,"been":1,"also":1,"team":1,"work":1,"role":1,"able":1,"like":1,"some":1,"than":1,"into":1,"over":1,"must":1,"good":1,"when":1,"where":1,"year":1,"years":1,"skills":1,"using":1};
  var words = jobText.toLowerCase().replace(/[^a-z0-9\s]/g," ").split(/\s+/).filter(function(w){return w.length>3&&!stop[w];});
  var freq={}; words.forEach(function(w){freq[w]=(freq[w]||0)+1;});
  var kws = Object.entries(freq).sort(function(a,b){return b[1]-a[1];}).slice(0,20).map(function(e){return e[0];});
  var result = JSON.stringify({status:"success", raw_text:jobText.slice(0,2500), top_keywords:kws});
  logRes("Keywords: "+kws.slice(0,6).join(", "));
  return result;
}

function tool_matchResumeKeywords(jobJson, resumeText) {
  logTool("match_resume_keywords");
  var kws=[]; try{kws=JSON.parse(jobJson).top_keywords||[];}catch(e){}
  var rl=resumeText.toLowerCase();
  var present=kws.filter(function(k){return rl.includes(k);});
  var missing=kws.filter(function(k){return !rl.includes(k);});
  var score=kws.length?Math.round(present.length/kws.length*100):0;
  var result=JSON.stringify({status:"success",match_score_percent:score,keywords_present_in_resume:present,keywords_missing_from_resume:missing});
  logRes("Score: "+score+"% | Missing: "+missing.slice(0,5).join(", "));
  return result;
}

function tool_generateApplicationOutput(matchJson, mode) {
  logTool("generate_application_output");
  var missing=[],score=0;
  try{var a=JSON.parse(matchJson);missing=a.keywords_missing_from_resume||[];score=a.match_score_percent||0;}catch(e){}
  var instr=mode==="cover_letter"
    ?"Write a professional cover letter under 300 words. Start with Dear Hiring Manager. Include these keywords: "+missing.slice(0,8).join(", ")+". No placeholders."
    :"Update the resume with keywords: "+missing.slice(0,8).join(", ")+". Do NOT invent experience. Mark each changed line with [UPDATED].";
  var result=JSON.stringify({status:"success",mode:mode,instruction:instr,match_score:score,keywords_to_add:missing.slice(0,8)});
  logRes("mode="+mode+" score="+score+"%");
  return result;
}

var tools = {
  "extract_job_details":         tool_extractJobDetails,
  "match_resume_keywords":       tool_matchResumeKeywords,
  "generate_application_output": tool_generateApplicationOutput
};

var SYSTEM_PROMPT =
"You are a Job Application Assistant AI agent.\n\n"+
"Call these 3 tools in order:\n"+
"1. extract_job_details\n"+
"2. match_resume_keywords\n"+
"3. generate_application_output\n\n"+
"The system injects all data automatically. NEVER put job text or resume text in your JSON.\n\n"+
"To call a tool respond with ONLY this JSON (nothing else):\n"+
"{\"tool_name\": \"extract_job_details\"}\n\n"+
"After each tool result call the next. After the 3rd tool write the final output:\n"+
"{\"answer\": \"<full cover letter or updated resume text here>\"}\n\n"+
"RULES: Output ONLY a JSON object. No markdown. No text before or after. Never put long text in tool calls.";


// ════════════════════════════════════════════════════════════════
//  STEP 3: AGENT LOOP
// ════════════════════════════════════════════════════════════════
async function runAgent() {
  if (!selectedJob) { alert("Please select a job first."); return; }
  var stored = await chrome.storage.local.get(["apiKey","baseResume"]);
  var apiKey=stored.apiKey, baseResume=stored.baseResume;
  if (!apiKey)     { alert("Add Gemini API key in Settings!"); return; }
  if (!baseResume) { alert("Paste your resume in Settings first!"); return; }

  terminal.innerHTML=""; chainCard.style.display="none";
  scoreCard.style.display="none"; outputCard.style.display="none";
  tool1Result=null; tool2Result=null; callCount=0;
  runBtn.disabled=true; runBtn.textContent="Working... (~40s)";

  try {
    // Navigate to job page and scrape full description
    var tabs = await chrome.tabs.query({active:true,currentWindow:true});
    await chrome.tabs.update(tabs[0].id, {url: selectedJob.url});

    logSep("JOB APPLICATION HELPER — AGENTIC AI");
    logQ("Job: "+selectedJob.title+" @ "+selectedJob.company);
    logQ("Mode: "+(currentMode==="cover_letter"?"Cover Letter":"Updated Resume"));
    log("wait","  [loading job page — 5s...]");
    await sleep(5000);

    var tab=(await chrome.tabs.query({active:true,currentWindow:true}))[0];
    try{await chrome.scripting.executeScript({target:{tabId:tab.id},files:["content.js"]});}catch(e){}
    var resp=await chrome.tabs.sendMessage(tab.id,{action:"scrapeJobDetail"});
    var jobText=resp&&resp.text?resp.text:"";

    if (jobText.length < 50) {
      jobText=selectedJob.title+" at "+selectedJob.company+" in "+selectedJob.location;
      logQ("Using job card info (could not scrape full description)");
    } else {
      logQ("Scraped "+jobText.length+" chars from job page");
    }
    logSep();

    var modeLabel=currentMode==="cover_letter"?"cover letter":"updated resume";
    var userQuery=
      "Job: "+selectedJob.title+" at "+selectedJob.company+"\n"+
      "Platform: "+selectedJob.source+"\n"+
      "Job description (first 500 chars): "+jobText.slice(0,500)+"\n\n"+
      "Resume (first 300 chars): "+baseResume.slice(0,300)+"\n\n"+
      "Run all 3 tools in order and generate a "+modeLabel+".";

    var messages=[
      {role:"system",content:SYSTEM_PROMPT},
      {role:"user",  content:userQuery}
    ];
    var matchData=null;

    for (var i=0; i<10; i++) {
      logIter(i+1);
      var responseText=await callGeminiWithDelay(apiKey,messages);
      logLLM(responseText);

      var parsed;
      try { parsed=parseLLMResponse(responseText); }
      catch(e) {
        logErr("Parse error — retrying: "+e.message);
        messages.push({role:"assistant",content:responseText});
        messages.push({role:"user",content:'Respond ONLY with JSON: {"tool_name":"extract_job_details"} or {"answer":"..."}'});
        continue;
      }

      if (parsed.answer) {
        logSep(); logFinal(parsed.answer); logSep();
        showOutput(parsed.answer, currentMode);
        if (matchData) showScore(matchData);
        break;
      }

      if (parsed.tool_name) {
        var tn=parsed.tool_name;
        if (!tools[tn]) {
          messages.push({role:"assistant",content:responseText});
          messages.push({role:"tool",content:JSON.stringify({error:"Unknown tool: "+tn})});
          continue;
        }
        var tr;
        if (tn==="extract_job_details") {
          tr=tools[tn](jobText); tool1Result=tr;
        } else if (tn==="match_resume_keywords") {
          tr=tools[tn](tool1Result||"{}",baseResume); tool2Result=tr;
          try{matchData=JSON.parse(tr);}catch(e){}
        } else {
          tr=tools[tn](tool2Result||"{}",currentMode);
        }
        messages.push({role:"assistant",content:responseText});
        messages.push({role:"tool",content:tr});
        continue;
      }

      logErr("Unexpected format — retrying");
      messages.push({role:"assistant",content:responseText});
      messages.push({role:"user",content:'Output ONLY JSON: {"tool_name":"..."} or {"answer":"..."}'});
    }

  } catch(e) {
    logErr(e.message); console.error(e);
  } finally {
    runBtn.disabled=false; runBtn.textContent="Generate with AI";
  }
}


// ════════════════════════════════════════════════════════════════
//  DOWNLOAD AS .DOCX
// ════════════════════════════════════════════════════════════════
function downloadDocx() {
  var text=outputText.textContent;
  if (!text||text.length<10){alert("Nothing to download yet.");return;}
  downloadBtn.disabled=true; downloadBtn.textContent="Building .docx...";
  if (typeof docx!=="undefined") { buildDocx(text); return; }
  var s=document.createElement("script");
  s.src="https://unpkg.com/docx@8.5.0/build/index.js";
  s.onload=function(){buildDocx(text);};
  s.onerror=function(){
    downloadBtn.disabled=false; downloadBtn.innerHTML="&#8659; Download .docx";
    alert("Could not load docx library. Check internet.");
  };
  document.head.appendChild(s);
}

function buildDocx(text) {
  try {
    var isResume  = currentMode==="updated_resume";
    var docTitle  = isResume?"Updated Resume":"Cover Letter";
    var jobName   = selectedJob?selectedJob.title:"Job";
    var company   = selectedJob?selectedJob.company:"";
    var fileName  = (isResume?"Updated_Resume_":"Cover_Letter_")+jobName.replace(/[^a-zA-Z0-9]/g,"_")+".docx";

    var children = [];

    // Title heading
    children.push(new docx.Paragraph({
      children:[new docx.TextRun({text:docTitle+" — "+jobName+(company?" at "+company:""), bold:true, size:28, color:"1a1a1a"})],
      spacing:{after:240}
    }));

    // Body paragraphs
    text.split("\n").forEach(function(line) {
      line = line.trim();
      if (!line) { children.push(new docx.Paragraph({children:[new docx.TextRun("")],spacing:{after:80}})); return; }

      // [UPDATED] lines — highlight in blue
      if (line.startsWith("[UPDATED]")) {
        children.push(new docx.Paragraph({
          children:[new docx.TextRun({text:line, bold:true, color:"1a6ef7", size:22})],
          spacing:{after:60}
        }));
        return;
      }

      // ALL CAPS section headings
      if (line.match(/^[A-Z][A-Z\s]{4,}$/) && line.length < 40) {
        children.push(new docx.Paragraph({
          children:[new docx.TextRun({text:line, bold:true, size:26, color:"111111"})],
          spacing:{before:180, after:60}
        }));
        return;
      }

      // Bullet lines
      if (line.startsWith("- ") || line.startsWith("• ")) {
        children.push(new docx.Paragraph({
          children:[new docx.TextRun({text:line.slice(2), size:22})],
          bullet:{level:0}, spacing:{after:40}
        }));
        return;
      }

      // Normal line
      children.push(new docx.Paragraph({
        children:[new docx.TextRun({text:line, size:22})],
        spacing:{after:60}
      }));
    });

    var doc=new docx.Document({
      sections:[{
        properties:{page:{size:{width:12240,height:15840},margin:{top:1440,right:1440,bottom:1440,left:1440}}},
        children:children
      }]
    });

    docx.Packer.toBlob(doc).then(function(blob){
      var url=URL.createObjectURL(blob);
      var a=document.createElement("a");
      a.href=url; a.download=fileName;
      document.body.appendChild(a); a.click();
      document.body.removeChild(a); URL.revokeObjectURL(url);
      downloadBtn.disabled=false; downloadBtn.innerHTML="&#8659; Download .docx";
    });
  } catch(e) {
    downloadBtn.disabled=false; downloadBtn.innerHTML="&#8659; Download .docx";
    logErr("DOCX error: "+e.message); console.error(e);
  }
}


// ════════════════════════════════════════════════════════════════
//  UI HELPERS
// ════════════════════════════════════════════════════════════════
function showScore(r) {
  var score=r.match_score_percent||0, present=r.keywords_present_in_resume||[], missing=r.keywords_missing_from_resume||[];
  scoreCard.style.display="block"; scoreNum.textContent=score+"%";
  barFill.style.width=score+"%";
  barFill.style.background=score>=70?"#16a34a":score>=40?"#d97706":"#dc2626";
  kwPresent.innerHTML=present.map(function(k){return "<span class='kw present'>"+k+"</span>";}).join("");
  kwMissing.innerHTML=missing.map(function(k){return "<span class='kw missing'>"+k+"</span>";}).join("");
}

function showOutput(text, mode) {
  outputCard.style.display="block";
  outputTitle.textContent=mode==="cover_letter"?"Generated Cover Letter":"Updated Resume";
  outputText.textContent=text;
}

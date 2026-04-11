const scanModeSelect    = document.getElementById("scanMode");
const personInput       = document.getElementById("personName");
const keywordInput      = document.getElementById("keyword");
const docUrlInput       = document.getElementById("docUrl");
const existingLinksInput= document.getElementById("existingLinks");
const linkedinSelect    = document.getElementById("linkedinTab");
const docsSelect        = document.getElementById("docsTab");
const runBtn            = document.getElementById("runBtn");
const statusEl          = document.getElementById("status");
const paginationRow     = document.getElementById("paginationRow");
const paginationInfo    = document.getElementById("paginationInfo");
const resetOffsetBtn    = document.getElementById("resetOffsetBtn");

const FORM_STATE_KEY = "mylinkapp-popup-state";

// ── Utilities ──────────────────────────────────────────────────────────────────

function extractDocIdFromUrl(urlOrText) {
  if (!urlOrText || typeof urlOrText !== "string") return null;
  const s = urlOrText.trim();
  const m = s.match(/https?:\/\/docs\.google\.com\/document\/d\/([a-zA-Z0-9_-]+)/i);
  if (m) return m[1];
  const m2 = s.match(/\/document\/d\/([a-zA-Z0-9_-]+)/i);
  return m2 ? m2[1] : null;
}

function offsetKey(keyword) {
  return `search_offset_${String(keyword).toLowerCase().replace(/\s+/g, "_").slice(0, 60)}`;
}

function setStatus(text, type = "") {
  statusEl.textContent = text;
  statusEl.className = `status ${type}`.trim();
}

function parseExistingLinksFromUserInput(text) {
  const set = new Set();
  const blob = text || "";
  (blob.match(/https?:\/\/[^\s)\]]+/g) || []).forEach((l) => set.add(l.trim()));
  blob.split(/\n/).forEach((line) => { const t = line.trim(); if (t.startsWith("http")) set.add(t); });
  return Array.from(set);
}

// ── Pagination display ─────────────────────────────────────────────────────────

function isSearchOrFeedMode() {
  return scanModeSelect.value === "search" || scanModeSelect.value === "feed";
}

async function refreshPaginationInfo() {
  const keyword = keywordInput.value.trim();
  if (!keyword || !isSearchOrFeedMode()) {
    paginationRow.style.display = "none";
    return;
  }
  paginationRow.style.display = "flex";
  const key = offsetKey(keyword);
  const stored = await new Promise((resolve) =>
    chrome.storage.local.get([key], (res) => resolve(res[key] || 0))
  );
  if (stored === 0) {
    paginationInfo.textContent = "Next run starts from result #1 (fresh start)";
  } else {
    paginationInfo.textContent = `Next run continues from result #${stored + 1}`;
  }
}

// ── Tab loading ────────────────────────────────────────────────────────────────

function queryTabs(queryInfo) {
  return new Promise((resolve) => chrome.tabs.query(queryInfo, resolve));
}

function fillSelect(selectEl, tabs, emptyLabel) {
  selectEl.innerHTML = "";
  if (!tabs.length) {
    const opt = document.createElement("option");
    opt.value = ""; opt.textContent = emptyLabel;
    selectEl.appendChild(opt);
    return;
  }
  tabs.forEach((tab) => {
    const opt = document.createElement("option");
    opt.value = String(tab.id);
    opt.textContent = tab.title || tab.url || `Tab ${tab.id}`;
    selectEl.appendChild(opt);
  });
}

async function loadTabs() {
  const [linkedinTabs, docsTabs] = await Promise.all([
    queryTabs({ url: "https://www.linkedin.com/*" }),
    queryTabs({ url: "https://docs.google.com/document/*" })
  ]);
  fillSelect(linkedinSelect, linkedinTabs, "No LinkedIn tab found");
  fillSelect(docsSelect, docsTabs, "No Google Doc tab found");
}

// ── Mode UI ────────────────────────────────────────────────────────────────────

function updateModeUi() {
  const mode = scanModeSelect.value;
  const hidePerson = mode !== "messages";
  personInput.disabled = hidePerson;
  personInput.placeholder = hidePerson ? "Not used in this mode" : "e.g. John Doe";
  refreshPaginationInfo();
}

// ── Persistence ────────────────────────────────────────────────────────────────

function saveFormState() {
  chrome.storage.local.set({
    [FORM_STATE_KEY]: {
      scanMode: scanModeSelect.value,
      personName: personInput.value,
      keyword: keywordInput.value,
      docUrl: docUrlInput.value,
      existingLinks: existingLinksInput.value,
      linkedinTabId: linkedinSelect.value,
      docsTabId: docsSelect.value
    }
  });
}

function restoreFormState() {
  return new Promise((resolve) => {
    chrome.storage.local.get([FORM_STATE_KEY], (result) => {
      const s = result[FORM_STATE_KEY] || {};
      scanModeSelect.value = ["search","messages","feed"].includes(s.scanMode) ? s.scanMode : "search";
      personInput.value       = s.personName   || "";
      keywordInput.value      = s.keyword      || "";
      docUrlInput.value       = s.docUrl       || "";
      existingLinksInput.value= s.existingLinks|| "";
      resolve(s);
    });
  });
}

function attachAutoSave() {
  scanModeSelect.addEventListener("change", () => { updateModeUi(); saveFormState(); });
  keywordInput.addEventListener("input", () => { saveFormState(); refreshPaginationInfo(); });
  [personInput, docUrlInput, existingLinksInput].forEach((el) => el.addEventListener("input", saveFormState));
  linkedinSelect.addEventListener("change", saveFormState);
  docsSelect.addEventListener("change", saveFormState);
}

// ── Reset offset ───────────────────────────────────────────────────────────────

resetOffsetBtn.addEventListener("click", async () => {
  const keyword = keywordInput.value.trim();
  if (!keyword) { setStatus("Enter a keyword first to reset its offset.", "error"); return; }
  await new Promise((resolve) =>
    chrome.runtime.sendMessage({ type: "RESET_SEARCH_OFFSET", payload: { keyword } }, resolve)
  );
  setStatus(`Offset reset for "${keyword}". Next run will start from result #1.`, "success");
  await refreshPaginationInfo();
});

// ── Run ────────────────────────────────────────────────────────────────────────

function sendMessage(payload) {
  return new Promise((resolve) => chrome.runtime.sendMessage(payload, resolve));
}

async function copyToClipboard(text) {
  if (!text) return false;
  try { await navigator.clipboard.writeText(text); return true; } catch (_) { return false; }
}

runBtn.addEventListener("click", async () => {
  const scanMode    = scanModeSelect.value;
  const personName  = personInput.value.trim();
  const keyword     = keywordInput.value.trim();
  const docUrl      = docUrlInput.value.trim();
  const existingLinks = parseExistingLinksFromUserInput(existingLinksInput.value);
  const linkedinTabId = Number(linkedinSelect.value);
  const docsTabId     = Number(docsSelect.value);

  if (!keyword) { setStatus("Keyword is required.", "error"); return; }
  if (scanMode === "messages" && !personName) { setStatus("Person name is required for Messages mode.", "error"); return; }
  if (!docUrl || !extractDocIdFromUrl(docUrl)) {
    setStatus("Paste a valid Google Doc URL (docs.google.com/document/d/...).", "error");
    return;
  }
  if (!linkedinTabId || !docsTabId) { setStatus("Open both LinkedIn and a Google Doc tab first.", "error"); return; }

  saveFormState();
  runBtn.disabled = true;
  setStatus("Running… LinkedIn is being scanned. This may take up to 60 seconds.", "");

  const result = await sendMessage({
    type: "RUN_COLLECTION",
    payload: { scanMode, personName, keyword, docUrl, existingLinks, linkedinTabId, docsTabId }
  });

  runBtn.disabled = false;

  if (!result?.ok) {
    if (result?.fallbackText) {
      const copied = await copyToClipboard(result.fallbackText);
      if (copied) {
        setStatus("Auto-insert failed — text copied to clipboard. Click inside the Google Doc and press Ctrl+V to paste.", "error");
        return;
      }
    }
    setStatus(result?.error || "Something went wrong.", "error");
    return;
  }

  setStatus(result.message, "success");
  await refreshPaginationInfo(); // update the "next run from result #N" display
});

// ── Init ───────────────────────────────────────────────────────────────────────

(async () => {
  try {
    const state = await restoreFormState();
    await loadTabs();
    updateModeUi();
    if (state.linkedinTabId && linkedinSelect.querySelector(`option[value="${state.linkedinTabId}"]`)) {
      linkedinSelect.value = state.linkedinTabId;
    }
    if (state.docsTabId && docsSelect.querySelector(`option[value="${state.docsTabId}"]`)) {
      docsSelect.value = state.docsTabId;
    }
    attachAutoSave();
    await refreshPaginationInfo();
  } catch (_) {
    setStatus("Could not initialize popup.", "error");
  }
})();
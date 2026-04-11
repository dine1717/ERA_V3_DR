const LINKEDIN_PATTERN = "https://www.linkedin.com/*";
const DOCS_PATTERN = "https://docs.google.com/document/*";

// ── Utilities ─────────────────────────────────────────────────────────────────

function extractDocIdFromUrl(urlOrText) {
  if (!urlOrText || typeof urlOrText !== "string") return null;
  const s = urlOrText.trim();
  const m = s.match(/https?:\/\/docs\.google\.com\/document\/d\/([a-zA-Z0-9_-]+)/i);
  if (m) return m[1];
  const m2 = s.match(/\/document\/d\/([a-zA-Z0-9_-]+)/i);
  return m2 ? m2[1] : null;
}

function queryTabs(q) {
  return new Promise((r) => chrome.tabs.query(q, r));
}

function getTab(id) {
  return new Promise((resolve, reject) => {
    chrome.tabs.get(id, (t) => {
      if (chrome.runtime.lastError) { reject(new Error(chrome.runtime.lastError.message)); return; }
      resolve(t);
    });
  });
}

function sendTabMsg(tabId, payload) {
  return new Promise((resolve, reject) => {
    chrome.tabs.sendMessage(tabId, payload, (r) => {
      if (chrome.runtime.lastError) { reject(new Error(chrome.runtime.lastError.message)); return; }
      resolve(r);
    });
  });
}

function isMissingScript(msg) {
  const m = (msg || "").toLowerCase();
  return m.includes("receiving end does not exist") || m.includes("could not establish connection");
}

async function sendWithInject(tabId, payload, files) {
  try { return await sendTabMsg(tabId, payload); }
  catch (err) {
    if (!isMissingScript(err.message)) throw err;
    await chrome.scripting.executeScript({ target: { tabId, allFrames: false }, files });
    await sleep(300);
    return await sendTabMsg(tabId, payload);
  }
}

function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

function waitTabComplete(tabId, ms = 30000) {
  return new Promise((resolve) => {
    let done = false;
    const finish = () => {
      if (done) return; done = true;
      chrome.tabs.onUpdated.removeListener(fn);
      clearTimeout(t); resolve();
    };
    const t = setTimeout(finish, ms);
    const fn = (id, info) => { if (id === tabId && info.status === "complete") finish(); };
    chrome.tabs.onUpdated.addListener(fn);
  });
}

// ── Pagination ────────────────────────────────────────────────────────────────

function offsetKey(kw) {
  return `search_offset_${String(kw).toLowerCase().replace(/\s+/g, "_").slice(0, 60)}`;
}
function getOffset(kw) {
  return new Promise((r) => chrome.storage.local.get([offsetKey(kw)], (res) => r(res[offsetKey(kw)] || 0)));
}
function setOffset(kw, v) {
  return new Promise((r) => chrome.storage.local.set({ [offsetKey(kw)]: v }, r));
}

// ── LinkedIn navigation ───────────────────────────────────────────────────────

async function goToLinkedInSearch(tabId, keyword, offset) {
  offset = offset || 0;
  const url =
    `https://www.linkedin.com/search/results/content/` +
    `?keywords=${encodeURIComponent(keyword)}` +
    `&origin=GLOBAL_SEARCH_HEADER&sortBy=date_posted` +
    (offset > 0 ? `&start=${offset}` : "");
  await new Promise((r) => chrome.tabs.update(tabId, { url }, r));
  await waitTabComplete(tabId);
  await sleep(6000);
}

// ── Docs tab resolution ───────────────────────────────────────────────────────

async function resolveDocsTab(docId, preferredTabId) {
  const want = String(docId).toLowerCase();
  if (preferredTabId) {
    try {
      const tab = await getTab(preferredTabId);
      const id = extractDocIdFromUrl(tab.url || "");
      if (id && id.toLowerCase() === want) return preferredTabId;
    } catch (_) {}
  }
  for (const pat of [
    `https://docs.google.com/document/d/${docId}/*`,
    `https://docs.google.com/document/d/${docId}*`
  ]) {
    const tabs = await queryTabs({ url: pat });
    if (tabs[0]?.id) return tabs[0].id;
  }
  const all = await queryTabs({ url: DOCS_PATTERN });
  for (const t of all) {
    const id = extractDocIdFromUrl(t.url || "");
    if (id && id.toLowerCase() === want) return t.id;
  }
  return null;
}

// ── INSERT INTO GOOGLE DOCS ───────────────────────────────────────────────────
//
// Google Docs architecture:
//   - There is a hidden <iframe class="docs-texteventtarget-iframe">
//   - Inside it lives a <textarea> that captures ALL keyboard/paste events
//   - Google Docs attaches its paste handler to iframeDoc (the iframe's document)
//   - When paste fires, GDocs reads event.clipboardData.getData("text/plain")
//
// The working method (no OAuth needed):
//   1. Focus the textarea inside the iframe
//   2. Dispatch a ClipboardEvent("paste") on iframeDoc with DataTransfer
//      containing our text in "text/plain"
//   3. Google Docs' paste handler receives it and inserts the text
//
// This runs in world:"MAIN" so it has access to the real page JS context.

async function insertIntoGoogleDoc(docsTabId, text) {
  // Bring window + tab to foreground — required for focus APIs
  const tab = await getTab(docsTabId);
  await new Promise((r) => chrome.windows.update(tab.windowId, { focused: true }, r));
  await new Promise((r) => chrome.tabs.update(docsTabId, { active: true }, r));
  await sleep(700);

  const results = await chrome.scripting.executeScript({
    target: { tabId: docsTabId, allFrames: false },
    world: "MAIN",
    args: [text],
    func: (textToInsert) => {
      // ── Find the editor iframe ────────────────────────────────────────────
      function findEditorIframe() {
        const byClass = document.querySelector("iframe.docs-texteventtarget-iframe");
        if (byClass) return byClass;
        for (const f of document.querySelectorAll("iframe")) {
          try {
            if (f.contentDocument && f.contentDocument.querySelector("textarea")) return f;
          } catch (_) {}
        }
        return null;
      }

      const iframe = findEditorIframe();
      if (!iframe) return { ok: false, error: "Google Docs editor iframe not found. Is the doc fully loaded?" };

      let iframeDoc, ta;
      try {
        iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
        ta = iframeDoc.querySelector("textarea");
      } catch (e) {
        return { ok: false, error: `Cannot access iframe document: ${e.message}` };
      }
      if (!ta) return { ok: false, error: "Textarea inside editor iframe not found." };

      // ── Focus the textarea so Docs cursor is active ───────────────────────
      ta.focus();

      // ── Move cursor to end of doc: dispatch Ctrl+End on iframeDoc ────────
      const endEvent = new KeyboardEvent("keydown", {
        key: "End", code: "End", keyCode: 35, which: 35,
        ctrlKey: true, bubbles: true, cancelable: true
      });
      iframeDoc.dispatchEvent(endEvent);

      // ── Build a DataTransfer with our text ────────────────────────────────
      // Google Docs reads event.clipboardData.getData("text/plain") on paste
      let dt;
      try {
        dt = new DataTransfer();
        dt.setData("text/plain", textToInsert);
        dt.setData("text/html", "<p>" + textToInsert.replace(/\n/g, "</p><p>") + "</p>");
      } catch (e) {
        return { ok: false, error: `DataTransfer construction failed: ${e.message}` };
      }

      // ── Dispatch paste event on the iframe document ───────────────────────
      // GDocs listens at document level, not on the textarea itself
      const pasteEvent = new ClipboardEvent("paste", {
        bubbles: true,
        cancelable: true,
        clipboardData: dt
      });

      iframeDoc.dispatchEvent(pasteEvent);

      // Small check: also try dispatching on the textarea in case GDocs
      // moved its listener there in a newer version
      if (!pasteEvent.defaultPrevented) {
        const pasteEvent2 = new ClipboardEvent("paste", {
          bubbles: true,
          cancelable: true,
          clipboardData: dt
        });
        ta.dispatchEvent(pasteEvent2);
      }

      return { ok: true, method: "ClipboardEvent-on-iframeDoc" };
    }
  });

  const result = results?.[0]?.result;
  if (!result) {
    throw new Error("No result from executeScript — reload the Google Doc tab and try again.");
  }
  if (!result.ok) {
    throw new Error(result.error || "Insert failed.");
  }

  // Give Google Docs a moment to process the paste event
  await sleep(800);
  return result;
}

// ── Main handler ──────────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type !== "RUN_COLLECTION") return false;

  (async () => {
    try {
      const {
        scanMode, personName, keyword, docUrl,
        existingLinks, linkedinTabId, docsTabId
      } = message.payload || {};

      const mode = scanMode === "feed" ? "feed"
        : scanMode === "search" ? "search"
        : "messages";

      if (!keyword) throw new Error("Keyword is required.");
      if (mode === "messages" && !personName) throw new Error("Person name is required for Messages mode.");

      const docId = extractDocIdFromUrl(docUrl);
      if (!docId) throw new Error("Invalid Google Doc URL.");

      const linkedinTab = typeof linkedinTabId === "number"
        ? { id: linkedinTabId }
        : (await queryTabs({ url: LINKEDIN_PATTERN }))[0];
      if (!linkedinTab?.id) throw new Error("No LinkedIn tab found.");

      const resolvedDocsTabId = await resolveDocsTab(
        docId,
        typeof docsTabId === "number" ? docsTabId : null
      );
      if (!resolvedDocsTabId) throw new Error("No Google Doc tab found. Open the doc and try again.");

      // ── Load known links ─────────────────────────────────────────────────
      const storageKey = `seen_links_${docId}`;
      const stored = await new Promise((r) =>
        chrome.storage.local.get([storageKey], (res) => r(res[storageKey] || []))
      );
      const storedKnown = new Set(Array.isArray(stored) ? stored.map(String) : []);
      const userKnown = new Set((Array.isArray(existingLinks) ? existingLinks : []).map(String));

      let docKnownLinks = new Set();
      try {
        const resp = await sendWithInject(
          resolvedDocsTabId,
          { type: "GET_DOC_LINKS", payload: { expectedDocId: docId } },
          ["content-docs.js"]
        );
        if (resp?.ok) docKnownLinks = new Set((resp.links || []).map(String));
      } catch (_) {}

      const knownLinks = new Set([...userKnown, ...docKnownLinks, ...storedKnown]);

      // ── Scan LinkedIn ────────────────────────────────────────────────────
      let linkedInScanMode = mode;
      let currentOffset = 0;

      if (mode === "feed" || mode === "search") {
        currentOffset = await getOffset(keyword);
        await goToLinkedInSearch(linkedinTab.id, keyword, currentOffset);
        linkedInScanMode = "collectSearch";
      }

      const scanResult = await sendWithInject(
        linkedinTab.id,
        { type: "SCAN_LINKEDIN", payload: { scanMode: linkedInScanMode, personName, keyword } },
        ["content-linkedin.js"]
      );

      if (!scanResult?.ok) throw new Error(scanResult?.error || "Failed to scan LinkedIn.");

      const links = scanResult.links || [];
      const scanStats = scanResult.stats || {};

      if (mode === "feed" || mode === "search") {
        await setOffset(keyword, currentOffset + Math.max(links.length, 10));
      }

      if (!links.length) {
        sendResponse({
          ok: true,
          message: `No post links found. Scanned ${scanStats.unitsScanned ?? 0} blocks. Try running again.`,
          stats: { scanStats }
        });
        return;
      }

      // ── Deduplicate ──────────────────────────────────────────────────────
      const uniqueToAdd = links.filter((l) => !knownLinks.has(String(l)));

      if (!uniqueToAdd.length) {
        sendResponse({
          ok: true,
          message: `All ${links.length} link(s) already in the doc — nothing new to add.`,
          stats: { scanStats }
        });
        return;
      }

      // ── Build text block ─────────────────────────────────────────────────
      const contextLabel = mode === "messages"
        ? (String(personName || "").trim() || "Messages")
        : `Search: ${keyword}`;
      const header = `\nLinkedIn matches for "${contextLabel}" — keyword: "${keyword}":\n`;
      const body = uniqueToAdd.map((l) => `- ${l}`).join("\n");
      const textBlock = `${header}${body}\n`;

      // ── Insert into Google Doc ───────────────────────────────────────────
      try {
        await insertIntoGoogleDoc(resolvedDocsTabId, textBlock);
      } catch (insertErr) {
        // Write to clipboard as fallback so user can Ctrl+V manually
        try {
          await chrome.scripting.executeScript({
            target: { tabId: resolvedDocsTabId },
            world: "MAIN",
            args: [textBlock],
            func: (t) => navigator.clipboard.writeText(t)
          });
        } catch (_) {}

        sendResponse({
          ok: false,
          fallbackText: textBlock,
          error: `Found ${uniqueToAdd.length} links but auto-paste failed: ${insertErr.message}. ` +
            `The links have been copied to your clipboard — ` +
            `click inside the Google Doc and press Ctrl+V to paste.`
        });
        return;
      }

      // ── Persist ──────────────────────────────────────────────────────────
      const allKnown = Array.from(new Set([...storedKnown, ...uniqueToAdd.map(String)]));
      await new Promise((r) => chrome.storage.local.set({ [storageKey]: allKnown }, r));

      sendResponse({
        ok: true,
        message: `Done. Added ${uniqueToAdd.length} new link(s), skipped ${links.length - uniqueToAdd.length} duplicates.`,
        stats: { scanStats }
      });

    } catch (error) {
      sendResponse({ ok: false, error: error.message || "Unexpected error." });
    }
  })();

  return true;
});

// ── Reset offset ──────────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type !== "RESET_SEARCH_OFFSET") return false;
  const { keyword } = message.payload || {};
  if (!keyword) { sendResponse({ ok: false }); return true; }
  chrome.storage.local.remove(offsetKey(keyword), () => sendResponse({ ok: true }));
  return true;
});
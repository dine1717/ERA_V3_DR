// content-docs.js — reads existing links from the Google Doc for deduplication.
// Insertion is handled entirely in background.js via executeScript world:MAIN.

function extractDocIdFromUrl(url) {
  if (!url || typeof url !== "string") return null;
  const m = url.match(/\/document\/d\/([a-zA-Z0-9_-]+)/i);
  return m ? m[1] : null;
}

function getAllLinksFromDoc() {
  const parts = [];

  document.querySelectorAll(
    ".kix-lineview-text-block, .kix-wordhtmlgenerator-word-node, .kix-lineview-content"
  ).forEach((el) => parts.push(el.textContent || ""));

  // Texteventtarget iframe textarea often holds full document text
  const iframe = document.querySelector("iframe.docs-texteventtarget-iframe");
  if (iframe) {
    try {
      const ta = iframe.contentDocument?.querySelector("textarea");
      if (ta && ta.value) parts.push(ta.value);
    } catch (_) {}
  }

  const full = parts.join("\n");
  const matches = full.match(/https?:\/\/[^\s)\]>"]+/g) || [];
  return [...new Set(matches.map((l) => l.replace(/[.,;]+$/, "").trim()))];
}

(function () {
  if (globalThis.__MYLINKAPP_DOCS_CS__) return;
  globalThis.__MYLINKAPP_DOCS_CS__ = true;

  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message?.type !== "GET_DOC_LINKS") return false;
    try {
      const docId = extractDocIdFromUrl(location.href);
      const exp = message.payload?.expectedDocId
        ? String(message.payload.expectedDocId).toLowerCase() : "";
      const got = docId ? String(docId).toLowerCase() : "";
      if (exp && got && exp !== got) {
        sendResponse({ ok: false, error: "Wrong Google Doc tab open.", links: [] });
        return true;
      }
      sendResponse({ ok: true, links: getAllLinksFromDoc() });
    } catch (e) {
      sendResponse({ ok: false, error: e.message, links: [] });
    }
    return true;
  });
})();
// content-docs.js
// Responsibilities:
//   1. Read all existing links from the doc (for deduplication)
//   2. Signal back to background — actual text insertion is done by
//      background.js via chrome.scripting.executeScript (world: MAIN)
//      which runs in the real page context Google Docs responds to.

function extractDocIdFromUrl(url) {
  if (!url || typeof url !== "string") return null;
  const m = url.match(/\/document\/d\/([a-zA-Z0-9_-]+)/i);
  return m ? m[1] : null;
}

function extractLinksFromText(text) {
  const matches = (text || "").match(/https?:\/\/[^\s)\]>"]+/g) || [];
  return new Set(matches.map((l) => l.replace(/[.,;]+$/, "").trim()));
}

/**
 * Read all text out of the Google Doc DOM.
 * Google Docs renders text into .kix-lineview-text-block spans.
 * We collect ALL of them regardless of scroll position.
 */
function getAllDocLinks() {
  const textParts = [];

  // Primary: kix paragraph text spans
  document.querySelectorAll(".kix-lineview-text-block").forEach((el) => {
    textParts.push(el.textContent || "");
  });

  // Secondary: any anchor hrefs already rendered as hyperlinks in the doc
  document.querySelectorAll(".kix-wordhtmlgenerator-word-node").forEach((el) => {
    textParts.push(el.textContent || "");
  });

  // Also grab the texteventtarget textarea value if available
  const iframe = document.querySelector("iframe.docs-texteventtarget-iframe");
  if (iframe && iframe.contentDocument) {
    const ta = iframe.contentDocument.querySelector("textarea");
    if (ta && ta.value) textParts.push(ta.value);
  }

  const fullText = textParts.join("\n");
  return Array.from(extractLinksFromText(fullText));
}

(function registerDocsBridge() {
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
        sendResponse({ ok: false, error: "Wrong doc tab open. Open the correct Google Doc and try again." });
        return true;
      }

      const links = getAllDocLinks();
      sendResponse({ ok: true, links });
    } catch (e) {
      sendResponse({ ok: false, error: e.message });
    }

    return true;
  });
})();
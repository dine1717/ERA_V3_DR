function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function normalizeText(value) {
  return String(value || "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

function nodeSearchText(node) {
  if (!node) return "";
  const a = node.innerText || "";
  const b = node.textContent || "";
  return normalizeText(`${a}\n${b}`);
}

function keywordMatchesNodeText(text, keyword) {
  const t = normalizeText(text);
  const k = normalizeText(keyword);
  if (!k) return false;
  if (t.includes(k)) return true;
  const words = k.split(" ").filter(Boolean);
  if (words.length > 1) return words.every((w) => t.includes(w));
  return false;
}

// ─── URL helpers ──────────────────────────────────────────────────────────────

function toAbsoluteUrl(href) {
  if (!href || typeof href !== "string") return null;
  const t = href.trim();
  if (!t || t.startsWith("javascript") || t.startsWith("#")) return null;
  if (t.startsWith("http")) return t;
  try {
    return new URL(t, location.origin).href;
  } catch (_) {
    return null;
  }
}

function isLinkedInPostLink(urlString) {
  try {
    const url = new URL(urlString);
    const host = url.hostname.toLowerCase();
    if (!host.endsWith("linkedin.com")) return false;

    let path = url.pathname.toLowerCase();
    try { path = decodeURIComponent(path); } catch (_) {}
    const full = url.href.toLowerCase();

    // Exclude non-post navigation links
    const excluded = [
      "/in/", "/company/", "/school/", "/jobs/", "/learning/",
      "/notifications/", "/messaging/", "/mynetwork/", "/sales/",
      "/signup", "/login", "/authwall", "/search/"
    ];
    if (excluded.some((x) => path.startsWith(x))) return false;

    return (
      path.includes("/feed/update/") ||
      path.includes("activity:") ||
      path.includes("ugcpost") ||
      path.startsWith("/posts/") ||
      path.startsWith("/pulse/") ||
      path.includes("/recent-activity/all/") ||
      full.includes("activityurn=") ||
      full.includes("ugcpost=") ||
      /\/posts\/[^/?#]+/.test(path)
    );
  } catch (_) {
    return false;
  }
}

/**
 * Extract all LinkedIn post links from a DOM subtree.
 * Covers <a href>, data-href, data-li-url, data-urn / data-id URNs.
 */
function extractPostLinksFromNode(node) {
  const links = new Set();
  if (!node || node.nodeType !== 1) return links;

  const consider = (raw) => {
    const abs = toAbsoluteUrl(raw);
    if (abs && isLinkedInPostLink(abs)) links.add(abs);
  };

  for (const attr of ["href", "data-href", "data-li-url", "data-test-app-link"]) {
    const v = node.getAttribute && node.getAttribute(attr);
    if (v) consider(v);
  }

  node.querySelectorAll("a[href]").forEach((el) => consider(el.getAttribute("href")));
  node.querySelectorAll("[data-href]").forEach((el) => consider(el.getAttribute("data-href")));
  node.querySelectorAll("[data-li-url]").forEach((el) => consider(el.getAttribute("data-li-url")));

  // URN attributes → reconstruct canonical feed URL
  node.querySelectorAll("[data-urn],[data-id],[data-chameleon-result-urn]").forEach((el) => {
    for (const attr of ["data-urn", "data-id", "data-chameleon-result-urn"]) {
      const v = el.getAttribute(attr);
      if (!v) continue;
      if (v.includes("urn:li:activity") || v.includes("urn:li:ugcPost")) {
        links.add(`https://www.linkedin.com/feed/update/${encodeURIComponent(v)}/`);
      }
    }
  });

  return links;
}

// ─── SEARCH (primary mode) ────────────────────────────────────────────────────

function isSearchResultsContentPage() {
  return (location.pathname || "").includes("/search/results/content");
}

/**
 * Get all search result card containers currently in the DOM.
 * Uses every known LinkedIn search result selector (2024-2025 DOM).
 */
function getSearchResultContainers() {
  const set = new Set();

  const selectors = [
    // Current LinkedIn search results (2024-2025)
    "li.reusable-search__result-container",
    "div[data-view-name='search-entity-result-universal-template']",
    "li[data-view-name='search-entity-result-universal-template']",
    // Chameleon search cards
    "div[data-chameleon-result-urn]",
    "li[data-chameleon-result-urn]",
    // Older class names still seen in some regions
    ".reusable-search__result-container",
    ".search-reusables__result-container",
    // Feed-style cards embedded in search
    "div.feed-shared-update-v2",
    "article.feed-shared-update-v2",
    // Activity/ugcPost URN containers
    'li[data-urn*="urn:li:activity"]',
    'div[data-urn*="urn:li:activity"]',
    'li[data-urn*="urn:li:ugcPost"]',
    'div[data-urn*="urn:li:ugcPost"]',
  ];

  selectors.forEach((sel) => {
    try { document.querySelectorAll(sel).forEach((el) => set.add(el)); } catch (_) {}
  });

  // Keep outermost unique containers — avoid counting a child and its parent as two
  const arr = Array.from(set);
  return arr.filter((el) => !arr.some((other) => other !== el && other.contains(el)));
}

/**
 * Poll until at least minCount result containers appear, or timeout.
 */
async function waitForSearchResults(minCount, timeoutMs) {
  minCount = minCount || 1;
  timeoutMs = timeoutMs || 12000;
  const step = 500;
  let waited = 0;
  while (waited < timeoutMs) {
    if (getSearchResultContainers().length >= minCount) return true;
    await wait(step);
    waited += step;
  }
  return false;
}

/**
 * Try clicking the "Date posted" sort option in LinkedIn's filter UI.
 * The URL already has sortBy=date_posted so this is best-effort UI confirmation.
 */
async function applySortByDate() {
  // Look for any visible "Sort by" or "Date posted" button/pill
  const allClickable = Array.from(document.querySelectorAll(
    "button, [role='option'], [role='menuitem'], [role='radio'], li, .artdeco-pill"
  ));

  // First try: find a "Date posted" option directly visible (e.g. chip filters)
  const dateChip = allClickable.find((el) => {
    const text = normalizeText(el.textContent);
    return text === "date posted" || text === "most recent" || text === "latest";
  });
  if (dateChip) {
    dateChip.click();
    await wait(2500);
    return true;
  }

  // Second try: open a sort dropdown first
  const sortBtn = allClickable.find((el) => {
    const text = normalizeText(el.textContent);
    const label = normalizeText(el.getAttribute("aria-label") || "");
    return text.includes("sort by") || label.includes("sort by") || text === "sort";
  });
  if (sortBtn) {
    sortBtn.click();
    await wait(700);
    const menuItems = Array.from(document.querySelectorAll(
      "[role='option'], [role='menuitem'], .artdeco-dropdown__item, li button"
    ));
    const dateOpt = menuItems.find((el) => {
      const t = normalizeText(el.textContent);
      return t.includes("date posted") || t.includes("most recent") || t.includes("latest");
    });
    if (dateOpt) {
      dateOpt.click();
      await wait(2500);
      return true;
    }
    // Close dropdown if nothing found
    document.body.click();
    await wait(300);
  }

  return false;
}

/**
 * Scroll to load more search results until we have targetCount posts
 * or the page stops loading new ones.
 */
async function loadMoreSearchResults(targetCount) {
  targetCount = targetCount || 40;
  const MAX_ROUNDS = 80;
  const MIN_ROUNDS = 8;
  const STABLE_STOP = 6;
  let stable = 0;

  for (let round = 0; round < MAX_ROUNDS; round++) {
    const current = getSearchResultContainers().length;
    if (current >= targetCount) break;

    // Scroll window (primary)
    window.scrollTo({ top: document.body.scrollHeight, behavior: "instant" });
    document.documentElement.scrollTop = document.documentElement.scrollHeight;

    // Also scroll main content container
    const main = document.querySelector("main.scaffold-layout__main, main");
    if (main && main.scrollHeight > main.clientHeight + 100) {
      main.scrollTop = main.scrollHeight;
    }

    // Also scroll the results list itself if it has its own scroll
    const resultsList = document.querySelector(
      ".reusable-search__entity-result-list, .search-results-container, ul.reusable-search__entity-result-list"
    );
    if (resultsList && resultsList.scrollHeight > resultsList.clientHeight + 50) {
      resultsList.scrollTop = resultsList.scrollHeight;
    }

    await wait(2200);

    const after = getSearchResultContainers().length;
    if (after > current) {
      stable = 0;
    } else {
      stable++;
      if (round + 1 >= MIN_ROUNDS && stable >= STABLE_STOP) break;
    }
  }
}

/**
 * Main search collection. Called after background.js navigates to:
 * /search/results/content/?keywords=...&sortBy=date_posted
 */
async function collectSearchResultsLinks(opts) {
  var keyword = (opts && opts.keyword) || "";

  if (!isSearchResultsContentPage()) {
    throw new Error("Expected LinkedIn Posts search results page (/search/results/content/...).");
  }

  // Wait for initial cards to render
  await waitForSearchResults(3, 12000);

  // Best-effort: click date sort in UI (URL already requests it)
  await applySortByDate();

  // Re-wait after sort change
  await waitForSearchResults(3, 8000);

  // Scroll until we have 40+ posts
  await loadMoreSearchResults(40);

  // Final settle
  await wait(1000);

  var containers = getSearchResultContainers();
  var foundLinks = new Set();

  // Primary: extract from containers
  containers.forEach(function(c) {
    extractPostLinksFromNode(c).forEach(function(l) { foundLinks.add(l); });
  });

  // Fallback: if still sparse, scan all anchors in main
  if (foundLinks.size < 5) {
    var anchors = document.querySelectorAll("main a[href], .search-results-container a[href]");
    anchors.forEach(function(a) {
      var abs = toAbsoluteUrl(a.getAttribute("href"));
      if (abs && isLinkedInPostLink(abs)) foundLinks.add(abs);
    });
  }

  return {
    links: Array.from(foundLinks),
    stats: {
      scanMode: "search",
      unitsScanned: containers.length,
      keywordHits: containers.length,
      postLinksFound: foundLinks.size,
      keyword: String(keyword)
    }
  };
}

// ─── FEED ─────────────────────────────────────────────────────────────────────

function isFeedOrHomePage() {
  var p = location.pathname || "";
  return p === "/" || p === "/feed" || p.startsWith("/feed/") || p === "/home" || p.startsWith("/home/");
}

async function ensureFeedPage() {
  if (isFeedOrHomePage()) return;
  var homeLink = document.querySelector('a[href="/feed/"], a[href="/feed"], a[href="/"], a[aria-label*="Home" i]');
  if (homeLink) { homeLink.click(); await wait(2500); }
  if (!isFeedOrHomePage()) throw new Error("Please navigate to LinkedIn Home/Feed, then run again.");
}

function getFeedUpdateCards() {
  var set = new Set();
  var selectors = [
    'li[data-urn*="urn:li:activity"]', 'li[data-urn*="urn:li:ugcPost"]',
    'div[data-urn*="urn:li:activity"]', 'div[data-urn*="urn:li:ugcPost"]',
    "div.feed-shared-update-v2", "article.feed-shared-update-v2",
    '[data-id*="urn:li:activity"]', '[data-id*="urn:li:ugcPost"]',
    ".occludable-update"
  ];
  selectors.forEach(function(sel) {
    try { document.querySelectorAll(sel).forEach(function(el) { set.add(el); }); } catch (_) {}
  });
  var arr = Array.from(set);
  return arr.filter(function(el) { return !arr.some(function(other) { return other !== el && el.contains(other); }); });
}

async function loadMoreFeed() {
  var maxRounds = 60, minRounds = 5, stable = 0;
  for (var round = 0; round < maxRounds; round++) {
    var before = getFeedUpdateCards().length;
    window.scrollTo({ top: document.body.scrollHeight, behavior: "instant" });
    document.documentElement.scrollTop = document.documentElement.scrollHeight;
    var main = document.querySelector("main");
    if (main && main.scrollHeight > main.clientHeight + 100) main.scrollTop = main.scrollHeight;
    await wait(1800);
    var after = getFeedUpdateCards().length;
    if (after > before) { stable = 0; }
    else { stable++; if (round + 1 >= minRounds && stable >= 5) break; }
  }
  window.scrollTo({ top: 0, behavior: "instant" });
  await wait(300);
}

async function scanFeed(opts) {
  var keyword = (opts && opts.keyword) || "";
  await ensureFeedPage();
  await wait(1000);
  await loadMoreFeed();
  var cards = getFeedUpdateCards();
  var foundLinks = new Set();
  var keywordHits = 0;
  cards.forEach(function(card) {
    var text = nodeSearchText(card);
    if (!keyword || keywordMatchesNodeText(text, keyword)) {
      keywordHits++;
      extractPostLinksFromNode(card).forEach(function(link) { foundLinks.add(link); });
    }
  });
  if (cards.length === 0) {
    document.querySelectorAll("main a[href], article a[href]").forEach(function(a) {
      var abs = toAbsoluteUrl(a.getAttribute("href"));
      if (abs && isLinkedInPostLink(abs)) {
        var text = nodeSearchText(a.closest("article, li, div") || a);
        if (!keyword || keywordMatchesNodeText(text, keyword)) { foundLinks.add(abs); keywordHits++; }
      }
    });
  }
  return { links: Array.from(foundLinks), stats: { scanMode: "feed", unitsScanned: cards.length, keywordHits: keywordHits, postLinksFound: foundLinks.size } };
}

// ─── MESSAGES ─────────────────────────────────────────────────────────────────

function isMessagingPage() {
  return location.pathname.startsWith("/messaging");
}

async function ensureMessagingPage() {
  if (isMessagingPage()) return;
  var messageNav = document.querySelector("a[href*='/messaging'], a[aria-label*='Messaging']");
  if (messageNav) { messageNav.click(); await wait(1800); }
  if (!isMessagingPage()) throw new Error("Open LinkedIn Messaging page first.");
}

async function searchPersonInMessages(personName) {
  var searchInput = document.querySelector([
    "input[placeholder*='Search messages']",
    "input[aria-label*='Search messages']",
    "input.msg-conversations-container__search-term",
    ".msg-conversations-container__search input",
    "aside input[type='text']"
  ].join(", "));

  if (!searchInput) return false;

  var nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value") &&
    Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;

  searchInput.focus();
  await wait(200);

  if (nativeSetter) { nativeSetter.call(searchInput, ""); }
  else { searchInput.value = ""; }
  searchInput.dispatchEvent(new Event("input", { bubbles: true }));
  await wait(150);

  for (var i = 0; i < personName.length; i++) {
    var char = personName[i];
    var current = searchInput.value;
    if (nativeSetter) { nativeSetter.call(searchInput, current + char); }
    else { searchInput.value = current + char; }
    searchInput.dispatchEvent(new Event("input", { bubbles: true }));
    searchInput.dispatchEvent(new KeyboardEvent("keypress", { bubbles: true, key: char }));
    await wait(40);
  }

  searchInput.dispatchEvent(new KeyboardEvent("keyup", { bubbles: true, key: "Enter" }));
  await wait(1500);
  return true;
}

function findConversationByPerson(personName) {
  var target = normalizeText(personName);
  if (!target) return null;

  var allItems = Array.from(document.querySelectorAll([
    "li.msg-conversation-listitem", ".msg-conversation-listitem",
    ".msg-conversation-card", "[data-view-name='message-list-item']",
    "ul.msg-conversations-container__conversations-list > li"
  ].join(", ")));

  if (!allItems.length) return null;

  var exact = allItems.find(function(item) { return normalizeText(item.textContent).includes(target); });
  if (exact) return exact;

  var words = target.split(" ").filter(function(w) { return w.length > 1; });
  if (words.length > 1) {
    var allWords = allItems.find(function(item) {
      var t = normalizeText(item.textContent);
      return words.every(function(w) { return t.includes(w); });
    });
    if (allWords) return allWords;
  }

  if (words.length >= 3) {
    var firstLast = [words[0], words[words.length - 1]];
    var fl = allItems.find(function(item) {
      var t = normalizeText(item.textContent);
      return firstLast.every(function(w) { return t.includes(w); });
    });
    if (fl) return fl;
  }

  if (words.length >= 1) {
    var fn = allItems.find(function(item) { return normalizeText(item.textContent).includes(words[0]); });
    if (fn) return fn;
  }

  return null;
}

async function waitForConversationList(maxWaitMs) {
  maxWaitMs = maxWaitMs || 5000;
  var step = 300, waited = 0;
  while (waited < maxWaitMs) {
    var items = document.querySelectorAll([
      "li.msg-conversation-listitem", ".msg-conversation-listitem",
      ".msg-conversation-card", "[data-view-name='message-list-item']",
      "ul.msg-conversations-container__conversations-list > li"
    ].join(", "));
    if (items.length > 0) return true;
    await wait(step);
    waited += step;
  }
  return false;
}

function getThreadMessageNodes() {
  var selectors = [
    ".msg-s-message-list__event", ".msg-s-message-group__messages li",
    ".msg-s-event-listitem", ".msg-s-message-list__bubble",
    ".msg-s-message-list-content", "li.msg-s-message-list__event",
    "[class*='msg-s-event-listitem']", "[data-view-name='message-entity']"
  ];
  var set = new Set();
  selectors.forEach(function(sel) { try { document.querySelectorAll(sel).forEach(function(el) { set.add(el); }); } catch (_) {} });
  return Array.from(set);
}

function findMessageScrollContainer() {
  var selectors = [
    ".msg-s-message-list__container", ".msg-s-message-list",
    ".msg-thread__scroll-container", ".scaffold-finite-scroll__content",
    "[class*='msg-s-message-list__container']", "[class*='msg-thread']"
  ];
  for (var i = 0; i < selectors.length; i++) {
    var el = document.querySelector(selectors[i]);
    if (el && el.scrollHeight > el.clientHeight + 40) return el;
  }
  var messages = document.querySelectorAll(".msg-s-message-list__event, .msg-s-event-listitem");
  var scores = new Map();
  messages.forEach(function(msg) {
    var el = msg.parentElement;
    for (var d = 0; d < 22 && el; d++) {
      var delta = el.scrollHeight - el.clientHeight;
      if (delta > 30 && delta > (scores.get(el) || 0)) scores.set(el, delta);
      el = el.parentElement;
    }
  });
  var bestEl = null, bestDelta = 0;
  scores.forEach(function(delta, el) { if (delta > bestDelta) { bestDelta = delta; bestEl = el; } });
  return bestEl;
}

async function nextPaint() {
  return new Promise(function(r) { requestAnimationFrame(function() { requestAnimationFrame(r); }); });
}

function dispatchScrollNudge(el) {
  [-400, -800].forEach(function(deltaY) {
    try { el.dispatchEvent(new WheelEvent("wheel", { bubbles: true, cancelable: true, deltaY: deltaY, deltaMode: WheelEvent.DOM_DELTA_PIXEL })); } catch (_) {}
  });
}

async function loadOlderMessagesInThread() {
  var container = findMessageScrollContainer();
  var stable = 0;
  for (var round = 0; round < 150; round++) {
    if (!container) container = findMessageScrollContainer();
    var beforeH = container ? container.scrollHeight : 0;
    var beforeC = getThreadMessageNodes().length;
    if (container) { container.scrollTop = 0; if (container.scrollBy) container.scrollBy(0, -99999); dispatchScrollNudge(container); }
    var nodes = getThreadMessageNodes();
    if (nodes.length) { try { nodes[0].scrollIntoView({ block: "start", behavior: "instant" }); } catch (_) {} }
    await nextPaint();
    await wait(1600);
    await wait(350);
    if (!container) container = findMessageScrollContainer();
    var grew = (container ? container.scrollHeight : 0) > beforeH + 5 || getThreadMessageNodes().length > beforeC;
    if (grew) { stable = 0; } else { stable++; if (round + 1 >= 8 && stable >= 6) break; }
  }
  if (container) { try { container.scrollTop = container.scrollHeight; } catch (_) {} }
  await wait(500);
}

async function scanMessages(opts) {
  var personName = (opts && opts.personName) || "";
  var keyword = (opts && opts.keyword) || "";

  await ensureMessagingPage();
  await wait(1000);
  await waitForConversationList(5000);
  await searchPersonInMessages(personName);
  await wait(1200);

  var conversation = findConversationByPerson(personName);

  if (!conversation) {
    var allItems = Array.from(document.querySelectorAll([
      "li.msg-conversation-listitem", ".msg-conversation-listitem",
      ".msg-conversation-card", "[data-view-name='message-list-item']",
      "ul.msg-conversations-container__conversations-list > li"
    ].join(", ")));
    var visibleNames = allItems.slice(0, 6).map(function(el) {
      var nameEl = el.querySelector(".msg-conversation-listitem__participant-names, .truncate, span[dir='ltr']");
      return normalizeText(nameEl ? nameEl.textContent : el.textContent).slice(0, 40);
    }).filter(Boolean);
    var hint = visibleNames.length
      ? " Visible conversations: \"" + visibleNames.join('" | "') + "\""
      : " No conversation items found — make sure LinkedIn Messaging is open and fully loaded.";
    throw new Error("Could not find conversation for \"" + personName + "\"." + hint);
  }

  conversation.click();
  await wait(2200);
  await loadOlderMessagesInThread();

  var messageNodes = getThreadMessageNodes();
  var foundLinks = new Set();
  var keywordHits = 0;
  messageNodes.forEach(function(node) {
    var text = nodeSearchText(node);
    if (!keywordMatchesNodeText(text, keyword)) return;
    keywordHits++;
    extractPostLinksFromNode(node).forEach(function(link) { foundLinks.add(link); });
  });

  return { links: Array.from(foundLinks), stats: { scanMode: "messages", unitsScanned: messageNodes.length, keywordHits: keywordHits, postLinksFound: foundLinks.size } };
}

// ─── Message bridge ───────────────────────────────────────────────────────────

(function registerLinkedInBridge() {
  if (globalThis.__MYLINKAPP_LINKEDIN_CS__) return;
  globalThis.__MYLINKAPP_LINKEDIN_CS__ = true;

  chrome.runtime.onMessage.addListener(function(message, sender, sendResponse) {
    var type = message && message.type;
    if (type !== "SCAN_LINKEDIN" && type !== "SCAN_LINKEDIN_MESSAGES") return false;

    (async function() {
      try {
        var payload = message.payload || {};
        var scanMode = payload.scanMode || "messages";
        var result;
        if (scanMode === "collectSearch") {
          result = await collectSearchResultsLinks({ keyword: payload.keyword });
        } else if (scanMode === "feed") {
          result = await scanFeed({ keyword: payload.keyword });
        } else {
          result = await scanMessages({ personName: payload.personName, keyword: payload.keyword });
        }
        sendResponse({ ok: true, links: result.links, stats: result.stats });
      } catch (error) {
        sendResponse({ ok: false, error: error.message || "Failed to scan LinkedIn." });
      }
    })();
    return true;
  });
})();
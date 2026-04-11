# LinkedIn Link Collector — Chrome Extension

A Chrome extension that searches LinkedIn for posts matching a keyword across three modes — **Global Search**, **Messages**, and **Feed** — then automatically appends the unique post links into a Google Doc, skipping any duplicates from previous runs.

Video Link -- https://youtu.be/LBD05pwSPQ0 

---

## What It Does

1. **Searches LinkedIn** for posts matching your keyword (sorted by most recent)
2. **Collects post URLs** from the results — up to 40 posts per run
3. **Deduplicates** against links already saved in the Google Doc and all previous runs
4. **Writes the new links** directly into your Google Doc (no copy-paste needed)
5. **Paginates automatically** — each run picks up where the last one left off, so you never get the same 20 results twice

---

## Scan Modes

### 🔍 Search Mode (recommended)
Navigates LinkedIn to `search/results/content/?keywords=YOUR_KEYWORD&sortBy=date_posted`, scrolls to load 40+ results, and collects all post URLs. Results are always sorted **newest first**.

### 💬 Messages Mode
Opens LinkedIn Messaging, searches for a person by name, opens their conversation thread, scrolls all the way back through the entire message history, and extracts any post links shared in that thread that match your keyword.

### 🏠 Feed Mode
Same as Search Mode — navigates to the LinkedIn Posts search page for your keyword rather than scanning the home feed (which gives more reliable and keyword-relevant results).

---

## Project Files

| File | Purpose |
|------|---------|
| `manifest.json` | Chrome extension config (Manifest V3), declares permissions |
| `background.js` | Main orchestrator — handles LinkedIn navigation, pagination, deduplication, and Google Doc insertion via `executeScript world:MAIN` |
| `content-linkedin.js` | Runs on LinkedIn — scrolls pages, collects post URLs, handles all three scan modes |
| `content-docs.js` | Runs on Google Docs — reads existing links from the doc for deduplication |
| `popup.html` | Extension popup UI |
| `popup.css` | Popup styles |
| `popup.js` | Popup logic — form state, pagination display, reset offset button |

---

## How to Load the Extension

1. Open Chrome and go to `chrome://extensions/`
2. Enable **Developer mode** (toggle in the top-right corner)
3. Click **Load unpacked**
4. Select the extension folder
5. The extension icon appears in your Chrome toolbar

After any code change: click **Reload** on the extension card in `chrome://extensions/`.

---

## How to Use

### Step 1 — Open required tabs
- Open **LinkedIn** in one tab (`https://www.linkedin.com`)
- Open your **Google Doc** in another tab

### Step 2 — Open the extension popup
Click the extension icon in the Chrome toolbar.

### Step 3 — Fill in the form

| Field | What to enter |
|-------|--------------|
| **Where to scan** | Choose Search, Messages, or Feed |
| **Person name** | Only for Messages mode — enter the name exactly as it appears in your chat list (e.g. `John Doe`) |
| **Keyword** | The word or phrase to search for (e.g. `vLLM`, `AI hiring`, `open source`) |
| **LinkedIn Tab** | Select the LinkedIn tab from the dropdown |
| **Google Doc URL** | Paste the full URL of your Google Doc |
| **Google Doc Tab** | Select the Google Doc tab from the dropdown |
| **Extra links to skip** | Optional — paste any URLs you want to exclude. Previous run links are already tracked automatically |

### Step 4 — Click "Find and Add Links"
The extension will:
1. Navigate the LinkedIn tab to the search results (sorted by date)
2. Scroll the page to load 40+ posts
3. Extract all post URLs
4. Remove any already saved in the doc or previous runs
5. Switch to the Google Doc tab and insert the new links

### Step 5 — Pagination (getting the next batch)
After each run, the blue info bar in the popup shows:
> *"Next run continues from result #21"*

Run again with the same keyword to get the **next 20–40 posts** that weren't in the first batch. Each run automatically advances to the next page of results.

To **start over from result #1**, click the **↺ Reset** button next to the pagination info.

---

## Duplicate Handling

The extension skips a link if it appears in **any** of these sources:

- Links currently visible in the Google Doc DOM
- Links saved to `chrome.storage` from all previous runs (persists across popup close/reopen)
- Links manually pasted into the "Extra links to skip" field

You **do not** need to manually copy links from the doc after each run — the extension remembers everything automatically.

---

## Troubleshooting

**"Could not find Google Docs editor iframe"**
The Google Doc tab didn't finish loading. Refresh the doc tab, wait for it to fully load, then run again.

**"Could not find conversation for [name]"**
The error message will show which conversations are actually visible (e.g. `Visible conversations: "john doe" | "jane smith"`). Make sure:
- The LinkedIn tab is on the Messaging page (`linkedin.com/messaging`)
- The name matches what's shown in the chat list (first + last name is usually enough)

**"No post links found. Scanned 0 blocks."**
The search results page didn't load in time. Run again — the extension waits 6 seconds for the page to load but LinkedIn can sometimes be slower.

**"Auto-paste failed — links copied to clipboard"**
The extension couldn't insert into the doc automatically. The links are on your clipboard — click once inside the Google Doc body and press **Ctrl+V** (Windows/Linux) or **Cmd+V** (Mac).

**Extension not responding / "Receiving end does not exist"**
Go to `chrome://extensions/`, click **Reload** on the extension, then refresh both the LinkedIn and Google Doc tabs.

---

## How the Google Doc Insertion Works

The extension uses `chrome.scripting.executeScript` with `world: "MAIN"` to run code inside Google Docs' own JavaScript environment. It:

1. Brings the Google Doc tab to the foreground (required for focus APIs)
2. Finds the hidden `<iframe class="docs-texteventtarget-iframe">` that Google Docs uses to capture keyboard input
3. Focuses the `<textarea>` inside that iframe
4. Dispatches a `ClipboardEvent("paste")` with a `DataTransfer` object containing the links text directly on the iframe's `document`
5. Google Docs' paste handler receives the event, reads the text, and inserts it at the cursor position

No OAuth, no Google sign-in, no external API calls required.

---

## Permissions Used

| Permission | Why it's needed |
|-----------|----------------|
| `tabs` | Read tab URLs to find the right LinkedIn and Google Doc tabs |
| `storage` | Remember seen links and pagination offsets across runs |
| `scripting` | Inject content scripts and run insertion code in Google Docs |
| `activeTab` | Access the currently active tab |
| `windows` | Bring the Google Doc window to the foreground before inserting |

---

## Known Limitations

- LinkedIn's DOM structure changes periodically. If selectors break, update `content-linkedin.js`.
- The extension can only read links that are visible in the Google Doc's DOM (not the full document if it's very long). Links from all previous runs are stored separately in `chrome.storage` to compensate.
- LinkedIn may rate-limit searches if you run many times quickly. Wait a minute between runs if you see empty results.

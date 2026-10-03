# Privata — Private Local Search Engine

> **Search privately. Discover locally.** · Your files stay on your device.

## Introduction
Privata is a lightweight search engine for **your own documents**. It reads files you add, builds an **inverted index**, and ranks results with **TF-IDF** — all on your computer. Nothing is sent to Google, Bing, OpenAI, a cloud service or any other external API. It is an MCA academic project that demonstrates how the core of a search engine works.

## Problem Statement
Cloud and desktop search tools often upload content or queries to remote servers. Students and professionals who keep private notes, reports or study material need a way to find information quickly **without giving their data to a third party**. Building such a tool is also a practical way to understand how search actually works.

## Objectives
1. Build a search engine that works completely offline on local files.
2. Implement text extraction, tokenization, an inverted index and TF-IDF ranking from scratch.
3. Provide a modern, responsive interface with snippets, highlighting and filters.
4. Keep it simple: Python + Flask + plain HTML/CSS/JS, no database server.
5. Add basic security (file validation, size limit, path-traversal protection, HTML escaping).

## Features
- Local document indexing (`.txt .md .html .csv`, plus `.pdf` through the optional `pypdf` package)
- Inverted index + TF-IDF ranking with a relevance percentage
- Highlighted snippets, file path, size and last-modified date
- Filters (file type, date, minimum relevance) and sorting (relevance, A–Z, newest, oldest)
- Search suggestions from the indexed vocabulary and your past searches (no external API)
- Recent searches with *Clear history*
- Drag-and-drop upload with progress, friendly errors and duplicate detection
- Documents page: view, remove, filter, Build / Rebuild / Clear index
- Analytics from real activity: searches, average time, top terms, documents by type
- Dark / light theme, animated background that can be switched off, responsive layout
- Privacy and About pages

## Technology Stack
| Layer | Technology |
|-------|-----------|
| Frontend | HTML5, CSS3, vanilla JavaScript (canvas background; no libraries, CDN or web fonts) |
| Backend | Python 3, Flask |
| Search | Python standard library (`re`, `math`, `json`, `csv`, `html.parser`) |
| Storage | JSON and TXT files in `data/` — **no database server** |
| Optional | `pypdf` for PDF text extraction |

## System Architecture
```
User
  ↓
Web Interface (HTML / CSS / JavaScript)
  ↓  fetch() calls to 127.0.0.1 only
Flask Application (app.py)
  ↓
Query Processor (tokenizer.py)
  ↓
Search Engine (searcher.py)
  ↓
Inverted Index (indexer.py)  →  data/index/index.json
  ↓
Ranking Engine (ranking.py: TF-IDF)
  ↓
Local Documents (data/documents/)
  ↓
Search Results (snippets, highlights, measured timing)
```

## Working Flow
```
 INDEXING                                       SEARCHING
 ────────                                       ─────────
 Document file                                  Query "machine learning"
   │ extract text (txt/md/html/csv/pdf)           │ same normalisation
   ▼                                              ▼
 lowercase → remove punctuation                 tokens: [machine, learning]
   │ split into tokens                            │ look up each token
   ▼                                              ▼
 remove stop words → light stemming             inverted index → candidate documents
   │ count words                                  │ TF-IDF score per document
   ▼                                              ▼
 inverted index (word → {doc: count})           sort → filters → snippets → results (+ timing)
```

## Search Algorithm
1. **Normalize** – lowercase, replace punctuation with spaces.
2. **Tokenize** – split into words; ignore 1-letter tokens.
3. **Remove stop words** – `the`, `and`, `of` …
4. **Stem lightly** – plurals are folded (`algorithms` → `algorithm`).
5. **Look up** each query word in the inverted index.
6. **Score** each candidate with TF-IDF × coverage.
7. **Sort** best first. Relevance % is relative to the best match (best = 100%).
8. **Snippet** – choose the ~230-character window containing the most query words, escape HTML, wrap matches in `<mark>`.

### Inverted Index
A dictionary from each word to the documents that contain it and how many times:
```python
{ "python":   {"doc1": 4, "doc3": 1, "doc7": 2},
  "machine":  {"doc2": 6, "doc3": 1},
  "learning": {"doc2": 5, "doc4": 2} }
```
A query only touches the entries for its own words, so it never has to read every file. The index is saved in `data/index/index.json`.

### TF-IDF
```
TF     = (times the word appears in the document) / (document length)
IDF    = ln((N + 1) / (df + 1)) + 1      N = number of documents, df = documents containing the word
TF-IDF = TF × IDF
score(document) = Σ TF-IDF(query word) × (query words found / query words total)
```
A word that is frequent in one document but rare across the library gets a high score. Words in the **file name** count as if they appeared 3 extra times (simple field boosting).

## Project Structure
```
privata/
├── app.py                  Flask app: pages + JSON API + validation
├── requirements.txt        Flask, pypdf (optional)
├── README.md  VIVA.md  TESTING.md
├── search_engine/
│   ├── tokenizer.py        normalise, tokenize, stop words, stemming
│   ├── indexer.py          text extraction + inverted index + JSON storage
│   ├── ranking.py          TF-IDF ranking
│   ├── searcher.py         query processing, filters, snippets, highlighting, suggestions
│   └── history.py          local search history + analytics
├── templates/              base, index, search, documents, analytics, privacy, about, error
├── static/css/style.css    themes, layout, animations
├── static/js/app.js        UI logic (theme.js prevents a theme flash on load)
├── data/documents/         your documents (samples included)
├── data/index/             index.json + cached text (created automatically)
├── data/app_data/          history.json (created automatically)
└── screenshots/
```

## Installation
1. Install **Python 3.9+** from python.org (tick *Add Python to PATH*).
2. Open a terminal in the project folder (the one containing `app.py`).
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Start the app:
   ```
   python app.py
   ```
5. Open **http://127.0.0.1:5000** in your browser.

No Docker, Node.js, npm, MySQL, MongoDB, Redis or Apache is needed. The sample documents are indexed automatically at start-up, so you can search straight away. If `pypdf` cannot be installed, delete that line from `requirements.txt`; everything except `.pdf` still works.

## How to Run
`python app.py` → open `http://127.0.0.1:5000` → try the sample queries below. Stop with `Ctrl+C`. If port 5000 is busy, change the port on the last line of `app.py`.

**Sample queries:** `machine learning` · `inverted index` · `python` · `database` · `flask` · `privacy` · `tf idf` · `responsive design`

## Screenshots
| Home | Search |
|---|---|
| ![Home](screenshots/01-home.png) | ![Search](screenshots/02-search.png) |
| **Dark mode** | **Documents** |
| ![Dark](screenshots/03-search-dark.png) | ![Documents](screenshots/04-documents.png) |
| **Analytics** | **Mobile** |
| ![Analytics](screenshots/05-analytics.png) | ![Mobile](screenshots/06-mobile.png) |

## Testing
See **TESTING.md** for the manual test table. The backend was also exercised with Flask's test client and the UI with a headless browser (search, filters, upload, unsupported file, delete, theme, mobile width, no external requests).

## Limitations
- Keyword search only: no synonyms or meaning-based search ("car" will not find "automobile").
- Very light stemming (plurals only) and English stop words only.
- Scanned PDFs (images) have no extractable text.
- The index is a JSON file loaded in memory: fine for hundreds or a few thousand documents, not millions.
- Files and the index are **not encrypted**, and there is no login because the app is meant for one user on one computer.
- Search matches words, not exact phrases.

## Future Scope
Phrase search and word-proximity boost · BM25 ranking · Porter stemmer / more languages · DOCX support · folder watching for automatic re-indexing · encrypted index · "did you mean" spelling correction · SQLite storage for bigger libraries.

## Conclusion
Privata shows, with small readable code, how a search engine turns documents into an inverted index, scores them with TF-IDF and returns ranked, highlighted results — while keeping every file and every query on the user's own computer.

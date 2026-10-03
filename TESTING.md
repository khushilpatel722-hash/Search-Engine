# Privata — Testing

Start the app with `python app.py` and open http://127.0.0.1:5000. The sample documents are indexed automatically.

## Manual test cases

| # | Test | Steps | Expected result |
|---|------|-------|-----------------|
| 1 | Search existing keyword | Search page → type `machine learning` → *Search Privately* | Several results, `sample_ml.txt` first at 100%; words highlighted; text like "4 results found in 3.2 ms" |
| 2 | Search unknown keyword | Search `qqqzzz` | "No matching documents found." and "Try different keywords or remove filters." |
| 3 | Upload TXT | Documents → *Browse Files* → choose a `.txt` file with some words | Progress bar, "Document indexed successfully.", new card appears, document count increases |
| 4 | Upload MD | Drag a `.md` file onto the drop area | Same as test 3 |
| 5 | Duplicate upload | Upload the same file again (or a copy with another name) | Friendly error: already exists / content already indexed; no second card |
| 6 | Delete document | Click *Remove* on a card → confirm | Card disappears; searching for its words returns no result; count decreases |
| 7 | Rebuild index | Documents → *Rebuild Index* → confirm | Toast "Rebuild complete…"; status "Ready"; searches still work |
| 8 | Empty search | Press *Search Privately* with an empty box | Message: "Please type something to search for." |
| 9 | Special characters | Search `<script>alert(1)</script>`, `!!!`, `c++ & "quotes"` | No script runs and no error page; `!!!` shows "only contains symbols…"; text is shown escaped |
| 10 | Dark mode | Click *Dark Mode* in the navigation, reload | Dark theme applies; choice is remembered after reload; button now says *Light Mode* |
| 11 | Mobile layout | Narrow the browser to ~390 px (or use device mode) | Menu becomes a hamburger, cards stack, **no horizontal scrolling** on any page |

## Additional test cases

| # | Test | Expected result |
|---|------|-----------------|
| 12 | Unsupported file (`.exe`, `.jpg`) | "is not supported. Allowed: …" shown in the queue; nothing saved |
| 13 | Empty file | "is empty." |
| 14 | Corrupted file (binary data named `.txt`, fake `.pdf`) | "looks corrupted…" / "not a valid PDF"; file is not kept |
| 15 | File over 10 MB | "larger than 10 MB." |
| 16 | Path traversal file name (`../../evil.txt`) | Saved safely as `evil.txt` inside `data/documents` only |
| 17 | Clear Index | Count becomes 0, status "Empty"; files in `data/documents` still exist; *Build Index* restores everything |
| 18 | Add a file by hand | Copy a `.txt` into `data/documents`; Documents shows status "Needs update (1 file waiting)"; *Build Index* indexes it |
| 19 | Filters and sorting | On Search, change File type, Date, Relevance and Sort; results update immediately |
| 20 | Suggestions | Type `mach` → suggestions such as `machine learning` appear; arrow keys + Enter select |
| 21 | Recent searches | Searches appear in the side panel; clicking one re-runs it; *Clear history* empties it |
| 22 | Animation off | Click *Animation: On* → background stops; setting is remembered |
| 23 | View document | Click a result title or *View* → text opens; type in "Find" to highlight words |
| 24 | Analytics | After several searches, totals, average time and top terms match your activity |
| 25 | Offline | Disconnect from the internet and repeat tests 1–7: everything still works |

## Automated checks that were run during development
- Flask test client: search ranking, filters, unknown/empty/symbol queries, XSS query, suggestions, upload (valid, duplicate name, duplicate content, unsupported, empty, binary, fake PDF, stop-words-only), delete, clear, build, analytics, all page routes and 404.
- Headless browser: search with highlighting, type filter, no-result state, XSS query, upload + rejected file, delete, theme switch, mobile layout (no horizontal scroll on 5 pages), zero external network requests, zero console errors.

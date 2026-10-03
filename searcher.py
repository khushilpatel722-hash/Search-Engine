"""
searcher.py - QUERY PROCESSING, FILTERING, SNIPPETS
===================================================
What happens when the user searches:

  1. validate the query            4. rank with TF-IDF (ranking.py)
  2. tokenize it (same as docs)    5. apply filters + sorting
  3. look words up in the          6. build a highlighted snippet per result
     inverted index                7. report the measured search time
"""
import html
import re
from bisect import bisect_left, bisect_right
import time
from datetime import datetime, timedelta

from .ranking import rank
from .tokenizer import tokenize, stem

MAX_QUERY_LENGTH = 200
MAX_RESULTS = 100
_WORD = re.compile(r"[^\W_]+", re.UNICODE)


class SearchError(Exception):
    """Invalid search request. The message is safe to show to the user."""


def highlight_html(text, terms, max_chars=None):
    """Escape `text` for HTML and wrap words matching `terms` in <mark>. Returns (html, count)."""
    if max_chars:
        text = text[:max_chars]
    terms, out, last, count = set(terms), [], 0, 0
    for m in _WORD.finditer(text):
        if stem(m.group().lower()) in terms:
            out.append(html.escape(text[last:m.start()]))        # escaping = XSS protection
            out.append("<mark>" + html.escape(m.group()) + "</mark>")
            last, count = m.end(), count + 1
    out.append(html.escape(text[last:]))
    return "".join(out), count


def make_snippet(text, terms, width=230):
    """Choose the ~230 character window that contains the most query words."""
    if not text:
        return ""
    terms = set(terms)
    starts = [m.start() for m in _WORD.finditer(text) if stem(m.group().lower()) in terms][:400]
    if starts:
        best, best_n = starts[0], 0
        for s in starts:                                          # try a window at each match
            n = bisect_right(starts, s + width - 60) - bisect_left(starts, s)
            if n > best_n:
                best, best_n = s, n
        start = max(0, best - 40)
    else:
        start = 0
    end = min(len(text), start + width)
    if start > 0:
        gap = text.find(" ", start)
        if gap != -1 and gap - start < 30:
            start = gap + 1
    if end < len(text):
        gap = text.rfind(" ", start, end)
        if gap > start + 50:
            end = gap
    body, _ = highlight_html(text[start:end], terms)
    return ("… " if start > 0 else "") + body + (" …" if end < len(text) else "")


class Searcher:
    def __init__(self, index):
        self.index = index

    def parse(self, query):
        query = (query or "").strip()
        if not query:
            raise SearchError("Please type something to search for.")
        if len(query) > MAX_QUERY_LENGTH:
            raise SearchError(f"Your query is too long (maximum {MAX_QUERY_LENGTH} characters).")
        terms = tokenize(query)
        if not terms:
            raise SearchError("Your query only contains symbols or very common words. Try more specific keywords.")
        return terms

    @staticmethod
    def _date_limit(date):
        now = datetime.now()
        days = {"week": 7, "month": 30, "year": 365}
        if date == "today":
            return now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        if date in days:
            return (now - timedelta(days=days[date])).timestamp()
        return None

    def search(self, query, file_type="all", date="any", sort="relevance", min_relevance=0):
        terms = self.parse(query)
        started = time.perf_counter()                       # real, measured timing

        with self.index.lock:
            ranked = rank(terms, self.index.postings, self.index.docs)
            docs = self.index.docs
            top = ranked[0][1] if ranked else 1.0
            limit = self._date_limit(date)
            rows = []
            for doc_id, score in ranked:
                meta = docs[doc_id]
                if file_type not in ("all", "") and meta["ext"] != "." + file_type.lstrip("."):
                    continue
                if limit is not None and meta["modified"] < limit:
                    continue
                percent = max(1, round(score / top * 100))  # relative to the best match
                if percent < min_relevance:
                    continue
                rows.append((meta, percent))
            library_size = len(docs)

        keys = {
            "alpha": (lambda r: r[0]["filename"].lower(), False),
            "newest": (lambda r: r[0]["modified"], True),
            "oldest": (lambda r: r[0]["modified"], False),
        }
        if sort in keys:
            fn, rev = keys[sort]
            rows.sort(key=fn, reverse=rev)
        # (default "relevance" keeps the ranked order)

        results = []
        for meta, percent in rows[:MAX_RESULTS]:
            folder = meta["rel"].rsplit("/", 1)[0] if "/" in meta["rel"] else ""
            results.append({
                "id": meta["id"], "filename": meta["filename"], "ext": meta["ext"].lstrip("."),
                "relevance": percent, "size": meta["size"], "modified": meta["modified"],
                "path": "Documents/" + folder if folder else "Documents/",
                "snippet": make_snippet(self.index.get_text(meta["id"]), terms),
            })
        elapsed_ms = (time.perf_counter() - started) * 1000
        return {"results": results, "count": len(rows), "time_ms": round(elapsed_ms, 2),
                "terms": terms, "library_size": library_size}

    def suggest(self, text, history_queries, limit=8):
        """Suggestions come only from past local searches and the indexed vocabulary."""
        text = (text or "").lower().strip()[:MAX_QUERY_LENGTH]
        if not text:
            return []
        out = [q for q in history_queries if q.lower().startswith(text) and q.lower() != text]
        words = text.split(" ")
        head, last = " ".join(words[:-1]), words[-1]
        prefix = tokenize(last, remove_stop=False, use_stem=False)
        if prefix and len(last) >= 2:
            for term in self.index.complete(prefix[0], limit):
                candidate = (head + " " + term).strip()
                if candidate not in out and candidate != text:
                    out.append(candidate)
        return out[:limit]

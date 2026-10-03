"""
history.py - LOCAL SEARCH HISTORY + ANALYTICS
=============================================
Every search is appended to data/app_data/history.json on THIS computer.
The Analytics page is calculated from this real log (nothing is invented).
"""
import json
import os
import threading
import time
from collections import Counter
from datetime import datetime, timedelta

MAX_ENTRIES = 2000


class HistoryStore:
    def __init__(self, folder):
        os.makedirs(folder, exist_ok=True)
        self.path = os.path.join(folder, "history.json")
        self.lock = threading.Lock()
        self.entries = []
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                self.entries = json.load(fh).get("searches", [])
        except (OSError, ValueError, AttributeError):
            self.entries = []

    def _save(self):
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump({"searches": self.entries}, fh)
            os.replace(tmp, self.path)
        except OSError:
            pass            # history is a convenience: never break a search because of it

    def record(self, query, time_ms, count, terms):
        with self.lock:
            self.entries.append({"q": query.strip(), "t": time.time(), "ms": time_ms,
                                 "n": count, "terms": terms})
            self.entries = self.entries[-MAX_ENTRIES:]
            self._save()

    def recent(self, limit=8):
        with self.lock:
            seen, out = set(), []
            for entry in reversed(self.entries):
                key = entry["q"].lower()
                if key not in seen:
                    seen.add(key)
                    out.append(entry["q"])
                if len(out) >= limit:
                    break
            return out

    def queries(self):
        return self.recent(limit=50)

    def clear(self):
        with self.lock:
            self.entries = []
            self._save()

    def analytics(self):
        with self.lock:
            entries = list(self.entries)
        total = len(entries)
        avg = round(sum(e["ms"] for e in entries) / total, 2) if total else 0
        terms = Counter(t for e in entries for t in set(e.get("terms", [])))
        today = datetime.now().date()
        per_day = []
        for back in range(6, -1, -1):
            day = today - timedelta(days=back)
            n = sum(1 for e in entries if datetime.fromtimestamp(e["t"]).date() == day)
            per_day.append({"label": day.strftime("%a"), "count": n})
        return {"total_searches": total, "avg_ms": avg,
                "no_results": sum(1 for e in entries if e["n"] == 0),
                "top_terms": [{"term": t, "count": c} for t, c in terms.most_common(8)],
                "per_day": per_day}

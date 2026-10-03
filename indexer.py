"""
indexer.py - TEXT EXTRACTION + INVERTED INDEX
=============================================
INVERTED INDEX = a dictionary that maps every WORD to the documents that
contain it (and how many times):

    "python"  -> {doc1: 4, doc3: 1, doc7: 2}
    "machine" -> {doc2: 6, doc3: 1}
    "learning"-> {doc2: 5, doc4: 2}

To answer a query we only look up the query words in this dictionary instead
of reading every document - that is why search is fast.

Everything is saved as plain JSON in data/index/ (no database server).
"""
import csv
import hashlib
import json
import os
import re
import threading
import time
from collections import Counter
from html.parser import HTMLParser

from .tokenizer import tokenize

try:                                    # PDF support is optional
    from pypdf import PdfReader
    PDF_AVAILABLE = True
except Exception:                       # pragma: no cover
    PdfReader = None
    PDF_AVAILABLE = False

TEXT_TYPES = (".txt", ".md", ".html", ".csv")
SUPPORTED_EXTENSIONS = TEXT_TYPES + ((".pdf",) if PDF_AVAILABLE else ())
TITLE_BOOST = 3          # words in the file name count as if they appeared 3 extra times


class IndexingError(Exception):
    """A problem with one file or with the index. The message is user-friendly."""


# ----------------------------------------------------------------- extraction
class _HTMLText(HTMLParser):
    """Collects visible text from an HTML page (ignores <script>/<style>)."""
    SKIP = {"script", "style", "noscript", "template", "head"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.depth = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.depth += 1
        self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.depth:
            self.depth -= 1
        self.parts.append(" ")

    def handle_data(self, data):
        if not self.depth:
            self.parts.append(data)


def _read_text(path):
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except PermissionError:
        raise IndexingError("Permission denied while reading the file.")
    except FileNotFoundError:
        raise IndexingError("The file no longer exists.")
    except OSError:
        raise IndexingError("The file could not be read.")
    if b"\x00" in raw[:4096]:
        raise IndexingError("The file looks corrupted or is not a plain-text file.")
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def extract_text(path, ext):
    """Return the plain text of a supported file (whitespace collapsed)."""
    if ext in (".txt", ".md"):
        text = _read_text(path)
    elif ext == ".html":
        parser = _HTMLText()
        try:
            parser.feed(_read_text(path))
            parser.close()
        except IndexingError:
            raise
        except Exception:
            raise IndexingError("The HTML file is corrupted and could not be parsed.")
        text = " ".join(parser.parts)
    elif ext == ".csv":
        try:
            rows = csv.reader(_read_text(path).splitlines())
            text = " | ".join(", ".join(cell for cell in row if cell.strip()) for row in rows)
        except csv.Error:
            raise IndexingError("The CSV file is corrupted and could not be parsed.")
    elif ext == ".pdf":
        if not PDF_AVAILABLE:
            raise IndexingError("PDF support needs the 'pypdf' package (pip install pypdf).")
        try:
            reader = PdfReader(path)
            if reader.is_encrypted and not reader.decrypt(""):
                raise IndexingError("The PDF is password protected.")
            text = " ".join((page.extract_text() or "") for page in reader.pages)
        except IndexingError:
            raise
        except PermissionError:
            raise IndexingError("Permission denied while reading the file.")
        except Exception:
            raise IndexingError("The PDF is corrupted or could not be read.")
    else:
        raise IndexingError("Unsupported file type.")
    return re.sub(r"\s+", " ", text).strip()


# ----------------------------------------------------------------- the index
class InvertedIndex:
    def __init__(self, docs_dir, index_dir):
        self.docs_dir = os.path.abspath(docs_dir)
        self.index_dir = os.path.abspath(index_dir)
        self.text_dir = os.path.join(self.index_dir, "texts")      # cached extracted text
        self.index_path = os.path.join(self.index_dir, "index.json")
        self.lock = threading.RLock()
        self.docs = {}        # doc_id -> metadata
        self.postings = {}    # term   -> {doc_id: count}   <- the inverted index
        self.failed = {}      # relative path -> {"mtime", "error"} (files we could not index)
        self.updated = None
        os.makedirs(self.docs_dir, exist_ok=True)
        os.makedirs(self.text_dir, exist_ok=True)
        self._load()

    # ---- persistence
    def _load(self):
        try:
            with open(self.index_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self.docs = data["docs"]
            self.postings = data["postings"]
            self.failed = data.get("failed", {})
            self.updated = data.get("updated")
        except FileNotFoundError:
            pass
        except (ValueError, KeyError, OSError):
            # Damaged index file: start empty; "Build Index" recreates it.
            self.docs, self.postings, self.failed, self.updated = {}, {}, {}, None

    def _save(self):
        self.updated = time.time()
        payload = {"version": 1, "updated": self.updated, "docs": self.docs,
                   "postings": self.postings, "failed": self.failed}
        tmp = self.index_path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False)
            os.replace(tmp, self.index_path)          # atomic: never leaves a half-written file
        except OSError:
            raise IndexingError("The index could not be saved (check folder permissions and disk space).")

    # ---- helpers
    @staticmethod
    def make_id(rel_path):
        return hashlib.sha1(rel_path.lower().encode("utf-8")).hexdigest()[:12]

    def _safe_abs(self, rel_path):
        """Resolve a stored path and make sure it is INSIDE the documents folder."""
        root = os.path.realpath(self.docs_dir)
        full = os.path.realpath(os.path.join(root, rel_path))
        if os.path.commonpath([root, full]) != root:
            raise IndexingError("Access outside the documents folder is not allowed.")
        return full

    def scan_files(self):
        """Supported files currently inside the documents folder: {rel_path: (abs, size, mtime)}."""
        found = {}
        for folder, dirs, files in os.walk(self.docs_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for name in files:
                ext = os.path.splitext(name)[1].lower()
                if name.startswith(".") or ext not in SUPPORTED_EXTENSIONS:
                    continue
                full = os.path.join(folder, name)
                try:
                    st = os.stat(full)
                except OSError:
                    continue
                rel = os.path.relpath(full, self.docs_dir).replace(os.sep, "/")
                found[rel] = (full, st.st_size, st.st_mtime)
        return found

    def _remove_postings(self, doc_id):
        for term in list(self.postings):
            posting_list = self.postings[term]
            posting_list.pop(doc_id, None)
            if not posting_list:
                del self.postings[term]

    def _text_path(self, doc_id):
        return os.path.join(self.text_dir, doc_id + ".txt")

    # ---- indexing one file
    def index_file(self, abs_path, save=True):
        with self.lock:
            full = self._safe_abs(os.path.relpath(abs_path, self.docs_dir))
            rel = os.path.relpath(full, os.path.realpath(self.docs_dir)).replace(os.sep, "/")
            ext = os.path.splitext(full)[1].lower()
            try:
                st = os.stat(full)
            except FileNotFoundError:
                raise IndexingError("The file could not be found.")
            except PermissionError:
                raise IndexingError("Permission denied while reading the file.")
            if st.st_size == 0:
                raise IndexingError("The file is empty.")
            try:
                text = extract_text(full, ext)
                with open(full, "rb") as fh:
                    digest = hashlib.sha1(fh.read()).hexdigest()
            except OSError:
                raise IndexingError("The file could not be read.")

            filename = os.path.basename(full)
            content_tokens = tokenize(text)
            if not content_tokens:
                raise IndexingError("The file has no searchable words.")
            title_tokens = tokenize(os.path.splitext(filename)[0])
            all_tokens = content_tokens + title_tokens * TITLE_BOOST    # field boosting

            doc_id = self.make_id(rel)
            self._remove_postings(doc_id)                               # re-index = replace
            for term, count in Counter(all_tokens).items():
                self.postings.setdefault(term, {})[doc_id] = count

            try:
                with open(self._text_path(doc_id), "w", encoding="utf-8") as fh:
                    fh.write(text)
            except OSError:
                self._remove_postings(doc_id)
                raise IndexingError("The extracted text could not be stored.")

            self.docs[doc_id] = {
                "id": doc_id, "filename": filename, "ext": ext, "rel": rel,
                "size": st.st_size, "modified": st.st_mtime, "indexed_at": time.time(),
                "words": len(content_tokens), "length": len(all_tokens), "sha1": digest,
            }
            self.failed.pop(rel, None)
            if save:
                self._save()
            return self.docs[doc_id]

    # ---- removing / clearing
    def remove_document(self, doc_id, delete_file=False):
        with self.lock:
            meta = self.docs.get(doc_id)
            if not meta:
                raise IndexingError("That document is not in the index.")
            if delete_file:
                full = self._safe_abs(meta["rel"])
                try:
                    if os.path.exists(full):
                        os.remove(full)
                except PermissionError:
                    raise IndexingError("Permission denied: the file could not be removed.")
                except OSError:
                    raise IndexingError("The file could not be removed.")
            self._remove_postings(doc_id)
            del self.docs[doc_id]
            try:
                os.remove(self._text_path(doc_id))
            except OSError:
                pass
            self._save()
            return meta

    def clear(self):
        """Delete ONLY the search index (never the user's documents)."""
        with self.lock:
            self.docs, self.postings, self.failed = {}, {}, {}
            for name in os.listdir(self.text_dir):
                if name.endswith(".txt"):
                    try:
                        os.remove(os.path.join(self.text_dir, name))
                    except OSError:
                        pass
            self._save()

    # ---- bulk operations
    def sync(self):
        """Incremental update: add new files, refresh changed files, drop deleted files."""
        with self.lock:
            files = self.scan_files()
            summary = {"added": 0, "updated": 0, "removed": 0, "errors": []}
            for doc_id, meta in list(self.docs.items()):
                if meta["rel"] not in files:
                    self._remove_postings(doc_id)
                    del self.docs[doc_id]
                    summary["removed"] += 1
            for rel, (full, size, mtime) in files.items():
                doc_id = self.make_id(rel)
                known = self.docs.get(doc_id)
                if known and known["size"] == size and known["modified"] == mtime:
                    continue
                if rel in self.failed and self.failed[rel]["mtime"] == mtime:
                    continue
                try:
                    self.index_file(full, save=False)
                    summary["updated" if known else "added"] += 1
                except IndexingError as exc:
                    self.failed[rel] = {"mtime": mtime, "error": str(exc)}
                    summary["errors"].append({"file": rel, "error": str(exc)})
            for rel in list(self.failed):
                if rel not in files:
                    del self.failed[rel]
            self._save()
            return summary

    def rebuild(self):
        """Throw the index away and index every file again from scratch."""
        with self.lock:
            self.docs, self.postings, self.failed = {}, {}, {}
            return self.sync()

    # ---- information
    def pending_count(self):
        files = self.scan_files()
        pending = 0
        for rel, (full, size, mtime) in files.items():
            known = self.docs.get(self.make_id(rel))
            if known and known["size"] == size and known["modified"] == mtime:
                continue
            if rel in self.failed and self.failed[rel]["mtime"] == mtime:
                continue
            pending += 1
        return pending

    def stats(self):
        with self.lock:
            pending = self.pending_count()
            if not self.docs:
                status = "Needs update" if pending else "Empty"
            else:
                status = "Needs update" if pending else "Ready"
            return {
                "documents": len(self.docs),
                "words": sum(d["words"] for d in self.docs.values()),
                "terms": len(self.postings),
                "last_update": self.updated if self.docs or self.updated else None,
                "status": status,
                "pending": pending,
                "failed": [{"file": k, "error": v["error"]} for k, v in self.failed.items()],
            }

    def list_documents(self):
        with self.lock:
            return sorted(self.docs.values(), key=lambda d: d["filename"].lower())

    def get_text(self, doc_id):
        try:
            with open(self._text_path(doc_id), "r", encoding="utf-8") as fh:
                return fh.read()
        except OSError:
            return ""

    def find_by_hash(self, digest):
        with self.lock:
            for meta in self.docs.values():
                if meta.get("sha1") == digest:
                    return meta
        return None

    def complete(self, prefix, limit=8):
        """Vocabulary words starting with `prefix`, most widely used first."""
        with self.lock:
            hits = [(len(p), t) for t, p in self.postings.items() if t.startswith(prefix)]
        hits.sort(key=lambda item: (-item[0], item[1]))
        return [term for _, term in hits[:limit]]

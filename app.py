"""
app.py - Privata: Private Local Search Engine (Flask application)
=================================================================
Run with:  python app.py     then open  http://127.0.0.1:5000

The server listens on 127.0.0.1 only (this computer), uses no database server
and makes NO outgoing network requests.
"""
import hashlib
import logging
import os

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename

from search_engine import (HistoryStore, IndexingError, InvertedIndex, Searcher,
                           SearchError, highlight_html)
from search_engine.indexer import SUPPORTED_EXTENSIONS
from search_engine.searcher import MAX_QUERY_LENGTH
from search_engine.tokenizer import tokenize

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(BASE_DIR, "data", "documents")
INDEX_DIR = os.path.join(BASE_DIR, "data", "index")
APP_DATA_DIR = os.path.join(BASE_DIR, "data", "app_data")
MAX_FILE_MB = 10
MAX_FILE_BYTES = MAX_FILE_MB * 1024 * 1024

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_BYTES + 1024 * 1024
app.config["JSON_SORT_KEYS"] = False
log = logging.getLogger("privata")

index = InvertedIndex(DOCS_DIR, INDEX_DIR)
searcher = Searcher(index)
history = HistoryStore(APP_DATA_DIR)


def fail(message, status=400):
    return jsonify({"ok": False, "error": message}), status


def ok(**data):
    return jsonify({"ok": True, **data})


# ------------------------------------------------------------------- security
@app.after_request
def security_headers(resp):
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'")
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["X-Frame-Options"] = "DENY"
    if request.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


@app.errorhandler(HTTPException)
def http_error(exc):
    messages = {404: "That page or resource was not found.",
                405: "That action is not allowed here.",
                413: f"The file is too large. The limit is {MAX_FILE_MB} MB per file."}
    message = messages.get(exc.code, exc.description or "Something went wrong.")
    if request.path.startswith("/api/"):
        return fail(message, exc.code)
    return render_template("error.html", page="", code=exc.code, message=message), exc.code


@app.errorhandler(Exception)
def unexpected_error(exc):
    log.exception("Unexpected error")          # details go to the console, never to the user
    message = "Something went wrong on the server. Please try again."
    if request.path.startswith("/api/"):
        return fail(message, 500)
    return render_template("error.html", page="", code=500, message=message), 500


# ---------------------------------------------------------------------- pages
@app.route("/")
def page_home():
    return render_template("index.html", page="home")


@app.route("/search")
def page_search():
    return render_template("search.html", page="search")


@app.route("/documents")
def page_documents():
    return render_template("documents.html", page="documents")


@app.route("/analytics")
def page_analytics():
    return render_template("analytics.html", page="analytics")


@app.route("/privacy")
def page_privacy():
    return render_template("privacy.html", page="privacy")


@app.route("/about")
def page_about():
    return render_template("about.html", page="about")


# ------------------------------------------------------------------ search API
@app.get("/api/search")
def api_search():
    query = request.args.get("q", "")
    try:
        min_rel = max(0, min(100, int(request.args.get("rel", "0") or 0)))
    except ValueError:
        min_rel = 0
    try:
        data = searcher.search(query, request.args.get("type", "all").lower(),
                               request.args.get("date", "any"),
                               request.args.get("sort", "relevance"), min_rel)
    except SearchError as exc:
        return fail(str(exc), 400)
    history.record(query, data["time_ms"], data["count"], tokenize(query, use_stem=False))
    return ok(**data)


@app.get("/api/suggest")
def api_suggest():
    return ok(suggestions=searcher.suggest(request.args.get("q", ""), history.queries()))


@app.get("/api/recent")
def api_recent():
    return ok(recent=history.recent(8))


@app.delete("/api/recent")
def api_recent_clear():
    history.clear()
    return ok()


@app.get("/api/config")
def api_config():
    return ok(supported=list(SUPPORTED_EXTENSIONS), max_mb=MAX_FILE_MB, max_query=MAX_QUERY_LENGTH)


# ------------------------------------------------------------- documents API
@app.get("/api/documents")
def api_documents():
    return ok(documents=index.list_documents())


@app.get("/api/documents/<doc_id>/text")
def api_document_text(doc_id):
    meta = index.docs.get(doc_id)
    if not meta:
        return fail("That document is not in the index.", 404)
    text = index.get_text(doc_id)
    terms = tokenize(request.args.get("q", "")[:MAX_QUERY_LENGTH])
    shown, truncated = text[:200_000], len(text) > 200_000
    body, matches = highlight_html(shown, terms)
    return ok(filename=meta["filename"], html=body, matches=matches, truncated=truncated)


@app.post("/api/upload")
def api_upload():
    """Upload ONE file: validate -> save inside data/documents -> index it."""
    upload = request.files.get("file")
    if not upload or not upload.filename:
        return fail("No file was received.")
    original = os.path.basename(upload.filename.replace("\\", "/"))
    stem, ext = os.path.splitext(original)
    ext = ext.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return fail(f"'{original}' is not supported. Allowed types: {', '.join(SUPPORTED_EXTENSIONS)}", 415)
    name = (secure_filename(stem)[:80] or "document") + ext      # blocks ../ and odd characters
    data = upload.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        return fail(f"'{original}' is larger than {MAX_FILE_MB} MB.", 413)
    if not data.strip():
        return fail(f"'{original}' is empty.", 422)
    if ext == ".pdf" and not data.startswith(b"%PDF"):
        return fail(f"'{original}' is not a valid PDF file.", 422)

    destination = os.path.join(DOCS_DIR, name)
    if os.path.exists(destination):
        return fail(f"A document named '{name}' already exists.", 409)
    twin = index.find_by_hash(hashlib.sha1(data).hexdigest())
    if twin:
        return fail(f"This content is already indexed as '{twin['filename']}'.", 409)
    try:
        with open(destination, "xb") as fh:
            fh.write(data)
    except FileExistsError:
        return fail(f"A document named '{name}' already exists.", 409)
    except PermissionError:
        return fail("Permission denied: Privata cannot write to the documents folder.", 403)
    except OSError:
        return fail("The file could not be saved. Check free disk space.", 500)

    try:
        meta = index.index_file(destination)
    except IndexingError as exc:
        try:
            os.remove(destination)                 # do not keep files we cannot search
        except OSError:
            pass
        return fail(f"'{original}': {exc}", 422)
    return ok(document=meta, message="Document indexed successfully.")


@app.delete("/api/documents/<doc_id>")
def api_delete_document(doc_id):
    try:
        meta = index.remove_document(doc_id, delete_file=True)
    except IndexingError as exc:
        return fail(str(exc), 404)
    return ok(message=f"'{meta['filename']}' was removed.")


# ----------------------------------------------------------------- index API
@app.get("/api/index/status")
def api_index_status():
    return ok(**index.stats())


def _summary(action, result):
    text = (f"{action} complete: {result['added']} added, {result['updated']} updated, "
            f"{result['removed']} removed.")
    if result["errors"]:
        text += f" {len(result['errors'])} file(s) skipped."
    return text


@app.post("/api/index/build")
def api_build():
    try:
        result = index.sync()
    except IndexingError as exc:
        return fail(str(exc), 500)
    return ok(message=_summary("Index update", result), **result)


@app.post("/api/index/rebuild")
def api_rebuild():
    try:
        result = index.rebuild()
    except IndexingError as exc:
        return fail(str(exc), 500)
    return ok(message=_summary("Rebuild", result), **result)


@app.post("/api/index/clear")
def api_clear():
    try:
        index.clear()
    except IndexingError as exc:
        return fail(str(exc), 500)
    return ok(message="Search index cleared. Your documents were not deleted.")


# --------------------------------------------------------------- analytics API
@app.get("/api/analytics")
def api_analytics():
    stats = index.stats()
    types = {}
    for meta in index.list_documents():
        entry = types.setdefault(meta["ext"].lstrip("."), {"type": meta["ext"].lstrip("."), "docs": 0, "words": 0})
        entry["docs"] += 1
        entry["words"] += meta["words"]
    return ok(documents=stats["documents"], words=stats["words"], terms=stats["terms"],
              types=sorted(types.values(), key=lambda t: -t["docs"]), **history.analytics())


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    try:
        report = index.sync()                      # index any new files (e.g. the samples) at start-up
        print(f"Privata ready: {len(index.docs)} documents indexed.")
        for problem in report["errors"]:
            print(f"  skipped {problem['file']}: {problem['error']}")
    except IndexingError as exc:
        print("Warning:", exc)
    print("Open http://127.0.0.1:5000  (press Ctrl+C to stop)")
    try:
        app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
    except OSError:
        print("Port 5000 is already in use. Close the other program or change the port at the bottom of app.py.")

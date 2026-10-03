"""Privata search engine package (all processing is local)."""
from .indexer import InvertedIndex, IndexingError, PDF_AVAILABLE
from .searcher import Searcher, SearchError, highlight_html
from .history import HistoryStore

__all__ = ["InvertedIndex", "IndexingError", "PDF_AVAILABLE", "Searcher",
           "SearchError", "highlight_html", "HistoryStore"]

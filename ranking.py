"""
ranking.py - TF-IDF RELEVANCE RANKING
=====================================
TF  (term frequency)          = how often a term appears in ONE document,
                                divided by that document's length.
IDF (inverse doc. frequency)  = how RARE the term is across ALL documents.
                                  idf = ln((N + 1) / (df + 1)) + 1
                                N = number of documents, df = documents containing the term.
TF-IDF = TF x IDF             -> high when a term is frequent here but rare elsewhere.

Score of a document for a query = sum of TF-IDF of every query term,
multiplied by "coverage" (fraction of query terms that the document contains),
so a document containing ALL the query words beats one containing only one.
"""
import math


def idf(n_docs, doc_freq):
    """Smoothed inverse document frequency (never zero or negative)."""
    return math.log((n_docs + 1) / (doc_freq + 1)) + 1


def rank(query_terms, postings, docs):
    """
    Score every document that contains at least one query term.

    postings: {term: {doc_id: term_count}}   (the inverted index)
    docs:     {doc_id: {"length": ...}}      (document metadata)
    Returns a list of (doc_id, score) sorted best-first.
    """
    n_docs = len(docs)
    unique_terms = set(query_terms)
    scores, matched = {}, {}

    for term in unique_terms:
        posting_list = postings.get(term)
        if not posting_list:
            continue                                   # unknown word: skip
        weight = idf(n_docs, len(posting_list))
        for doc_id, count in posting_list.items():
            meta = docs.get(doc_id)
            if not meta or meta["length"] <= 0:
                continue
            tf = count / meta["length"]
            scores[doc_id] = scores.get(doc_id, 0.0) + tf * weight
            matched[doc_id] = matched.get(doc_id, 0) + 1

    total = len(unique_terms)
    for doc_id in scores:
        scores[doc_id] *= matched[doc_id] / total      # coverage factor

    return sorted(scores.items(), key=lambda item: item[1], reverse=True)

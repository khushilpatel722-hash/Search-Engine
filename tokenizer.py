"""
tokenizer.py - TEXT PREPROCESSING
=================================
Documents and queries go through the SAME pipeline, otherwise they would
never match each other:

    raw text -> lowercase -> remove punctuation -> split into words (tokens)
             -> drop stop words -> light stemming (plural -> singular)

Example:  "The Databases are Fast!"  ->  ["database", "fast"]
"""
import re

# Stop words are very common words ("the", "and") that carry little meaning.
# Removing them makes the index smaller and the ranking better.
STOP_WORDS = frozenset("""
a about above after again all also am an and any are as at be because been before
being below between both but by can could did do does doing down during each few for
from further had has have having he her here hers him his how i if in into is it its
itself just me more most my no nor not now of off on once only or other our out over
own same she should so some such than that the their them then there these they this
those through to too under until up us very was we were what when where which while
who whom why will with would you your yours
""".split())

_PUNCTUATION = re.compile(r"[\W_]+", re.UNICODE)   # anything that is not a letter/digit


def normalize(text):
    """Step 1+2: lowercase the text and replace punctuation with spaces."""
    return _PUNCTUATION.sub(" ", text.lower())


def stem(word):
    """
    Very small stemmer: only folds plural forms so that 'algorithms' matches
    'algorithm'. (A full stemmer such as Porter is a possible future upgrade.)
    """
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 5 and word.endswith(("sses", "ches", "shes", "xes")):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def tokenize(text, remove_stop=True, use_stem=True):
    """Step 3-5: split into tokens, remove stop words, stem. Returns a list."""
    tokens = []
    for word in normalize(text).split():
        if len(word) < 2:                       # single characters are noise
            continue
        if remove_stop and word in STOP_WORDS:
            continue
        tokens.append(stem(word) if use_stem else word)
    return tokens

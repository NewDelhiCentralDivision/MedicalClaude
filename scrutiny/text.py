"""Text normalisation shared by the rate loader and the matcher."""
from __future__ import annotations

import re

CONSULT = "consult"

# Words that carry no matching value.
STOPWORDS = {
    "the", "of", "for", "and", "a", "an", "in", "on", "with", "per", "to",
    "charge", "charges", "fee", "fees", "day", "rs", "view", "patient",
}

# Words so general that a bill line made only of them cannot identify one
# specific rate-sheet item (e.g. "Medicine", "IV Fluid", "Injection IM/IV").
GENERIC_TERMS = {
    "medicine", "drug", "injection", "inj", "im", "iv", "intravenous",
    "intramuscular", "fluid", "emergency", "management", "bed", "room",
    "nursing", "checkup", "check", "monitoring", "bp", "misc",
    "miscellaneous", "other", "service", "treatment", "material",
    "consumable", "pharmacy", "stay", "admission", "procedure",
}

_SYNONYMS = {
    "consultant": CONSULT,
    "consultation": CONSULT,
    "consulting": CONSULT,
    "doctor": CONSULT,
    "xray": "x ray",
    "medicines": "medicine",
}


def _stem(word: str) -> str:
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def tokens(text: str, keep_generic: bool = False) -> list[str]:
    """Lower-case, de-punctuate and normalise `text` into match tokens.

    Numbers are dropped (a bill line like "Bed/3" is about the bed, not "3").
    `keep_generic=True` keeps stopwords so setting words like "patient" survive
    when classifying rate-sheet entries.
    """
    s = (text or "").lower()
    s = re.sub(r"\bb\s*\.?\s*p\s*\.?(?=\s|$)", " bp ", s)  # "B.P." -> bp
    s = re.sub(r"[^a-z0-9]+", " ", s)
    out: list[str] = []
    for word in s.split():
        if word.isdigit():
            continue
        word = _SYNONYMS.get(word, word)
        for part in word.split():
            part = _stem(part)
            if not keep_generic and part in STOPWORDS:
                continue
            out.append(part)
    return out


def is_generic(toks: list[str]) -> bool:
    """True when every token is a generic term (or there are no tokens)."""
    return all(t in GENERIC_TERMS for t in toks)

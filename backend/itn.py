
import re

_CONNECTOR = r"(?:dot|underscore|hyphen|dash)"
_WORD = r"[a-z0-9]+"


_GAP = r"[\s,?!.]*\s[\s,?!.]*"

_EMAIL_SPAN_RE = re.compile(
    rf"({_WORD}(?:{_GAP}{_CONNECTOR}{_GAP}{_WORD})*)"
    rf"{_GAP}at{_GAP}"
    rf"({_WORD}(?:{_GAP}{_CONNECTOR}{_GAP}{_WORD})+)",
    re.IGNORECASE,
)

_SYMBOL_MAP = {"dot": ".", "underscore": "_", "hyphen": "-", "dash": "-"}

_KNOWN_DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com"]

_FORMED_EMAIL_RE = re.compile(
    r"([a-z0-9._-]+)@([a-z0-9-]+(?:\.[a-z0-9-]+)+)",
    re.IGNORECASE,
)


def normalize_email_like(text: str) -> str:
    text = _EMAIL_SPAN_RE.sub(_convert_match, text)
    text = _FORMED_EMAIL_RE.sub(_correct_formed_email, text)
    return text


def _correct_formed_email(match: re.Match) -> str:
    local = match.group(1)
    domain = _fuzzy_correct_domain(match.group(2).lower())
    return f"{local}@{domain}"


def _convert_match(match: re.Match) -> str:
    local = _convert_segment(match.group(1))
    domain = _convert_segment(match.group(2))
    domain = _fuzzy_correct_domain(domain)
    return f"{local}@{domain}"


def _convert_segment(segment: str) -> str:
    out = []
    for tok in segment.lower().split():
        if tok in _SYMBOL_MAP:
            out.append(_SYMBOL_MAP[tok])
        else:
            # drop any stray punctuation the STT attached to a spoken token
            out.append(re.sub(r"[^a-z0-9]", "", tok))
    return "".join(out)


def _fuzzy_correct_domain(domain: str) -> str:
    if domain in _KNOWN_DOMAINS:
        return domain

    for known in _KNOWN_DOMAINS:
        if domain.endswith(known) and 0 < len(domain) - len(known) <= 4:
            return known

    best = min(_KNOWN_DOMAINS, key=lambda d: _levenshtein(domain, d))
    if _levenshtein(domain, best) <= 2:
        return best
    return domain


def _levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = curr
    return prev[-1]

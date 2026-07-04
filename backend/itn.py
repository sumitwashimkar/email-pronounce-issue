"""
Inverse Text Normalization for spoken structured entities (emails, etc.).

STT engines transcribe speech as natural language, so "john dot smith at
gmail dot com" comes back as literal words, not "john.smith@gmail.com".
Deepgram's smart_format helps some, but doesn't reliably catch every
spoken-symbol pattern -- so we run an explicit regex pass as a safety net.

Only the matched email-like span is rewritten; the rest of the sentence is
left untouched so a stray "at"/"dot" elsewhere doesn't get mangled.
"""
import re

_CONNECTOR = r"(?:dot|underscore|hyphen|dash)"
_WORD = r"[a-z0-9]+"

# Gap between two spoken tokens. When an email is dictated inside a
# conversational sentence, the STT often inserts sentence punctuation and
# capitalization at the pauses -- e.g. "spell Sumit? At gmail dot com?" --
# so the separator has to absorb stray ? . , ! while still requiring at
# least one actual space (which is what genuinely delimits spoken tokens).
_GAP = r"[\s,?!.]*\s[\s,?!.]*"

# local part: word, optionally chained with dot/underscore/hyphen separators
# domain part: same, but requires at least one separator (so "at the office"
# -- which has no "dot"/"dash" -- never matches).
_EMAIL_SPAN_RE = re.compile(
    rf"({_WORD}(?:{_GAP}{_CONNECTOR}{_GAP}{_WORD})*)"
    rf"{_GAP}at{_GAP}"
    rf"({_WORD}(?:{_GAP}{_CONNECTOR}{_GAP}{_WORD})+)",
    re.IGNORECASE,
)

_SYMBOL_MAP = {"dot": ".", "underscore": "_", "hyphen": "-", "dash": "-"}

_KNOWN_DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com"]

# An already-formed email in the transcript. Deepgram's smart_format often
# assembles the email itself (producing "smith@redgmail.com" directly), in
# which case the spoken-form pass above finds nothing to do -- so we also
# fuzzy-correct the domain of any address that is already in x@y.z form.
_FORMED_EMAIL_RE = re.compile(
    r"([a-z0-9._-]+)@([a-z0-9-]+(?:\.[a-z0-9-]+)+)",
    re.IGNORECASE,
)


def normalize_email_like(text: str) -> str:
    """Rewrite spoken email phrases found in `text` into email syntax.

    Runs two passes: (1) convert spoken-form emails ("john dot smith at
    gmail dot com"), then (2) fuzzy-correct the domain of any already-formed
    address (which smart_format may have produced). Non-email text is left
    untouched.
    """
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
    """Snap a slightly-off domain (STT mishearing) to the nearest known one."""
    if domain in _KNOWN_DOMAINS:
        return domain

    # STT often prepends a phantom syllable to a known domain
    # (e.g. "gmail.com" heard as "redgmail.com"). If a known domain is a
    # suffix and the extra prefix is short, treat it as that domain.
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

import re

PALAVROES = [
    r"\bporra\b", r"\bmerda\b", r"\bcaralho\b", r"\bdroga\b",
    r"\bidiota\b", r"\bimbecil\b", r"\bfdp\b", r"\bbosta\b",
    r"\bpalhaçada\b", r"\babsurdo\b",
]
_RE = re.compile("|".join(PALAVROES), re.IGNORECASE)


def mask(text: str | None) -> str:
    """Substitui palavras impróprias por *** preservando o resto do texto."""
    if not text:
        return text or ""
    return _RE.sub("***", text)

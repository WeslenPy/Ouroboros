import re
import unicodedata

_SPACES = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Minúsculas, sem acento, espaços colapsados. Usado em busca e resolução de entidades."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return _SPACES.sub(" ", stripped).strip().lower()

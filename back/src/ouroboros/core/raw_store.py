import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from ouroboros.core.settings import get_settings


@dataclass(frozen=True, slots=True)
class RawRecord:
    """Resposta bruta de uma fonte, guardada como veio para permitir reprocessamento e auditoria."""

    fonte: str
    recurso: str
    particao: str
    url: str
    payload: bytes
    content_type: str = "application/json"
    obtido_em: datetime = field(default_factory=lambda: datetime.now(UTC))
    # calculado uma vez: transforms usam o hash em cada linha e o payload pode ter dezenas de MB
    sha256: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "sha256", hashlib.sha256(self.payload).hexdigest())


_EXT = {"application/json": "json", "text/csv": "csv", "application/zip": "zip"}


class RawStore:
    """Landing de arquivos brutos em disco: <raw_dir>/<fonte>/<recurso>/<particao>/<sha256>.<ext>.

    Mesmo conteúdo = mesmo arquivo (idempotente). Trocar por S3/MinIO quando o volume pedir.
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or get_settings().raw_dir

    def path_for(self, record: RawRecord) -> Path:
        ext = _EXT.get(record.content_type.split(";")[0], "bin")
        return (
            self.root / record.fonte / record.recurso / record.particao / f"{record.sha256}.{ext}"
        )

    def save(self, record: RawRecord) -> Path:
        path = self.path_for(record)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_bytes(record.payload)
            tmp.replace(path)
        return path

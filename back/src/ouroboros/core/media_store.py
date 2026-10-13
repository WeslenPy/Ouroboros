"""Armazenamento de imagens endereçado por conteúdo: <fotos_dir>/<sha[:2]>/<sha>.<ext>.

Mesma imagem vinda de fontes diferentes vira um arquivo só. Nome derivado do hash: servir
o arquivo não depende de nada que o cliente controle além de um id validado.
"""

import hashlib
import io
import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from ouroboros.core.settings import get_settings

_FORMATOS = {
    "JPEG": ("jpg", "image/jpeg"),
    "PNG": ("png", "image/png"),
    "WEBP": ("webp", "image/webp"),
}
_SHA = re.compile(r"^[0-9a-f]{64}$")


class ImagemInvalida(ValueError):
    pass


@dataclass(frozen=True)
class Imagem:
    sha256: str
    extensao: str
    content_type: str
    tamanho_bytes: int
    largura: int
    altura: int


def inspecionar(data: bytes) -> Imagem:
    """Valida que os bytes são uma imagem suportada e extrai formato e dimensões."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.verify()
            formato, (largura, altura) = img.format, img.size
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise ImagemInvalida(str(exc)) from exc
    if formato not in _FORMATOS:
        raise ImagemInvalida(f"formato não suportado: {formato}")
    ext, content_type = _FORMATOS[formato]
    return Imagem(
        sha256=hashlib.sha256(data).hexdigest(),
        extensao=ext,
        content_type=content_type,
        tamanho_bytes=len(data),
        largura=largura,
        altura=altura,
    )


class MediaStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or get_settings().fotos_dir

    def path_for(self, sha256: str, extensao: str) -> Path:
        if not _SHA.match(sha256) or extensao not in {e for e, _ in _FORMATOS.values()}:
            raise ValueError("identificador de mídia inválido")
        return self.root / sha256[:2] / f"{sha256}.{extensao}"

    def save(self, data: bytes) -> Imagem:
        imagem = inspecionar(data)
        path = self.path_for(imagem.sha256, imagem.extensao)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_bytes(data)
            tmp.replace(path)
        return imagem

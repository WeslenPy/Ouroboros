from datetime import datetime

from sqlalchemy import (
    CHAR,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from ouroboros.models.base import Base


class ArquivoImagemMixin:
    """Campos do arquivo baixado para o MediaStore. Nulos quando só a URL da fonte é guardada."""

    sha256: Mapped[str | None] = mapped_column(CHAR(64))
    extensao: Mapped[str | None] = mapped_column(String(5))
    content_type: Mapped[str | None] = mapped_column(String(20))
    tamanho_bytes: Mapped[int | None] = mapped_column(Integer)
    largura: Mapped[int | None] = mapped_column(SmallInteger)
    altura: Mapped[int | None] = mapped_column(SmallInteger)

    @property
    def armazenada(self) -> bool:
        return self.sha256 is not None


class PoliticoFoto(ArquivoImagemMixin, Base):
    """Foto de um político numa fonte. Uma por (origem, id_externo).

    Quando a fonte serve a imagem por URL estável (Câmara, Senado) guarda só a URL. Quando não
    serve (TSE publica só ZIP por UF e bloqueia o link individual), o arquivo é baixado para o
    MediaStore e os campos de arquivo (sha256, extensao...) são preenchidos.

    `ano` = quando a foto valia: eleição (TSE) ou último ano de mandato (casas legislativas).
    """

    __tablename__ = "politico_foto"

    id: Mapped[int] = mapped_column(primary_key=True)
    politico_id: Mapped[int] = mapped_column(ForeignKey("politico.id", ondelete="CASCADE"))
    origem: Mapped[str] = mapped_column(String(20))
    id_externo: Mapped[str] = mapped_column(String(40))
    ano: Mapped[int | None] = mapped_column(SmallInteger)
    url_origem: Mapped[str] = mapped_column(Text)
    obtida_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("origem", "id_externo", name="uq_politico_foto_origem_id"),
        Index("ix_politico_foto_politico", "politico_id"),
    )


class PartidoLogo(ArquivoImagemMixin, Base):
    """Logo de um partido numa origem. Uma por (partido, origem).

    `wikidata`: logo oficial (P154) do item com o número TSE do partido (P4251), baixada do
    Wikimedia Commons já rasterizada (muitas são SVG). `manual`: enviada pela CLI, por URL ou
    arquivo; tem prioridade sobre a coletada. Sem arquivo, `url_origem` é servida direto.
    """

    __tablename__ = "partido_logo"

    id: Mapped[int] = mapped_column(primary_key=True)
    partido_id: Mapped[int] = mapped_column(ForeignKey("partido.id", ondelete="CASCADE"))
    origem: Mapped[str] = mapped_column(String(20))
    id_externo: Mapped[str | None] = mapped_column(String(40))  # item Wikidata (Q...)
    url_origem: Mapped[str] = mapped_column(Text)
    obtida_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("partido_id", "origem", name="uq_partido_logo_origem"),)


class RecursoRemoto(Base):
    """Validadores HTTP (ETag/Last-Modified) de arquivos grandes já processados, para GET
    condicional: o ZIP de fotos de SP do TSE tem 90 MB e quase nunca muda."""

    __tablename__ = "recurso_remoto"

    url: Mapped[str] = mapped_column(Text, primary_key=True)
    etag: Mapped[str | None] = mapped_column(String(200))
    last_modified: Mapped[str | None] = mapped_column(String(64))
    processado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

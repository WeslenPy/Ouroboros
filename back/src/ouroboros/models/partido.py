from sqlalchemy import Boolean, ForeignKey, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from ouroboros.models.base import Base, LineageMixin


class Partido(LineageMixin, Base):
    """Partido político. Sigla muda com o tempo (PMDB -> MDB); número TSE é a chave estável."""

    __tablename__ = "partido"

    id: Mapped[int] = mapped_column(primary_key=True)
    sigla: Mapped[str] = mapped_column(String(30), index=True)
    nome: Mapped[str] = mapped_column(String(200))
    numero_tse: Mapped[int | None] = mapped_column(SmallInteger, unique=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    # logo principal escolhida entre partido_logo (ver pipelines/logos.py)
    logo_id: Mapped[int | None] = mapped_column(
        ForeignKey("partido_logo.id", ondelete="SET NULL", use_alter=True)
    )

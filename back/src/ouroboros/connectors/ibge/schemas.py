"""Formato bruto da API de localidades do IBGE (servicodados.ibge.gov.br/api/v1/localidades)."""

from pydantic import BaseModel, ConfigDict, Field


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class Regiao(_Model):
    id: int
    sigla: str
    nome: str


class UF(_Model):
    id: int
    sigla: str
    nome: str
    regiao: Regiao


class Mesorregiao(_Model):
    UF: UF


class Microrregiao(_Model):
    mesorregiao: Mesorregiao


class RegiaoIntermediaria(_Model):
    UF: UF


class RegiaoImediata(_Model):
    regiao_intermediaria: RegiaoIntermediaria = Field(alias="regiao-intermediaria")


class Municipio(_Model):
    id: int
    nome: str
    # Municípios recém-criados (ex.: Boa Esperança do Norte/MT) vêm com microrregiao = null.
    microrregiao: Microrregiao | None = None
    regiao_imediata: RegiaoImediata | None = Field(default=None, alias="regiao-imediata")

    @property
    def uf(self) -> UF:
        if self.microrregiao:
            return self.microrregiao.mesorregiao.UF
        if self.regiao_imediata:
            return self.regiao_imediata.regiao_intermediaria.UF
        raise ValueError(f"município {self.id} sem UF")

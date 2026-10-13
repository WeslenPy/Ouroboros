from datetime import date
from functools import lru_cache
from pathlib import Path

from loguru import logger
from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# back/src/ouroboros/core/settings.py -> raiz do repositório (Ouroboros/)
REPO_ROOT = Path(__file__).resolve().parents[4]
DEV_HASH_KEY = "dev-inseguro-troque-em-producao"
_HOJE = date.today()
# Legislatura 57 começou em 2023; cada uma dura 4 anos
_LEGISLATURA_ATUAL = 57 + (_HOJE.year - 2023) // 4


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OUROBOROS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://ouroboros:ouroboros@localhost:5433/ouroboros"
    raw_dir: Path = REPO_ROOT / "data" / "raw"
    fotos_dir: Path = REPO_ROOT / "data" / "fotos"
    log_level: str = "INFO"

    http_timeout: float = 60.0
    http_user_agent: str = "Ouroboros/0.1 (dados abertos; +https://github.com/)"

    # Portal da Transparência exige chave (header chave-api-dados). Fica só no .env.
    transparencia_api_key: SecretStr | None = None

    # Chave do HMAC de CPF. CPF tem só 10^9 valores: hash sem chave é reversível por força bruta.
    # Trocar a chave invalida todos os cpf_hmac gravados (exige reprocessar as fontes).
    hash_key: SecretStr = SecretStr(DEV_HASH_KEY)

    # Partições padrão das ingestões (CLI e Dagster): todo o histórico publicado por cada fonte.
    # Legislatura 50 (1995) = primeira eleita em eleição com dados no TSE (1994).
    camara_legislaturas: list[int] = list(range(50, _LEGISLATURA_ATUAL + 1))
    senado_legislaturas: list[int] = list(range(50, _LEGISLATURA_ATUAL + 1))
    # CEAP/CEAPS: arquivos a partir de 2008
    despesas_anos: list[int] = list(range(2008, _HOJE.year + 1))
    # Todas as eleições (gerais e municipais) desde 1994
    tse_anos: list[int] = list(range(1994, _HOJE.year + 1, 2))
    # Fotos: só eleições gerais recentes (municipais são centenas de milhares de fotos)
    tse_fotos_anos: list[int] = [2014, 2018, 2022]
    emendas_anos: list[int] = list(range(2014, _HOJE.year + 1))
    # CPGF da Presidência no Portal; 2003-2022 vem da planilha da Casa Civil
    cpgf_anos: list[int] = list(range(2023, _HOJE.year + 1))
    # Convênios do Transferegov (ano da proposta): Siconv começou em 2008
    convenios_anos: list[int] = list(range(2008, _HOJE.year + 1))
    # ZIPs de fotos do TSE: um por UF; "BR" = candidatos a presidente
    tse_fotos_ufs: list[str] = (
        "AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO BR"
    ).split()

    api_cors_origins: list[str] = ["*"]
    api_page_max: int = 500

    @field_validator("hash_key")
    @classmethod
    def _hash_key_nao_vazia(cls, v: SecretStr) -> SecretStr:
        if len(v.get_secret_value()) < 16:
            raise ValueError("OUROBOROS_HASH_KEY precisa de pelo menos 16 caracteres")
        return v


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.hash_key.get_secret_value() == DEV_HASH_KEY:
        logger.warning("OUROBOROS_HASH_KEY não definida: usando chave de desenvolvimento")
    return settings

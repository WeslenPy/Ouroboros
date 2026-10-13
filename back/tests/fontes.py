"""Conectores reais alimentados por fixtures (sem rede). Os arquivos em tests/fixtures são recortes
de arquivos oficiais, com CPFs, títulos e nomes de pessoas físicas substituídos por fictícios."""

import io
import zipfile
from collections.abc import AsyncIterator
from pathlib import Path

from ouroboros.connectors.base import Connector
from ouroboros.connectors.camara import CamaraCeapConnector, CamaraDeputadosConnector
from ouroboros.connectors.ibge import IbgeConnector
from ouroboros.connectors.senado import SenadoCeapsConnector, SenadoSenadoresConnector
from ouroboros.connectors.transparencia import TransparenciaEmendasConnector
from ouroboros.connectors.tse import TseCandidatosConnector
from ouroboros.core.raw_store import RawRecord

FIXTURES = Path(__file__).parent / "fixtures"


def zipped(path: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.write(path, path.name)
    return buf.getvalue()


def com_fixtures(cls: type[Connector], arquivos: list[tuple[str, bytes]]) -> Connector:
    class _Fixture(cls):  # type: ignore[valid-type, misc]
        async def extract(self, particao: str) -> AsyncIterator[RawRecord]:
            for recurso, payload in arquivos:
                yield RawRecord(
                    fonte=self.fonte,
                    recurso=recurso,
                    particao=particao,
                    url=f"fixture://{self.fonte}/{recurso}",
                    payload=payload,
                )

    return _Fixture()


def _b(*parts: str) -> bytes:
    return FIXTURES.joinpath(*parts).read_bytes()


def ibge() -> Connector:
    return com_fixtures(
        IbgeConnector,
        [("estados", _b("ibge", "estados.json")), ("municipios", _b("ibge", "municipios.json"))],
    )


def camara_deputados() -> Connector:
    return com_fixtures(
        CamaraDeputadosConnector,
        [
            ("legislatura", _b("camara", "legislatura_57.json")),
            ("deputados", _b("camara", "deputados_57_p1.json")),
            ("deputados_csv", _b("camara", "deputados.csv")),
        ],
    )


def camara_ceap() -> Connector:
    return com_fixtures(
        CamaraCeapConnector, [("ceap", zipped(FIXTURES / "camara" / "ceap_2024.csv"))]
    )


def senado_senadores() -> Connector:
    return com_fixtures(
        SenadoSenadoresConnector,
        [
            ("lista", _b("senado", "lista_57.json")),
            ("senador", _b("senado", "senador_5411.json")),
        ],
    )


def senado_ceaps() -> Connector:
    return com_fixtures(SenadoCeapsConnector, [("ceaps", _b("senado", "ceaps_2024.csv"))])


def tse_candidatos() -> Connector:
    return com_fixtures(
        TseCandidatosConnector,
        [
            ("consulta_cand", zipped(FIXTURES / "tse" / "consulta_cand_2022_BRASIL.csv")),
            # motivos fictícios: só exercitam a junção por SQ_CANDIDATO
            ("motivo_cassacao", zipped(FIXTURES / "tse" / "motivo_cassacao_2022_BRASIL.csv")),
        ],
    )


def transparencia_emendas() -> Connector:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for nome in ("EmendasParlamentares.csv", "EmendasParlamentares_PorFavorecido.csv"):
            zf.write(FIXTURES / "transparencia" / nome, nome)
    return com_fixtures(TransparenciaEmendasConnector, [("emendas_zip", buf.getvalue())])

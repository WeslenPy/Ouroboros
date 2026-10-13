"""Transform da Presidência com dados fictícios no formato das fontes (sem rede)."""

import io
import zipfile
from datetime import date
from decimal import Decimal

from ouroboros.canonical import GastoPresidenciaRow, MandatoRow, PessoaRow
from ouroboros.connectors.presidencia.connector import (
    PRESIDENTES,
    CartaoHistoricoConnector,
    CpgfPresidenciaConnector,
    PresidentesConnector,
    decodificar,
)
from ouroboros.core.raw_store import RawRecord

# Formato da planilha da Casa Civil: notas antes do cabeçalho, glossário depois, CNPJ em
# notação científica, mistura de cp850 (80 C7 = ÇÃ) e latin-1 (C3 = Ã).
HISTORICO = (
    b"Esclarecimentos;;;;;;;;;\r\n"
    b"Diferen\x87as de valor;;;;;;;;;\r\n"
    b"DATA PGTO;CPF SERVIDOR;CPF/CNPJ FORNECEDOR;NOME FORNECEDOR; VALOR ;TIPO;"
    b"SUBELEMENTO DE DESPESA;CDIC;;\r\n"
    b"03/01/2003;***.111.222-**;3,13492E+13;HOTEL FICT\xd6CIO;R$ 2.590,00;C;HOSPEDAGENS;"
    b"00200.1/2003-63.R.08;;\r\n"
    b"15/03/2019;***.333.444-**;12345678901;JOAO FICTICIO;R$ 300,00;D;"
    b"LOCACAO DE MEIOS DE TRANSPORTE;00200.2/2019-11.R.08;;\r\n"
    b"20/03/2019;***.333.444-**;07575651000159;S\xc3O PEDRO ALIMENTA\x80\xc7O LTDA;"
    b"-R$ 8,33;C;GENEROS DE ALIMENTA\xc7\xc7O;00200.3/2019-11.R.08;;\r\n"
    b";;;;;;;;;\r\n"
    b"DATA PGTO;Data do pagamento;;;;;;;;\r\n"
)

CPGF_CSV = (
    '"CÓDIGO ÓRGÃO SUPERIOR";"NOME ÓRGÃO SUPERIOR";"CÓDIGO ÓRGÃO";"NOME ÓRGÃO";'
    '"CÓDIGO UNIDADE GESTORA";"NOME UNIDADE GESTORA";"ANO EXTRATO";"MÊS EXTRATO";'
    '"CPF PORTADOR";"NOME PORTADOR";"CNPJ OU CPF FAVORECIDO";"NOME FAVORECIDO";"TRANSAÇÃO";'
    '"DATA TRANSAÇÃO";"VALOR TRANSAÇÃO"\r\n'
    '"20000";"Presidência da República";"20101";"Presidência da República";"110001";'
    '"SECRETARIA DE ADMINISTRACAO/PR";"2024";"01";"";"Sigiloso";"-11";"Sigiloso";'
    '"Informações protegidas por sigilo";"";"27251,70"\r\n'
    '"20000";"Presidência da República";"20101";"Presidência da República";"110322";'
    '"GABINETE DE SEGURANCA INSTITUCIONAL/PR";"2024";"01";"***.555.666-**";"MARIA FICTICIA";'
    '"07575651000159";"EMPRESA FICTICIA LTDA";"SAQUE CASH/ATM BB";"02/12/2023";"500,00"\r\n'
    '"20000";"Presidência da República";"20101";"Presidência da República";"110538";'
    '"AGENCIA BRASILEIRA DE INTELIGENCIA";"2024";"01";"***.777.888-**";"JOSE FICTICIO";'
    '"07575651000159";"EMPRESA FICTICIA LTDA";"COMPRA A/V - R$ - APRES";"03/12/2023";"90,00"\r\n'
    '"63000";"Advocacia-Geral da União";"63000";"AGU";"110161";"SUPERINTENDENCIA";"2024";"01";'
    '"***.999.000-**";"ANA FICTICIA";"07575651000159";"EMPRESA FICTICIA LTDA";'
    '"COMPRA A/V - R$ - APRES";"06/12/2023";"90,00"\r\n'
).encode("latin-1")


def _record(fonte: str, payload: bytes, particao: str) -> RawRecord:
    return RawRecord(
        fonte=fonte, recurso="r", particao=particao, url="fixture://x", payload=payload
    )


def _zip(nome: str, data: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(nome, data)
    return buf.getvalue()


def test_decodificar_mistura_cp850_e_latin1():
    assert decodificar(b"S\xc7O") == "SÃO"  # cp850
    assert decodificar(b"S\xc3O") == "SÃO"  # latin-1
    assert decodificar(b"LOCA\x80\xc7O") == "LOCAÇÃO"
    assert decodificar(b"ALIMENTA\xc7\xc7O") == "ALIMENTAÇÃO"  # Ç latin-1 + Ã cp850
    assert decodificar(b"FICT\xd6CIO") == "FICTÍCIO"


def test_historico_casa_civil():
    rows = CartaoHistoricoConnector().transform([_record("casacivil", HISTORICO, "2003-2022")])
    assert len(rows) == 3  # cabeçalho, notas e glossário ficam fora
    hotel, saque, estorno = rows
    assert isinstance(hotel, GastoPresidenciaRow)
    assert hotel.data == date(2003, 1, 3) and hotel.valor == Decimal("2590.00")
    assert hotel.favorecido_documento is None  # CNPJ perdido em notação científica
    assert hotel.favorecido_nome == "HOTEL FICTÍCIO"
    assert hotel.sigiloso and hotel.classificacao.startswith("00200")
    assert saque.tipo == "saque"
    assert saque.favorecido_documento == "***.456.789-**"  # CPF de terceiro sai mascarado
    assert estorno.valor == Decimal("-8.33")
    assert estorno.favorecido_documento == "07575651000159"
    assert estorno.favorecido_nome == "SÃO PEDRO ALIMENTAÇÃO LTDA"
    assert estorno.categoria == "GENEROS DE ALIMENTAÇÃO"


def test_cpgf_portal_so_presidencia_sem_abin():
    payload = _zip("202401_CPGF.csv", CPGF_CSV)
    rows = CpgfPresidenciaConnector().transform([_record("transparencia", payload, "2024")])
    assert len(rows) == 2  # AGU e ABIN fora
    sigiloso, gsi = rows
    assert sigiloso.sigiloso and sigiloso.data is None
    assert (sigiloso.ano, sigiloso.mes) == (2024, 1)
    assert sigiloso.favorecido_documento is None and sigiloso.portador is None
    assert sigiloso.valor == Decimal("27251.70")
    assert gsi.tipo == "saque" and not gsi.sigiloso
    assert gsi.data == date(2023, 12, 2)  # data da compra; ano/mes = extrato
    assert gsi.unidade_gestora == "GABINETE DE SEGURANCA INSTITUCIONAL/PR"


async def test_presidentes_mandatos_sem_buraco():
    conn = PresidentesConnector()
    records = [r async for r in conn.extract("atual")]
    rows = conn.transform(records)
    pessoas = [r for r in rows if isinstance(r, PessoaRow)]
    mandatos = sorted((r for r in rows if isinstance(r, MandatoRow)), key=lambda m: m.inicio)
    assert len(pessoas) == len(PRESIDENTES)
    assert all(p.nome_civil and p.data_nascimento for p in pessoas)
    # exercício contínuo: cada mandato começa no dia seguinte ao fim do anterior
    for anterior, seguinte in zip(mandatos, mandatos[1:], strict=False):
        assert (seguinte.inicio - anterior.fim).days == 1, (anterior.id_externo, seguinte)
    assert mandatos[0].inicio == date(2003, 1, 1)
    assert all(len(m.condicao or "") <= 40 for m in mandatos)

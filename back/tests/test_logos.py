from ouroboros.pipelines.logos import LogoWikidata, PartidoAlvo, escolher_logos, ler_sparql

_PREFERIDA = "http://wikiba.se/ontology#PreferredRank"
_NORMAL = "http://wikiba.se/ontology#NormalRank"


def _binding(item, numero, arquivo, *, rank=_NORMAL, extinto=False, siglas="", rotulos=""):
    b = {
        "item": {"value": f"http://www.wikidata.org/entity/{item}"},
        "numero": {"value": str(numero)},
        "logo": {"value": f"http://commons.wikimedia.org/wiki/Special:FilePath/{arquivo}"},
        "rank": {"value": rank},
    }
    if extinto:
        b["extinto"] = {"value": "2023-11-09T00:00:00Z"}
    if siglas:
        b["siglas"] = {"value": siglas}
    if rotulos:
        b["rotulos"] = {"value": rotulos}
    return b


def _logos(*bindings) -> list[LogoWikidata]:
    return ler_sparql({"results": {"bindings": list(bindings)}})


def test_ler_sparql_decodifica_arquivo_e_nomes():
    (logo,) = _logos(
        _binding(
            "Q657089",
            13,
            "PT%20%28Brazil%29%20logo%202021.svg",
            siglas="PT",
            rotulos="Partido dos Trabalhadores",
        )
    )
    assert logo.item == "Q657089"
    assert logo.numero == 13
    assert logo.arquivo == "PT (Brazil) logo 2021.svg"
    assert logo.nomes == {"pt", "partidodostrabalhadores"}
    assert not logo.extinto and not logo.preferida


def test_ler_sparql_ignora_numero_nao_numerico():
    assert _logos(_binding("Q1", "13a", "x.png")) == []


def test_bate_por_sigla_ou_nome_sem_acento_e_espaco():
    logos = _logos(
        # sigla antiga no Wikidata (PPS), mas o rótulo bate com o nome do TSE
        _binding("Q2598527", 23, "Cidadania.png", siglas="PPS", rotulos="Cidadania"),
        _binding("Q504000", 65, "PCdoB.svg", siglas="PCdoB"),
        _binding("Q108837483", 44, "Uniao.svg", rotulos="União Brasil"),
    )
    partidos = [
        PartidoAlvo(1, 23, "CIDADANIA", "CIDADANIA"),
        PartidoAlvo(2, 65, "PC do B", "PARTIDO COMUNISTA DO BRASIL"),
        PartidoAlvo(3, 44, "UNIÃO", "UNIÃO BRASIL"),
    ]
    escolhidas = escolher_logos(logos, partidos)
    assert {pid: lg.item for pid, lg in escolhidas.items()} == {
        1: "Q2598527",
        2: "Q504000",
        3: "Q108837483",
    }


def test_numero_reaproveitado_nao_herda_logo_de_partido_extinto():
    logos = _logos(_binding("Q1576143", 14, "PTB.png", extinto=True, siglas="PTB"))
    novo = PartidoAlvo(1, 14, "NOVO14", "PARTIDO NOVO QUATORZE")
    antigo = PartidoAlvo(2, 14, "PTB", "PARTIDO TRABALHISTA BRASILEIRO")
    assert escolher_logos(logos, [novo]) == {}
    assert escolher_logos(logos, [antigo])[2].item == "Q1576143"


def test_sem_nome_igual_nao_aceita_nem_item_ativo():
    # 25 era DEM e hoje é PRD: item ativo com o número, mas é outro partido
    logos = _logos(_binding("Q115156140", 25, "PRD.svg", siglas="PRD", rotulos="PRD"))
    assert escolher_logos(logos, [PartidoAlvo(1, 25, "DEM", "DEMOCRATAS")]) == {}


def test_alias_cobre_partido_renomeado():
    logos = _logos(
        _binding("Q429972", 33, "Mobiliza.png", siglas="MOBILIZA", rotulos="PMN|Mobiliza")
    )
    partido = PartidoAlvo(1, 33, "PMN", "PARTIDO DA MOBILIZAÇÃO NACIONAL")
    assert escolher_logos(logos, [partido])[1].item == "Q429972"


def test_prefere_item_ativo_e_logo_de_rank_preferido():
    logos = _logos(
        _binding("Q1", 22, "velho.png", extinto=True, siglas="PL"),
        _binding("Q2", 22, "b-normal.svg", siglas="PL"),
        _binding("Q2", 22, "c-preferida.svg", rank=_PREFERIDA, siglas="PL"),
    )
    escolhida = escolher_logos(logos, [PartidoAlvo(1, 22, "PL", "PARTIDO LIBERAL")])[1]
    assert (escolhida.item, escolhida.arquivo) == ("Q2", "c-preferida.svg")

# Ouroboros — back

API (FastAPI) + ingestão (Dagster) de dados públicos da política brasileira.
Plano completo das fases: ver `readme.md` na raiz.

## Rodar local

```bash
docker compose up -d db                 # Postgres em localhost:5433
cd back
cp .env.example .env                    # defina OUROBOROS_HASH_KEY (ver "Privacidade")
poetry install
poetry run alembic upgrade head
poetry run ouroboros ingest federal     # IBGE, TSE, Câmara, Senado, CEAP, CEAPS (todas as partições)
poetry run ouroboros ingest camara_ceap -p 2024   # um job, uma partição
poetry run uvicorn ouroboros.api.main:app --reload
# http://localhost:8000/docs
poetry run dagster dev                  # UI de ingestão em http://localhost:3000
```

Tudo em container: `docker compose up --build` na raiz (api :8000, dagster :3000).

Partições padrão (anos, legislaturas) ficam em `core/settings.py` e podem ser trocadas por
variáveis `OUROBOROS_*`.

## Fontes (fase 1)

| job | fonte | partição |
| --- | --- | --- |
| `ibge` | IBGE localidades | `atual` |
| `tse_candidatos` | TSE `consulta_cand_{ano}.zip` + `motivo_cassacao_{ano}.zip` | ano da eleição |
| `camara_deputados` | API Câmara v2 + `deputados.csv` | legislatura |
| `senado_senadores` | API Senado (lista + detalhe) | legislatura |
| `camara_ceap` | `Ano-{ano}.csv.zip` (cota parlamentar) | ano |
| `senado_ceaps` | `despesa_ceaps_{ano}.csv` | ano |
| `fotos_parlamentares` | URL oficial da foto (Câmara, Senado) — só valida, não baixa | `camara`, `senado` |
| `tse_fotos` | `foto_cand{ano}_{UF}_div.zip` — baixa e serve | ano da eleição |
| `partidos_logos` | Wikidata (número TSE → logo) + Wikimedia Commons — baixa e serve | `atual` |
| `transparencia_emendas` | Portal da Transparência: emendas, favorecidos e convênios | ano |
| `transferegov_especiais` | API Transferegov: transferências especiais (emendas Pix) | `atual` |
| `transferegov_convenios` | `repositorio.dados.gov.br/seges/detru` (Siconv): convênios, obras, contratos | ano da proposta |
| `transferegov_pagamentos` | `siconv_pagamento.csv.zip` (~1 GB) somado por convênio x fornecedor | `atual` |

## Endpoints

- `GET /v1/politicos?busca=&cargo=&uf=&partido=&em_exercicio=&com_mandato=`
- `GET /v1/politicos/{id}` — perfil: identificadores por fonte, mandatos, gastos por ano
- `GET /v1/politicos/{id}/mandatos | candidaturas | despesas | despesas/resumo`
- `GET /v1/despesas?ano=&mes=&verba=&uf=&categoria=&fornecedor=` e `/v1/despesas/resumo`
- `GET /v1/politicos/{id}/foto` (redireciona para a foto principal) e `/fotos` (todas)
- `GET /v1/fotos/{id}` — arquivo (fotos do TSE) ou redirecionamento para a URL oficial
- `GET /v1/partidos` e `/v1/partidos/{sigla}` trazem `logo.url`; `/v1/partidos/{sigla}/logo`
  redireciona para a logo principal e `/v1/partidos/logos/{id}` serve o arquivo
- `GET /v1/entes`, `GET /v1/fontes` (status das ingestões)
- `GET /v1/emendas/{codigo}` — emenda de ponta a ponta: destinos, favorecidos, convênios/obras e
  transferências especiais; `/v1/emendas/transferencias-especiais?politico=&municipio=&emenda=`
- `GET /v1/obras?politico=&municipio=&uf=&emenda=&fornecedor=&proponente=&situacao=&parada=`,
  `/v1/obras/resumo`, `/v1/obras/mapa` (coordenadas) e `/v1/obras/{numero}` (emendas, metas,
  desembolsos, contratos e pagamentos); grafo em `/v1/grafo/obra/{numero}`
- `GET /v1/alertas?detector=&severidade=&politico=&entidade=&ano=&score_min=` (do mais forte ao
  mais fraco), `/v1/alertas/{id}`, `/v1/alertas/detectores` (metodologia + contagens) e
  `/v1/alertas/ranking?politico=&uf=&partido=&detector=` (risco por político)

## Fotos

Resumo e perfil de político trazem `foto.url`, pronta para `<img src>`:
- Câmara/Senado: link oficial da casa (nada é armazenado aqui; um HEAD confirma que existe).
- TSE: o tribunal só publica ZIP por UF e bloqueia link individual (403), então as fotos de
  candidatos são extraídas para `data/fotos/` (endereçadas por hash) e servidas em
  `/v1/fotos/{id}` com ETag. ZIP sem mudança não é baixado de novo.

Foto principal: a mais recente (último ano de mandato ou ano da eleição); empate → foto oficial
da casa; depois maior resolução.

## Logos de partidos

O TSE não serve logos fora do navegador (403). `partidos_logos` busca no Wikidata o item com o
número TSE do partido (P4251) e a logo dele (P154), e baixa o arquivo do Commons já rasterizado
em PNG (muitas são SVG). `logo.url_origem` aponta para a página do arquivo no Commons, com
autoria e licença. Número TSE é reaproveitado (25 era DEM, hoje PRD), então o item só vale se a
sigla ou o nome do partido batem com sigla, rótulo ou alias do item. Arquivo do Commons já
baixado não é baixado de novo. Wikimedia bloqueia User-Agent sem contato (403): defina
`OUROBOROS_HTTP_USER_AGENT` com URL ou e-mail do projeto.

Partido sem logo no Wikidata (ou logo errada) recebe logo manual, que tem prioridade:

```bash
poetry run ouroboros logo PSOL --arquivo psol.png          # guarda o arquivo
poetry run ouroboros logo 50 --url https://.../psol.png    # baixa e guarda
poetry run ouroboros logo PSOL --url https://... --sem-baixar  # só valida; API redireciona
poetry run ouroboros logo PSOL --remover                   # volta para a coletada
```

Listagens são paginadas por cursor (`next_cursor`) e respondem CSV com `Accept: text/csv`
(próximo cursor no header `X-Next-Cursor`). Valores monetários saem como string decimal.

## Identidade: como uma pessoa vira um `politico`

`resolution/politicos.py` liga cada pessoa de cada fonte, nesta ordem: id já ligado → CPF (HMAC)
→ nome civil + nascimento exatos → nome aproximado com mesmo nascimento (`resolution/nomes.py`)
→ político novo. Empates viram `match_pendente`. CPF igual em dois políticos prova que são a
mesma pessoa e as linhas são fundidas (`resolution/fusao.py`). `politico_identificador.metodo`
diz como cada ligação foi feita.

Despesas que chegam antes do parlamentar ficam com `politico_id` nulo e são religadas
automaticamente quando as pessoas são carregadas — a ordem dos jobs não muda o resultado.

## Privacidade

- CPF de político é guardado só como HMAC-SHA256 com `OUROBOROS_HASH_KEY` (CPF tem 10⁹ valores;
  hash sem chave seria reversível). Trocar a chave exige reprocessar as fontes.
- CPF de fornecedor pessoa física sai mascarado (`***.456.789-**`); CNPJ sai completo.
- Fixtures de teste são recortes de arquivos oficiais com CPFs e nomes de pessoas físicas
  trocados por fictícios.

## Presidência: cartão de pagamento por presidente

| job | fonte | partição |
| --- | --- | --- |
| `presidentes` | tabela fixa dos períodos de exercício (Biblioteca da Presidência) | `atual` |
| `presidencia_cartao_historico` | planilha da Casa Civil com os gastos 2003-2022 antes sigilosos | `2003-2022` |
| `presidencia_cpgf` | CPGF mensal do Portal da Transparência, órgão Presidência (sem ABIN) | ano (2023+) |

Endpoints: `GET /v1/presidencia/presidentes` (total, saques e gasto por dia de cada mandato),
`/v1/presidencia/gastos?politico=&mandato=&ano=&categoria=&favorecido=&tipo=&sigiloso=` e
`/v1/presidencia/resumo` (mesmos filtros). O presidente de cada lançamento é quem exercia o cargo
na data (ou no dia 15 do mês do extrato, quando a data é sigilosa): Dilma até 11/05/2016, Temer
interino desde 12/05/2016. Presidentes são ligados aos políticos do TSE por nome civil + nascimento.

Cuidados com a fonte:
- A planilha da Casa Civil foi salva pelo Excel: CNPJs viraram notação científica (`3,13492E+13`)
  e se perderam; maiores favorecidos são agrupados por nome. CPF de fornecedor vem sem máscara e é
  mascarado na carga. O texto mistura cp850 e latin-1 (ver `connectors/presidencia.decodificar`).
- 2023 em diante a maior parte ainda é sigilosa no Portal (sem data, portador e fornecedor).
- Valores nominais, sem correção pela inflação. O total de 2019-2022 (R$ 41,2 mi) é o da planilha
  oficial; parte da imprensa publicou R$ 27,6 mi com outro recorte.
- O escopo 2023+ (Secretaria de Administração + GSI) pode não ser idêntico ao do sistema interno
  que gerou a planilha 2003-2022; compare mandatos antigos entre si com mais confiança.
- O Portal bloqueia (HTTP 405) depois de ~20 downloads seguidos. Meses com mais de 3 meses são
  lidos do raw store (`data/raw/transparencia/cpgf_AAAAMM/`) em vez de baixados de novo.

## Análises: indícios de fraude e desvio

`poetry run ouroboros ingest analises` (último job do grupo `federal`, ~2 min) roda os detectores
de `analises/detectores.py` sobre o que está no banco e substitui a tabela `alerta`. Cada alerta
tem `score` (0-100, força do indício), `severidade` (alta ≥ 70, média ≥ 45), métricas que o
dispararam e links das notas/emendas oficiais.

| detector | o que pega | peso |
| --- | --- | --- |
| `nota_duplicada` | mesma nota (fornecedor, número, valor, data) reembolsada 2+ vezes, sem estorno | 0,8 |
| `notas_sequenciais` | gabinete tem metade+ da numeração de notas do fornecedor: ele é o único cliente | 0,7 |
| `fornecedor_exclusivo` | 90%+ do que o fornecedor de serviço recebe da cota vem de um gabinete | 0,4 |
| `valor_atipico_nota` | nota 5x+ o percentil 99 da categoria (ex.: refeição de R$ 27 mil) | 0,5 |
| `digitos_atipicos` | primeiros dígitos fora do padrão dos pares (Benford ajustado ao mix de categorias) | 0,25 |
| `nota_extemporanea` | nota emitida 120+ dias antes do mês de reembolso | 0,25 |
| `fornecedor_favorecido` | entidade privada paga pela cota e favorecida por emenda do mesmo parlamentar | 0,8 |
| `favorecido_dependente` | ONG/empresa que recebe 80%+ das emendas de um único autor, em 2+ emendas | 0,5 |
| `emenda_fora_da_base` | 25%+ das emendas individuais pagas fora da UF do mandato | 0,3 |
| `obra_parada` | obras pagas com emendas do autor, com dinheiro liberado e sem medição há 1 ano+ | 0,4 |
| `empreiteira_concentrada` | mesma empresa contratada em 3+ convênios do autor, em 2+ municípios, e 50%+ dos contratos dela | 0,5 |
| `historico_eleitoral` | candidatura barrada por compra de voto, abuso de poder, ficha limpa... | 0,6 |

Risco do político = OU probabilístico dos detectores (`estatistica.risco`): cada detector entra
com peso × (achado mais forte + bônus pequeno por repetição). Detectores diferentes se reforçam;
muitos achados fracos do mesmo detector não viram um forte.

Calibração (contra os dados reais 2015-2026): ficam fora categorias de preço tabelado ou cobrança
impessoal (passagens, telefonia, pedágio, Correios), varejo de cupom fiscal nos testes de
numeração, aluguel/locadores, entes públicos e sociedades anônimas nos cruzamentos, CNPJs com
dígito verificador inválido. Testes que não funcionaram foram descartados: Benford puro (a cota
inteira desvia, porque combustível e refeição concentram valores em 1 e 2), z-score do total anual
por categoria (o teto da cota corta a cauda) e despesa fora do mandato (falta de cobertura das
legislaturas antigas gerava falso positivo).

**Alerta é indício, não acusação.** Exemplos de legítimo que pode aparecer: duplicata por erro de
lançamento da própria casa, prestador local que só atende um parlamentar, Santa Casa locadora do
escritório que também recebe emenda. A API repete esse aviso em `aviso`.

Próximos cruzamentos dependem das fases seguintes: sócios e data de abertura do CNPJ (Receita),
doadores de campanha (TSE), sanções (CEIS/CNEP/TCU) e convênios/Pix (Transferegov).

## Testes

```bash
poetry run pytest                                     # unitários (sem rede, sem banco)
OUROBOROS_TEST_DATABASE_URL=postgresql+asyncpg://ouroboros:ouroboros@localhost:5433/ouroboros_test \
  poetry run pytest                                   # + integração (banco descartável, recriado)
```

## Adicionar uma fonte

1. `src/ouroboros/connectors/<fonte>/`: um `HttpConnector` com `extract(particao)` (baixa,
   devolve `RawRecord` sem interpretar) e `transform(records)` (puro: brutos da partição ->
   linhas de `canonical.py`).
2. Loader em `pipelines/loaders.py` (idempotente). Pessoas passam por `resolver_pessoas`.
3. `Job` em `pipelines/jobs.py` (vira asset Dagster automaticamente).
4. Recorte de arquivo real em `tests/fixtures/<fonte>/` (sem dado pessoal) + teste do transform.

Dados brutos ficam em `data/raw/<fonte>/<recurso>/<particao>/<sha256>.<ext>`; toda linha no banco
guarda `fonte`, `fonte_url` e `raw_hash` para auditoria.

## Obras: do dinheiro da emenda à obra

O Portal da Transparência diz quanto da emenda foi pago e a quem; o Transferegov (antigo Siconv)
diz o que virou: convênio, obra, local, prazos, execução física e empresas contratadas.

```
emenda (Transparência) --codigo--> convenio_emenda --numero--> convenio --> convenio_meta (endereço)
        politico <-- politico_id --'                           |        --> convenio_desembolso
                                     municipio_codigo_ibge --> ente      --> convenio_contrato (empreiteira)
                                     proponente_cnpj --> emenda_favorecido --> convenio_fornecedor (pago)
```

- Código da emenda no Siconv = ano do programa (dígitos 6-9 de `COD_PROGRAMA_EMENDA`) +
  `NR_EMENDA`: casa com `emenda.codigo` em ~90% das emendas desde 2016. Sem par, a ligação ao
  político cai no nome parlamentar (como nas emendas).
- `emenda_convenio.numero` (Transparência) = `convenio.numero` (Siconv).
- Obra "parada" (`?parada=true`, detector `obra_parada`): tem acompanhamento físico, está abaixo de
  100% e sem medição há 180+ dias ou com vigência vencida ainda em execução.
- Coordenadas fora da caixa do Brasil são descartadas; algumas vêm com sinal trocado na fonte.
- A API do Obrasgov (`api.obrasgov.gestao.gov.br`) não entra: ~25 s por página de 100 obras
  (~15 h por carga). As obras de convênio dela já vêm no Siconv (`siconv_dados_obrasgov_geral`).

## Limitações conhecidas

- Partido no mandato: a lista da Câmara repete o deputado a cada troca de partido sem dizer a
  ordem, então `partido_sigla` só é preenchido quando não houve troca (ver `partidos`). O Senado
  só informa o partido atual, aplicado apenas ao mandato em curso.
- CEAPS identifica o senador só pelo nome; a ligação é por nome (100% em 2024).
- Despesas de liderança (ex.: `LID.GOV-CD`) não pertencem a uma pessoa e ficam sem político.
- Endpoint `/deputados/{id}/despesas` da API da Câmara estava vazio em out/2026; a CEAP vem do
  arquivo anual, conferido linha a linha contra o total do CSV oficial.

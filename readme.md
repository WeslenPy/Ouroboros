# Ouroboros

Sistema único para extrair, agregar e expor via API os dados públicos da política brasileira
(federal, estadual e municipal): mandatos, gastos de gabinete, emendas, campanhas, patrimônio,
atuação legislativa, sanções e vínculos com fornecedores — tudo ligado a cada político.

- `back/` — API FastAPI + ingestão Dagster (ver `back/README.md` para rodar)
- `data/` — arquivos brutos baixados das fontes (não versionado)
- `front/` — reservado

## Status das fases

- [x] 0. Fundação: infra, conector base, landing bruto, IBGE (entes), `/v1/entes`, `/v1/fontes`
- [x] 1. Legislativo federal: Câmara + Senado (CEAP/CEAPS) + TSE candidatos, resolução de identidade, `/v1/politicos`, `/v1/despesas`
- [ ] 2. Emendas: Portal da Transparência + Transferegov (Pix)
- [ ] 3. Dinheiro e vínculos: contas de campanha, bens, CNPJ, sanções
- [ ] 4. Atuação: proposições, votações, presença
- [ ] 5. Estados: SICONFI, ALEs, TCEs, PNCP
- [ ] 6. Municípios: TSE, SICONFI, PNCP, Querido Diário, TCEs/TCMs, câmaras das capitais
- [ ] 7. Análises: alertas e rankings

## Plano

### Contexto
Dados públicos sobre políticos estão espalhados em dezenas de fontes (Câmara, Senado, Portal da Transparência, TSE, Transferegov, SICONFI, TCEs, ALEs, câmaras municipais), cada uma com formato, IDs e cobertura próprios. Objetivo: um sistema só que extrai, normaliza, liga tudo à **pessoa** (político) e expõe API REST para ver, por político: mandatos, gastos de gabinete, emendas (destino + execução), campanha (doadores/gastos), patrimônio, atuação legislativa, sanções e vínculos com fornecedores.

Diretório `Documents/Projects/Ouroboros` está vazio (só `readme.md` vazio) — projeto greenfield.

Decisões do usuário: **Python + FastAPI**, escopo **federal + estados + municípios** (entregue em fases, federal primeiro), **só API + docs OpenAPI** (sem frontend).

### Stack
- Python 3.12, Poetry, FastAPI, pydantic-settings, loguru, SQLAlchemy 2 async + Alembic (padrão dos outros projetos do usuário).
- PostgreSQL 16 (particionamento por ano nas tabelas de fatos, `pg_trgm` + `unaccent` p/ busca por nome).
- Orquestração ETL: **Dagster** (assets particionados por ano/mês, lineage, retries, schedules).
- Raw landing: MinIO/S3 (arquivo bruto + hash, reprocessável). Transformação: polars/duckdb.
- Redis: cache de respostas + rate limit (slowapi).
- httpx async + tenacity (retry/backoff) nos conectores.
- docker-compose: postgres, redis, minio, dagster (webserver+daemon), api.

### Estrutura
```
Ouroboros/
  pyproject.toml, docker-compose.yml, .env.example, alembic/
  src/ouroboros/
    core/        settings.py, db.py, logging.py, http.py (cliente base c/ rate limit + retry)
    connectors/  camara/ senado/ transparencia/ transferegov/ tse/ siconfi/ pncp/
                 receita_cnpj/ tcu/ querido_diario/ ibge/ ales/<uf>/ tces/<uf>/ camaras_municipais/<ibge>/
                 cada um: client.py, extract.py, schemas.py (pydantic do formato bruto)
    pipelines/   assets Dagster: raw -> staging -> canônico
    models/      SQLAlchemy canônico
    resolution/  ligação de entidades (político, empresa, ente)
    api/         main.py, routers/, schemas/ (DTOs de saída), deps.py
  tests/         pytest + respx; fixtures gravadas de cada fonte
```
Cada conector implementa interface comum `Connector.extract(partition) -> Iterator[RawRecord]` + `transform(raw) -> list[CanonicalModel]`, para novos estados/municípios entrarem como plugin.

### Fontes de dados (por fase)
**Federal**
- Câmara API v2 `dadosabertos.camara.leg.br/api/v2` + arquivos bulk (deputados, CEAP/cota, proposições, votações, presença, órgãos, frentes).
- Senado `legis.senado.leg.br/dadosabertos` (senadores, matérias, votações) + CSV CEAPS (transparência do Senado).
- Portal da Transparência `api.portaldatransparencia.gov.br` (header `chave-api-dados`, respeitar limite ~90 req/min diurno; preferir download bulk de emendas): emendas parlamentares, documentos de pagamento, convênios, viagens, CEIS/CNEP/CEPIM, servidores.
- Transferegov — transferências especiais ("emendas Pix") e convênios.
- TSE `dadosabertos.tse.jus.br` (CSV bulk): candidatos, bens declarados, prestação de contas (receitas/despesas), resultados, filiação.
- Receita Federal CNPJ bulk (empresas, sócios) — liga fornecedores/doadores a pessoas.
- TCU: contas julgadas irregulares, inabilitados.

**Estados**
- SICONFI (`apidatalake.tesouro.gov.br/ords/siconfi`): RREO/RGF/DCA de estados.
- ALEs: adaptadores por UF, começando pelas que têm API/dados abertos (ALMG, ALESP, ALERJ, ALRS…); demais via scraping de verba indenizatória.
- TCEs com dados abertos; PNCP (`pncp.gov.br/api/consulta`) p/ contratos.
- TSE cobre governadores/deputados estaduais automaticamente.

**Municípios**
- TSE cobre todos prefeitos/vereadores (5.570 municípios) sem esforço extra.
- SICONFI municipal, PNCP, emendas recebidas (já vem da fase federal, por código IBGE), Querido Diário (diários oficiais).
- TCEs/TCMs com API (TCE-RS, TCE-SP, TCE-PE, TCM-BA…).
- Câmaras municipais: scrapers só para capitais inicialmente.
- IBGE localidades = tabela mestre de entes.

### Modelo canônico (principal)
- `politico` (nome, nome_civil, data_nasc, genero, cpf_hash, foto) + `politico_identificador` (fonte, id_externo: id Câmara, código Senado, SQ_CANDIDATO TSE, etc.).
- `ente` (código IBGE, esfera, UF), `partido`, `filiacao`.
- `mandato` (politico, cargo, esfera, ente, partido, inicio, fim, situação).
- `despesa_gabinete` (CEAP/CEAPS/verba indenizatória estadual/municipal: data, categoria, valor, fornecedor_cnpj_cpf, url documento).
- `emenda` (código, autor, tipo: individual/bancada/comissão/relator RP9/Pix, ano, função/subfunção, ente beneficiado, favorecido) + `emenda_execucao` (empenhado/liquidado/pago por documento).
- `campanha_receita`, `campanha_despesa`, `bem_declarado` (por eleição).
- `proposicao`, `autoria`, `votacao`, `voto`, `presenca`.
- `sancao` (CEIS/CNEP/TCU), `empresa`, `socio`.
- `contrato` (PNCP/TCE), `remuneracao`, `viagem`.
- Toda linha factual: `fonte`, `fonte_url`, `raw_hash`, `ingerido_em` (lineage auditável).

### Resolução de entidades (`resolution/`)
- Chave forte quando existe: IDs cruzados oficiais (Câmara expõe dados que batem com TSE; CPF quando disponível → guardar só hash).
- Fallback: nome normalizado (unaccent, lower) + data nascimento + UF + cargo; score com rapidfuzz; abaixo do limiar vai para tabela `match_pendente` revisável.
- Empresas por CNPJ raiz; sócios por nome + CPF mascarado da Receita.

### API (FastAPI, `/v1`)
- `GET /politicos?busca=&cargo=&uf=&partido=&esfera=` ; `GET /politicos/{id}` (resumo agregado: totais gasto gabinete, emendas pagas, receita campanha, patrimônio por eleição, presença %).
- `GET /politicos/{id}/mandatos|despesas|emendas|campanhas|patrimonio|votos|proposicoes|sancoes`.
- `GET /despesas`, `GET /emendas` (filtros: ano, autor, ente_destino, tipo, favorecido).
- `GET /entes/{ibge}` + `/emendas-recebidas`, `/financas` (SICONFI), `/politicos`.
- `GET /empresas/{cnpj}` → quem pagou (gabinetes, emendas, contratos), doações feitas, sócios, sanções.
- `GET /rankings/{metrica}` e `GET /comparar?ids=`.
- `GET /fontes` (status/última atualização de cada fonte).
- Paginação cursor, export CSV (`Accept: text/csv`), OpenAPI/Swagger automático, API key opcional + rate limit, cache Redis.

### Fases
0. **Fundação**: repo, Poetry, docker-compose, settings, base HTTP client, Alembic, tabelas `ente`/`partido`, carga IBGE.
1. **Legislativo federal**: Câmara + Senado (parlamentares, mandatos, CEAP/CEAPS) + TSE candidatos → resolução de identidade. API `/politicos` e `/despesas`. ← primeiro entregável usável.
2. **Emendas**: Portal Transparência + Transferegov (Pix) + execução; ligação a autor e ente beneficiado.
3. **Dinheiro e vínculos**: TSE contas de campanha + bens; CNPJ Receita; sanções CEIS/CNEP/TCU; `/empresas`.
4. **Atuação**: proposições, votações, votos, presença.
5. **Estados**: SICONFI, framework de adaptadores ALE (prioriza UFs com API), TCEs, PNCP.
6. **Municípios**: TSE prefeitos/vereadores, SICONFI municipal, PNCP, Querido Diário, TCEs/TCMs, scrapers câmaras das capitais.
7. **Análises**: alertas (fornecedor de gabinete = doador de campanha, sócio parente, emenda para ente governado por aliado, gasto fora do padrão por z-score por categoria), rankings.

### Cuidados
- LGPD: só dados de agentes públicos em função pública; nunca expor CPF completo de terceiros (hash/mascarado).
- Alertas são indicativos, não acusação — campo `metodologia` + disclaimer em toda resposta analítica.
- Cada fonte quebra/muda: testes de contrato com fixtures gravadas + monitoramento de falhas no Dagster.
- Chave da API do Portal da Transparência e credenciais só em `.env`, nunca no código.

### Verificação
- `docker compose up` sobe tudo; `alembic upgrade head`.
- Materializar no Dagster: `ibge_entes`, `camara_deputados`, `camara_ceap[2024]`, `tse_candidatos[2022]`.
- `pytest` (unit de transform + resolução, contrato de conectores com respx).
- Conferir: `GET /v1/politicos?busca=<deputado>` e total de `GET /v1/politicos/{id}/despesas?ano=2024` bate com o total exibido no site da Câmara para o mesmo deputado; idem emendas pagas vs Portal da Transparência.
- Swagger em `/docs` lista todos endpoints.

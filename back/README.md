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
| `tse_candidatos` | TSE `consulta_cand_{ano}.zip` | ano da eleição |
| `camara_deputados` | API Câmara v2 + `deputados.csv` | legislatura |
| `senado_senadores` | API Senado (lista + detalhe) | legislatura |
| `camara_ceap` | `Ano-{ano}.csv.zip` (cota parlamentar) | ano |
| `senado_ceaps` | `despesa_ceaps_{ano}.csv` | ano |
| `fotos_parlamentares` | URL oficial da foto (Câmara, Senado) — só valida, não baixa | `camara`, `senado` |
| `tse_fotos` | `foto_cand{ano}_{UF}_div.zip` — baixa e serve | ano da eleição |

## Endpoints

- `GET /v1/politicos?busca=&cargo=&uf=&partido=&em_exercicio=&com_mandato=`
- `GET /v1/politicos/{id}` — perfil: identificadores por fonte, mandatos, gastos por ano
- `GET /v1/politicos/{id}/mandatos | candidaturas | despesas | despesas/resumo`
- `GET /v1/despesas?ano=&mes=&verba=&uf=&categoria=&fornecedor=` e `/v1/despesas/resumo`
- `GET /v1/politicos/{id}/foto` (redireciona para a foto principal) e `/fotos` (todas)
- `GET /v1/fotos/{id}` — arquivo (fotos do TSE) ou redirecionamento para a URL oficial
- `GET /v1/entes`, `GET /v1/fontes` (status das ingestões)

## Fotos

Resumo e perfil de político trazem `foto.url`, pronta para `<img src>`:
- Câmara/Senado: link oficial da casa (nada é armazenado aqui; um HEAD confirma que existe).
- TSE: o tribunal só publica ZIP por UF e bloqueia link individual (403), então as fotos de
  candidatos são extraídas para `data/fotos/` (endereçadas por hash) e servidas em
  `/v1/fotos/{id}` com ETag. ZIP sem mudança não é baixado de novo.

Foto principal: a mais recente (último ano de mandato ou ano da eleição); empate → foto oficial
da casa; depois maior resolução.

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

## Limitações conhecidas

- Partido no mandato: a lista da Câmara repete o deputado a cada troca de partido sem dizer a
  ordem, então `partido_sigla` só é preenchido quando não houve troca (ver `partidos`). O Senado
  só informa o partido atual, aplicado apenas ao mandato em curso.
- CEAPS identifica o senador só pelo nome; a ligação é por nome (100% em 2024).
- Despesas de liderança (ex.: `LID.GOV-CD`) não pertencem a uma pessoa e ficam sem político.
- Endpoint `/deputados/{id}/despesas` da API da Câmara estava vazio em out/2026; a CEAP vem do
  arquivo anual, conferido linha a linha contra o total do CSV oficial.

"""Definições Dagster: `dagster dev` (em back/) sobe UI com os assets de ingestão.

Cada job vira um asset; jobs com mais de uma partição (anos, legislaturas) viram asset
particionado, materializável por partição.
"""

import dagster as dg

from ouroboros.core.logging import setup_logging
from ouroboros.pipelines.jobs import JOBS, Job, run_sync

setup_logging()

GRUPO = {
    "ibge": "referencia",
    "tse_candidatos": "eleicoes",
    "camara_deputados": "parlamentares",
    "senado_senadores": "parlamentares",
    "camara_ceap": "despesas",
    "senado_ceaps": "despesas",
    "transparencia_emendas": "emendas",
    "transferegov_especiais": "emendas",
    "transferegov_convenios": "obras",
    "transferegov_pagamentos": "obras",
    "fotos_parlamentares": "fotos",
    "tse_fotos": "fotos",
    "partidos_logos": "fotos",
    "presidentes": "presidencia",
    "presidencia_cartao_historico": "presidencia",
    "presidencia_cpgf": "presidencia",
    "analises": "analises",
}


def _asset(job: Job) -> dg.AssetsDefinition:
    particoes = list(job.particoes())
    partitions_def = dg.StaticPartitionsDefinition(particoes) if particoes != ["atual"] else None

    @dg.asset(
        name=job.nome,
        group_name=GRUPO.get(job.nome, "outros"),
        partitions_def=partitions_def,
        description=job.descricao,
    )
    def _materialize(context: dg.AssetExecutionContext) -> dg.MaterializeResult:
        particao = [context.partition_key] if context.has_partition_key else None
        registros = run_sync(job, particao)
        context.log.info(f"{registros} registros")
        return dg.MaterializeResult(metadata={"registros": registros})

    return _materialize


assets = [_asset(job) for job in JOBS.values()]

referencia_job = dg.define_asset_job("referencia", selection=dg.AssetSelection.groups("referencia"))

defs = dg.Definitions(
    assets=assets,
    jobs=[referencia_job],
    schedules=[
        dg.ScheduleDefinition(job=referencia_job, cron_schedule="0 3 1 * *"),  # mensal
    ],
)

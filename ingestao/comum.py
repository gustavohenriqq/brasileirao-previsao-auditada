"""Peças comuns da ingestão: configuração, download com cache e carga no raw.

Regra da camada raw: tudo em texto, sem casting. O casting fica no staging do
dbt, versionado e testável. As únicas colunas que não vêm da fonte são os
metadados da carga (_arquivo, _sha256, _carregado_em).
"""
from __future__ import annotations

import csv
import hashlib
import io
import os
import time
from pathlib import Path

import psycopg2
import requests
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
BRUTOS = RAIZ / "dados" / "brutos"

load_dotenv(RAIZ / ".env")

TEMPORADAS = range(2003, 2026)  # 2003 a 2025, a base histórica da Fase 0

USER_AGENT = "projeto-brasileirao/0.1 (estudo, github.com/gustavohenriqq)"


def conectar():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5433"),
        dbname=os.getenv("POSTGRES_DB", "brasileirao"),
        user=os.getenv("POSTGRES_USER", "brasileirao"),
        password=os.getenv("POSTGRES_PASSWORD", "brasileirao"),
    )


def baixar(url: str, destino: Path, *, headers: dict | None = None,
           refazer: bool = False, pausa: float = 0.0) -> Path:
    """Baixa `url` para `destino`, reaproveitando o arquivo se ele já existe.

    O cache evita bater de novo na fonte a cada execução. `refazer=True`
    força o download (use quando a fonte publicar correções).
    """
    if destino.exists() and not refazer:
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    cab = {"User-Agent": USER_AGENT, **(headers or {})}
    for tentativa in range(3):
        resp = requests.get(url, headers=cab, timeout=60)
        if resp.status_code == 429:
            time.sleep(60)
            continue
        resp.raise_for_status()
        destino.write_bytes(resp.content)
        if pausa:
            time.sleep(pausa)
        return destino
    raise RuntimeError(f"Limite de requisições estourado em {url}")


def sha256(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def carregar_raw(tabela: str, colunas: list[str], linhas: list[dict]) -> int:
    """Recria raw.<tabela> com todas as colunas em texto e carrega por COPY.

    Carga full e transacional: ou a tabela inteira é trocada, ou nada muda.
    """
    todas = colunas + ["_arquivo", "_sha256"]
    defs = ", ".join(f'"{c}" text' for c in todas)
    buf = io.StringIO()
    escritor = csv.writer(buf, lineterminator="\n")
    for linha in linhas:
        escritor.writerow(
            [None if linha.get(c) in (None, "") else str(linha[c]) for c in todas]
        )
    buf.seek(0)
    with conectar() as con, con.cursor() as cur:
        cur.execute("create schema if not exists raw")
        cur.execute(f"drop table if exists raw.{tabela}")
        cur.execute(
            f"create table raw.{tabela} ({defs}, "
            "_carregado_em timestamptz not null default now())"
        )
        lista = ", ".join(f'"{c}"' for c in todas)
        cur.copy_expert(
            f"copy raw.{tabela} ({lista}) from stdin with (format csv)", buf
        )
    return len(linhas)

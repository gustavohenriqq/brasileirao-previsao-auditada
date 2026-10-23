"""Coletores de cada fonte. Cada função baixa (com cache), lê e devolve as
linhas no formato da origem, só com nomes de coluna em snake_case.

Nenhuma fonte usa raspagem de HTML: são arquivos publicados (CSV, JSON, TXT)
ou APIs JSON. Licença e limites de cada uma estão em docs/fontes.md.
"""
from __future__ import annotations

import csv
import io
import json
import os
import re

from .comum import BRUTOS, TEMPORADAS, baixar, sha256

# ---------------------------------------------------------------------------
# 1. adaoduque/Brasileirao_Dataset (GitHub): a espinha da base, 2003 a 2025.
#    CSV consolidado para 2003 a 2024 (datas dd/mm/aaaa, id estável) e o JSON
#    da temporada para 2025, que ainda não entrou no CSV.
# ---------------------------------------------------------------------------
ADAODUQUE = "https://raw.githubusercontent.com/adaoduque/Brasileirao_Dataset/master"

ADAODUQUE_COLS = [
    "id", "temporada_arquivo", "rodada", "data", "hora", "mandante", "visitante",
    "placar_mandante", "placar_visitante", "arena", "uf_mandante", "uf_visitante",
]


def adaoduque() -> tuple[list[str], list[dict]]:
    pasta = BRUTOS / "adaoduque"
    linhas: list[dict] = []

    arq = baixar(f"{ADAODUQUE}/campeonato-brasileiro-full.csv",
                 pasta / "campeonato-brasileiro-full.csv")
    hash_ = sha256(arq)
    with arq.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            linhas.append({
                "id": r["ID"], "temporada_arquivo": None, "rodada": r["rodata"],
                "data": r["data"], "hora": r["hora"], "mandante": r["mandante"],
                "visitante": r["visitante"], "placar_mandante": r["mandante_Placar"],
                "placar_visitante": r["visitante_Placar"], "arena": r["arena"].strip(),
                "uf_mandante": r["mandante_Estado"], "uf_visitante": r["visitante_Estado"],
                "_arquivo": arq.name, "_sha256": hash_,
            })

    # 2025 só existe no JSON por temporada. A temporada vem do nome do arquivo.
    arq = baixar(f"{ADAODUQUE}/data/brasileirao-2025.json", pasta / "brasileirao-2025.json")
    hash_ = sha256(arq)
    dados = json.loads(arq.read_text(encoding="utf-8"))
    for rodada, jogos in dados.items():
        for j in jogos:
            linhas.append({
                "id": None, "temporada_arquivo": "2025", "rodada": rodada,
                "data": j["date"], "hora": j["hour"], "mandante": j["clubs"]["home"],
                "visitante": j["clubs"]["away"], "placar_mandante": j["goals"]["home"],
                "placar_visitante": j["goals"]["away"], "arena": j.get("stadium"),
                "uf_mandante": None, "uf_visitante": None,
                "_arquivo": arq.name, "_sha256": hash_,
            })
    return ADAODUQUE_COLS, linhas


# ---------------------------------------------------------------------------
# 2. Mendeley Data "Brazilian Championship A-Series" (CC BY 4.0), 2003 a 2019.
#    Única fonte de conferência para 2003 a 2005. ROUND aqui é o turno (1 ou 2).
# ---------------------------------------------------------------------------
MENDELEY = ("https://data.mendeley.com/public-files/datasets/thsvj4sycn/files/"
            "76756f75-6f29-4e7b-949c-e04f731c5346/file_downloaded")

MENDELEY_COLS = ["turno", "data", "hora", "mandante", "placar", "visitante"]


def mendeley() -> tuple[list[str], list[dict]]:
    arq = baixar(MENDELEY, BRUTOS / "mendeley" / "matches-2003-2019.txt")
    hash_ = sha256(arq)
    texto = arq.read_bytes().decode("latin-1")
    leitor = csv.reader(io.StringIO(texto), delimiter=";")
    next(leitor)  # cabeçalho: #ROUND;DATE;HOUR;HOME-TEAM;SCORE;AWAY-TEAM
    linhas = [
        dict(zip(MENDELEY_COLS, r), _arquivo=arq.name, _sha256=hash_)
        for r in leitor if r
    ]
    return MENDELEY_COLS, linhas


# ---------------------------------------------------------------------------
# 3. football-data.co.uk, arquivo BRA.csv: 2012 em diante, com odds de
#    fechamento. Sem rodada.
# ---------------------------------------------------------------------------
FDCOUK = "https://www.football-data.co.uk/new/BRA.csv"


def fdcouk() -> tuple[list[str], list[dict]]:
    arq = baixar(FDCOUK, BRUTOS / "football-data-co-uk" / "BRA.csv")
    hash_ = sha256(arq)
    with arq.open(encoding="utf-8-sig") as f:
        leitor = csv.DictReader(f)
        cols = [c.lower() for c in leitor.fieldnames]
        linhas = [
            {**{k.lower(): v for k, v in r.items()}, "_arquivo": arq.name, "_sha256": hash_}
            for r in leitor
        ]
    return cols, linhas


# ---------------------------------------------------------------------------
# 4. ESPN (API JSON pública, não documentada, sem chave): 2006 em diante.
#    Traz o público pagante, que interessa à Fase 1. `dates=AAAA` devolve o
#    ano civil; a temporada vem do campo season de cada jogo (2020 foi até 2021).
# ---------------------------------------------------------------------------
ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer/bra.1/scoreboard"

ESPN_COLS = [
    "id", "temporada", "data_utc", "status", "mandante", "visitante",
    "placar_mandante", "placar_visitante", "publico", "estadio", "cidade",
]


def espn() -> tuple[list[str], list[dict]]:
    pasta = BRUTOS / "espn"
    linhas: list[dict] = []
    vistos: set[str] = set()
    for ano in range(2006, max(TEMPORADAS) + 2):  # +1 ano civil: 2020 terminou em 2021
        arq = baixar(f"{ESPN}?dates={ano}&limit=1000", pasta / f"{ano}.json", pausa=0.5)
        hash_ = sha256(arq)
        for e in json.loads(arq.read_text(encoding="utf-8")).get("events", []):
            temporada = e.get("season", {}).get("year")
            if temporada not in TEMPORADAS or e["id"] in vistos:
                continue
            vistos.add(e["id"])
            c = e["competitions"][0]
            lado = {t["homeAway"]: t for t in c["competitors"]}
            venue = c.get("venue") or {}
            linhas.append({
                "id": e["id"], "temporada": temporada, "data_utc": e["date"],
                "status": c["status"]["type"]["name"],
                "mandante": lado["home"]["team"]["displayName"],
                "visitante": lado["away"]["team"]["displayName"],
                "placar_mandante": lado["home"].get("score"),
                "placar_visitante": lado["away"].get("score"),
                "publico": c.get("attendance"),
                "estadio": venue.get("fullName"),
                "cidade": (venue.get("address") or {}).get("city"),
                "_arquivo": arq.name, "_sha256": hash_,
            })
    return ESPN_COLS, linhas


# ---------------------------------------------------------------------------
# 5. openfootball/brazil (CC0, domínio público): 2018 em diante, com rodada.
#    Formato texto Football.TXT; o parser está em parse_openfootball.
# ---------------------------------------------------------------------------
OPENFOOTBALL = "https://raw.githubusercontent.com/openfootball/brazil/master/brazil"

OPENFOOTBALL_COLS = [
    "temporada", "rodada", "data", "hora", "mandante", "visitante",
    "placar_mandante", "placar_visitante", "linha_original",
]

_MESES = {m: i for i, m in enumerate(
    "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), start=1)}
_RE_RODADA = re.compile(r"^\W*Matchday\s+(\d+)")
_RE_DATA = re.compile(r"^\s{1,3}\w{3}\s+(\w{3})\s+(\d{1,2})(?:\s+(\d{4}))?\s*$")
_RE_JOGO = re.compile(
    r"^\s+(?:(\d{1,2}[:.]\d{2})\s+)?(.+?)\s+v\s+(.+?)\s+(\d+)-(\d+)(?:\s+\(.*\))?\s*$"
)
_RE_JOGO_SEM_PLACAR = re.compile(r"^\s+(?:(\d{1,2}[:.]\d{2})\s+)?(.+?)\s+v\s+(.+?)\s*$")


def parse_openfootball(texto: str, temporada: int) -> list[dict]:
    """Lê um arquivo Football.TXT. Data e hora valem para as linhas seguintes
    até aparecer outra; o ano, quando omitido, é o do último ano visto."""
    jogos: list[dict] = []
    rodada = data = hora = None
    ano = temporada
    for linha in texto.splitlines():
        if not linha.strip() or linha.lstrip().startswith(("#", "=")):
            continue
        if m := _RE_RODADA.match(linha):
            rodada = int(m.group(1))
            continue
        if m := _RE_DATA.match(linha):
            if m.group(3):
                ano = int(m.group(3))
            data = f"{ano:04d}-{_MESES[m.group(1)]:02d}-{int(m.group(2)):02d}"
            hora = None
            continue
        if m := _RE_JOGO.match(linha):
            hora = m.group(1) or hora
            jogos.append({
                "temporada": temporada, "rodada": rodada, "data": data, "hora": hora,
                "mandante": m.group(2).strip(), "visitante": m.group(3).strip(),
                "placar_mandante": m.group(4), "placar_visitante": m.group(5),
                "linha_original": linha.strip(),
            })
            continue
        if m := _RE_JOGO_SEM_PLACAR.match(linha):
            # Jogo sem placar (não realizado ou ainda por jogar): fica no raw
            # com placar nulo, para o staging decidir.
            hora = m.group(1) or hora
            jogos.append({
                "temporada": temporada, "rodada": rodada, "data": data, "hora": hora,
                "mandante": m.group(2).strip(), "visitante": m.group(3).strip(),
                "placar_mandante": None, "placar_visitante": None,
                "linha_original": linha.strip(),
            })
    return jogos


def openfootball() -> tuple[list[str], list[dict]]:
    linhas: list[dict] = []
    for temporada in range(2018, max(TEMPORADAS) + 1):
        nome = f"{temporada}_br1.txt"
        arq = baixar(f"{OPENFOOTBALL}/{nome}", BRUTOS / "openfootball" / nome)
        hash_ = sha256(arq)
        for j in parse_openfootball(arq.read_text(encoding="utf-8"), temporada):
            linhas.append({**j, "_arquivo": nome, "_sha256": hash_})
    return OPENFOOTBALL_COLS, linhas


# ---------------------------------------------------------------------------
# 6. football-data.org (API v4, plano gratuito): Série A (código BSA).
#    Testado em 23/10/2026: o plano gratuito libera 2023 a 2026 e devolve 403
#    para 2022 e antes. 10 chamadas por minuto. Precisa de chave no .env.
# ---------------------------------------------------------------------------
FDORG = "https://api.football-data.org/v4/competitions/BSA/matches"
FDORG_TEMPORADAS = range(2023, max(TEMPORADAS) + 1)

FDORG_COLS = [
    "id", "temporada", "rodada", "data_utc", "status", "mandante", "mandante_curto",
    "visitante", "visitante_curto", "placar_mandante", "placar_visitante",
]


def fdorg() -> tuple[list[str], list[dict]] | None:
    chave = os.getenv("FOOTBALL_DATA_API_KEY")
    if not chave:
        print("  football-data.org: sem FOOTBALL_DATA_API_KEY no .env, fonte pulada")
        return None
    linhas: list[dict] = []
    for temporada in FDORG_TEMPORADAS:
        arq = baixar(f"{FDORG}?season={temporada}",
                     BRUTOS / "football-data-org" / f"BSA-{temporada}.json",
                     headers={"X-Auth-Token": chave}, pausa=6.5)
        hash_ = sha256(arq)
        for m in json.loads(arq.read_text(encoding="utf-8"))["matches"]:
            linhas.append({
                "id": m["id"], "temporada": temporada, "rodada": m.get("matchday"),
                "data_utc": m["utcDate"], "status": m["status"],
                "mandante": m["homeTeam"]["name"], "mandante_curto": m["homeTeam"].get("shortName"),
                "visitante": m["awayTeam"]["name"], "visitante_curto": m["awayTeam"].get("shortName"),
                "placar_mandante": m["score"]["fullTime"]["home"],
                "placar_visitante": m["score"]["fullTime"]["away"],
                "_arquivo": arq.name, "_sha256": hash_,
            })
    return FDORG_COLS, linhas


FONTES = {
    "adaoduque": adaoduque,
    "mendeley": mendeley,
    "fdcouk": fdcouk,
    "espn": espn,
    "openfootball": openfootball,
    "fdorg": fdorg,
}

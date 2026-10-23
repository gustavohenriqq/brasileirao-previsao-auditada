"""Baixa as fontes e carrega cada uma em raw.<fonte>_jogos.

Uso:
    python -m ingestao.carregar                 # todas as fontes
    python -m ingestao.carregar espn fdcouk     # só algumas
"""
from __future__ import annotations

import sys

from .comum import carregar_raw
from .fontes import FONTES


def main(nomes: list[str]) -> None:
    desconhecidas = set(nomes) - set(FONTES)
    if desconhecidas:
        sys.exit(f"Fonte desconhecida: {', '.join(sorted(desconhecidas))}. "
                 f"Opções: {', '.join(FONTES)}")
    for nome in nomes or FONTES:
        print(f"{nome}: baixando e lendo...")
        resultado = FONTES[nome]()
        if resultado is None:
            continue
        colunas, linhas = resultado
        n = carregar_raw(f"{nome}_jogos", colunas, linhas)
        print(f"{nome}: {n} linhas em raw.{nome}_jogos")


if __name__ == "__main__":
    main(sys.argv[1:])

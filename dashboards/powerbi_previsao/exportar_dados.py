"""Exporta a simulação e o teste de 2026 para os CSVs que o Power BI lê
(pasta dados/, fora do Git).

Fonte: os arquivos da Fase 2 em analise/ (simulacao_2026_*.csv e as seções
simulacao_2026 e teste_2026 de resultados_fase2.json). Não precisa do banco:
a simulação já foi feita por analise/fase2_simular_2026.py.

Tabelas:
- times.csv: um time (20), com pontos atuais, pontos esperados, faixa de 90% e
  as chances de cada zona; escudo em data URI.
- posicoes.csv: um time em uma posição final (20 x 20), com a probabilidade.
- jogos.csv: um jogo que falta (53), com as probabilidades do modelo.
- modelos.csv: um modelo no teste de 2026 (RPS jogo a jogo e erro de pontos
  no replay da tabela). O mercado entra só como referência.
- info.csv: uma linha com os totais da simulação.

Uso: python dashboards/powerbi_previsao/exportar_dados.py
"""
from __future__ import annotations

import base64
import csv
import io
import json
from pathlib import Path

PASTA = Path(__file__).resolve().parent
DADOS = PASTA / "dados"
ANALISE = PASTA.parents[1] / "analise"
ESCUDOS = PASTA / "arte" / "escudos"

# Faixas exclusivas para colorir o mapa de posições (a zona G4 inclui o 1º,
# mas no mapa o 1º é "Título"). Os limites vêm das zonas da simulação.
ROTULO_ZONA = {"titulo": "Título", "g4": "G4", "g6": "G6", "sul_americana": "Sul-Americana",
               "z4": "Z4"}
MODELOS = {
    # chave no JSON: rótulo, papel, ordem no gráfico
    "ingenua": ("Ingênua", "alternativa", 1),
    "elo": ("Elo", "alternativa", 2),
    "dc": ("Dixon-Coles", "alternativa", 3),
    "conjunto_dc": ("Modelo escolhido", "escolhido", 4),
    "mercado": ("Mercado (referência)", "referencia", 5),
}


def ler_csv(arquivo: Path) -> list[dict]:
    with arquivo.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def gravar(arquivo: str, linhas: list[dict]) -> int:
    with (DADOS / arquivo).open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)
    return len(linhas)


def escudo(time_id: str) -> str:
    """PNG em data URI sobre um círculo branco (os escuros não somem no navy),
    com margem transparente. Mesmo desenho do painel da Fase 1."""
    from PIL import Image, ImageDraw

    png = ESCUDOS / f"{time_id}.png"
    if not png.exists():
        return ""
    disco = Image.new("RGBA", (88, 88), (0, 0, 0, 0))
    ImageDraw.Draw(disco).ellipse((8, 8, 79, 79), fill=(255, 255, 255, 255))
    disco.alpha_composite(Image.open(png).convert("RGBA").resize((52, 52), Image.LANCZOS), (18, 18))
    buf = io.BytesIO()
    disco.save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def zona_exclusiva(posicao: int, zonas: dict) -> tuple[str, int]:
    for ordem, chave in enumerate(["titulo", "g4", "g6", "sul_americana"], start=1):
        de, ate = zonas[chave]
        if de <= posicao <= ate:
            return ROTULO_ZONA[chave], ordem
    de, ate = zonas["z4"]
    return ("Z4", 6) if de <= posicao <= ate else ("Meio", 5)


def conferir_probabilidades(times: list[dict], posicoes: list[dict], zonas: dict) -> None:
    """As chances de cada zona (times.csv) têm de sair da distribuição de
    posições (posicoes.csv), e cada time e cada posição somam 1."""
    p = {(r["time_id"], int(r["posicao"])): float(r["probabilidade"]) for r in posicoes}
    n = len(times)
    for t in times:
        tid = t["time_id"]
        soma = sum(p[tid, k] for k in range(1, n + 1))
        assert abs(soma - 1) < 1e-4, f"{tid}: posições somam {soma}"
        for chave in ("titulo", "g4", "g6", "sul_americana", "z4"):
            de, ate = zonas[chave]
            z = sum(p[tid, k] for k in range(de, ate + 1))
            assert abs(z - float(t[f"p_{chave}"])) < 1e-4, f"{tid} {chave}: {z} x {t[f'p_{chave}']}"
    for k in range(1, n + 1):
        soma = sum(p[t["time_id"], k] for t in times)
        assert abs(soma - 1) < 1e-4, f"posição {k}: soma {soma}"


def main() -> None:
    DADOS.mkdir(exist_ok=True)
    r = json.loads((ANALISE / "resultados_fase2.json").read_text(encoding="utf-8"))
    sim, teste = r["simulacao_2026"], r["teste_2026"]
    zonas = sim["zonas"]

    times = ler_csv(ANALISE / "simulacao_2026_times.csv")
    posicoes = ler_csv(ANALISE / "simulacao_2026_posicoes.csv")
    conferir_probabilidades(times, posicoes, zonas)
    if len(times) != len(sim["times"]):
        raise SystemExit(f"times.csv tem {len(times)} times; o JSON tem {len(sim['times'])}")

    # Ordem da tabela: pontos esperados (o desempate fica na posição esperada)
    ordem = sorted(times, key=lambda t: (-float(t["pontos_esperados"]), float(t["posicao_esperada"])))
    ordem_prevista = {t["time_id"]: i for i, t in enumerate(ordem, start=1)}
    for t in times:
        t["ordem_prevista"] = ordem_prevista[t["time_id"]]
        t["escudo"] = escudo(t["time_id"])
    sem_escudo = [t["time_id"] for t in times if not t["escudo"]]

    for linha in posicoes:
        linha["posicao_rotulo"] = f'{linha["posicao"]}º'
        linha["zona"], linha["zona_ordem"] = zona_exclusiva(int(linha["posicao"]), zonas)
        del linha["time"]

    jogos = []
    for j in sorted(ler_csv(ANALISE / "simulacao_2026_jogos.csv"),
                    key=lambda j: (j["data_definida"] != "True", j["data"], int(j["rodada"]), j["mandante"])):
        definida = j["data_definida"] == "True"
        a, m, d = j["data"].split("-")
        jogos.append({
            "id_jogo": j["id_fdorg"], "ordem": len(jogos) + 1, "rodada": j["rodada"],
            "data": j["data"] if definida else "",
            "quando": f"{d}/{m}" if definida else "a definir",
            "mandante": j["mandante"], "visitante": j["visitante"],
            "mandante_id": j["mandante_id"], "visitante_id": j["visitante_id"],
            "p_mandante": j["p_mandante"], "p_empate": j["p_empate"], "p_visitante": j["p_visitante"],
            "placar_mais_provavel": j["placar_mais_provavel"],
        })
    if len(jogos) != sim["jogos_pendentes"]:
        raise SystemExit(f"jogos.csv tem {len(jogos)} jogos; a simulação tem {sim['jogos_pendentes']}")

    # Replay da tabela: média dos cortes (10, 15, 20, 25 rodadas) de cada modelo
    replay = teste["replay"]["linhas"]
    modelos = []
    for chave, (rotulo, papel, ordem_m) in MODELOS.items():
        linhas = replay.get(chave, [])
        media = lambda campo: (sum(x[campo] for x in linhas) / len(linhas)) if linhas else ""  # noqa: E731
        modelos.append({
            "modelo": chave, "rotulo": rotulo, "papel": papel, "ordem": ordem_m,
            "rps": teste["resumo"][chave]["rps"], "log_loss": teste["resumo"][chave]["log_loss"],
            "erro_pontos": media("erro_pontos"), "erro_posicao": media("erro_posicao"),
            "cobertura_90": media("cobertura_90"),
        })

    cortes = teste["replay"]["cortes"]
    info = [{
        "simulacoes": sim["simulacoes"], "jogos_disputados": sim["jogos_disputados"],
        "jogos_restantes": sim["jogos_pendentes"], "jogos_total": sim["jogos_disputados"] + sim["jogos_pendentes"],
        "ultimo_jogo": sim["ultimo_jogo_disputado"], "pendentes_sem_data": sim["pendentes_sem_data"],
        "incerteza": sim["incerteza"], "jogos_teste": teste["jogos"],
        "cortes_replay": len(teste["replay"]["cortes"]),
        "cortes_texto": ", ".join(map(str, cortes[:-1])) + f" e {cortes[-1]}",
        "rodada_alvo_replay": teste["replay"]["alvo"],
        "gerado_em": sim["gerado_em"],
    }]

    n_t = gravar("times.csv", times)
    n_p = gravar("posicoes.csv", posicoes)
    n_j = gravar("jogos.csv", jogos)
    n_m = gravar("modelos.csv", modelos)
    gravar("info.csv", info)
    print(f"times.csv: {n_t} times ({n_t - len(sem_escudo)} com escudo); posicoes.csv: {n_p} linhas; "
          f"jogos.csv: {n_j} jogos; modelos.csv: {n_m} modelos; info.csv: 1 linha")
    if sem_escudo:
        print(f"  sem escudo: {', '.join(sem_escudo)} (rode arte/baixar_escudos.py)")


if __name__ == "__main__":
    main()

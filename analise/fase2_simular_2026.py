"""Fase 2: simulação das rodadas que faltam do Brasileirão 2026 (ensaio interno).

Modelo escolhido na validação, congelado: Dixon-Coles + mando por time +
finalizações, treinado com todos os jogos disputados até hoje. Os jogos que
faltam vêm de marts.jogos_pendentes (football-data.org), adiado incluído; o
adiado sem data nova entra com a data do último jogo previsto.

Cada jogo restante é previsto uma vez (matriz de placares) e o resto do
campeonato é sorteado 100 mil vezes. Em cada simulação, cada time recebe um
desvio de força ~ Normal(0; 0,1) no log dos gols (incerteza de parâmetro,
escala escolhida no replay de 2005 a 2011), o mesmo em todos os jogos daquela
simulação.

Classificação: pontos, vitórias, saldo, gols pró. Confronto direto e cartões
(critérios seguintes do regulamento) não são simulados: o que sobrar empatado
vai por sorteio.

Zonas (nominais; as vagas mudam com os campeões das copas): título, G4
(Libertadores direto), G6 (Libertadores), 7º a 12º (Sul-Americana), Z4.

Saídas:
- analise/simulacao_2026_times.csv: uma linha por time;
- analise/simulacao_2026_posicoes.csv: probabilidade de cada time em cada posição;
- analise/simulacao_2026_jogos.csv: probabilidades de cada jogo restante;
- seção "simulacao_2026" de analise/resultados_fase2.json.

Rodar com
    .venv\\Scripts\\python -u analise/fase2_simular_2026.py > analise/fase2_simular_2026.log 2>&1
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ingestao.comum import RAIZ  # noqa: E402
from modelos.carga import _consultar, carregar_jogos  # noqa: E402
from modelos.fatores import carregar_estatisticas  # noqa: E402
from modelos.metricas import SEMENTE  # noqa: E402
from modelos.replay import _somar, _sortear_placares_incerteza, posicoes  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fase2_teste_2026 import ESCOLHIDO, INCERTEZA, modelo_escolhido  # noqa: E402

TEMPORADA = 2026
SIMULACOES = 100_000
LOTE = 25_000
ZONAS = {"titulo": (1, 1), "g4": (1, 4), "g6": (1, 6), "sul_americana": (7, 12), "z4": (17, 20)}
SAIDA = RAIZ / "analise"


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def carregar_pendentes() -> pd.DataFrame:
    linhas = _consultar("select id_fdorg, temporada, rodada, data_prevista, mandante_id, visitante_id, "
                        "status_fonte from marts.jogos_pendentes where temporada = %s "
                        "order by data_prevista nulls last, id_fdorg", (TEMPORADA,))
    p = pd.DataFrame(linhas, columns=["id_fdorg", "temporada", "rodada", "data", "mandante_id",
                                      "visitante_id", "status_fonte"])
    p["data"] = pd.to_datetime(p["data"])
    p["data_definida"] = p["data"].notna()
    p["data"] = p["data"].fillna(p["data"].max())
    p["jogo_id"] = "pendente_" + p["id_fdorg"].astype(str)
    return p


def main() -> None:
    t0 = time.time()
    jogos = carregar_jogos(permitir_teste=True)
    estat = carregar_estatisticas(TEMPORADA, permitir_teste=True)
    estat = estat[estat["jogo_id"].isin(set(jogos["jogo_id"]))]
    pend = carregar_pendentes()
    feitos = jogos[jogos["temporada"] == TEMPORADA]
    if len(feitos) + len(pend) != 380:
        raise SystemExit(f"2026 não fecha 380 jogos: {len(feitos)} disputados + {len(pend)} pendentes")
    if pend["data"].min() <= feitos["data"].max() and pend["data_definida"].all():
        log("aviso: há pendente com data anterior ao último jogo disputado")
    log(f"disputados {len(feitos)} (último em {feitos['data'].max():%d/%m/%Y}), pendentes {len(pend)}")

    times_base = sorted(set(jogos["mandante_id"]) | set(jogos["visitante_id"]))
    modelo = modelo_escolhido(times_base, estat)
    modelo.ajustar(jogos)
    prev = modelo.prever(pend[["jogo_id", "temporada", "rodada", "data", "mandante_id", "visitante_id"]])
    placares = prev.placares
    log(f"modelo ajustado e {len(pend)} jogos previstos ({time.time() - t0:.0f} s)")

    times = sorted(set(feitos["mandante_id"]) | set(feitos["visitante_id"]))
    idx = {t: i for i, t in enumerate(times)}
    n = len(times)
    im_f, iv_f = feitos["mandante_id"].map(idx).to_numpy(), feitos["visitante_id"].map(idx).to_numpy()
    im_p, iv_p = pend["mandante_id"].map(idx).to_numpy(), pend["visitante_id"].map(idx).to_numpy()
    p_f, v_f, s_f, g_f = _somar(feitos["gols_mandante"], feitos["gols_visitante"], im_f, iv_f, n)

    rng = np.random.default_rng(SEMENTE)
    eps_rng = np.random.default_rng([SEMENTE, 1])
    pontos_t, pos_t = [], []
    for _ in range(SIMULACOES // LOTE):
        eps = eps_rng.normal(0.0, INCERTEZA[ESCOLHIDO], (LOTE, n))
        gm, gv = _sortear_placares_incerteza(placares, eps[:, im_p] - eps[:, iv_p], rng)
        p_s, v_s, s_s, g_s = _somar(gm, gv, im_p, iv_p, n)
        pts = p_f + p_s
        pontos_t.append(pts.astype(np.int16))
        pos_t.append(posicoes(pts, v_f + v_s, s_f + s_s, g_f + g_s,
                              rng.random((LOTE, n)) * 0.5).astype(np.int8))
    pontos, pos = np.concatenate(pontos_t), np.concatenate(pos_t)
    log(f"{SIMULACOES} temporadas simuladas ({time.time() - t0:.0f} s)")

    nomes = dict(_consultar("select time_id, nome from marts.dim_times", ()))
    prob_pos = np.stack([(pos == k).mean(axis=0) for k in range(1, n + 1)], axis=1)  # time x posição
    lo, hi = np.percentile(pontos, [5, 95], axis=0)
    tab = pd.DataFrame({
        "time_id": times, "time": [nomes.get(t, t) for t in times],
        "pontos_atuais": p_f.astype(int), "vitorias_atuais": v_f.astype(int),
        "saldo_atual": s_f.astype(int), "gols_pro_atuais": g_f.astype(int),
        "jogos_disputados": np.bincount(np.r_[im_f, iv_f], minlength=n),
        "jogos_restantes": np.bincount(np.r_[im_p, iv_p], minlength=n),
        "pontos_esperados": pontos.mean(axis=0), "pontos_p5": lo, "pontos_p95": hi,
        "posicao_esperada": pos.mean(axis=0),
    })
    for zona, (a, b) in ZONAS.items():
        tab[f"p_{zona}"] = prob_pos[:, a - 1:b].sum(axis=1)
    pos_atual = posicoes(p_f, v_f, s_f, g_f, np.zeros(n))
    tab.insert(2, "posicao_atual", pos_atual)
    tab = tab.sort_values("posicao_esperada").reset_index(drop=True)
    tab.to_csv(SAIDA / "simulacao_2026_times.csv", index=False)

    longa = pd.DataFrame([{"time_id": t, "time": nomes.get(t, t), "posicao": k + 1,
                           "probabilidade": float(prob_pos[i, k])}
                          for i, t in enumerate(times) for k in range(n)])
    longa.to_csv(SAIDA / "simulacao_2026_posicoes.csv", index=False)

    g = placares.shape[1]
    x = np.arange(g)
    melhor = placares.reshape(len(pend), -1).argmax(axis=1)
    jog = pend[["id_fdorg", "rodada", "data", "data_definida", "status_fonte",
                "mandante_id", "visitante_id"]].copy()
    jog.insert(5, "mandante", jog["mandante_id"].map(lambda t: nomes.get(t, t)))
    jog.insert(6, "visitante", jog["visitante_id"].map(lambda t: nomes.get(t, t)))
    jog["p_mandante"], jog["p_empate"], jog["p_visitante"] = prev.probs[:, 0], prev.probs[:, 1], prev.probs[:, 2]
    jog["gols_esperados_mandante"] = (placares.sum(axis=2) * x).sum(axis=1)
    jog["gols_esperados_visitante"] = (placares.sum(axis=1) * x).sum(axis=1)
    jog["placar_mais_provavel"] = [f"{c // g}x{c % g}" for c in melhor]
    jog.to_csv(SAIDA / "simulacao_2026_jogos.csv", index=False)

    for _, r in tab.iterrows():
        log(f"  {r['time']:22s} {r['pontos_atuais']:3d} pts -> {r['pontos_esperados']:5.1f} "
            f"[{r['pontos_p5']:.0f}-{r['pontos_p95']:.0f}]  título {r['p_titulo']:6.1%}  "
            f"G6 {r['p_g6']:6.1%}  Z4 {r['p_z4']:6.1%}")

    destino = SAIDA / "resultados_fase2.json"
    dados = json.loads(destino.read_text(encoding="utf-8"))
    dados["simulacao_2026"] = {
        "gerado_por": "analise/fase2_simular_2026.py",
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "modelo": ESCOLHIDO, "incerteza": INCERTEZA[ESCOLHIDO], "simulacoes": SIMULACOES,
        "semente": SEMENTE, "jogos_disputados": int(len(feitos)),
        "ultimo_jogo_disputado": f"{feitos['data'].max():%Y-%m-%d}",
        "jogos_pendentes": int(len(pend)), "pendentes_sem_data": int((~pend["data_definida"]).sum()),
        "desempate": "pontos, vitórias, saldo, gols pró, sorteio (confronto direto e cartões não simulados)",
        "zonas": {k: list(v) for k, v in ZONAS.items()},
        "times": tab.to_dict(orient="records"),
        "segundos": time.time() - t0,
    }
    destino.write_text(json.dumps(dados, ensure_ascii=False, indent=2, default=lambda o: o.item()),
                       encoding="utf-8")
    log(f"gravado ({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()

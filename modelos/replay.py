"""Replay de tabela: projeta a classificação a partir de uma rodada de corte.

Para uma temporada e uma rodada de corte k:
1. o modelo treina com os jogos de data menor que a primeira data da rodada
   k + 1 (mesma regra do backtest);
2. os jogos da temporada que ainda não tinham acontecido nessa data (rodadas
   k + 1 em diante e adiados de rodadas anteriores) são previstos uma vez, com
   o modelo congelado no corte, e simulados jogo a jogo por Monte Carlo;
3. a tabela de cada rodada alvo (ex.: 33 e 38) = jogos de rodada <= alvo:
   os já jogados no corte com o placar real, os demais sorteados;
4. compara com a tabela real nesse alvo.

Métricas por (temporada, corte, alvo):
- erro_pontos: erro absoluto médio entre os pontos esperados (média das
  simulações) e os pontos reais, por time;
- erro_posicao: erro absoluto médio entre a posição esperada e a real;
- acerto_g4, acerto_g6, acerto_z4: fração dos times reais do G4/G6/Z4 que
  estão entre os 4/6 melhores (ou 4 piores) pela posição esperada;
- cobertura_90: fração dos times cujos pontos reais caem na faixa de 90% das
  simulações (percentis 5 e 95).

Classificação: pontos, vitórias, saldo, gols pró (ordem do regulamento da CBF);
o que sobrar empatado vai por sorteio. Modelo sem placar (ingênua, Elo) só
sorteia o resultado: saldo e gols pró contam apenas os jogos já disputados.

A régua do mercado não entra no replay: as odds de fechamento das rodadas
futuras não existiam na data do corte.

Incerteza de parâmetro (`incerteza` > 0): as forças estimadas no corte não são
exatas. Em cada simulação, cada time recebe um desvio e ~ Normal(0, incerteza),
o mesmo em todos os jogos daquela simulação, e cada jogo usa
d = e_mandante - e_visitante:
- modelo com placar (Dixon-Coles): os gols esperados viram lam_m e^d e
  lam_v e^-d, o que equivale a inclinar a matriz de placares,
  P'(x, y) proporcional a P(x, y) e^(d (x - y)); d é arredondado para uma grade
  de 41 pontos (erro desprezível) para reaproveitar as matrizes;
- modelo só com probabilidades (Elo, ingênua): logit ordenado, os cortes
  logit(P(V)) e logit(P(V ou E)) andam -d.
A unidade da escala é log de gols no Dixon-Coles e logit no Elo. Com
incerteza = 0 o replay é idêntico ao de antes (mesmos sorteios).

Uso:
    from modelos.replay import replay_tabela
    r = replay_tabela(jogos, DixonColes(), 2015, corte=20, alvos=(33, 38))
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.special import expit, logit

from modelos.backtest import COLUNAS_POS_JOGO
from modelos.carga import COLUNAS_ODDS
from modelos.metricas import SEMENTE

SIMULACOES = 10_000
PONTOS_GRADE_INCERTEZA = 41
CORTES = (10, 15, 20, 25)
ALVOS = (33, 38)


def _incidencia(idx: np.ndarray, n_times: int) -> np.ndarray:
    inc = np.zeros((len(idx), n_times))
    inc[np.arange(len(idx)), idx] = 1.0
    return inc


def _somar(gm, gv, im, iv, n_times):
    """Pontos, vitórias, saldo e gols pró por time. gm/gv: (..., jogos)."""
    gm, gv = np.asarray(gm, dtype=float), np.asarray(gv, dtype=float)
    vm, ve = (gm > gv).astype(float), (gm == gv).astype(float)
    vv = (gm < gv).astype(float)
    hm, hv = _incidencia(im, n_times), _incidencia(iv, n_times)
    pontos = (3 * vm + ve) @ hm + (3 * vv + ve) @ hv
    vitorias = vm @ hm + vv @ hv
    saldo = (gm - gv) @ hm + (gv - gm) @ hv
    gp = gm @ hm + gv @ hv
    return pontos, vitorias, saldo, gp


def posicoes(pontos, vitorias, saldo, gp, sorteio) -> np.ndarray:
    """Posição (1 = líder) por linha. Todos os argumentos com a mesma forma."""
    chave = (((pontos * 50 + vitorias) * 500 + (saldo + 240)) * 1000 + gp) + sorteio
    return np.argsort(np.argsort(-chave, axis=-1), axis=-1) + 1


def _sortear_placares(placares: np.ndarray, rng, n_sim: int) -> tuple[np.ndarray, np.ndarray]:
    g = placares.shape[1]
    gm = np.empty((n_sim, len(placares)), dtype=np.int16)
    gv = np.empty_like(gm)
    for k, mat in enumerate(placares):
        acum = np.cumsum(mat.ravel())
        cel = np.minimum(np.searchsorted(acum, rng.random(n_sim) * acum[-1]), g * g - 1)
        gm[:, k], gv[:, k] = cel // g, cel % g
    return gm, gv


def _sortear_resultados(probs: np.ndarray, rng, n_sim: int) -> tuple[np.ndarray, np.ndarray]:
    """Sem placar: vitória vira 1x0, empate 0x0, derrota 0x1 (só para contar
    pontos e vitórias; o saldo dos simulados é zerado depois)."""
    u = rng.random((n_sim, len(probs)))
    m = u < probs[:, 0]
    e = ~m & (u < probs[:, 0] + probs[:, 1])
    gm = m.astype(np.int16)
    gv = (~m & ~e).astype(np.int16)
    return gm, gv


def _sortear_placares_incerteza(placares: np.ndarray, delta: np.ndarray, rng) -> tuple[np.ndarray, np.ndarray]:
    """Placares com a matriz de cada jogo inclinada por delta (n_sim, jogos)."""
    g = placares.shape[1]
    n_sim, n_j = delta.shape
    x = np.arange(g)
    dif = (x[:, None] - x[None, :]).ravel().astype(float)
    dmax = max(float(np.abs(delta).max()), 1e-9)
    grade = np.linspace(-dmax, dmax, PONTOS_GRADE_INCERTEZA)
    passo = grade[1] - grade[0]
    faixas = np.clip(np.rint((delta + dmax) / passo).astype(int), 0, len(grade) - 1)
    inclina = np.exp(grade[:, None] * dif[None, :])
    gm = np.empty((n_sim, n_j), dtype=np.int16)
    gv = np.empty_like(gm)
    for k in range(n_j):
        acum = np.cumsum(placares[k].ravel()[None, :] * inclina, axis=1)
        acum /= acum[:, -1:]
        u = rng.random(n_sim)
        cel = np.minimum((acum[faixas[:, k]] < u[:, None]).sum(axis=1), g * g - 1)
        gm[:, k], gv[:, k] = cel // g, cel % g
    return gm, gv


def _sortear_resultados_incerteza(probs: np.ndarray, delta: np.ndarray, rng) -> tuple[np.ndarray, np.ndarray]:
    """Resultados com o logit ordenado deslocado por delta (n_sim, jogos)."""
    pv = np.clip(probs[:, 2], 1e-9, 1 - 1e-9)
    pve = np.clip(probs[:, 1] + probs[:, 2], 1e-9, 1 - 1e-9)
    PV = expit(logit(pv)[None, :] - delta)
    PVE = expit(logit(pve)[None, :] - delta)
    u = rng.random(delta.shape)
    vis = u < PV
    emp = ~vis & (u < PVE)
    return (~vis & ~emp).astype(np.int16), vis.astype(np.int16)


def replay_tabela(jogos: pd.DataFrame, modelo, temporada: int, corte: int,
                  alvos=ALVOS, n_sim: int = SIMULACOES, semente: int = SEMENTE,
                  detalhar: bool = False, incerteza: float = 0.0) -> list[dict]:
    """Uma linha por alvo. `jogos` em ordem de data, índice 0..n-1, com a
    temporada inteira (os resultados reais servem só para a comparação)."""
    jogos = jogos.reset_index(drop=True)
    temp = jogos[jogos["temporada"] == temporada]
    inicio = temp.loc[temp["rodada"] == corte + 1, "data"].min()
    if pd.isna(inicio):
        raise ValueError(f"{temporada} não tem a rodada {corte + 1}")
    pos = int(np.searchsorted(jogos["data"].to_numpy(), inicio.to_datetime64(), side="left"))
    passados = jogos.iloc[:pos]
    alvo_max = max(alvos)
    conhecidos = temp[temp["data"] < inicio]
    futuros = temp[(temp["data"] >= inicio) & (temp["rodada"] <= alvo_max)]

    modelo.ajustar(passados)
    # Odds de fechamento dos jogos depois do corte ainda não existiam no corte.
    ocultas = COLUNAS_POS_JOGO + COLUNAS_ODDS
    cego = futuros.drop(columns=[c for c in ocultas if c in futuros.columns])
    prev = modelo.prever(cego)
    times = sorted(set(temp["mandante_id"]) | set(temp["visitante_id"]))
    idx = {t: i for i, t in enumerate(times)}
    n = len(times)

    def indices(df):
        return df["mandante_id"].map(idx).to_numpy(), df["visitante_id"].map(idx).to_numpy()

    rng = np.random.default_rng(semente)
    tem_placar = prev.placares is not None
    if incerteza > 0:
        # desvios por time e simulação, de um gerador próprio
        eps = np.random.default_rng([semente, 1]).normal(0.0, incerteza, (n_sim, n))
        im_fut, iv_fut = indices(futuros)
        delta = eps[:, im_fut] - eps[:, iv_fut]
        if tem_placar:
            gm_s, gv_s = _sortear_placares_incerteza(prev.placares, delta, rng)
        else:
            gm_s, gv_s = _sortear_resultados_incerteza(prev.probs, delta, rng)
    elif tem_placar:
        gm_s, gv_s = _sortear_placares(prev.placares, rng, n_sim)
    else:
        gm_s, gv_s = _sortear_resultados(prev.probs, rng, n_sim)

    saida = []
    for alvo in alvos:
        # tabela real no alvo
        real = temp[temp["rodada"] <= alvo]
        im, iv = indices(real)
        p_r, v_r, s_r, g_r = _somar(real["gols_mandante"], real["gols_visitante"], im, iv, n)
        pos_r = posicoes(p_r, v_r, s_r, g_r, rng.random(n) * 0.5)

        # parte fixa (jogada antes do corte) + parte sorteada
        fixos = conhecidos[conhecidos["rodada"] <= alvo]
        im_f, iv_f = indices(fixos)
        p_f, v_f, s_f, g_f = _somar(fixos["gols_mandante"], fixos["gols_visitante"], im_f, iv_f, n)
        sel = (futuros["rodada"] <= alvo).to_numpy()
        im_s, iv_s = indices(futuros[sel])
        p_s, v_s, s_s, g_s = _somar(gm_s[:, sel], gv_s[:, sel], im_s, iv_s, n)
        if not tem_placar:
            s_s, g_s = np.zeros_like(s_s), np.zeros_like(g_s)
        pontos = p_f + p_s
        pos_s = posicoes(pontos, v_f + v_s, s_f + s_s, g_f + g_s, rng.random((n_sim, n)) * 0.5)

        esp_pontos, esp_pos = pontos.mean(axis=0), pos_s.mean(axis=0)
        lo, hi = np.percentile(pontos, [5, 95], axis=0)
        ordem_esp = np.argsort(esp_pos)

        def acerto(k, de_baixo=False):
            proj = set(ordem_esp[-k:] if de_baixo else ordem_esp[:k])
            reais = set(np.where(pos_r > n - k)[0] if de_baixo else np.where(pos_r <= k)[0])
            return len(proj & reais) / k

        linha = {
            "temporada": int(temporada), "corte": int(corte), "alvo": int(alvo),
            "modelo": modelo.nome, "jogos_simulados": int(sel.sum()), "incerteza": float(incerteza),
            "erro_pontos": float(np.abs(esp_pontos - p_r).mean()),
            "erro_posicao": float(np.abs(esp_pos - pos_r).mean()),
            "acerto_g4": acerto(4), "acerto_g6": acerto(6), "acerto_z4": acerto(4, de_baixo=True),
            "cobertura_90": float(((p_r >= lo) & (p_r <= hi)).mean()),
        }
        if detalhar:
            linha["por_time"] = [
                {"time": t, "pontos_reais": float(p_r[i]), "pontos_esperados": float(esp_pontos[i]),
                 "faixa_90": [float(lo[i]), float(hi[i])], "posicao_real": int(pos_r[i]),
                 "posicao_esperada": float(esp_pos[i])} for i, t in enumerate(times)]
        saida.append(linha)
    return saida

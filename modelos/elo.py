"""Elo para a Série A, com probabilidades M/E/V por logit ordenado.

Atualização (jogo a jogo, em ordem de data):
    esperado_m = 1 / (1 + 10^(-(R_m + mando - R_v) / 400))
    delta      = K * G(saldo) * (S_m - esperado_m)     (S_m: 1, 0,5 ou 0)
    R_m += delta;  R_v -= delta                        (soma zero)
G(saldo) é o multiplicador do World Football Elo: 1 para saldo 0 ou 1, 1,5
para 2 e (11 + saldo) / 8 para 3 ou mais.

Entre temporadas: as notas dos times da temporada anterior regridem uma fração
`regressao` em direção à média deles. Time que não estava na temporada anterior
(promovido ou de volta) entra com média + `nota_promovido` (negativa). Na
primeira temporada da base todo mundo começa em 1500.

Probabilidades: logit ordenado sobre x = (R_m + mando - R_v) / 100:
    P(V) = sigmoide(c1 - b x),  P(V ou E) = sigmoide(c2 - b x),  c2 > c1
Cortes e inclinação ajustados por máxima verossimilhança com as notas pré-jogo
dos jogos passados (últimas `temporadas_logit` temporadas), só com o passado.

Uso:
    from modelos.elo import Elo
    m = Elo(k=20, mando=60, regressao=0.3, nota_promovido=-100)
    m.ajustar(passados); prev = m.prever(bloco)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit

from modelos.backtest import Previsao

NOTA_INICIAL = 1500.0
TEMPORADAS_LOGIT = 5
MINIMO_JOGOS_LOGIT = 100
# chute inicial do logit (c1, log(c2 - c1), b): mandante ~47%, empate ~27%
LOGIT_INICIAL = np.array([-1.3, np.log(1.1), 0.25])
PONTOS = {"M": 1.0, "E": 0.5, "V": 0.0}


def multiplicador_saldo(saldo: int) -> float:
    s = abs(int(saldo))
    if s <= 1:
        return 1.0
    if s == 2:
        return 1.5
    return (11.0 + s) / 8.0


def delta_elo(r_m: float, r_v: float, gols_m: int, gols_v: int, k: float, mando: float) -> float:
    """Pontos que o mandante ganha (o visitante perde o mesmo tanto)."""
    esperado = 1.0 / (1.0 + 10.0 ** (-(r_m + mando - r_v) / 400.0))
    s = 1.0 if gols_m > gols_v else (0.5 if gols_m == gols_v else 0.0)
    return k * multiplicador_saldo(gols_m - gols_v) * (s - esperado)


def probs_logit(x: np.ndarray, c1: float, c2: float, b: float) -> np.ndarray:
    pv = expit(c1 - b * x)
    pve = expit(c2 - b * x)
    return np.column_stack([1.0 - pve, pve - pv, pv])


def _ajustar_logit(x: np.ndarray, y: np.ndarray, inicio: np.ndarray) -> np.ndarray:
    """MLE do logit ordenado. y: 0 = M, 1 = E, 2 = V. Devolve (c1, log gap, b)."""

    def nll(theta):
        c1, lg, b = theta
        c2 = c1 + np.exp(lg)
        pv = expit(c1 - b * x)
        pve = expit(c2 - b * x)
        p = np.where(y == 2, pv, np.where(y == 1, pve - pv, 1.0 - pve))
        p = np.clip(p, 1e-12, 1.0)
        # gradiente analítico
        dpv = pv * (1 - pv)
        dpve = pve * (1 - pve)
        # derivadas de p em relação a (c1, c2, b)
        dc1 = np.where(y == 2, dpv, np.where(y == 1, -dpv, 0.0))
        dc2 = np.where(y == 2, 0.0, np.where(y == 1, dpve, -dpve))
        db = np.where(y == 2, -x * dpv, np.where(y == 1, -x * dpve + x * dpv, x * dpve))
        g_c1 = -(dc1 / p).sum() - (dc2 / p).sum()       # c2 = c1 + e^lg
        g_lg = -(dc2 / p).sum() * np.exp(lg)
        g_b = -(db / p).sum()
        return -np.log(p).sum(), np.array([g_c1, g_lg, g_b])

    r = minimize(nll, inicio, jac=True, method="L-BFGS-B")
    return r.x


class Elo:
    def __init__(self, k: float = 20.0, mando: float = 60.0, regressao: float = 0.3,
                 nota_promovido: float = -100.0, temporadas_logit: int = TEMPORADAS_LOGIT,
                 nome: str = "elo"):
        self.nome = nome
        self.k, self.mando = k, mando
        self.regressao, self.nota_promovido = regressao, nota_promovido
        self.temporadas_logit = temporadas_logit
        self._zerar()

    def _zerar(self) -> None:
        self.notas: dict[str, float] = {}
        self.ultima: dict[str, int] = {}   # última temporada em que o time tem nota
        self.corrente: int | None = None
        self.primeira: int | None = None
        self.media_ref = NOTA_INICIAL
        self.processados = 0
        self.ultimo_id = None
        # histórico pré-jogo para o logit
        self.hist_x: list[float] = []
        self.hist_y: list[int] = []
        self.hist_t: list[int] = []
        self.theta = LOGIT_INICIAL.copy()
        self._logit_em = None  # (jogos no histórico, temporada) do último ajuste

    # -- temporadas e times --------------------------------------------------
    def _nova_temporada(self, t: int) -> None:
        if self.corrente is None:
            self.corrente = self.primeira = t
            return
        if t <= self.corrente:
            return
        anteriores = [tm for tm, s in self.ultima.items() if s == self.corrente]
        if anteriores:
            media = float(np.mean([self.notas[tm] for tm in anteriores]))
            for tm in anteriores:
                self.notas[tm] = media + (1.0 - self.regressao) * (self.notas[tm] - media)
            self.media_ref = media
        self.corrente = t

    def _garantir_time(self, time: str, t: int) -> None:
        ult = self.ultima.get(time)
        if ult is not None and ult >= t:
            return
        if ult is None or ult < t - 1 or t == self.primeira:
            if t == self.primeira:
                self.notas[time] = NOTA_INICIAL
            else:
                self.notas[time] = self.media_ref + self.nota_promovido
        self.ultima[time] = t

    def _x(self, m: str, v: str) -> float:
        return (self.notas[m] + self.mando - self.notas[v]) / 100.0

    # -- interface -------------------------------------------------------------
    def ajustar(self, jogos_passados: pd.DataFrame) -> None:
        """Processa, em ordem, os jogos ainda não vistos (o treino de cada
        bloco contém o do bloco anterior; se não contiver, recomeça)."""
        n = len(jogos_passados)
        if n < self.processados or (self.processados > 0 and
                                    jogos_passados["jogo_id"].iat[self.processados - 1] != self.ultimo_id):
            self._zerar()
        novos = jogos_passados.iloc[self.processados:]
        for t, m, v, gm, gv, res in zip(novos["temporada"], novos["mandante_id"],
                                        novos["visitante_id"], novos["gols_mandante"],
                                        novos["gols_visitante"], novos["resultado"]):
            t = int(t)
            self._nova_temporada(t)
            self._garantir_time(m, t)
            self._garantir_time(v, t)
            self.hist_x.append(self._x(m, v))
            self.hist_y.append({"M": 0, "E": 1, "V": 2}[res])
            self.hist_t.append(t)
            d = delta_elo(self.notas[m], self.notas[v], gm, gv, self.k, self.mando)
            self.notas[m] += d
            self.notas[v] -= d
        self.processados = n
        if n:
            self.ultimo_id = jogos_passados["jogo_id"].iat[n - 1]

    def _logit(self, t: int) -> tuple[float, float, float]:
        chave = (len(self.hist_x), t)
        if self._logit_em != chave:
            ht = np.asarray(self.hist_t)
            m = ht >= t - self.temporadas_logit
            if m.sum() >= MINIMO_JOGOS_LOGIT:
                self.theta = _ajustar_logit(np.asarray(self.hist_x)[m],
                                            np.asarray(self.hist_y)[m], self.theta)
            self._logit_em = chave
        c1, lg, b = self.theta
        return c1, c1 + np.exp(lg), b

    def prever(self, jogos_do_bloco: pd.DataFrame) -> Previsao:
        ts = jogos_do_bloco["temporada"].astype(int).to_numpy()
        x = np.empty(len(ts))
        for i, (t, m, v) in enumerate(zip(ts, jogos_do_bloco["mandante_id"],
                                          jogos_do_bloco["visitante_id"])):
            self._nova_temporada(int(t))  # só regressão e promovidos: não usa resultado
            self._garantir_time(m, int(t))
            self._garantir_time(v, int(t))
            x[i] = self._x(m, v)
        c1, c2, b = self._logit(int(ts.max()))
        diff = x * 100.0 - self.mando
        return Previsao(probs_logit(x, c1, c2, b), extras={"diferenca": diff})

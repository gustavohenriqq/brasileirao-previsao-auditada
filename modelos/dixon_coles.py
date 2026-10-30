"""Dixon-Coles: Poisson bivariado para os gols de mandante e visitante.

Médias de gols de um jogo (mandante i contra visitante j):
    log lam_m = mu + mando + ataque_i - defesa_j + X_m . beta
    log lam_v = mu         + ataque_j - defesa_i + X_v . beta
(defesa maior = defesa melhor). X_m e X_v são covariáveis opcionais por jogo e
por lado (uma linha por jogo, mesmas colunas nos dois lados), com os
coeficientes beta ajustados junto. É por aí que as camadas de fatores entram:
estilo do atacante x estilo do defensor, forma, técnico novo etc. Basta a
camada gravar as colunas no DataFrame de jogos e passar os nomes em
`cov_mandante` / `cov_visitante`.

Probabilidade do placar (x, y): Poisson(x; lam_m) * Poisson(y; lam_v) * tau,
com a correção de Dixon e Coles (1997) para placares baixos:
    tau(0,0) = 1 - lam_m lam_v rho    tau(0,1) = 1 + lam_m rho
    tau(1,0) = 1 + lam_v rho          tau(1,1) = 1 - rho

Ajuste por máxima verossimilhança ponderada:
- peso de cada jogo = 0,5 ^ (dias antes do bloco / meia_vida);
- penalização ridge: ridge * soma((ataque - prior)^2 + (defesa - prior)^2) e
  soma(ridge_cov * beta^2) (ridge_cov pode ser um número ou um vetor, um
  valor por covariável). O prior é 0 para quem estava na temporada anterior
  e -forca_promovido (ataque e defesa) para quem não estava (promovido);
- janela de treino: temporadas t - janela_temporadas até t (t = do bloco);
- warm start: começa do ajuste do bloco anterior.

O ajuste acontece em `prever`, porque o prior de promovido depende de quais
times jogam a temporada do bloco (o bloco chega sem resultado, então isso não
vaza nada).

Uso:
    from modelos.dixon_coles import DixonColes
    m = DixonColes(meia_vida=240, ridge=3.0, forca_promovido=0.2)
    m.ajustar(passados); prev = m.prever(bloco)   # prev.placares: (n, 11, 11)
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import poisson

from modelos.backtest import Previsao

MAX_GOLS = 10
LIMITE_RHO = 0.3
PISO_TAU = 1e-10
INICIO_MU, INICIO_MANDO, INICIO_RHO = np.log(1.2), 0.3, -0.05


# ---------------------------------------------------------------------------
# Probabilidades de placar
# ---------------------------------------------------------------------------
def matriz_placares(lam_m, lam_v, rho, max_gols: int = MAX_GOLS) -> np.ndarray:
    """(n, G+1, G+1): [k, i, j] = P(mandante i x j visitante) no jogo k.
    A massa acima de max_gols é desprezada e a matriz é renormalizada."""
    lam_m = np.atleast_1d(np.asarray(lam_m, dtype=float))
    lam_v = np.atleast_1d(np.asarray(lam_v, dtype=float))
    rho = np.broadcast_to(np.asarray(rho, dtype=float), lam_m.shape)
    g = np.arange(max_gols + 1)
    pm = poisson.pmf(g[None, :], lam_m[:, None])
    pv = poisson.pmf(g[None, :], lam_v[:, None])
    mat = pm[:, :, None] * pv[:, None, :]
    mat[:, 0, 0] *= 1 - lam_m * lam_v * rho
    mat[:, 0, 1] *= 1 + lam_m * rho
    mat[:, 1, 0] *= 1 + lam_v * rho
    mat[:, 1, 1] *= 1 - rho
    mat = np.clip(mat, 0.0, None)
    return mat / mat.sum(axis=(1, 2), keepdims=True)


def probs_resultado(mat: np.ndarray) -> np.ndarray:
    """De (n, G+1, G+1) para (n, 3): mandante, empate, visitante."""
    pm = np.tril(np.ones(mat.shape[1:]), -1)
    pe = np.eye(mat.shape[1])
    return np.column_stack([(mat * pm).sum(axis=(1, 2)), (mat * pe).sum(axis=(1, 2)),
                            (mat * pm.T).sum(axis=(1, 2))])


def simular_placares(lam_m, lam_v, rho, rng, max_gols: int = MAX_GOLS) -> np.ndarray:
    """Sorteia um placar por jogo da distribuição de Dixon-Coles. (n, 2)."""
    mat = matriz_placares(lam_m, lam_v, rho, max_gols)
    acum = mat.reshape(len(mat), -1).cumsum(axis=1)
    u = rng.random(len(mat))[:, None]
    k = np.minimum((acum < u).sum(axis=1), acum.shape[1] - 1)
    return np.column_stack([k // (max_gols + 1), k % (max_gols + 1)])


# ---------------------------------------------------------------------------
# Verossimilhança e ajuste
# ---------------------------------------------------------------------------
@dataclass
class DadosDC:
    im: np.ndarray        # índice do mandante
    iv: np.ndarray        # índice do visitante
    gm: np.ndarray        # gols do mandante
    gv: np.ndarray        # gols do visitante
    peso: np.ndarray
    xm: np.ndarray        # (n, p) covariáveis do lado mandante
    xv: np.ndarray        # (n, p) covariáveis do lado visitante
    n_times: int
    prior_a: np.ndarray
    prior_d: np.ndarray
    ridge: float
    ridge_cov: float


def _desempacotar(theta: np.ndarray, n: int):
    return theta[0], theta[1], theta[2], theta[3:3 + n], theta[3 + n:3 + 2 * n], theta[3 + 2 * n:]


def objetivo(theta: np.ndarray, d: DadosDC) -> tuple[float, np.ndarray]:
    """Menos a log-verossimilhança ponderada mais a penalização, e o gradiente."""
    n = d.n_times
    mu, h, rho, a, df, beta = _desempacotar(theta, n)
    eta_m = mu + h + a[d.im] - df[d.iv] + d.xm @ beta
    eta_v = mu + a[d.iv] - df[d.im] + d.xv @ beta
    lm, lv = np.exp(eta_m), np.exp(eta_v)
    x, y = d.gm, d.gv

    ll = x * eta_m - lm + y * eta_v - lv   # sem log(x!) e log(y!), constantes
    g1, g2 = x - lm, y - lv
    grho = np.zeros_like(lm)
    tau = np.ones_like(lm)

    m = (x == 0) & (y == 0)
    tau[m] = np.maximum(1 - lm[m] * lv[m] * rho, PISO_TAU)
    g1[m] += -lm[m] * lv[m] * rho / tau[m]
    g2[m] += -lm[m] * lv[m] * rho / tau[m]
    grho[m] = -lm[m] * lv[m] / tau[m]
    m = (x == 0) & (y == 1)
    tau[m] = np.maximum(1 + lm[m] * rho, PISO_TAU)
    g1[m] += lm[m] * rho / tau[m]
    grho[m] = lm[m] / tau[m]
    m = (x == 1) & (y == 0)
    tau[m] = np.maximum(1 + lv[m] * rho, PISO_TAU)
    g2[m] += lv[m] * rho / tau[m]
    grho[m] = lv[m] / tau[m]
    m = (x == 1) & (y == 1)
    tau[m] = max(1 - rho, PISO_TAU)
    grho[m] = -1 / tau[m]
    ll = ll + np.log(tau)

    w = d.peso
    wg1, wg2 = w * g1, w * g2
    da, dd = a - d.prior_a, df - d.prior_d
    valor = -(w * ll).sum() + d.ridge * ((da ** 2).sum() + (dd ** 2).sum()) \
        + (d.ridge_cov * beta ** 2).sum()

    grad = np.empty_like(theta)
    grad[0] = -(wg1.sum() + wg2.sum())
    grad[1] = -wg1.sum()
    grad[2] = -(w * grho).sum()
    grad[3:3 + n] = -(np.bincount(d.im, wg1, n) + np.bincount(d.iv, wg2, n)) + 2 * d.ridge * da
    grad[3 + n:3 + 2 * n] = (np.bincount(d.iv, wg1, n) + np.bincount(d.im, wg2, n)) + 2 * d.ridge * dd
    grad[3 + 2 * n:] = -(d.xm.T @ wg1 + d.xv.T @ wg2) + 2 * d.ridge_cov * beta
    return float(valor), grad


def ajustar_dc(d: DadosDC, inicio: np.ndarray | None = None) -> np.ndarray:
    """Vetor theta = [mu, mando, rho, ataque (n), defesa (n), beta (p)]."""
    n, p = d.n_times, d.xm.shape[1]
    if inicio is None:
        inicio = np.concatenate([[INICIO_MU, INICIO_MANDO, INICIO_RHO],
                                 d.prior_a, d.prior_d, np.zeros(p)])
    limites = [(None, None), (None, None), (-LIMITE_RHO, LIMITE_RHO)] + [(None, None)] * (2 * n + p)
    r = minimize(objetivo, inicio, args=(d,), jac=True, method="L-BFGS-B",
                 bounds=limites, options={"maxiter": 1000})
    return r.x


# ---------------------------------------------------------------------------
# Modelo para o backtest
# ---------------------------------------------------------------------------
class DixonColes:
    def __init__(self, meia_vida: float | None = 240.0, ridge: float = 3.0,
                 forca_promovido: float = 0.2, janela_temporadas: int = 3,
                 ridge_cov: float = 1.0, cov_mandante: list[str] | tuple = (),
                 cov_visitante: list[str] | tuple = (), max_gols: int = MAX_GOLS,
                 nome: str = "dc"):
        if len(cov_mandante) != len(cov_visitante):
            raise ValueError("cov_mandante e cov_visitante precisam ter o mesmo tamanho")
        self.nome = nome
        self.meia_vida, self.ridge = meia_vida, ridge
        self.forca_promovido = forca_promovido
        self.janela_temporadas, self.ridge_cov = janela_temporadas, ridge_cov
        self.cov_mandante, self.cov_visitante = list(cov_mandante), list(cov_visitante)
        self.max_gols = max_gols
        self.passados: pd.DataFrame | None = None
        self.parametros: dict | None = None    # último ajuste, por nome de time
        self._chave = None

    def ajustar(self, jogos_passados: pd.DataFrame) -> None:
        self.passados = jogos_passados

    def _covariaveis(self, jogos: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        n = len(jogos)
        if not self.cov_mandante:
            return np.zeros((n, 0)), np.zeros((n, 0))
        xm = jogos[self.cov_mandante].to_numpy(dtype=float)
        xv = jogos[self.cov_visitante].to_numpy(dtype=float)
        if not (np.isfinite(xm).all() and np.isfinite(xv).all()):
            raise ValueError("covariável com valor ausente")
        return xm, xv

    def ajustar_para(self, temporada: int, data_ref: pd.Timestamp, times_alvo) -> dict:
        """Ajusta com os jogos passados da janela, prior de promovido para quem
        joga `temporada` e não jogou a anterior. Devolve os parâmetros."""
        p = self.passados if self.passados is not None else pd.DataFrame()
        chave = (len(p), temporada, data_ref)
        if self._chave == chave and self.parametros is not None:
            return self.parametros

        treino = p[p["temporada"] >= temporada - self.janela_temporadas] if len(p) else p
        anteriores = set()
        if len(p):
            ant = p[p["temporada"] == temporada - 1]
            anteriores = set(ant["mandante_id"]) | set(ant["visitante_id"])
            atual = p[p["temporada"] == temporada]
            da_temporada = set(atual["mandante_id"]) | set(atual["visitante_id"]) | set(times_alvo)
        else:
            da_temporada = set(times_alvo)
        promovidos = (da_temporada - anteriores) if anteriores else set()

        nomes = set(times_alvo)
        if len(treino):
            nomes |= set(treino["mandante_id"]) | set(treino["visitante_id"])
        nomes = sorted(nomes)
        idx = {tm: i for i, tm in enumerate(nomes)}
        n = len(nomes)
        prior = np.array([-self.forca_promovido if tm in promovidos else 0.0 for tm in nomes])

        if len(treino):
            dias = (data_ref - treino["data"]).dt.days.to_numpy(dtype=float)
            peso = np.ones(len(treino)) if not self.meia_vida else 0.5 ** (dias / self.meia_vida)
            xm, xv = self._covariaveis(treino)
            im = treino["mandante_id"].map(idx).to_numpy()
            iv = treino["visitante_id"].map(idx).to_numpy()
            gm = treino["gols_mandante"].to_numpy(dtype=float)
            gv = treino["gols_visitante"].to_numpy(dtype=float)
        else:
            peso = np.zeros(0)
            k = len(self.cov_mandante)
            xm, xv = np.zeros((0, k)), np.zeros((0, k))
            im = iv = np.zeros(0, dtype=int)
            gm = gv = np.zeros(0)
        dados = DadosDC(im, iv, gm, gv, peso, xm, xv, n, prior, prior.copy(),
                        self.ridge, self.ridge_cov)

        # warm start: parâmetros do ajuste anterior; time novo começa no prior
        inicio = None
        if self.parametros is not None:
            ant = self.parametros
            a0 = np.array([ant["ataque"].get(tm, prior[i]) for i, tm in enumerate(nomes)])
            d0 = np.array([ant["defesa"].get(tm, prior[i]) for i, tm in enumerate(nomes)])
            inicio = np.concatenate([[ant["mu"], ant["mando"], ant["rho"]], a0, d0, ant["beta"]])

        theta = ajustar_dc(dados, inicio)
        mu, h, rho, a, df, beta = _desempacotar(theta, n)
        self.parametros = {
            "mu": float(mu), "mando": float(h), "rho": float(rho), "beta": np.array(beta),
            "ataque": dict(zip(nomes, a)), "defesa": dict(zip(nomes, df)),
            "promovidos": sorted(promovidos),
        }
        self._chave = chave
        return self.parametros

    def medias_de_gols(self, jogos: pd.DataFrame, par: dict) -> tuple[np.ndarray, np.ndarray]:
        xm, xv = self._covariaveis(jogos)
        a, d = par["ataque"], par["defesa"]
        am = jogos["mandante_id"].map(a).to_numpy(dtype=float)
        av = jogos["visitante_id"].map(a).to_numpy(dtype=float)
        dm = jogos["mandante_id"].map(d).to_numpy(dtype=float)
        dv = jogos["visitante_id"].map(d).to_numpy(dtype=float)
        lam_m = np.exp(par["mu"] + par["mando"] + am - dv + xm @ par["beta"])
        lam_v = np.exp(par["mu"] + av - dm + xv @ par["beta"])
        return lam_m, lam_v

    def prever(self, jogos_do_bloco: pd.DataFrame) -> Previsao:
        t = int(jogos_do_bloco["temporada"].max())
        times = set(jogos_do_bloco["mandante_id"]) | set(jogos_do_bloco["visitante_id"])
        par = self.ajustar_para(t, jogos_do_bloco["data"].min(), times)
        lam_m, lam_v = self.medias_de_gols(jogos_do_bloco, par)
        mat = matriz_placares(lam_m, lam_v, par["rho"], self.max_gols)
        return Previsao(probs_resultado(mat), placares=mat,
                        extras={"lam_m": lam_m, "lam_v": lam_v,
                                "rho": np.full(len(lam_m), par["rho"])})

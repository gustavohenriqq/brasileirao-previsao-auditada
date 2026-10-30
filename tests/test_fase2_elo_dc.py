import numpy as np
import pandas as pd
import pytest
from scipy.optimize import approx_fprime

from modelos.dixon_coles import (DadosDC, DixonColes, ajustar_dc, matriz_placares,
                                 objetivo, probs_resultado, simular_placares)
from modelos.elo import NOTA_INICIAL, Elo, delta_elo


# ---------------------------------------------------------------------------
# Elo
# ---------------------------------------------------------------------------
def test_elo_delta_e_soma_zero_por_jogo():
    d = delta_elo(1550, 1480, 3, 0, k=20, mando=60)
    assert d > 0
    # inverter o jogo inverte o sinal: o que um ganha, o outro perde
    assert delta_elo(1480, 1550, 0, 3, k=20, mando=-60) == pytest.approx(-d)


def test_elo_soma_das_notas_constante_na_temporada(fabrica):
    jogos = fabrica(n_times=8, temporadas=1)
    m = Elo(k=30, mando=60)
    m.ajustar(jogos)
    assert len(m.notas) == 8
    assert sum(m.notas.values()) == pytest.approx(8 * NOTA_INICIAL)
    assert any(abs(v - NOTA_INICIAL) > 1 for v in m.notas.values())


def test_elo_regressao_e_promovido(fabrica):
    jogos = fabrica(n_times=8, temporadas=2, trocar_times=True)
    t1 = jogos[jogos["temporada"] == 2010]
    m = Elo(k=30, mando=60, regressao=0.5, nota_promovido=-100)
    m.ajustar(t1)
    fim_t1 = dict(m.notas)
    media = np.mean(list(fim_t1.values()))
    t2 = jogos[jogos["temporada"] == 2011]
    primeira = t2[t2["rodada"] == 1]
    m.prever(primeira.drop(columns=["gols_mandante", "gols_visitante", "resultado"]))
    for tm in set(primeira["mandante_id"]) | set(primeira["visitante_id"]):
        if tm in fim_t1:
            assert m.notas[tm] == pytest.approx(media + 0.5 * (fim_t1[tm] - media))
        else:  # promovido
            assert m.notas[tm] == pytest.approx(media - 100)
    # a temporada nova continua soma zero jogo a jogo
    antes = sum(m.notas.values())
    m.ajustar(jogos)
    assert sum(m.notas.values()) == pytest.approx(antes)


def test_elo_probabilidades(fabrica):
    jogos = fabrica(n_times=8, temporadas=3)
    m = Elo()
    treino = jogos[jogos["temporada"] < 2012]
    m.ajustar(treino)
    bloco = jogos[(jogos["temporada"] == 2012) & (jogos["rodada"] == 1)]
    p = m.prever(bloco).probs
    assert np.allclose(p.sum(axis=1), 1.0) and (p > 0).all()
    # quanto maior a diferença de Elo, maior a chance do mandante
    dif = m.prever(bloco).extras["diferenca"]
    assert np.all(np.diff(p[np.argsort(dif), 0]) >= -1e-12)


# ---------------------------------------------------------------------------
# Dixon-Coles
# ---------------------------------------------------------------------------
def test_matriz_de_placares_soma_um_e_casa_com_mev():
    mat = matriz_placares([1.6, 0.9], [1.0, 1.4], -0.1)
    assert mat.shape == (2, 11, 11)
    assert np.allclose(mat.sum(axis=(1, 2)), 1.0)
    p = probs_resultado(mat)
    assert np.allclose(p.sum(axis=1), 1.0)
    assert p[0, 0] > p[0, 2] and p[1, 2] > p[1, 0]
    # rho negativo puxa massa para 0x0 e 1x1 em relação ao Poisson independente
    indep = matriz_placares([1.6], [1.0], 0.0)[0]
    assert mat[0, 1, 1] > indep[1, 1] and mat[0, 0, 0] > indep[0, 0]


def _dados_aleatorios(rng, n_jogos=300, n_times=8, p=2):
    im = rng.integers(0, n_times, n_jogos)
    iv = (im + rng.integers(1, n_times, n_jogos)) % n_times
    return DadosDC(im, iv, rng.poisson(1.4, n_jogos).astype(float),
                   rng.poisson(1.0, n_jogos).astype(float), rng.uniform(0.2, 1, n_jogos),
                   rng.normal(size=(n_jogos, p)), rng.normal(size=(n_jogos, p)), n_times,
                   np.zeros(n_times), np.full(n_times, -0.1), 2.0, 0.5)


def test_gradiente_analitico_confere_com_numerico():
    rng = np.random.default_rng(2027)
    d = _dados_aleatorios(rng)
    theta = np.concatenate([[0.1, 0.25, -0.08], rng.normal(0, 0.2, 16), [0.1, -0.05]])
    _, g = objetivo(theta, d)
    num = approx_fprime(theta, lambda t: objetivo(t, d)[0], 1e-6)
    assert np.allclose(g, num, rtol=1e-4, atol=1e-3)


def test_dixon_coles_recupera_parametros(fabrica):
    rng = np.random.default_rng(7)
    n = 16
    ataque = rng.normal(0, 0.3, n)
    defesa = rng.normal(0, 0.3, n)
    jogos = fabrica(n_times=n, temporadas=10, semente=11, mu=0.1, mando=0.3, rho=-0.1,
                    ataque=ataque, defesa=defesa)
    idx = {f"T{i:02d}": i for i in range(n)}
    d = DadosDC(jogos["mandante_id"].map(idx).to_numpy(), jogos["visitante_id"].map(idx).to_numpy(),
                jogos["gols_mandante"].to_numpy(float), jogos["gols_visitante"].to_numpy(float),
                np.ones(len(jogos)), np.zeros((len(jogos), 0)), np.zeros((len(jogos), 0)), n,
                np.zeros(n), np.zeros(n), 1e-3, 1.0)
    theta = ajustar_dc(d)
    mu, h, rho = theta[:3]
    a, df = theta[3:3 + n], theta[3 + n:3 + 2 * n]
    assert h == pytest.approx(0.3, abs=0.06)
    assert rho == pytest.approx(-0.1, abs=0.08)
    # ataque e defesa só são identificados a menos de uma constante
    assert np.corrcoef(a, ataque)[0, 1] > 0.9 and np.corrcoef(df, defesa)[0, 1] > 0.9
    assert np.abs((a - a.mean()) - (ataque - ataque.mean())).max() < 0.2
    # média de gols do jogo de forças médias recuperada
    verdadeiro = 0.1 + ataque.mean() - defesa.mean()
    assert mu + a.mean() - df.mean() == pytest.approx(verdadeiro, abs=0.06)


def test_dixon_coles_recupera_covariavel():
    """Covariável por jogo e por lado entra no log da média de gols."""
    rng = np.random.default_rng(3)
    n_times, n_jogos, beta = 10, 4000, 0.25
    forca_a, forca_d = rng.normal(0, 0.2, n_times), rng.normal(0, 0.2, n_times)
    im = rng.integers(0, n_times, n_jogos)
    iv = (im + rng.integers(1, n_times, n_jogos)) % n_times
    xm, xv = rng.normal(size=n_jogos), rng.normal(size=n_jogos)
    lm = np.exp(0.1 + 0.3 + forca_a[im] - forca_d[iv] + beta * xm)
    lv = np.exp(0.1 + forca_a[iv] - forca_d[im] + beta * xv)
    gols = simular_placares(lm, lv, 0.0, rng)
    times = [f"T{i:02d}" for i in range(n_times)]
    datas = pd.Timestamp("2015-05-01") + pd.to_timedelta(np.arange(n_jogos) // 10, unit="D")
    jogos = pd.DataFrame({
        "jogo_id": np.arange(n_jogos).astype(str), "temporada": 2015, "rodada": 1, "data": datas,
        "mandante_id": [times[i] for i in im], "visitante_id": [times[i] for i in iv],
        "gols_mandante": gols[:, 0], "gols_visitante": gols[:, 1],
        "estilo_m": xm, "estilo_v": xv,
    })
    m = DixonColes(meia_vida=None, ridge=0.01, ridge_cov=0.01,
                   cov_mandante=["estilo_m"], cov_visitante=["estilo_v"])
    m.ajustar(jogos)
    bloco = jogos.iloc[:5].drop(columns=["gols_mandante", "gols_visitante"]).assign(
        data=datas[-1] + pd.Timedelta(days=1), temporada=2015)
    prev = m.prever(bloco)
    assert m.parametros["beta"][0] == pytest.approx(beta, abs=0.04)
    assert np.allclose(prev.probs.sum(axis=1), 1.0)


def test_promovido_entra_com_prior(fabrica):
    jogos = fabrica(n_times=8, temporadas=2, trocar_times=True)
    t1 = jogos[jogos["temporada"] == 2010]
    bloco = jogos[(jogos["temporada"] == 2011) & (jogos["rodada"] == 1)]
    m = DixonColes(meia_vida=180, ridge=2.0, forca_promovido=0.3)
    m.ajustar(t1)
    m.prever(bloco.drop(columns=["gols_mandante", "gols_visitante", "resultado"]))
    novo = (set(bloco["mandante_id"]) | set(bloco["visitante_id"])) - set(t1["mandante_id"])
    assert len(novo) == 1
    tm = novo.pop()
    assert m.parametros["promovidos"] == [tm]
    assert m.parametros["ataque"][tm] == pytest.approx(-0.3, abs=1e-4)
    assert m.parametros["defesa"][tm] == pytest.approx(-0.3, abs=1e-4)

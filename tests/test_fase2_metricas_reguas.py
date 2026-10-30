import numpy as np
import pandas as pd
import pytest

from modelos.metricas import calibracao, codificar, diferenca_pareada, log_loss, rps
from modelos.reguas import (Ingenua, Mercado, sem_margem_proporcional,
                            sem_margem_shin)


# ---------------------------------------------------------------------------
# RPS e log-loss com contas feitas à mão
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("probs, resultado, esperado", [
    ((1.0, 0.0, 0.0), "M", 0.0),                      # certeza e acerto
    ((0.0, 0.0, 1.0), "M", 1.0),                      # certeza e erro máximo
    ((0.5, 0.3, 0.2), "E", (0.5 ** 2 + 0.2 ** 2) / 2),  # acumuladas 0,5/0,8 x 0/1
    ((1 / 3, 1 / 3, 1 / 3), "M", ((2 / 3) ** 2 + (1 / 3) ** 2) / 2),
    ((0.6, 0.25, 0.15), "V", (0.6 ** 2 + 0.85 ** 2) / 2),
])
def test_rps_valores_conhecidos(probs, resultado, esperado):
    assert rps(np.array([probs]), codificar([resultado]))[0] == pytest.approx(esperado)


def test_rps_premia_errar_perto():
    # mesmo peso no resultado certo; errar para o empate custa menos que para o oposto
    y = codificar(["M"])
    perto = rps(np.array([[0.5, 0.5, 0.0]]), y)[0]
    longe = rps(np.array([[0.5, 0.0, 0.5]]), y)[0]
    assert perto == pytest.approx(0.125) and longe == pytest.approx(0.25)


def test_log_loss_valor_conhecido():
    assert log_loss(np.array([[0.5, 0.3, 0.2]]), codificar(["E"]))[0] == pytest.approx(-np.log(0.3))


def test_calibracao_conta_jogos():
    probs = np.array([[0.55, 0.25, 0.20], [0.52, 0.28, 0.20], [0.15, 0.25, 0.60]])
    tab = calibracao(probs, codificar(["M", "V", "V"]))
    linha = [t for t in tab if t["resultado"] == "M" and t["faixa"][0] == pytest.approx(0.5)][0]
    assert linha["jogos"] == 2 and linha["frequencia_observada"] == pytest.approx(0.5)
    assert sum(t["jogos"] for t in tab if t["resultado"] == "E") == 3


def test_diferenca_pareada_iguais_da_zero():
    a = np.array([0.2, 0.3, 0.1, 0.25])
    r = diferenca_pareada(a, a, [2012] * 4, [1, 1, 2, 2])
    assert r["diferenca"] == 0 and r["ic95"] == [0.0, 0.0] and r["blocos"] == 2


def test_diferenca_pareada_sinal_e_semente():
    rng = np.random.default_rng(1)
    b = rng.uniform(0.1, 0.3, 400)
    a = b - 0.01 + rng.normal(0, 0.002, 400)
    t, r = np.repeat([2012, 2013], 200), np.tile(np.repeat(np.arange(20), 10), 2)
    r1 = diferenca_pareada(a, b, t, r)
    r2 = diferenca_pareada(a, b, t, r)
    assert r1 == r2                       # semente fixa: mesmo IC
    assert r1["diferenca"] == pytest.approx(-0.01, abs=0.001)
    assert r1["ic95"][1] < 0              # A melhor, IC inteiro abaixo de zero
    assert r1["blocos"] == 40


# ---------------------------------------------------------------------------
# Odds sem margem
# ---------------------------------------------------------------------------
ODDS = [(1.50, 4.20, 7.00), (2.10, 3.30, 3.60), (3.40, 3.20, 2.25), (1.10, 9.0, 21.0)]


@pytest.mark.parametrize("odds", ODDS)
def test_proporcional_e_shin_somam_um(odds):
    assert sem_margem_proporcional(odds).sum() == pytest.approx(1.0, abs=1e-12)
    assert sem_margem_shin(odds).sum() == pytest.approx(1.0, abs=1e-12)
    assert (sem_margem_shin(odds) > 0).all()


def test_shin_tira_mais_margem_da_zebra():
    odds = (1.50, 4.20, 7.00)
    prop, shin = sem_margem_proporcional(odds), sem_margem_shin(odds)
    assert shin[0] > prop[0]   # favorito ganha probabilidade
    assert shin[2] < prop[2]   # zebra perde


def test_shin_sem_margem_igual_proporcional():
    odds = np.array([2.0, 4.0, 4.0])  # 1/2 + 1/4 + 1/4 = 1
    assert np.allclose(sem_margem_shin(odds), [0.5, 0.25, 0.25])


def test_mercado_prefere_pinnacle_e_marca_a_fonte():
    bloco = pd.DataFrame({
        "odd_pinnacle_mandante": [2.0, np.nan, np.nan],
        "odd_pinnacle_empate": [3.4, np.nan, np.nan],
        "odd_pinnacle_visitante": [3.9, np.nan, np.nan],
        "odd_media_mandante": [1.9, 2.5, np.nan],
        "odd_media_empate": [3.2, 3.1, np.nan],
        "odd_media_visitante": [3.7, 2.8, np.nan],
    })
    p = Mercado("proporcional").prever(bloco)
    assert list(p.extras["fonte"]) == ["pinnacle", "media", "sem_odds"]
    assert np.allclose(p.probs[0], sem_margem_proporcional([2.0, 3.4, 3.9]))
    assert np.allclose(p.probs[:2].sum(axis=1), 1.0) and np.isnan(p.probs[2]).all()


# ---------------------------------------------------------------------------
# Ingênua
# ---------------------------------------------------------------------------
def test_ingenua_usa_so_as_5_temporadas_anteriores():
    linhas = []
    for t in range(2003, 2010):
        # 2003 só de mandante; depois metade M, metade V
        res = ["M"] * 4 if t == 2003 else ["M", "M", "V", "V"]
        linhas += [{"temporada": t, "resultado": r} for r in res]
    passados = pd.DataFrame(linhas)
    m = Ingenua()
    m.ajustar(passados)
    assert np.allclose(m.frequencias(2009), [0.5, 0.0, 0.5])         # 2004 a 2008
    assert np.allclose(m.frequencias(2008), [0.6, 0.0, 0.4])         # 2003 a 2007
    assert np.allclose(m.frequencias(2004), [1.0, 0.0, 0.0])         # só 2003

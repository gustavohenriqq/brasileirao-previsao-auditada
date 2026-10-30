"""Testes dos fatores (modelos/fatores.py) e da incerteza no replay."""
import numpy as np
import pandas as pd
import pytest

from modelos.backtest import rodar_backtest
from modelos.dixon_coles import DixonColes
from modelos.elo import Elo
from modelos.fatores import (Animo, Calendario, Cansaco, ComFatores, ConfrontoDireto, Estilo,
                             Finalizacoes, Forma, Historia, MandoTime, Motivacao, Tecnico,
                             ajustar_logit_cov, faixa, misturar, preparar_estatisticas,
                             probs_logit_cov)
from modelos.replay import replay_tabela

CORTE_TEMPORADA, CORTE_RODADA = 2011, 10


def estatisticas_sinteticas(jogos, semente=1):
    rng = np.random.default_rng(semente)
    linhas = []
    for r in jogos.itertuples():
        for t, a, g in ((r.mandante_id, r.visitante_id, r.gols_mandante),
                        (r.visitante_id, r.mandante_id, r.gols_visitante)):
            linhas.append({"jogo_id": r.jogo_id, "time_id": t, "adversario_id": a,
                           "posse": float(rng.uniform(35, 65)),
                           "chutes_f": float(3 * g + rng.integers(3, 10)),
                           "sot_f": float(g + rng.integers(0, 4))})
    return preparar_estatisticas(pd.DataFrame(linhas))


def trocas_sinteticas():
    return pd.DataFrame({"time_id": ["T01", "T03", "T05", "T07"],
                         "data_troca": pd.to_datetime(["2010-07-01", "2011-06-01",
                                                       "2011-06-20", "2011-08-10"])})


def camadas(jogos, trocas):
    times = sorted(set(jogos["mandante_id"]) | set(jogos["visitante_id"]))
    return {
        "mando_time": ("dc", MandoTime(times, 3.0)),
        "forma": ("elo", Forma(5)),
        "animo": ("elo", Animo(4)),
        "motivacao": ("elo", Motivacao(1.0)),
        "confronto": ("elo", ConfrontoDireto(5)),
        "estilo": ("dc", Estilo(10)),
        "finalizacoes": ("dc", Finalizacoes(10)),
        "cansaco": ("elo", Cansaco(7)),
        "tecnico": ("elo", Tecnico(trocas, 5)),
    }


def embaralhar_futuro(jogos, estat, trocas, inicio, semente=7):
    """Placares, estatísticas e trocas de técnico a partir de `inicio` mudam;
    o passado fica igual."""
    rng = np.random.default_rng(semente)
    j = jogos.copy()
    fut = j.index[j["data"] >= inicio]
    j.loc[fut, "gols_mandante"] = rng.integers(0, 5, len(fut))
    j.loc[fut, "gols_visitante"] = rng.integers(0, 5, len(fut))
    gm, gv = j["gols_mandante"], j["gols_visitante"]
    j["resultado"] = np.where(gm > gv, "M", np.where(gm == gv, "E", "V"))
    ids_fut = set(j.loc[fut, "jogo_id"])
    e = estat.copy()
    m = e["jogo_id"].isin(ids_fut).to_numpy()
    for c in ("posse", "chutes_f", "sot_f", "chutes_c", "sot_c"):
        e.loc[m, c] = rng.permutation(e.loc[m, c].to_numpy()) * 1.7 + 3
    t = pd.concat([trocas, pd.DataFrame({"time_id": ["T00", "T02", "T04"],
                                         "data_troca": [inicio, inicio + pd.Timedelta(days=3),
                                                        inicio + pd.Timedelta(days=40)]})])
    return j, e, t.sort_values(["time_id", "data_troca"]).reset_index(drop=True)


@pytest.fixture(scope="module")
def base_sintetica():
    from conftest import gerar_jogos
    jogos = gerar_jogos(n_times=10, temporadas=2, trocar_times=True)
    return jogos, estatisticas_sinteticas(jogos), trocas_sinteticas()


NOMES = ["mando_time", "forma", "animo", "motivacao", "confronto", "estilo", "finalizacoes",
         "cansaco", "tecnico"]


@pytest.mark.parametrize("fator", NOMES)
def test_sem_vazamento_por_fator(base_sintetica, fator):
    """Mudar placares, estatísticas e trocas de técnico do futuro não muda as
    previsões feitas antes dele."""
    jogos, estat, trocas = base_sintetica
    temp = jogos[jogos["temporada"] == CORTE_TEMPORADA]
    inicio = temp.loc[temp["rodada"] == CORTE_RODADA, "data"].min()
    alt_j, alt_e, alt_t = embaralhar_futuro(jogos, estat, trocas, inicio)

    def rodar(j, e, t):
        base, cam = camadas(j, t)[fator]
        m = ComFatores(base, [cam], nome="f", estat=e)
        prev, _ = rodar_backtest(j, [m], CORTE_TEMPORADA, CORTE_TEMPORADA)
        cols = ["f_m", "f_e", "f_v"] + [c for c in prev.columns if c.startswith("f_")
                                         and c[2:] in cam.relatorio]
        return prev[prev["rodada"] <= CORTE_RODADA][cols].to_numpy(dtype=float), m

    a, m_a = rodar(jogos, estat, trocas)
    b, _ = rodar(alt_j, alt_e, alt_t)
    assert len(a) > 0
    np.testing.assert_allclose(a, b, rtol=0, atol=1e-12)
    # controle: a camada calculou algo que varia (não é tudo zero)
    feats = m_a.cache.to_numpy(dtype=float)
    assert np.nanstd(feats) > 0


@pytest.mark.parametrize("fator", ["forma", "animo", "motivacao", "estilo", "finalizacoes",
                                   "tecnico", "cansaco"])
def test_replay_congela_no_corte(base_sintetica, fator):
    """No replay, as previsões dos jogos futuros só dependem do que se sabia
    no corte: estatísticas e trocas posteriores não entram, e os fatores de
    forma, ânimo, motivação e estilo ficam com o valor do corte."""
    jogos, estat, trocas = base_sintetica
    temp = jogos[jogos["temporada"] == CORTE_TEMPORADA]
    inicio = temp.loc[temp["rodada"] == CORTE_RODADA + 1, "data"].min()
    passados = jogos[jogos["data"] < inicio]
    futuros = temp[temp["data"] >= inicio].drop(columns=["gols_mandante", "gols_visitante", "resultado"])
    _, alt_e, alt_t = embaralhar_futuro(jogos, estat, trocas, inicio)

    saidas = []
    for e, t in ((estat, trocas), (alt_e, alt_t)):
        base, cam = camadas(jogos, t)[fator]
        m = ComFatores(base, [cam], nome="f", estat=e)
        m.ajustar(passados)
        p = m.prever(futuros)
        saidas.append((p.probs, p.extras))
    np.testing.assert_allclose(saidas[0][0], saidas[1][0], atol=1e-12)
    if fator in ("forma", "animo", "motivacao"):
        ext = saidas[0][1]
        por_time = pd.DataFrame({"time": futuros["mandante_id"].to_numpy(), "v": ext[f"{fator}_m"]})
        assert (por_time.groupby("time")["v"].nunique() == 1).all()


def test_logit_com_covariavel_recupera_coeficiente():
    rng = np.random.default_rng(3)
    n = 20000
    x = rng.normal(0, 1.5, n)
    z = rng.normal(0, 1, n)
    s = 0.3 * x + 0.5 * z
    p = probs_logit_cov(s, -1.2, -0.1)
    u = rng.random(n)
    y = np.where(u < p[:, 0], 0, np.where(u < p[:, 0] + p[:, 1], 1, 2))
    th = ajustar_logit_cov(np.column_stack([x, z]), y, np.array([-1.0, 0.0, 0.2, 0.0]))
    assert abs(th[2] - 0.3) < 0.03 and abs(th[3] - 0.5) < 0.04


def test_elo_com_covariavel_zero_igual_ao_elo(fabrica):
    jogos = fabrica(n_times=8, temporadas=3)
    jogos["zero"] = 0.0
    from modelos.fatores import EloCov
    a, _ = rodar_backtest(jogos, [Elo(nome="a")], 2012, 2012)
    b, _ = rodar_backtest(jogos, [EloCov(["zero"], nome="b")], 2012, 2012)
    np.testing.assert_allclose(a[["a_m", "a_e", "a_v"]].to_numpy(), b[["b_m", "b_e", "b_v"]].to_numpy(),
                               atol=1e-4)


def test_ridge_vetor_no_dixon_coles(fabrica):
    jogos = fabrica(n_times=8, temporadas=2)
    jogos["c"] = np.random.default_rng(1).normal(size=len(jogos))
    m = DixonColes(meia_vida=180, cov_mandante=["c", "c"], cov_visitante=["c", "c"],
                   ridge_cov=np.array([1.0, 1e6]))
    prev, _ = rodar_backtest(jogos, [m], 2011, 2011)
    assert np.isfinite(prev[["dc_m", "dc_e", "dc_v"]].to_numpy()).all()
    assert abs(m.parametros["beta"][1]) < 1e-4   # ridge enorme zera o segundo coeficiente


def test_mistura_com_mercado():
    pm = np.array([[0.5, 0.3, 0.2], [0.2, 0.3, 0.5]])
    pk = np.array([[0.6, 0.25, 0.15], [0.3, 0.3, 0.4]])
    np.testing.assert_allclose(misturar(pm, pk, 0.0), pm)
    np.testing.assert_allclose(misturar(pm, pk, 1.0), pk)
    meio = misturar(pm, pk, 0.5)
    np.testing.assert_allclose(meio.sum(axis=1), 1.0)
    assert pm[0, 0] < meio[0, 0] < pk[0, 0]


def test_faixas_e_motivacao():
    assert [faixa(p, 20) for p in (1, 2, 6, 7, 12, 13, 16, 17, 20)] == [0, 1, 1, 2, 2, 3, 3, 4, 4]
    from conftest import gerar_jogos
    jogos = gerar_jogos(n_times=10, temporadas=1)
    H = jogos.copy()
    hist = Historia(H, np.full(len(H), 0.6))
    cal = Calendario(H)
    mot = Motivacao(1.0)
    inicio = H["data"].min().to_datetime64()
    fim = H.loc[H["rodada"] == 18, "data"].min().to_datetime64()
    assert sum(mot.tabela(hist, cal, 2010, inicio).values()) == 0      # começo: todos disputam
    assert sum(mot.tabela(hist, cal, 2010, fim).values()) > 0          # última rodada: alguém já decidiu
    assert sum(Motivacao(0.3).tabela(hist, cal, 2010, fim).values()) >= \
        sum(mot.tabela(hist, cal, 2010, fim).values())


def test_cansaco_e_tecnico():
    from conftest import gerar_jogos
    jogos = gerar_jogos(n_times=6, temporadas=1)
    cal = Calendario(jogos)
    hist = Historia(jogos, np.full(len(jogos), 0.6))
    g = jogos[jogos["rodada"] == 3].iloc[0]
    d = g["data"].to_datetime64()
    descanso = Cansaco(14).valor(hist, cal, g["mandante_id"], d, 2010, d)
    assert 6 <= descanso <= 8
    assert Cansaco(4).valor(hist, cal, g["mandante_id"], d, 2010, d) == 4
    primeiro = jogos[jogos["rodada"] == 1].iloc[0]
    assert Cansaco(7).valor(hist, cal, primeiro["mandante_id"], primeiro["data"].to_datetime64(),
                            2010, primeiro["data"].to_datetime64()) == 7

    time_ = "T02"
    dt = jogos.loc[jogos["rodada"] == 4, "data"].max() + pd.Timedelta(days=1)
    tec = Tecnico(pd.DataFrame({"time_id": [time_, "T03"],
                                "data_troca": [dt, jogos["data"].min() - pd.Timedelta(days=30)]}), k=2)
    seus = jogos[(jogos["mandante_id"] == time_) | (jogos["visitante_id"] == time_)]
    marcas = []
    for r in seus.itertuples():
        h = jogos.loc[jogos["rodada"] == r.rodada, "data"].min().to_datetime64()
        marcas.append(tec.valor(hist, cal, time_, h, 2010, r.data.to_datetime64()))
    rodadas = seus["rodada"].to_numpy()
    assert all(m == 0 for m, r in zip(marcas, rodadas) if r <= 4)
    assert [m for m, r in zip(marcas, rodadas) if r in (5, 6, 7)] == [1, 1, 0]
    # troca de pré-temporada não marca técnico novo
    g3 = jogos[(jogos["mandante_id"] == "T03") & (jogos["rodada"] <= 3)].iloc[0]
    h3 = jogos.loc[jogos["rodada"] == g3["rodada"], "data"].min().to_datetime64()
    assert tec.valor(hist, cal, "T03", h3, 2010, g3["data"].to_datetime64()) == 0


def test_incerteza_zero_igual_e_positiva_alarga_faixa(fabrica):
    jogos = fabrica(n_times=10, temporadas=3)
    for modelo in (Elo(), DixonColes(meia_vida=180, ridge=3.0)):
        a = replay_tabela(jogos, modelo, 2012, corte=5, alvos=(18,), n_sim=3000, detalhar=True)
        b = replay_tabela(jogos, modelo, 2012, corte=5, alvos=(18,), n_sim=3000, detalhar=True,
                          incerteza=0.0)
        assert a == b
        c = replay_tabela(jogos, modelo, 2012, corte=5, alvos=(18,), n_sim=3000, detalhar=True,
                          incerteza=0.3)
        largura = [np.mean([t["faixa_90"][1] - t["faixa_90"][0] for t in r[0]["por_time"]]) for r in (a, c)]
        assert largura[1] > largura[0]
        # pontos esperados quase iguais: o desvio tem média zero
        assert abs(c[0]["erro_pontos"] - a[0]["erro_pontos"]) < 1.0

import numpy as np

from modelos.backtest import COLUNAS_POS_JOGO, Previsao
from modelos.dixon_coles import DixonColes
from modelos.elo import Elo
from modelos.replay import posicoes, replay_tabela


class Oraculo:
    """Modelo trapaceiro (só para teste): sabe o placar real de cada jogo."""
    nome = "oraculo"

    def __init__(self, jogos):
        self.placar = dict(zip(jogos["jogo_id"], zip(jogos["gols_mandante"], jogos["gols_visitante"])))

    def ajustar(self, passados):
        self.max_treino = passados["data"].max()

    def prever(self, bloco):
        assert not set(COLUNAS_POS_JOGO) & set(bloco.columns)
        self.inicio = bloco["data"].min()
        mat = np.zeros((len(bloco), 11, 11))
        for k, jid in enumerate(bloco["jogo_id"]):
            gm, gv = self.placar[jid]
            mat[k, gm, gv] = 1.0
        return Previsao(np.full((len(bloco), 3), 1 / 3), placares=mat)


def test_oraculo_acerta_tudo(fabrica):
    jogos = fabrica(n_times=10, temporadas=2)  # 18 rodadas por temporada
    oraculo = Oraculo(jogos)
    linhas = replay_tabela(jogos, oraculo, 2011, corte=8, alvos=(12, 18), n_sim=200)
    assert oraculo.max_treino < oraculo.inicio      # treino antes da rodada 9
    for r in linhas:
        assert r["erro_pontos"] == 0 and r["cobertura_90"] == 1
        assert r["acerto_g4"] == 1 and r["acerto_z4"] == 1
        assert r["erro_posicao"] < 0.5   # só empates totais vão por sorteio


def test_replay_modelos_reais(fabrica):
    jogos = fabrica(n_times=10, temporadas=3)
    for modelo in (Elo(), DixonColes(meia_vida=180, ridge=3.0)):
        linhas = replay_tabela(jogos, modelo, 2012, corte=5, alvos=(12, 18), n_sim=2000)
        assert [r["alvo"] for r in linhas] == [12, 18]
        for r in linhas:
            assert 0 <= r["cobertura_90"] <= 1 and r["erro_pontos"] >= 0
            assert r["jogos_simulados"] > 0
        # quanto mais longe o alvo, mais jogos sorteados
        assert linhas[1]["jogos_simulados"] > linhas[0]["jogos_simulados"]


def test_posicoes_seguem_criterios():
    pontos = np.array([10, 10, 10, 7.0])
    vitorias = np.array([3, 3, 2, 2.0])
    saldo = np.array([2, 5, 9, 0.0])
    gp = np.zeros(4)
    assert list(posicoes(pontos, vitorias, saldo, gp, np.zeros(4))) == [2, 1, 3, 4]

import numpy as np
import pandas as pd

from modelos.backtest import COLUNAS_POS_JOGO, Previsao, montar_blocos, rodar_backtest
from modelos.dixon_coles import DixonColes
from modelos.elo import Elo
from modelos.reguas import Ingenua


class Espiao:
    """Modelo que só registra o que recebeu."""
    nome = "espiao"

    def __init__(self):
        self.registros = []

    def ajustar(self, passados):
        self.passados = passados

    def prever(self, bloco):
        assert not set(COLUNAS_POS_JOGO) & set(bloco.columns), "resultado chegou a prever()"
        self.registros.append({
            "max_treino": self.passados["data"].max() if len(self.passados) else None,
            "inicio_bloco": bloco["data"].min(),
            "treino": set(self.passados["jogo_id"]),
            "bloco": set(bloco["jogo_id"]),
        })
        return Previsao(np.full((len(bloco), 3), 1 / 3))


def jogos_com_adiado(fabrica):
    jogos = fabrica(n_times=6, temporadas=2)
    # um jogo da rodada 2 de 2010 adiado para depois da rodada 6
    alvo = jogos[(jogos["temporada"] == 2010) & (jogos["rodada"] == 2)].index[0]
    nova_data = jogos.loc[(jogos["temporada"] == 2010) & (jogos["rodada"] == 6), "data"].max() + pd.Timedelta(days=2)
    jogos.loc[alvo, "data"] = nova_data
    adiado = jogos.loc[alvo, "jogo_id"]
    return jogos.sort_values(["data", "jogo_id"]).reset_index(drop=True), adiado, nova_data


def test_treino_sempre_antes_do_bloco(fabrica):
    jogos, adiado, data_adiado = jogos_com_adiado(fabrica)
    espiao = Espiao()
    prev, _ = rodar_backtest(jogos, [espiao], 2010, 2011)

    for r in espiao.registros:
        if r["max_treino"] is not None:
            assert r["max_treino"] < r["inicio_bloco"]
        assert not r["treino"] & r["bloco"]
        # o adiado só entra no treino depois de jogado
        if adiado in r["treino"]:
            assert r["inicio_bloco"] > data_adiado
        elif r["inicio_bloco"] > data_adiado:
            raise AssertionError("adiado já jogado ficou fora do treino")
    # todo jogo é previsto uma vez, e o adiado junto com a rodada 2
    assert sorted(prev["jogo_id"]) == sorted(jogos["jogo_id"])
    bloco_r2 = [r for r in espiao.registros if adiado in r["bloco"]][0]
    assert bloco_r2["inicio_bloco"] < data_adiado


def test_blocos_em_ordem_de_data(fabrica):
    jogos, _, _ = jogos_com_adiado(fabrica)
    inicios = [b.primeira_data for b in montar_blocos(jogos)]
    assert inicios == sorted(inicios)


def test_modelos_reais_sem_vazamento(fabrica):
    jogos = fabrica(n_times=8, temporadas=3, trocar_times=True)
    vistos = []

    def gancho(bloco, passados):
        if len(passados):
            assert passados["data"].max() < bloco.primeira_data
        vistos.append(len(passados))

    modelos = [Ingenua(), Elo(), DixonColes(meia_vida=180, ridge=1.0)]
    prev, plac = rodar_backtest(jogos, modelos, 2011, 2012, guardar_placares=True, ao_treinar=gancho)
    assert vistos == sorted(vistos)
    for nome in ("ingenua", "elo", "dc"):
        soma = prev[[f"{nome}_m", f"{nome}_e", f"{nome}_v"]].sum(axis=1)
        assert np.allclose(soma, 1.0)
    assert len(plac["dc"]) == len(prev)


def test_previsao_nao_muda_se_o_resultado_do_bloco_mudar(fabrica):
    """Trocar o placar dos jogos de um bloco não pode mudar a previsão dele."""
    jogos = fabrica(n_times=8, temporadas=2)
    alterado = jogos.copy()
    m = (alterado["temporada"] == 2011) & (alterado["rodada"] == 5)
    alterado.loc[m, ["gols_mandante", "gols_visitante", "resultado"]] = [9, 0, "M"]

    def rodar(j):
        p, _ = rodar_backtest(j, [Elo(), DixonColes(meia_vida=180)], 2011, 2011)
        return p[(p["rodada"] == 5)].filter(regex="_(m|e|v)$").to_numpy()

    assert np.allclose(rodar(jogos), rodar(alterado))

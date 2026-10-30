"""Testes dos fatores de copa (modelos/fatores.py, fatores 11 e 12)."""
import numpy as np
import pandas as pd

from modelos.fatores import Calendario, CansacoCopas, CopaDepois


def d(s):
    return np.datetime64(pd.Timestamp(s), "ns")


def calendario():
    return Calendario(pd.DataFrame({
        "jogo_id": ["j1", "j2", "j3"], "temporada": [2015] * 3, "rodada": [1, 2, 3],
        "data": pd.to_datetime(["2015-05-10", "2015-05-17", "2015-05-24"]),
        "mandante_id": ["A", "B", "A"], "visitante_id": ["B", "A", "C"]}))


def copas():
    return pd.DataFrame({"time_id": ["A", "A", "C"],
                         "data": pd.to_datetime(["2015-05-14", "2015-05-20", "2015-05-27"])})


def test_cansaco_copas_conta_o_jogo_de_copa_no_meio_da_semana():
    cal, f = calendario(), CansacoCopas(copas(), teto=14)
    # A jogou a copa em 14/05: 3 dias até o jogo de 17/05 (a Série A sozinha daria 7)
    assert f.valor(None, cal, "A", None, 2015, d("2015-05-17")) == 3
    # B não joga copa: só a Série A conta
    assert f.valor(None, cal, "B", None, 2015, d("2015-05-17")) == 7
    # jogo de copa no mesmo dia ou depois não conta como anterior
    assert f.valor(None, cal, "A", None, 2015, d("2015-05-24")) == 4


def test_cansaco_copas_respeita_o_teto_e_o_primeiro_jogo():
    cal = calendario()
    assert CansacoCopas(copas(), teto=3).valor(None, cal, "B", None, 2015, d("2015-05-17")) == 3
    # C não tem jogo antes de 24/05: teto
    assert CansacoCopas(copas(), teto=7).valor(None, cal, "C", None, 2015, d("2015-05-24")) == 7


def test_copa_depois_olha_so_os_proximos_dias():
    cal = calendario()
    f3, f2 = CopaDepois(copas(), dias=3), CopaDepois(copas(), dias=2)
    assert f3.valor(None, cal, "A", None, 2015, d("2015-05-17")) == 1   # copa em 20/05
    assert f2.valor(None, cal, "A", None, 2015, d("2015-05-17")) == 0
    assert f3.valor(None, cal, "A", None, 2015, d("2015-05-10")) == 0   # copa só em 14/05
    assert f3.valor(None, cal, "C", None, 2015, d("2015-05-24")) == 1
    assert f3.valor(None, cal, "B", None, 2015, d("2015-05-17")) == 0   # sem copa


def test_camada_diferenca_dos_fatores_de_copa():
    cal = calendario()
    R = pd.DataFrame({"temporada": [2015], "mandante_id": ["B"], "visitante_id": ["A"],
                      "data": pd.to_datetime(["2015-05-17"])})
    h = np.array([d("2015-05-17")])
    c = CansacoCopas(copas(), teto=14).calcular(None, R, h, cal)
    assert c["cansaco_copas_dif"].iat[0] == 7 - 3
    c = CopaDepois(copas(), dias=3).calcular(None, R, h, cal)
    assert c["copa_depois_dif"].iat[0] == 0 - 1

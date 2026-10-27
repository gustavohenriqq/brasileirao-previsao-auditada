from ingestao.fontes import parse_openfootball

AMOSTRA = """\
= Brasileiro Série A 2020

▪ Matchday 1
  Sat Aug 8 2020
    19:00  Fortaleza EC            v Athletico Paranaense     0-2 (0-1)
           Coritiba FBC            v SC Internacional         0-1
  Sun Aug 9
    16:00  Flamengo RJ             v Atlético Mineiro         0-1 (0-0)

▪ Matchday 38
  Thu Feb 25 2021
    21:30  São Paulo FC            v CR Flamengo              2-1
           Grêmio FBPA             v Bahia BA
"""


def test_data_e_hora_valem_para_as_linhas_seguintes():
    jogos = parse_openfootball(AMOSTRA, 2020)
    assert [j["data"] for j in jogos[:3]] == ["2020-08-08", "2020-08-08", "2020-08-09"]
    assert jogos[1]["hora"] == "19:00"
    assert jogos[2]["hora"] == "16:00"


def test_rodada_placar_e_nomes():
    j = parse_openfootball(AMOSTRA, 2020)[0]
    assert j["rodada"] == 1
    assert (j["mandante"], j["visitante"]) == ("Fortaleza EC", "Athletico Paranaense")
    assert (j["placar_mandante"], j["placar_visitante"]) == ("0", "2")


def test_ano_novo_dentro_da_temporada_e_jogo_sem_placar():
    jogos = parse_openfootball(AMOSTRA, 2020)
    assert len(jogos) == 5
    ultimo = jogos[-1]
    assert ultimo["temporada"] == 2020
    assert ultimo["data"] == "2021-02-25"
    assert ultimo["rodada"] == 38
    assert ultimo["placar_mandante"] is None


def test_anotacao_entre_colchetes_nao_entra_no_nome():
    # 2026: "Chapecoense AF  v CR Vasco da Gama  [postponed]"
    texto = "▪ Matchday 21\n  Wed Feb 25 2026\n    Chapecoense AF          v CR Vasco da Gama         [postponed]\n"
    j = parse_openfootball(texto, 2026)[0]
    assert (j["mandante"], j["visitante"]) == ("Chapecoense AF", "CR Vasco da Gama")
    assert j["placar_mandante"] is None

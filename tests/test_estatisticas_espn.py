from ingestao.fontes import ESPN_ESTATISTICAS_COLS, linhas_estatisticas_espn


def _lado(lado, nome, placar, stats):
    return {
        "homeAway": lado,
        "team": {"displayName": nome},
        "score": placar,
        "statistics": [{"name": k, "abbreviation": "", "displayValue": v}
                       for k, v in stats.items()],
    }


EVENTO = {
    "id": "123",
    "date": "2026-05-31T21:30Z",
    "competitions": [{
        "status": {"type": {"name": "STATUS_FULL_TIME"}},
        "competitors": [
            _lado("home", "Palmeiras", "1", {"possessionPct": "52.4", "totalShots": "14",
                                              "totalGoals": "1"}),
            # Lado sem a lista: não gera linha (nem linha zerada).
            {"homeAway": "away", "team": {"displayName": "Chapecoense"}, "score": "0"},
        ],
    }],
}


def test_uma_linha_por_lado_com_estatisticas():
    linhas = linhas_estatisticas_espn(EVENTO, 2026)
    assert len(linhas) == 1
    linha = linhas[0]
    assert linha["lado"] == "home"
    assert linha["time"] == "Palmeiras"
    assert linha["temporada"] == 2026
    assert linha["possession_pct"] == "52.4"  # raw fica em texto
    assert linha["total_shots"] == "14"


def test_estatistica_ausente_vira_nulo_e_colunas_batem():
    linha = linhas_estatisticas_espn(EVENTO, 2026)[0]
    assert linha["won_corners"] is None
    assert set(linha) == set(ESPN_ESTATISTICAS_COLS)

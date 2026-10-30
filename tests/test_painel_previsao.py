"""Testes do gerador do painel de previsão (dashboards/powerbi_previsao/gerar_pbip.py).

Não abre o Power BI: confere o que o gerador monta antes de gravar. A
conferência dos números no motor fica em tools/conferir_painel.py.
"""
import importlib.util
import json
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def gerador():
    spec = importlib.util.spec_from_file_location(
        "gerar_pbip_previsao", RAIZ / "dashboards" / "powerbi_previsao" / "gerar_pbip.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def referencias(obj, tipo: str):
    """Todas as Property de Measure (ou Column) citadas num visual."""
    if isinstance(obj, dict):
        if tipo in obj and "Property" in obj[tipo]:
            yield obj[tipo]["Expression"]["SourceRef"]["Entity"], obj[tipo]["Property"]
        for v in obj.values():
            yield from referencias(v, tipo)
    elif isinstance(obj, list):
        for v in obj:
            yield from referencias(v, tipo)


def test_medidas_tem_nomes_unicos(gerador):
    nomes = [m[0] for m in gerador.medidas()]
    assert len(nomes) == len(set(nomes))


def test_visuais_so_citam_medidas_e_colunas_que_existem(gerador):
    medidas = {m[0] for m in gerador.medidas()}
    colunas = {(t, c[0]) for t, cols in gerador.COLUNAS.items() for c in cols}
    paginas = [gerador.pagina_chances(), gerador.pagina_posicoes(), gerador.pagina_jogos()]
    for pg in paginas:
        for v in pg.visuais:
            for tabela, nome in referencias(v, "Measure"):
                assert tabela == "_Medidas" and nome in medidas, (pg.exibicao, nome)
            for tabela, nome in referencias(v, "Column"):
                assert (tabela, nome) in colunas, (pg.exibicao, tabela, nome)
            # seletores por metadata também precisam apontar para algo que existe
            for sel in json.dumps(v, ensure_ascii=False).split('"metadata": "')[1:]:
                ref = sel.split('"', 1)[0]
                tabela, nome = ref.split(".", 1)
                assert nome in medidas if tabela == "_Medidas" else (tabela, nome) in colunas, ref


def test_nomes_de_visual_unicos_por_pagina(gerador):
    for pg in (gerador.pagina_chances(), gerador.pagina_posicoes(), gerador.pagina_jogos()):
        nomes = [v["name"] for v in pg.visuais]
        assert len(nomes) == len(set(nomes))


def test_escala_de_cor_cresce_com_a_chance(gerador):
    """Cada faixa é mais opaca que a anterior e a letra acompanha o fundo."""
    alfas = [a for _, a in gerador.FAIXAS]
    assert alfas == sorted(alfas)
    limites = [lim for lim, _ in gerador.FAIXAS if lim is not None]
    assert limites == sorted(limites) and gerador.MINIMO < limites[0]
    assert gerador.letra_para(gerador.misturar(gerador.LIMAO, 0.95)) == gerador.NAVY
    assert gerador.letra_para(gerador.misturar(gerador.LIMAO, 0.18)) == gerador.BRANCO


def test_texto_de_probabilidade_nao_arredonda_para_zero_nem_cem(gerador):
    dax = gerador.dax_texto_pct("[x]")
    assert '"<0,1%"' in dax and '">99,9%"' in dax and 'p = 0, BLANK ()' in dax
    inteiro = gerador.dax_texto_pct("[x]", inteiro=True)
    assert '"<1%"' in inteiro and '">99%"' in inteiro

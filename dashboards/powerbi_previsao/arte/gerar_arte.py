"""Gera a arte do painel de previsão (fundo, títulos e ícones) em PNG.

Mesmo desenho do painel da Fase 1: usa a bola, os ícones e o renderizador de
dashboards/powerbi/arte/gerar_arte.py (só leitura), com a saída apontada para
esta pasta. O rodapé diz que são probabilidades de um modelo, não dica de
aposta.

Datas e totais dos títulos saem de analise/resultados_fase2.json.

Uso: python dashboards/powerbi_previsao/arte/gerar_arte.py
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

PASTA = Path(__file__).resolve().parent
SAIDA = PASTA / "png"
RESULTADOS = PASTA.parents[2] / "analise" / "resultados_fase2.json"

_spec = importlib.util.spec_from_file_location(
    "arte_fase1", PASTA.parents[1] / "powerbi" / "arte" / "gerar_arte.py")
fase1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fase1)
# render() grava em PASTA/html e SAIDA do módulo: aponta os dois para cá
fase1.PASTA, fase1.SAIDA = PASTA, SAIDA
render, bola = fase1.render, fase1.bola

NAVY, NAVY2, PAINEL = fase1.NAVY, fase1.NAVY2, fase1.PAINEL
LIMAO, VIOLETA, BRANCO = fase1.LIMAO, fase1.VIOLETA, fase1.BRANCO

# Cabeçalho de cada página: chave, título grande, frase de baixo
PAGINAS = {
    "chances": ("CHANCES DE CADA TIME", "Quem fica com o título, a Libertadores e quem cai"),
    "posicoes": ("POSIÇÃO FINAL", "Probabilidade de cada time terminar em cada posição"),
    "jogos": ("JOGOS QUE FALTAM", "Probabilidades jogo a jogo e o teste do modelo em 2026"),
}


def fundo() -> None:
    """1920 x 1080, o mesmo fundo da Fase 1 com outro rodapé."""
    faixas = "".join(
        f'<div class="faixa" style="left:{x}px;width:{w}px;opacity:{o}"></div>'
        for x, w, o in [(980, 3, .10), (1060, 90, .035), (1220, 2, .14), (1300, 160, .03),
                        (1520, 4, .12), (1640, 60, .04), (-200, 120, .025), (120, 2, .08)])
    css = f"""
body{{background:
  radial-gradient(900px 600px at 105% -10%, rgba(93,77,255,.42), transparent 60%),
  radial-gradient(800px 520px at -8% 112%, rgba(93,77,255,.30), transparent 60%),
  radial-gradient(520px 340px at 50% -14%, rgba(198,245,0,.10), transparent 70%),
  linear-gradient(180deg, {NAVY2}, {NAVY});}}
.faixa{{position:absolute;top:-300px;height:1700px;background:linear-gradient(180deg,transparent,#fff 40%,transparent);transform:rotate(28deg);transform-origin:top left}}
.campo{{position:absolute;inset:0;opacity:.06}}
.topo{{position:absolute;left:0;right:0;top:0;height:6px;background:linear-gradient(90deg,{VIOLETA},{LIMAO} 50%,{VIOLETA})}}
.grade{{position:absolute;inset:0;background:
  linear-gradient(rgba(255,255,255,.025) 1px,transparent 1px) 0 0/48px 48px,
  linear-gradient(90deg,rgba(255,255,255,.025) 1px,transparent 1px) 0 0/48px 48px}}"""
    campo = f"""<svg class="campo" viewBox="0 0 1920 1080" preserveAspectRatio="none">
  <g fill="none" stroke="{BRANCO}" stroke-width="3">
    <rect x="60" y="60" width="1800" height="960" rx="6"/><line x1="960" y1="60" x2="960" y2="1020"/>
    <circle cx="960" cy="540" r="150"/><rect x="60" y="300" width="250" height="480"/>
    <rect x="1610" y="300" width="250" height="480"/></g></svg>"""
    rodape = (f'<div style="position:absolute;left:40px;right:40px;bottom:12px;display:flex;justify-content:space-between;'
              f'font:500 15px Inter;color:#B9BCDA"><span>Probabilidades de um modelo estatístico, não são dica de aposta'
              f' &nbsp;·&nbsp; Ensaio de estudo &nbsp;·&nbsp; Projeto independente, sem vínculo com a CBF</span>'
              f'<span style="color:{BRANCO};font-weight:700">Gustavo Henrique</span></div>')
    render("fundo", f'<div class="grade"></div>{campo}{faixas}<div class="topo"></div>{rodape}',
           1920, 1080, transparente=False, css=css)


def titulos() -> None:
    sim = json.loads(RESULTADOS.read_text(encoding="utf-8"))["simulacao_2026"]
    a, m, d = sim["ultimo_jogo_disputado"].split("-")
    olho = f"BRASILEIRÃO {a} &nbsp;·&nbsp; PREVISÃO &nbsp;·&nbsp; JOGOS ATÉ {d}/{m}"
    for chave, (grande, frase) in PAGINAS.items():
        texto = f"""<div>
    <div style="font:700 19px/1 Inter;letter-spacing:.32em;color:{LIMAO}">{olho}</div>
    <div class="larga" style="font-size:50px;line-height:1;white-space:nowrap;color:{BRANCO};margin-top:12px">{grande}</div>
    <div style="font:500 20px/1 Inter;color:#C9CCEA;margin-top:12px">{frase}</div>
  </div>"""
        bola_ = (f'<div style="border-radius:50%;box-shadow:0 0 0 4px {LIMAO},0 0 34px rgba(198,245,0,.45);'
                 f'line-height:0">{bola(BRANCO, NAVY, 100)}</div>')
        render(f"titulo_{chave}",
               f'<div style="display:flex;align-items:center;gap:26px;padding:6px 8px">{bola_}{texto}</div>', 1000, 132)
        # Variante sem a bola, para quando a logo do campeonato estiver no cabeçalho
        render(f"titulo_texto_{chave}", f'<div style="padding:6px 8px">{texto}</div>', 900, 132)


ICONES = {
    "icone_jogos": fase1.ICONES["icone_jogos"],
    "icone_titulo": fase1.ICONES["icone_vitorias"],
    # calendário
    "icone_restantes": '<rect x="10" y="14" width="44" height="40" rx="4"/><path d="M10 26h44M22 8v10M42 8v10"/><path d="M20 36h6M30 36h6M40 36h4M20 45h6M30 45h6"/>',
    # curva de distribuição sobre colunas: as simulações
    "icone_simulacoes": '<path d="M8 54h48"/><path d="M14 54V44M22 54V32M30 54V20M38 54V24M46 54V38M54 54V48" stroke-width="5"/><path d="M8 46C18 46 22 14 32 14S46 46 56 46" stroke-width="2.4"/>',
    # alvo: chance do favorito
    "icone_chance": '<circle cx="32" cy="32" r="22"/><circle cx="32" cy="32" r="13"/><circle cx="32" cy="32" r="4"/><path d="M32 4v10M32 50v10M4 32h10M50 32h10"/>',
    # seta para baixo sobre a linha: risco de queda
    "icone_queda": '<path d="M32 8v34"/><path d="M18 30l14 14 14-14"/><path d="M10 56h44"/>',
}


def icones() -> None:
    for nome, desenho in ICONES.items():
        miolo = (f'<svg width="44" height="44" viewBox="0 0 64 64" fill="none" stroke="{LIMAO}" '
                 f'stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round">{desenho}</svg>')
        corpo = f"""<div style="width:76px;height:76px;margin:4px;border-radius:50%;display:grid;place-items:center;
  background:radial-gradient(circle at 30% 25%, #23287A, {PAINEL});border:2px solid rgba(198,245,0,.55);
  box-shadow:0 0 22px rgba(198,245,0,.18)">{miolo}</div>"""
        render(nome, corpo, 84, 84)


def main() -> None:
    fundo()
    titulos()
    icones()
    print("Arte em", SAIDA)


if __name__ == "__main__":
    main()

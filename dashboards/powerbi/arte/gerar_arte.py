"""Gera a arte do painel (fundo, título, adesivo e ícones) em PNG.

Tudo desenhado aqui em SVG/HTML e renderizado com o Edge headless (fundo
transparente nos adesivos e ícones). Nada baixado de fora, sem escudo de clube
nem marca da CBF/Brasileirão: só bola, rede, troféu, casa, ônibus e cadeira.

Paleta inspirada na transmissão do campeonato: navy, limão neon e violeta.

Uso: python dashboards/powerbi/arte/gerar_arte.py
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

PASTA = Path(__file__).resolve().parent
SAIDA = PASTA / "png"
# Período da base (e a temporada em andamento) sai da análise, não do texto
RESULTADOS = PASTA.parents[2] / "analise" / "resultados_fase1.json"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

NAVY, NAVY2, PAINEL = "#0B0D26", "#11143A", "#14173A"
LIMAO, VIOLETA, BRANCO, LAVANDA = "#C6F500", "#5D4DFF", "#FFFFFF", "#8A8FB8"

FONTES = ('<link href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,700..900'
          '&family=Inter:wght@500;700&display=block" rel="stylesheet">')


def render(nome: str, corpo: str, w: int, h: int, transparente: bool = True, css: str = "") -> None:
    html = PASTA / "html" / f"{nome}.html"
    html.parent.mkdir(exist_ok=True)
    SAIDA.mkdir(exist_ok=True)
    fundo = "transparent" if transparente else NAVY
    html.write_text(f"""<!doctype html><html><head><meta charset="utf-8">{FONTES}
<style>*{{margin:0;padding:0;box-sizing:border-box}}html,body{{width:{w}px;height:{h}px;background:{fundo};overflow:hidden}}
.larga{{font-family:Archivo;font-stretch:125%;font-weight:900;letter-spacing:-.01em}}{css}</style></head>
<body>{corpo}</body></html>""", encoding="utf-8")
    args = [EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars",
            "--force-device-scale-factor=2", f"--window-size={w},{h}",
            "--virtual-time-budget=4000", f"--screenshot={SAIDA / (nome + '.png')}", html.as_uri()]
    if transparente:
        args.insert(1, "--default-background-color=00000000")
    subprocess.run(args, check=True, capture_output=True, timeout=120)


# ---------------------------------------------------------------------------
# Bola genérica (pentágono no centro e gomos cortados pela borda)
# ---------------------------------------------------------------------------
def bola(cor_fundo: str, cor_linha: str, tam: int = 100) -> str:
    """Bola clássica: pentágono central cheio, cinco hexágonos em volta e
    pentágonos cheios cortados pela borda."""
    import math

    def p(r, ang):
        a = math.radians(ang)
        return 50 + r * math.cos(a), 50 + r * math.sin(a)

    fmt = lambda pts: " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)  # noqa: E731
    angs = [-90 + 72 * i for i in range(5)]
    centro = [p(15, a) for a in angs]
    q = [p(28, a) for a in angs]
    mais = [p(40, a + 21) for a in angs]
    menos = [p(40, a - 21) for a in angs]
    pecas, linhas = [], []
    for i, a in enumerate(angs):
        # pentágono de borda (cheio, cortado pelo círculo)
        pecas.append(fmt([q[i], mais[i], p(60, a + 16), p(60, a - 16), menos[i]]))
        linhas.append((centro[i], q[i]))
        j = (i + 1) % 5
        linhas.append((mais[i], menos[j]))
        # costura que sai do meio do hexágono até a borda
        linhas.append(((mais[i][0] + menos[j][0]) / 2, (mais[i][1] + menos[j][1]) / 2)
                      and (((mais[i][0] + menos[j][0]) / 2, (mais[i][1] + menos[j][1]) / 2), p(60, a + 36)))
    segs = "".join(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}"/>' for a, b in linhas)
    polys = "".join(f'<polygon points="{s}" fill="{cor_linha}"/>' for s in pecas)
    return f"""<svg width="{tam}" height="{tam}" viewBox="0 0 100 100">
  <defs><clipPath id="c{tam}"><circle cx="50" cy="50" r="45"/></clipPath></defs>
  <circle cx="50" cy="50" r="46" fill="{cor_fundo}"/>
  <g clip-path="url(#c{tam})">{polys}
    <g stroke="{cor_linha}" stroke-width="3.4" stroke-linecap="round">{segs}</g>
    <polygon points="{fmt(centro)}" fill="{cor_linha}"/>
  </g>
  <circle cx="50" cy="50" r="46" fill="none" stroke="{cor_linha}" stroke-width="4"/></svg>"""


# ---------------------------------------------------------------------------
# Peças
# ---------------------------------------------------------------------------
def fundo() -> None:
    """1920 x 1080: navy com faixas diagonais de luz (estilo transmissão),
    brilhos violeta e limão e linhas de campo bem apagadas."""
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
              f'font:500 15px Inter;color:#B9BCDA"><span>Dados: base histórica do projeto, conferida entre fontes independentes'
              f' &nbsp;·&nbsp; Projeto independente, sem vínculo com a CBF</span>'
              f'<span style="color:{BRANCO};font-weight:700">Gustavo Henrique</span></div>')
    render("fundo", f'<div class="grade"></div>{campo}{faixas}<div class="topo"></div>{rodape}',
           1920, 1080, transparente=False, css=css)


def titulo() -> None:
    base = json.loads(RESULTADOS.read_text(encoding="utf-8"))["base"]
    andam = base["em_andamento"]
    parcial = (f" &nbsp;·&nbsp; {andam['temporada']} até a {andam['ultima_rodada']}ª rodada"
               if andam else "")
    corpo = f"""<div style="display:flex;align-items:center;gap:26px;padding:6px 8px">
  <div style="border-radius:50%;box-shadow:0 0 0 4px {LIMAO},0 0 34px rgba(198,245,0,.45);line-height:0">{bola(BRANCO, NAVY, 100)}</div>
  <div>
    <div style="font:700 19px/1 Inter;letter-spacing:.32em;color:{LIMAO}">BRASILEIRÃO SÉRIE A &nbsp;·&nbsp; {base["primeira_temporada"]} A {base["ultima_temporada"]}</div>
    <div class="larga" style="font-size:64px;line-height:.95;color:{BRANCO};margin-top:12px">MANDO DE CAMPO</div>
    <div style="font:500 20px/1 Inter;color:#C9CCEA;margin-top:12px">Quanto vale jogar em casa, com e sem torcida{parcial}</div>
  </div></div>"""
    render("titulo", corpo, 1000, 132)
    # Variante sem a bola, para quando a logo do campeonato estiver no cabeçalho
    corpo_texto = corpo.split("<div>", 1)[1].rsplit("</div></div>", 1)[0]
    render("titulo_texto", f'<div style="padding:6px 8px"><div>{corpo_texto}</div></div>', 900, 132)


def adesivo() -> None:
    """Adesivo 'SEM TORCIDA' com arquibancada vazia, girado e com borda branca."""
    cadeiras = "".join(
        f'<rect x="{18 + c * 22 + (r % 2) * 11}" y="{14 + r * 20}" width="15" height="12" rx="3" '
        f'fill="none" stroke="{NAVY}" stroke-width="2.6"/>'
        for r in range(3) for c in range(5))
    corpo = f"""<div style="padding:40px 34px">
<div style="transform:rotate(-6deg);display:inline-flex;align-items:center;gap:18px;padding:16px 26px 16px 18px;
  background:{LIMAO};border:6px solid {BRANCO};border-radius:22px;box-shadow:0 14px 30px rgba(0,0,0,.45)">
  <svg width="140" height="80" viewBox="0 0 140 80">{cadeiras}
    <line x1="8" y1="76" x2="132" y2="76" stroke="{NAVY}" stroke-width="3" stroke-linecap="round"/></svg>
  <div class="larga" style="font-size:40px;line-height:.92;color:{NAVY}">SEM<br>TORCIDA</div>
</div></div>"""
    render("adesivo_sem_torcida", corpo, 520, 220)


ICONES = {
    # traços em 64 x 64, desenhados com stroke
    # campinho: gramado, linha do meio, círculo central e as duas áreas
    "icone_jogos": '<rect x="6" y="14" width="52" height="36" rx="3"/><path d="M32 14v36"/><circle cx="32" cy="32" r="7"/><path d="M6 24h8v16H6M58 24h-8v16h8"/>',
    "icone_gols": None,  # bola
    "icone_vitorias": '<path d="M20 12h24v10a12 12 0 0 1-24 0z"/><path d="M20 16h-8a8 8 0 0 0 8 10M44 16h8a8 8 0 0 1-8 10"/><path d="M32 34v8M24 50h16M26 42h12v8H26z"/>',
    "icone_casa": '<path d="M10 30 32 12l22 18"/><path d="M16 26v24h32V26"/><path d="M28 50V38h8v12"/>',
    # aviãozinho: jogo fora de casa
    "icone_fora": '<path d="M32 6C35 6 36 9 36 12V25L56 36V42L36 36V49L42 54V58L32 55L22 58V54L28 49V36L8 42V36L28 25V12C28 9 29 6 32 6Z"/>',
    "icone_sem_torcida": '<path d="M20 12h24v18H20z"/><path d="M16 30h32v8H16z"/><path d="M20 38v14M44 38v14"/><path d="M8 8l48 48" stroke-width="4"/>',
}


def icones() -> None:
    for nome, desenho in ICONES.items():
        cor = LIMAO
        miolo = (bola(PAINEL, cor, 44) if desenho is None else
                 f'<svg width="44" height="44" viewBox="0 0 64 64" fill="none" stroke="{cor}" '
                 f'stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round">{desenho}</svg>')
        corpo = f"""<div style="width:76px;height:76px;margin:4px;border-radius:50%;display:grid;place-items:center;
  background:radial-gradient(circle at 30% 25%, #23287A, {PAINEL});border:2px solid rgba(198,245,0,.55);
  box-shadow:0 0 22px rgba(198,245,0,.18)">{miolo}</div>"""
        render(nome, corpo, 84, 84)


def main() -> None:
    fundo()
    titulo()
    adesivo()
    icones()
    print("Arte em", SAIDA)


if __name__ == "__main__":
    main()

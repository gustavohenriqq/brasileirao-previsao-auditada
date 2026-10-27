"""Card do post da Fase 1 (1080 x 1350, formato retrato do LinkedIn).

Lê analise/resultados_fase1.json (nenhum número digitado à mão), monta o HTML
na identidade visual "dark premium" e renderiza em PNG com o Edge ou o Chrome
em modo headless.

Saída: docs/img/fase1_card.html e docs/img/fase1_card.png
Uso:   python analise/card_fase1.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ESCALA_MAX = 1.0  # eixo das barras: 0 a 1 ponto por jogo

NAVEGADORES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
]


def br(x: float, casas: int = 2) -> str:
    return f"{x:.{casas}f}".replace(".", ",")


def pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def assentos(cheio: bool) -> str:
    """Arquibancada em miniatura: 3 fileiras de 6 cadeiras, cheias ou vazias."""
    classe = "cad cheia" if cheio else "cad vazia"
    return '<div class="arquibancada">' + "".join(
        f'<i class="{classe}"></i>' for _ in range(18)) + "</div>"


def linha(rotulo: str, anos: str, m: dict, cor: str, cheio: bool, fantasma: dict | None = None) -> str:
    v = m["vantagem_pontos"]
    lo, hi = m["ic95"]["vantagem_pontos"]
    w = lambda x: f"{100 * x / ESCALA_MAX:.2f}%"  # noqa: E731
    extra = ""
    if fantasma:
        ref = fantasma["referencia"]
        extra = (f'<div class="fantasma" style="left:{w(v)};width:{w(ref - v)}">'
                 f'<span>{fantasma["texto"]}</span></div>')
    return f"""
    <div class="linha">
      <div class="rotulo">
        {assentos(cheio)}
        <div><b>{rotulo}</b><small>{anos}</small></div>
      </div>
      <div class="trilho">
        {extra}
        <div class="barra {cor}" style="width:{w(v)}"></div>
        <div class="ic" style="left:{w(lo)};width:{w(hi - lo)}"></div>
        <div class="valor" style="left:calc({w(max(hi, fantasma['referencia'] if fantasma else hi))} + 18px)">+{br(v)}</div>
        <div class="detalhe">mandante <b>{br(m["pontos_por_jogo_mandante"])}</b> &nbsp;&middot;&nbsp; visitante <b>{br(m["pontos_por_jogo_visitante"])}</b> ponto/jogo</div>
      </div>
    </div>"""


def montar_html(r: dict) -> str:
    p = r["periodos"]
    antes, sem, depois = p["com_torcida_2015_2019"], p["sem_torcida"], p["com_torcida_depois"]
    dif = r["diferencas_vantagem_pontos"]["sem_torcida_menos_2015_2019"]
    queda = dif["queda_relativa"]
    mt = r["mesmo_time"]
    tend = r["contra_tendencia"]["periodos"]["sem_torcida"]
    base = r["base"]
    ultima = base["ultima_temporada"]
    andam = base["em_andamento"]
    parcial = f"; {andam['temporada']} até a {andam['ultima_rodada']}ª rodada" if andam else ""
    jogos = f"{base['jogos']:,}".replace(",", ".")

    # Conferências de coerência antes de desenhar (o card não pode contradizer o JSON).
    assert sem["ic95"]["vantagem_pontos"][0] > 0, "o IC sem torcida toca o zero: o título 'não sumiu' cairia"
    assert dif["ic95"][1] < 0, "a queda não é clara: o título cairia"
    assert tend["ic95"][1] < 0 and mt["ic95"][1] < 0

    ticks = "".join(
        f'<span style="left:{100 * t / ESCALA_MAX:.0f}%">{br(t, 2 if t % 0.5 else 1)}</span>'
        for t in (0, 0.25, 0.5, 0.75, 1.0))
    grade = "".join(f'<i style="left:{100 * t / ESCALA_MAX:.0f}%"></i>' for t in (0.25, 0.5, 0.75, 1.0))

    linhas = (
        linha("Com torcida", "2015 a 2019", antes, "azul", True)
        + linha("Sem torcida", "2020 e 2021", sem, "magenta", False,
                fantasma={"referencia": antes["vantagem_pontos"], "texto": f"&minus;{pct(queda)}"})
        + linha("Torcida voltou", f"2022 a {ultima}", depois, "azul", True)
    )

    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>Mando de campo sem torcida</title>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@700;800;900&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;700&display=block" rel="stylesheet">
<style>
:root {{
  --fundo:#080B15; --texto:#C3C2B7; --apagado:#8b93a7; --branco:#fff;
  --ouro:#C98500; --ouro-claro:#f0b43a; --azul:#4A86E8; --magenta:#E0559A;
}}
* {{ box-sizing:border-box; margin:0; padding:0; }}
html, body {{ width:1080px; height:1350px; }}
body {{
  background:
    radial-gradient(900px 520px at 85% -8%, rgba(201,133,0,.16), transparent 60%),
    radial-gradient(700px 500px at -10% 110%, rgba(74,134,232,.10), transparent 60%),
    linear-gradient(rgba(148,163,184,.045) 1px, transparent 1px) 0 0/48px 48px,
    linear-gradient(90deg, rgba(148,163,184,.045) 1px, transparent 1px) 0 0/48px 48px,
    var(--fundo);
  color:var(--texto); font-family:Inter, system-ui, sans-serif;
  padding:72px 72px 56px; display:flex; flex-direction:column; overflow:hidden;
}}
.kicker {{ font:700 17px/1 'JetBrains Mono', monospace; letter-spacing:.16em; color:var(--ouro); text-transform:uppercase; }}
h1 {{ font:900 66px/1.04 Archivo, sans-serif; color:var(--branco); letter-spacing:-.02em; margin-top:26px; }}
h1 em {{ font-style:normal; color:var(--ouro-claro); }}

.painel {{
  margin-top:56px; padding:44px 44px 36px; border-radius:22px;
  background:linear-gradient(158deg, rgba(28,38,62,.92), rgba(15,22,38,.92));
  border:1px solid rgba(255,255,255,.07); box-shadow:0 24px 60px rgba(0,0,0,.45);
}}
.cabeca {{ display:flex; justify-content:space-between; align-items:baseline; margin-left:262px; }}
.cabeca b {{ font:600 19px/1.3 Inter; color:var(--branco); }}
.cabeca b span {{ color:var(--apagado); font-weight:500; }}

.linha {{ display:flex; align-items:center; height:164px; }}
.rotulo {{ width:262px; display:flex; align-items:center; gap:16px; }}
.rotulo b {{ display:block; font:800 25px/1.1 Archivo; color:var(--branco); }}
.rotulo small {{ display:block; margin-top:6px; font:500 15px/1 'JetBrains Mono'; color:var(--apagado); }}
.arquibancada {{ display:grid; grid-template-columns:repeat(6, 7px); gap:3px; flex:none; }}
.cad {{ width:7px; height:7px; border-radius:2px; }}
.cheia {{ background:var(--texto); }}
.vazia {{ border:1.4px solid rgba(195,194,183,.45); }}

.trilho {{ position:relative; flex:1; height:66px; margin-right:120px; }}
.barra {{ position:absolute; left:0; top:0; height:100%; border-radius:0 12px 12px 0; }}
.barra.azul {{ background:linear-gradient(90deg, rgba(74,134,232,.55), var(--azul)); box-shadow:0 0 34px rgba(74,134,232,.28); }}
.barra.magenta {{ background:linear-gradient(90deg, rgba(224,85,154,.55), var(--magenta)); box-shadow:0 0 34px rgba(224,85,154,.30); }}
.ic {{ position:absolute; top:50%; height:3px; margin-top:-1.5px; background:rgba(255,255,255,.85); border-radius:2px; }}
.ic::before, .ic::after {{ content:''; position:absolute; top:-8px; width:3px; height:19px; background:rgba(255,255,255,.85); border-radius:2px; }}
.ic::before {{ left:-1px; }} .ic::after {{ right:-1px; }}
.valor {{ position:absolute; top:50%; transform:translateY(-50%); font:900 40px/1 Archivo; color:var(--branco); letter-spacing:-.01em; white-space:nowrap; }}
.detalhe {{ position:absolute; left:0; top:calc(100% + 12px); font:500 16px/1 'JetBrains Mono'; color:var(--apagado); white-space:nowrap; }}
.detalhe b {{ color:var(--texto); font-weight:700; }}
.fantasma {{
  position:absolute; top:0; height:100%; border:2px dashed rgba(240,180,58,.75); border-left:none;
  border-radius:0 12px 12px 0; background:repeating-linear-gradient(135deg, rgba(240,180,58,.10) 0 8px, transparent 8px 16px);
  display:flex; align-items:center; justify-content:center;
}}
.fantasma span {{ position:absolute; top:-44px; font:900 32px/1 Archivo; color:var(--ouro-claro); text-shadow:0 0 22px rgba(240,180,58,.55); }}

.eixo {{ position:relative; height:26px; margin:6px 120px 0 262px; border-top:1px solid rgba(255,255,255,.14); }}
.eixo span {{ position:absolute; top:10px; transform:translateX(-50%); font:500 14px/1 'JetBrains Mono'; color:var(--apagado); }}
.eixo span:first-child {{ transform:none; }}
.grade {{ position:absolute; left:262px; right:120px; top:0; bottom:0; pointer-events:none; }}
.grade i {{ position:absolute; top:0; bottom:0; border-left:1px dashed rgba(255,255,255,.06); }}
.corpo {{ position:relative; margin-top:14px; }}

.checks {{ display:grid; grid-template-columns:repeat(3, 1fr); gap:16px; margin-top:36px; }}
.check {{
  padding:24px 22px 22px; border-radius:16px; background:rgba(255,255,255,.035);
  border:1px solid rgba(255,255,255,.07);
}}
.check .n {{ font:900 30px/1 Archivo; color:var(--branco); }}
.check .n i {{ font-style:normal; color:var(--ouro-claro); }}
.check p {{ margin-top:9px; font:500 16px/1.32 Inter; color:var(--texto); }}

.rodape {{ margin-top:auto; padding-top:20px; border-top:1px solid rgba(255,255,255,.08);
  display:flex; justify-content:space-between; align-items:center; font:400 14px/1.4 Inter; color:var(--apagado); }}
.assina {{ display:flex; align-items:center; gap:10px; font:700 15px Inter; color:var(--branco); white-space:nowrap; }}
</style></head>
<body>
  <div class="kicker">Brasileirão Série A &middot; mando de campo</div>
  <h1>Sem torcida, a vantagem de jogar em casa caiu {pct(queda)}. <em>Mas não sumiu.</em></h1>

  <div class="painel">
    <div class="cabeca"><b>Pontos por jogo do mandante a mais que o visitante <span>(média)</span></b></div>
    <div class="corpo">
      <div class="grade">{grade}</div>
      {linhas}
    </div>
    <div class="eixo">{ticks}</div>
  </div>

  <div class="checks">
    <div class="check"><div class="n">{sem["jogos"]} <i>jogos</i></div><p>sem público, de ago/2020 a set/2021</p></div>
    <div class="check"><div class="n">{mt["times_com_queda"]} de {mt["times"]} <i>times</i></div><p>renderam menos em casa que eles mesmos em 2015 a 2019</p></div>
    <div class="check"><div class="n"><i>&minus;</i>{br(-tend["observado_menos_esperado"])}</div><p>ponto por jogo abaixo do que a tendência de 2003 a 2019 previa</p></div>
  </div>

  <div class="rodape">
    <span>{jogos} jogos da Série A ({base["primeira_temporada"]} a {ultima}{parcial}), conferidos em 5 fontes.<br>Traço branco: intervalo de confiança de 95%.</span>
    <span class="assina">
      <svg width="26" height="26" viewBox="0 0 26 26" fill="none" stroke="#C98500" stroke-width="2">
        <circle cx="5" cy="13" r="3" fill="#C98500"/><circle cx="21" cy="5" r="3" fill="#C98500"/><circle cx="21" cy="21" r="3" fill="#C98500"/>
        <path d="M8 12 L18 6 M8 14 L18 20"/></svg>
      Gustavo Henrique
    </span>
  </div>
</body></html>"""


def renderizar(html: Path, png: Path) -> None:
    exe = next((n for n in NAVEGADORES if Path(n).exists()), None) or shutil.which("msedge") or shutil.which("chrome")
    if not exe:
        sys.exit("Precisa do Edge ou do Chrome instalado para gerar o PNG (o HTML já foi gravado).")
    subprocess.run([
        exe, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        "--force-device-scale-factor=2", "--window-size=1080,1350",
        "--virtual-time-budget=8000", f"--screenshot={png}", html.as_uri(),
    ], check=True, capture_output=True, timeout=120)


def main() -> None:
    r = json.loads((RAIZ / "analise" / "resultados_fase1.json").read_text(encoding="utf-8"))
    pasta = RAIZ / "docs" / "img"
    pasta.mkdir(parents=True, exist_ok=True)
    html, png = pasta / "fase1_card.html", pasta / "fase1_card.png"
    html.write_text(montar_html(r), encoding="utf-8")
    renderizar(html, png)
    print(f"Card em {png.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()

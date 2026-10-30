"""Escudos dos 20 times da Série A de 2026 para o painel de previsão.

Reaproveita os escudos já baixados pelo painel da Fase 1
(dashboards/powerbi/arte/escudos, só leitura) e baixa os que faltam da
Wikipédia em português, do mesmo jeito (imagem principal da página do clube,
API pageimages). A logo do campeonato também vem de lá, se existir.
Escudos e logo são marcas: ficam fora do Git, com a origem em
arte/escudos/fontes.csv.

Saída: arte/escudos/<time_id>.png (64 x 64, fundo transparente)
Uso:   python dashboards/powerbi_previsao/arte/baixar_escudos.py
"""
from __future__ import annotations

import csv
import io
import json
import shutil
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

PASTA = Path(__file__).resolve().parent / "escudos"
RAIZ = Path(__file__).resolve().parents[3]
FASE1 = RAIZ / "dashboards" / "powerbi" / "arte"
TIMES = RAIZ / "analise" / "simulacao_2026_times.csv"
AGENTE = "projeto-brasileirao/0.1 (estudo; dados de portfolio)"

# Só os que o painel da Fase 1 não tem
PAGINAS = {
    "Bragantino": "Red Bull Bragantino",
    "Mirassol": "Mirassol Futebol Clube",
    "Remo": "Clube do Remo",
}


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def baixar(faltam: dict[str, str]) -> list[dict]:
    api = ("https://pt.wikipedia.org/w/api.php?action=query&format=json&redirects=1"
           "&prop=pageimages&piprop=thumbnail|name&pithumbsize=96&titles="
           + urllib.parse.quote("|".join(faltam.values())))
    dados = json.loads(get(api))
    redir = {r["from"]: r["to"] for r in dados["query"].get("redirects", [])}
    por_titulo = {p["title"]: p for p in dados["query"]["pages"].values()}
    fontes = []
    for time_id, pagina in faltam.items():
        p = por_titulo.get(redir.get(pagina, pagina), {})
        thumb = p.get("thumbnail", {}).get("source")
        if not thumb:
            print(f"  sem imagem: {time_id} ({pagina})")
            continue
        img = Image.open(io.BytesIO(get(thumb))).convert("RGBA")
        img.thumbnail((64, 64), Image.LANCZOS)
        quadro = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        quadro.paste(img, ((64 - img.width) // 2, (64 - img.height) // 2), img)
        quadro.save(PASTA / f"{time_id}.png", optimize=True)
        fontes.append({"time_id": time_id, "pagina": pagina, "arquivo": p.get("pageimage"), "url": thumb})
        time.sleep(0.3)
    return fontes


def main() -> None:
    PASTA.mkdir(exist_ok=True)
    with TIMES.open(encoding="utf-8") as f:
        times = [r["time_id"] for r in csv.DictReader(f)]
    with (FASE1 / "escudos" / "fontes.csv").open(encoding="utf-8") as f:
        fontes_fase1 = {r["time_id"]: r for r in csv.DictReader(f)}

    fontes, faltam = [], {}
    for t in times:
        origem = FASE1 / "escudos" / f"{t}.png"
        if origem.exists():
            shutil.copy(origem, PASTA / origem.name)
            fontes.append(fontes_fase1[t])
        elif t in PAGINAS:
            faltam[t] = PAGINAS[t]
        else:
            raise SystemExit(f"sem escudo nem página da Wikipédia para {t}")
    if faltam:
        fontes += baixar(faltam)
    with (PASTA / "fontes.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["time_id", "pagina", "arquivo", "url"])
        w.writeheader()
        w.writerows(sorted(fontes, key=lambda r: r["time_id"]))
    print(f"{len(fontes)} de {len(times)} escudos em {PASTA}")

    logo = FASE1 / "png" / "logo_brasileirao.png"
    if logo.exists():
        destino = PASTA.parent / "png"
        destino.mkdir(exist_ok=True)
        shutil.copy(logo, destino / logo.name)
        print(f"logo copiada do painel da Fase 1 para {destino}")


if __name__ == "__main__":
    main()

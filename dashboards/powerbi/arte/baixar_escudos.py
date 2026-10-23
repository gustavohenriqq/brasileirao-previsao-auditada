"""Baixa os escudos dos clubes para a tabela "cada time contra ele mesmo".

Fonte: a imagem principal (infobox) da página de cada clube na Wikipédia em
português, em miniatura de 96 px, pela API pageimages. Escudos são marcas dos
clubes; o uso aqui é ilustrativo, num projeto de estudo sem fins comerciais.
A origem de cada arquivo fica em arte/escudos/fontes.csv.

Saída: arte/escudos/<time_id>.png (64 x 64, fundo transparente)
Uso:   python dashboards/powerbi/arte/baixar_escudos.py
"""
from __future__ import annotations

import csv
import io
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

PASTA = Path(__file__).resolve().parent / "escudos"
AGENTE = "projeto-brasileirao/0.1 (estudo; dados de portfolio)"

PAGINAS = {
    "America-MG": "América Futebol Clube (Belo Horizonte)",
    "Athletico-PR": "Club Athletico Paranaense",
    "Atletico-GO": "Atlético Clube Goianiense",
    "Atletico-MG": "Clube Atlético Mineiro",
    "Bahia": "Esporte Clube Bahia",
    "Botafogo-RJ": "Botafogo de Futebol e Regatas",
    "Ceara": "Ceará Sporting Club",
    "Chapecoense": "Associação Chapecoense de Futebol",
    "Corinthians": "Sport Club Corinthians Paulista",
    "Coritiba": "Coritiba Foot Ball Club",
    "Flamengo": "Clube de Regatas do Flamengo",
    "Fluminense": "Fluminense Football Club",
    "Fortaleza": "Fortaleza Esporte Clube",
    "Goias": "Goiás Esporte Clube",
    "Gremio": "Grêmio Foot-Ball Porto Alegrense",
    "Internacional": "Sport Club Internacional",
    "Palmeiras": "Sociedade Esportiva Palmeiras",
    "Santos": "Santos Futebol Clube",
    "Sao Paulo": "São Paulo Futebol Clube",
    "Sport": "Sport Club do Recife",
    "Vasco": "Club de Regatas Vasco da Gama",
    # tradicionais que jogaram a Série B sem torcida
    "Cruzeiro": "Cruzeiro Esporte Clube",
    "Vitoria": "Esporte Clube Vitória",
    "Figueirense": "Figueirense Futebol Clube",
    "Ponte Preta": "Associação Atlética Ponte Preta",
}


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def main() -> None:
    PASTA.mkdir(exist_ok=True)
    titulos = "|".join(PAGINAS.values())
    api = ("https://pt.wikipedia.org/w/api.php?action=query&format=json&redirects=1"
           "&prop=pageimages&piprop=thumbnail|name&pithumbsize=96&titles=" + urllib.parse.quote(titulos))
    dados = json.loads(get(api))
    redir = {r["from"]: r["to"] for r in dados["query"].get("redirects", [])}
    por_titulo = {p["title"]: p for p in dados["query"]["pages"].values()}
    fontes = []
    for time_id, pagina in PAGINAS.items():
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
    with (PASTA / "fontes.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["time_id", "pagina", "arquivo", "url"])
        w.writeheader()
        w.writerows(fontes)
    print(f"{len(fontes)} de {len(PAGINAS)} escudos em {PASTA}")
    baixar_logo()


LOGO = ("https://upload.wikimedia.org/wikipedia/commons/thumb/2/2b/"
        "Campeonato_Brasileiro_S%C3%A9rie_A_logo_%282024%29.svg/"
        "960px-Campeonato_Brasileiro_S%C3%A9rie_A_logo_%282024%29.svg.png")


def baixar_logo() -> None:
    """Logo do campeonato (Wikimedia Commons, marcada como domínio público e
    marca registrada). Fica só o escudo: o nome do patrocinador, uma casa de
    apostas, é cortado, porque o projeto não faz propaganda de aposta."""
    img = Image.open(io.BytesIO(get(LOGO))).convert("RGBA")
    escudo = img.crop((0, 0, img.width, int(img.height * 0.763)))
    escudo = escudo.crop(escudo.getbbox())
    destino = PASTA.parent / "png" / "logo_brasileirao.png"
    escudo.save(destino)
    print(f"logo em {destino} ({escudo.width} x {escudo.height})")


if __name__ == "__main__":
    main()

"""Fase 1: sem torcida (2020 e 2021), o mando de campo sumiu?

Lê marts.mando_jogos, calcula a vantagem do mandante por período com
intervalo de confiança de 95% (bootstrap), confere os números contra
marts.mando_por_periodo (segunda conta, em SQL) e grava:

- analise/resultados_fase1.json  (fonte de todos os números do documento)
- docs/img/fase1_vantagem_por_temporada.png

Uso: python analise/fase1_mando.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ingestao.comum import RAIZ, conectar  # noqa: E402

SEMENTE = 2027
REPETICOES = 10_000
PERIODOS = ["com_torcida_antes", "sem_torcida", "volta_parcial", "com_torcida_depois"]


# ---------------------------------------------------------------------------
# Dados
# ---------------------------------------------------------------------------
def ler_jogos() -> dict[str, np.ndarray]:
    with conectar() as con, con.cursor() as cur:
        cur.execute("""
            select temporada, rodada, periodo, mandante_id, visitante_id,
                   resultado, pontos_mandante, pontos_visitante, saldo_mandante
            from marts.mando_jogos
            order by data, jogo_id
        """)
        linhas = cur.fetchall()
    cols = ["temporada", "rodada", "periodo", "mandante", "visitante",
            "resultado", "pm", "pv", "saldo"]
    d = {c: np.array([l[i] for l in linhas]) for i, c in enumerate(cols)}
    for c in ("temporada", "rodada", "pm", "pv", "saldo"):
        d[c] = d[c].astype(int)
    return d


def ler_sql_por_periodo() -> dict[str, dict]:
    with conectar() as con, con.cursor() as cur:
        cur.execute("""
            select periodo, jogos, taxa_vitoria_mandante, taxa_empate,
                   taxa_vitoria_visitante, pontos_por_jogo_mandante,
                   pontos_por_jogo_visitante, vantagem_pontos, saldo_medio_mandante
            from marts.mando_por_periodo
        """)
        return {r[0]: {"jogos": r[1], "taxa_vitoria_mandante": float(r[2]),
                       "taxa_empate": float(r[3]), "taxa_vitoria_visitante": float(r[4]),
                       "pontos_por_jogo_mandante": float(r[5]),
                       "pontos_por_jogo_visitante": float(r[6]),
                       "vantagem_pontos": float(r[7]), "saldo_medio_mandante": float(r[8])}
                for r in cur.fetchall()}


# ---------------------------------------------------------------------------
# Métricas e bootstrap
# ---------------------------------------------------------------------------
def metricas(res: np.ndarray, pm: np.ndarray, pv: np.ndarray, saldo: np.ndarray) -> dict:
    """Denominador de tudo: jogos disputados no recorte."""
    return {
        "jogos": int(len(res)),
        "taxa_vitoria_mandante": float(np.mean(res == "M")),
        "taxa_empate": float(np.mean(res == "E")),
        "taxa_vitoria_visitante": float(np.mean(res == "V")),
        "pontos_por_jogo_mandante": float(np.mean(pm)),
        "pontos_por_jogo_visitante": float(np.mean(pv)),
        "vantagem_pontos": float(np.mean(pm - pv)),
        "saldo_medio_mandante": float(np.mean(saldo)),
    }


def ic(amostras: np.ndarray) -> list[float]:
    lo, hi = np.percentile(amostras, [2.5, 97.5])
    return [float(lo), float(hi)]


def boot_media(valores: np.ndarray, rng) -> np.ndarray:
    idx = rng.integers(0, len(valores), size=(REPETICOES, len(valores)))
    return valores[idx].mean(axis=1)


def resumo_periodo(d, mascara, rng) -> dict:
    m = metricas(d["resultado"][mascara], d["pm"][mascara], d["pv"][mascara], d["saldo"][mascara])
    vant = (d["pm"] - d["pv"])[mascara]
    vm = (d["resultado"][mascara] == "M").astype(float)
    m["ic95"] = {
        "vantagem_pontos": ic(boot_media(vant, rng)),
        "saldo_medio_mandante": ic(boot_media(d["saldo"][mascara].astype(float), rng)),
        "taxa_vitoria_mandante": ic(boot_media(vm, rng)),
    }
    return m


def diferenca(d, m_a, m_b, rng, campo="vant") -> dict:
    """Média de B menos média de A, com IC por bootstrap independente."""
    v = d["pm"] - d["pv"] if campo == "vant" else d["saldo"]
    a, b = v[m_a].astype(float), v[m_b].astype(float)
    dif = boot_media(b, rng) - boot_media(a, rng)
    return {"diferenca": float(b.mean() - a.mean()), "ic95": ic(dif),
            "queda_relativa": float(1 - b.mean() / a.mean())}


def diferenca_por_rodada(d, m_a, m_b, rng) -> dict:
    """Sensibilidade: reamostra rodadas inteiras (jogos da mesma rodada podem
    não ser independentes: mesmo calendário, clima, arbitragem da época)."""
    v = (d["pm"] - d["pv"]).astype(float)

    def por_cluster(mascara):
        grupos = defaultdict(list)
        for t, r, x in zip(d["temporada"][mascara], d["rodada"][mascara], v[mascara]):
            grupos[(t, r)].append(x)
        somas = np.array([sum(g) for g in grupos.values()])
        ns = np.array([len(g) for g in grupos.values()])
        idx = rng.integers(0, len(somas), size=(REPETICOES, len(somas)))
        return somas[idx].sum(axis=1) / ns[idx].sum(axis=1)

    dif = por_cluster(m_b) - por_cluster(m_a)
    return {"ic95": ic(dif)}


def contra_tendencia(d, rng) -> dict:
    """Ajusta uma reta na vantagem por temporada de 2003 a 2019 e compara o
    observado sem torcida (e depois da volta) com o que a reta previa.
    O bootstrap reamostra jogos dentro de cada temporada e dentro de cada
    período, então a incerteza da reta entra no intervalo."""
    v = (d["pm"] - d["pv"]).astype(float)
    antes = d["periodo"] == "com_torcida_antes"
    temporadas = np.arange(2003, 2020)
    blocos = [v[antes & (d["temporada"] == t)] for t in temporadas]
    alvos = {p: d["periodo"] == p for p in ("sem_torcida", "com_torcida_depois")}

    def calcula(medias, alvo_vals):
        a, b = np.polyfit(temporadas, medias, 1)
        out = {}
        for p, (vals, temps) in alvo_vals.items():
            esperado = float(np.mean(a * temps + b))
            out[p] = (float(np.mean(vals)), esperado)
        return a, b, out

    alvo_vals = {p: (v[m], d["temporada"][m]) for p, m in alvos.items()}
    a, b, pontual = calcula(np.array([x.mean() for x in blocos]), alvo_vals)

    difs = {p: [] for p in alvos}
    for _ in range(2_000):  # 2.000 basta aqui: cada repetição refaz 17 médias e a reta
        medias = np.array([x[rng.integers(0, len(x), len(x))].mean() for x in blocos])
        alvo_b = {}
        for p, (vals, temps) in alvo_vals.items():
            i = rng.integers(0, len(vals), len(vals))
            alvo_b[p] = (vals[i], temps[i])
        _, _, r = calcula(medias, alvo_b)
        for p in alvos:
            difs[p].append(r[p][0] - r[p][1])

    return {
        "inclinacao_por_ano": float(a),
        "periodos": {
            p: {"observado": pontual[p][0], "esperado_pela_tendencia": pontual[p][1],
                "observado_menos_esperado": pontual[p][0] - pontual[p][1],
                "ic95": ic(np.array(difs[p]))}
            for p in alvos
        },
    }


def mesmo_time(d, rng) -> dict:
    """Cada time contra ele mesmo: pontos por jogo em casa menos fora, sem
    torcida contra 2015 a 2019. Tira o efeito de mudar quem está na Série A."""
    recente = (d["periodo"] == "com_torcida_antes") & (d["temporada"] >= 2015)
    sem = d["periodo"] == "sem_torcida"

    def gap(mascara):
        casa, fora = defaultdict(list), defaultdict(list)
        for m, vi, pm, pv in zip(d["mandante"][mascara], d["visitante"][mascara],
                                 d["pm"][mascara], d["pv"][mascara]):
            casa[m].append(pm)
            fora[vi].append(pv)
        return {t: (np.mean(casa[t]) - np.mean(fora[t]), len(casa[t]) + len(fora[t]))
                for t in casa if t in fora}

    g_rec, g_sem = gap(recente), gap(sem)
    times = sorted(set(g_rec) & set(g_sem))
    pares = np.array([g_sem[t][0] - g_rec[t][0] for t in times])
    idx = rng.integers(0, len(pares), size=(REPETICOES, len(pares)))
    return {
        "times": len(times),
        "gap_medio_2015_2019": float(np.mean([g_rec[t][0] for t in times])),
        "gap_medio_sem_torcida": float(np.mean([g_sem[t][0] for t in times])),
        "diferenca_media": float(pares.mean()),
        "ic95": ic(pares[idx].mean(axis=1)),
        "times_com_queda": int((pares < 0).sum()),
    }


TRADICIONAIS_B = ("Cruzeiro", "Vitoria", "Figueirense", "Ponte Preta")


def tradicionais_serie_b(d) -> dict:
    """Clubes tradicionais (9+ temporadas na Série A desde 2003, na Série A em
    2015-2019) que jogaram a Série B sem torcida. Cada um contra ele mesmo:
    pontos/jogo em casa menos fora na Série A 2015-2019 x na Série B sem
    torcida (período sem torcida e público zero na ESPN). Muda a divisão junto
    com a torcida, então fica fora dos números principais."""
    recente = (d["periodo"] == "com_torcida_antes") & (d["temporada"] >= 2015)
    with conectar() as con, con.cursor() as cur:
        cur.execute("""
            select mandante_id, visitante_id, pontos_mandante, pontos_visitante
            from marts.mando_jogos_serie_b where sem_torcida_de_fato
        """)
        b = cur.fetchall()
    saida = {}
    for time in TRADICIONAIS_B:
        casa_a = d["pm"][recente & (d["mandante"] == time)]
        fora_a = d["pv"][recente & (d["visitante"] == time)]
        casa_b = [pm for m, v, pm, pv in b if m == time]
        fora_b = [pv for m, v, pm, pv in b if v == time]
        gap_a = float(np.mean(casa_a) - np.mean(fora_a))
        gap_b = float(np.mean(casa_b) - np.mean(fora_b))
        saida[time] = {
            "jogos_serie_a_2015_2019": int(len(casa_a) + len(fora_a)),
            "jogos_serie_b_sem_torcida": len(casa_b) + len(fora_b),
            "gap_serie_a_2015_2019": gap_a,
            "gap_serie_b_sem_torcida": gap_b,
            "variacao": gap_b - gap_a,
        }
    return saida


def por_temporada(d, rng) -> list[dict]:
    """Uma linha por temporada; 2021 dividido entre sem torcida e volta parcial."""
    v = (d["pm"] - d["pv"]).astype(float)
    saida = []
    for t in range(2003, 2026):
        for p in PERIODOS:
            m = (d["temporada"] == t) & (d["periodo"] == p)
            if not m.any():
                continue
            saida.append({"temporada": int(t), "periodo": p, "jogos": int(m.sum()),
                          "vantagem_pontos": float(v[m].mean()),
                          "ic95": ic(boot_media(v[m], rng))})
    return saida


# ---------------------------------------------------------------------------
# Conferência e gráfico
# ---------------------------------------------------------------------------
def conferir(res_periodos: dict, sql: dict) -> None:
    for p, m in res_periodos.items():
        for k, v in sql[p].items():
            if abs(m[k] - v) > 1e-9:
                raise SystemExit(f"Python e SQL divergem em {p}.{k}: {m[k]} x {v}")
    print("Conferência Python x SQL (marts.mando_por_periodo): ok")


def grafico(serie: list[dict], tendencia: dict, destino: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # Paleta de referência da skill dataviz (modo claro): slot 1 azul, slot 2
    # laranja; cinzas para referência. Textos em tinta neutra, nunca na cor da série.
    cor = {"com_torcida_antes": "#2a78d6", "com_torcida_depois": "#2a78d6",
           "sem_torcida": "#eb6834", "volta_parcial": "#8a8985"}
    superficie, tinta, tinta2, grade = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"

    rotulos, xs = [], []
    for i, s in enumerate(serie):
        xs.append(i)
        t = s["temporada"]
        if s["periodo"] == "volta_parcial":
            rotulos.append("2021\n(volta)")
        else:
            rotulos.append(str(t))

    fig, ax = plt.subplots(figsize=(12, 6.2), dpi=150)
    fig.patch.set_facecolor(superficie)
    ax.set_facecolor(superficie)

    a = tendencia["inclinacao_por_ano"]
    # reta de 2003 a 2019, prolongada (tracejada) até 2025
    temporadas = np.array([s["temporada"] for s in serie], dtype=float)
    base = [s for s in serie if s["periodo"] == "com_torcida_antes"]
    b = np.mean([s["vantagem_pontos"] for s in base]) - a * np.mean([s["temporada"] for s in base])
    ajuste = a * temporadas + b
    n_antes = len(base)
    ax.plot(xs[:n_antes], ajuste[:n_antes], color=tinta2, lw=1.5, zorder=1)
    ax.plot(xs[n_antes - 1:], ajuste[n_antes - 1:], color=tinta2, lw=1.5, ls=(0, (4, 3)), zorder=1)

    for x, s in zip(xs, serie):
        lo, hi = s["ic95"]
        ax.plot([x, x], [lo, hi], color=cor[s["periodo"]], lw=2, alpha=0.55,
                solid_capstyle="round", zorder=2)
        ax.scatter([x], [s["vantagem_pontos"]], s=60, color=cor[s["periodo"]],
                   edgecolor=superficie, linewidth=2, zorder=3)

    ax.axhline(0, color=tinta2, lw=1)
    ax.set_xticks(xs)
    ax.set_xticklabels(rotulos, fontsize=8.5, color=tinta2)
    ax.tick_params(axis="y", colors=tinta2, labelsize=9)
    ax.tick_params(axis="x", length=0)
    ax.grid(axis="y", color=grade, lw=0.8)
    ax.set_axisbelow(True)
    for lado in ("top", "right", "left", "bottom"):
        ax.spines[lado].set_visible(False)
    ax.set_ylabel("Pontos por jogo do mandante menos os do visitante", color=tinta2, fontsize=9.5)

    # legenda com texto em tinta neutra
    from matplotlib.lines import Line2D
    itens = [
        Line2D([], [], marker="o", ls="", color=cor["com_torcida_antes"], markersize=8, label="Com torcida"),
        Line2D([], [], marker="o", ls="", color=cor["sem_torcida"], markersize=8, label="Sem torcida"),
        Line2D([], [], marker="o", ls="", color=cor["volta_parcial"], markersize=8, label="Volta parcial do público"),
        Line2D([], [], color=tinta2, lw=1.5, label="Tendência de 2003 a 2019 (tracejada: prolongada)"),
    ]
    leg = ax.legend(handles=itens, loc="lower left", bbox_to_anchor=(0.0, 0.07),
                    frameon=False, fontsize=9, ncol=2)
    for txt in leg.get_texts():
        txt.set_color(tinta)

    fig.suptitle("Sem torcida, a vantagem do mandante caiu, mas não sumiu",
                 x=0.06, ha="left", fontsize=15, fontweight="bold", color=tinta)
    ax.set_title("Série A, 2003 a 2025. Ponto: média da temporada. Barra: intervalo de 95% (bootstrap). "
                 "2021 dividido: até a 22ª rodada sem torcida, depois a volta parcial.",
                 loc="left", fontsize=9.5, color=tinta2, pad=10)
    fig.text(0.06, 0.015, "Fonte: base histórica do projeto (9.165 jogos de 2003 a 2025, "
             "conferida contra 5 fontes).", fontsize=8, color=tinta2)
    fig.subplots_adjust(left=0.06, right=0.98, top=0.86, bottom=0.12)
    destino.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destino, facecolor=superficie)
    plt.close(fig)


def main() -> None:
    rng = np.random.default_rng(SEMENTE)
    d = ler_jogos()
    mascaras = {p: d["periodo"] == p for p in PERIODOS}
    recente = mascaras["com_torcida_antes"] & (d["temporada"] >= 2015)

    periodos = {p: resumo_periodo(d, m, rng) for p, m in mascaras.items()}
    conferir(periodos, ler_sql_por_periodo())
    periodos["com_torcida_2015_2019"] = resumo_periodo(d, recente, rng)

    resultado = {
        "gerado_por": "analise/fase1_mando.py",
        "semente": SEMENTE,
        "repeticoes_bootstrap": REPETICOES,
        "periodos": periodos,
        "diferencas_vantagem_pontos": {
            "sem_torcida_menos_2003_2019": diferenca(d, mascaras["com_torcida_antes"], mascaras["sem_torcida"], rng),
            "sem_torcida_menos_2015_2019": diferenca(d, recente, mascaras["sem_torcida"], rng),
            "sem_torcida_menos_2022_2025": diferenca(d, mascaras["com_torcida_depois"], mascaras["sem_torcida"], rng),
            "2022_2025_menos_2015_2019": diferenca(d, recente, mascaras["com_torcida_depois"], rng),
        },
        "diferencas_saldo": {
            "sem_torcida_menos_2015_2019": diferenca(d, recente, mascaras["sem_torcida"], rng, campo="saldo"),
        },
        "sensibilidade_por_rodada": {
            "sem_torcida_menos_2015_2019": diferenca_por_rodada(d, recente, mascaras["sem_torcida"], rng),
        },
        "contra_tendencia": contra_tendencia(d, rng),
        "mesmo_time": mesmo_time(d, rng),
        "tradicionais_serie_b": tradicionais_serie_b(d),
        "por_temporada": por_temporada(d, rng),
    }

    destino = RAIZ / "analise" / "resultados_fase1.json"
    destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    grafico(resultado["por_temporada"], resultado["contra_tendencia"],
            RAIZ / "docs" / "img" / "fase1_vantagem_por_temporada.png")
    print(f"Resultados em {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()

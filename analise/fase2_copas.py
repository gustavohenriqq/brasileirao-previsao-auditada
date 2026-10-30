"""Fase 2: fatores 11 e 12, jogos de copa (Libertadores, Sul-Americana, Copa do Brasil).

Pergunta: jogar copa no meio da semana muda o resultado do time na Série A?
O fator 8 (cansaço) só via a Série A e quase passou (dRPS -0,00008
[-0,00020; +0,00001]). Aqui o calendário das copas entra (modelos/copas.py).

- Fator 11, cansaco_copas: dias desde o jogo anterior em qualquer dessas
  competições, limitado a um teto.
- Fator 12, copa_depois: 1 se o time tem jogo de copa até k dias depois.

Mesmas regras de analise/fase2_fatores.py, com 2026 fora (o teste final já
rodou e não roda de novo):
1. Escolha do hiperparâmetro em 2012 a 2014 (base lida até 2014), fator
   sozinho sobre o Dixon-Coles, menor RPS. Copa do Brasil na ESPN só desde
   2013: em 2012 o fator vê só as copas da Conmebol.
2. Validação em 2015 a 2025, diferença pareada de RPS com IC 95% (bootstrap
   por (temporada, rodada), semente 2027):
   - fator sozinho contra o Dixon-Coles (mesma regra dos fatores 1 a 9);
   - modelo escolhido (conjunto_dc) + fator contra o conjunto_dc. Esta
     decide: o fator entra no modelo se o IC ficar todo abaixo de zero.
     Se os dois passarem, os dois juntos entram só se baterem o melhor
     sozinho com IC abaixo de zero.
   - referência: conjunto_dc + cansaço só da Série A (mesmo teto), para
     separar o efeito das copas do efeito do descanso.
3. Se algum fator entrar: replay de tabela (cortes 10/15/20/25, alvo 33)
   contra o conjunto_dc. No replay o calendário das copas depois do corte
   inclui fases que o time ainda não sabia se ia jogar (vazamento pequeno, só
   nessa segunda métrica).

Grava a seção "copas" de analise/resultados_fase2.json. Rodar com
    .venv\\Scripts\\python -u analise/fase2_copas.py > analise/fase2_copas.log 2>&1
"""
from __future__ import annotations

import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from modelos.copas import baixar_copas, carregar_copas  # noqa: E402
from modelos.fatores import CansacoCopas, CopaDepois  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fase2_fatores as ff  # noqa: E402

ESCOLHA = (2012, 2014)
VALIDACAO = (2015, 2025)
GRADES = {"cansaco_copas": [3, 4, 7, 14], "copa_depois": [2, 3, 4]}
CONJUNTO = [("mando_time", 100), ("finalizacoes", 38)]   # modelo escolhido
DECISAO = "conjunto_dc"


@lru_cache(maxsize=None)
def copas_ate(ate: int) -> pd.DataFrame:
    return carregar_copas(ate)


def _ate(ctx) -> int:
    return int(ctx.jogos["temporada"].max())


ff.FABRICA["cansaco_copas"] = lambda v, c: CansacoCopas(copas_ate(_ate(c)), int(v))
ff.FABRICA["copa_depois"] = lambda v, c: CopaDepois(copas_ate(_ate(c)), int(v))
log = ff.log


def spec(nome: str, base: str, fatores: list) -> dict:
    return {"nome": nome, "base": base, "fatores": list(fatores)}


def cobertura(ctx) -> dict:
    """Quantos jogos da Série A de cada temporada têm copa por perto."""
    c = copas_ate(_ate(ctx))
    j = ctx.jogos[ctx.jogos["temporada"].between(*VALIDACAO)]
    saida = {}
    for t, g in j.groupby("temporada"):
        n = 0
        for lado in ("mandante_id", "visitante_id"):
            for time_id, d in zip(g[lado], g["data"]):
                datas = c.loc[c["time_id"] == time_id, "data"].to_numpy()
                dif = (datas - d.to_datetime64()) / np.timedelta64(1, "D")
                n += bool(((dif > 0) & (dif <= 3)).any())
        saida[int(t)] = {"jogos": len(g), "lados_com_copa_ate_3_dias_depois": n,
                         "jogos_de_copa_dos_times": int(c["data"].dt.year.eq(t).sum())}
    return saida


def main() -> None:
    baixar_copas()
    ctx14, _ = ff.carregar(ESCOLHA[1])
    ctx25, _ = ff.carregar(VALIDACAO[1])
    for ate in (ESCOLHA[1], VALIDACAO[1]):
        c = copas_ate(ate)
        log(f"copas até {ate}: {len(c)} registros (time, jogo); "
            + ", ".join(f"{k} {v}" for k, v in c.groupby("copa").size().items()))
    cob = cobertura(ctx25)
    for t, v in cob.items():
        log(f"  {t}: {v['lados_com_copa_ate_3_dias_depois']} de {2 * v['jogos']} lados de jogo "
            f"com copa até 3 dias depois")

    with ProcessPoolExecutor(max_workers=os.cpu_count(), initializer=ff._iniciar,
                             initargs=({ESCOLHA[1]: ctx14, VALIDACAO[1]: ctx25},)) as ex:
        # --- 1. escolha ---
        specs = [spec("dc", "dc", [])] + [spec(f"dc_{f}_{v}", "dc", [(f, v)])
                                          for f, vals in GRADES.items() for v in vals]
        fut = [ex.submit(ff.job_backtest, s, ESCOLHA[1], *ESCOLHA) for s in specs]
        res = {r["spec"]["nome"]: r for r in (f.result() for f in fut)}
        rps_base = float(ff.perdas(res["dc"]["prev"], "dc")[0].mean())
        escolha = {}
        for f, vals in GRADES.items():
            linhas = []
            for v in vals:
                nome = f"dc_{f}_{v}"
                r, ll = ff.perdas(res[nome]["prev"], nome)
                linhas.append({"valor": v, "rps": float(r.mean()), "log_loss": float(ll.mean()),
                               "beta_dc": res[nome]["beta_dc_final"]})
            melhor = min(linhas, key=lambda x: x["rps"])
            borda = melhor["valor"] in (vals[0], vals[-1])
            escolha[f] = {"grade": vals, "resultados": linhas, "rps_base": rps_base,
                          "escolhido": melhor["valor"], "na_borda_da_grade": borda}
            log(f"escolha {f}: " + ", ".join(f"{x['valor']}={x['rps']:.5f}" for x in linhas)
                + f" | base {rps_base:.5f} -> {melhor['valor']}" + (" (BORDA)" if borda else ""))

        # --- 2. validação ---
        cc = ("cansaco_copas", escolha["cansaco_copas"]["escolhido"])
        cd = ("copa_depois", escolha["copa_depois"]["escolhido"])
        specs = [spec("dc", "dc", []), spec("dc_cc", "dc", [cc]), spec("dc_cd", "dc", [cd]),
                 spec(DECISAO, "dc", CONJUNTO), spec("conj_cc", "dc", CONJUNTO + [cc]),
                 spec("conj_cd", "dc", CONJUNTO + [cd]),
                 spec("conj_cc_cd", "dc", CONJUNTO + [cc, cd]),
                 spec("conj_cansaco_serie_a", "dc", CONJUNTO + [("cansaco", cc[1])])]
        fut = [ex.submit(ff.job_backtest, s, VALIDACAO[1], *VALIDACAO) for s in specs]
        res = {r["spec"]["nome"]: r for r in (f.result() for f in fut)}
        for n, r in res.items():
            log(f"  validação {n}: {r['segundos']:.0f} s; beta DC {r['beta_dc_final']}")

        def par(a, b):
            d = ff.parear(res[a]["prev"], a, res[b]["prev"], b, VALIDACAO)
            log(f"  {a} - {b}: {d['diferenca']:+.5f} [{d['ic95'][0]:+.5f}; {d['ic95'][1]:+.5f}] "
                f"(RPS {d['media_a']:.5f} x {d['media_b']:.5f}, {d['jogos']} jogos)")
            return d

        pares = {f"{a}_menos_{b}": par(a, b) for a, b in [
            ("dc_cc", "dc"), ("dc_cd", "dc"), ("conj_cc", DECISAO), ("conj_cd", DECISAO),
            ("conj_cc_cd", DECISAO), ("conj_cansaco_serie_a", DECISAO),
            ("conj_cc", "conj_cansaco_serie_a")]}
        passa = {f: pares[f"{n}_menos_{DECISAO}"]["ic95"][1] < 0
                 for f, n in (("cansaco_copas", "conj_cc"), ("copa_depois", "conj_cd"))}
        entra = [f for f, ok in passa.items() if ok]
        if len(entra) == 2:
            melhor = min(("conj_cc", "conj_cd"), key=lambda n: pares[f"{n}_menos_{DECISAO}"]["diferenca"])
            pares[f"conj_cc_cd_menos_{melhor}"] = par("conj_cc_cd", melhor)
            if pares[f"conj_cc_cd_menos_{melhor}"]["ic95"][1] >= 0:
                entra = ["cansaco_copas" if melhor == "conj_cc" else "copa_depois"]
        log(f"passam (conjunto + fator contra conjunto): {passa} -> entram: {entra or 'nenhum'}")

        # --- 3. replay, só se algo entrar ---
        replay = None
        if entra:
            novo = spec("conj_copas", "dc", CONJUNTO + [cc if f == "cansaco_copas" else cd for f in entra])
            temporadas = list(range(VALIDACAO[0], VALIDACAO[1] + 1))
            fut = [ex.submit(ff.job_replay, s, VALIDACAO[1], temporadas, ff.SIMULACOES, 0.1)
                   for s in (spec(DECISAO, "dc", CONJUNTO), novo)]
            rep = [f.result() for f in fut]
            replay = {"modelo": novo, "delta_alvo_33": ff.delta_replay(rep[1]["linhas"], rep[0]["linhas"],
                                                                      VALIDACAO),
                      "novo": ff.resumo_replay(rep[1]["linhas"]),
                      "conjunto": ff.resumo_replay(rep[0]["linhas"])}
            d = replay["delta_alvo_33"]["erro_pontos"]
            log(f"replay alvo 33: erro de pontos {d['a']:.3f} x {d['b']:.3f} "
                f"({d['diferenca']:+.3f} {d['ic95_bootstrap_temporadas']})")

    destino = ff.gravar_secao("copas", {
        "gerado_por": "analise/fase2_copas.py",
        "regras": {"dados": "2003-2025 da Série A e copas da ESPN até 31/12/2025; 2026 não é lido",
                   "copas": "Libertadores e Sul-Americana desde 2012, Copa do Brasil desde 2013 "
                            "(ESPN); estaduais fora",
                   "escolha": f"fator sozinho sobre o DC, {ESCOLHA[0]}-{ESCOLHA[1]}, menor RPS",
                   "entrada": "conjunto_dc + fator contra conjunto_dc em 2015-2025; IC 95% todo "
                              "abaixo de zero",
                   "diferenca": "A menos B; negativo = A melhor"},
        "cobertura": cob, "escolha_hiperparametros": escolha, "diferencas": pares,
        "passam": passa, "entram": entra, "replay": replay,
        "segundos_total": time.time() - ff.T0,
    })
    log(f"gravado em {destino}")


if __name__ == "__main__":
    main()

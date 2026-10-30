"""Fase 2: fatores 1 a 10 sobre os modelos base, e incerteza de parâmetro no replay.

Etapas (todas só com 2003 a 2025; 2026 não é lido):
1. Escolha do hiperparâmetro de cada fator, com grade pequena declarada aqui
   (GRADES), pelo menor RPS médio:
   - fatores com dado antes de 2012: previsões de 2005 a 2011 (base até 2011);
   - estilo e finalizações (ESPN: chutes desde 2010, posse desde 2014) e troca
     de técnico (lista começa em 2012): previsões de 2012 a 2014 (base até
     2014). Esses três são validados só em 2015 a 2025.
2. Validação: cada fator sozinho contra o seu modelo base (BASE de cada um),
   diferença pareada de RPS com IC 95% (bootstrap por (temporada, rodada),
   semente 2027). Entra se o IC ficar todo abaixo de zero. Os fatores de Elo
   também rodam no Dixon-Coles, só como sensibilidade (não decidem).
   Segunda métrica: replay de tabela (cortes 10/15/20/25, alvos 33 e 38).
3. Conjunto dos que passaram, contra a base, contra o Elo e contra o mercado,
   com replay.
4. Fator 10: mistura em log-odds do melhor modelo com o mercado; peso pela
   validação (curva inteira reportada) e, como conferência honesta, peso
   escolhido deixando cada temporada de fora.
5. Tarefa B: escala da incerteza de parâmetro no replay (modelos/replay.py),
   escolhida no replay de 2005 a 2011 (cobertura média da faixa de 90% mais
   perto de 0,90) e aplicada na validação.

Grava a seção "fatores" de analise/resultados_fase2.json (as outras seções
ficam como estão). Log com horário em cada etapa: rodar com
    .venv\\Scripts\\python -u analise/fase2_fatores.py > analise/fase2_fatores.log 2>&1
"""
from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ingestao.comum import RAIZ  # noqa: E402
from modelos.backtest import probs_do_modelo, rodar_backtest  # noqa: E402
from modelos.carga import carregar_jogos  # noqa: E402
from modelos.dixon_coles import DixonColes  # noqa: E402
from modelos.elo import Elo  # noqa: E402
from modelos.fatores import (Animo, Cansaco, ComFatores, ConfrontoDireto, Estilo,  # noqa: E402
                             Finalizacoes, Forma, MandoTime, Motivacao, Tecnico,
                             carregar_estatisticas, carregar_trocas, misturar)
from modelos.hiperparametros import DIXON_COLES, ELO  # noqa: E402
from modelos.metricas import REPETICOES, SEMENTE, codificar, diferenca_pareada, log_loss, rps  # noqa: E402
from modelos.reguas import Mercado  # noqa: E402
from modelos.replay import ALVOS, CORTES, replay_tabela  # noqa: E402

ULTIMA = 2025                      # 2026 é o teste final: nunca carregado aqui
VALIDACAO = (2012, 2025)
VALIDACAO_ESPN = (2015, 2025)
ESCOLHA_ANTIGA = (2005, 2011)      # base lida só até 2011
ESCOLHA_ESPN = (2012, 2014)        # base lida só até 2014
SIMULACOES = 10_000
METRICAS_REPLAY = ("erro_pontos", "erro_posicao", "acerto_g4", "acerto_g6", "acerto_z4",
                   "cobertura_90")

# Grades declaradas antes de rodar. Todos os valores são reportados.
# A 1a rodada (grades menores, ver HISTORICO_GRADES) deu vencedor na borda em
# três fatores; as grades foram ampliadas para o lado da borda, ainda só no
# período de escolha, e tudo foi rodado de novo.
GRADES = {
    "mando_time":   {"base": "dc",  "param": "ridge", "valores": [3, 10, 30, 100, 300, 1000], "escolha": ESCOLHA_ANTIGA},
    "forma":        {"base": "elo", "param": "n",     "valores": [3, 5, 10],        "escolha": ESCOLHA_ANTIGA},
    "animo":        {"base": "elo", "param": "teto",  "valores": [2, 4, 8],         "escolha": ESCOLHA_ANTIGA},
    "motivacao":    {"base": "elo", "param": "alfa",  "valores": [0.5, 0.75, 1.0],  "escolha": ESCOLHA_ANTIGA},
    "confronto":    {"base": "elo", "param": "m",     "valores": [2, 5, 10],        "escolha": ESCOLHA_ANTIGA},
    "estilo":       {"base": "dc",  "param": "n",     "valores": [10, 19, 38],      "escolha": ESCOLHA_ESPN},
    "finalizacoes": {"base": "dc",  "param": "n",     "valores": [10, 19, 38, 76],  "escolha": ESCOLHA_ESPN},
    "cansaco":      {"base": "elo", "param": "teto",  "valores": [3, 4, 7, 14],        "escolha": ESCOLHA_ANTIGA},
    "tecnico":      {"base": "elo", "param": "k",     "valores": [3, 5, 10],        "escolha": ESCOLHA_ESPN},
}
HISTORICO_GRADES = (
    "1a rodada (30/10/2026, mesmas regras): mando_time ridge 3/10/30/100 -> RPS 0,21270/0,21149/"
    "0,21088/0,21073, vencedor 100 (borda); finalizacoes n 10/19/38 -> 0,20886/0,20874/0,20844, "
    "vencedor 38 (borda); cansaco teto 4/7/14 -> 0,21064/0,21079/0,21078, vencedor 4 (borda). "
    "Grades ampliadas: ridge 300 e 1000, n 76, teto 3. Na 1a rodada passaram mando_time (ridge 100, "
    "dRPS -0,00014 [-0,00027; -0,00001]) e finalizacoes (n 38, dRPS -0,00083 [-0,00153; -0,00009])."
    " Na 2a rodada: ridge 100 e n 38 continuaram vencendo, agora no meio da grade; cansaco ficou em teto 3, de novo na borda, sem ampliar: teto 2 só separaria descanso de 1 dia, que quase não existe na Série A (e nenhum teto bateu a base no período de escolha).")
NUMERO = {"mando_time": 1, "forma": 2, "animo": 3, "motivacao": 4, "confronto": 5,
          "estilo": 6, "finalizacoes": 7, "cansaco": 8, "tecnico": 9}
# Tarefa B: escala do desvio por time (log de gols no DC, logit no Elo)
GRADE_INCERTEZA = {"dc": [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30],
                   "elo": [0.0, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60]}
PESOS_MERCADO = [round(w, 2) for w in np.arange(0.0, 1.0001, 0.05)]

T0 = time.time()


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S} +{time.time() - T0:6.0f}s] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Dados por corte de leitura (cada processo recebe os seus)
# ---------------------------------------------------------------------------
@dataclass
class Contexto:
    jogos: pd.DataFrame
    estat: pd.DataFrame
    trocas: pd.DataFrame
    times: list


CTX: dict[int, Contexto] = {}


def _iniciar(ctx) -> None:
    global CTX
    CTX = ctx


def carregar(ate: int) -> tuple[Contexto, int]:
    assert ate <= ULTIMA
    jogos = carregar_jogos(ate_temporada=ate)
    assert jogos["temporada"].max() <= ate
    estat = carregar_estatisticas(ate)
    estat = estat[estat["jogo_id"].isin(set(jogos["jogo_id"]))]
    trocas, sem_data = carregar_trocas(ate)
    times = sorted(set(jogos["mandante_id"]) | set(jogos["visitante_id"]))
    return Contexto(jogos, estat, trocas, times), sem_data


FABRICA = {
    "mando_time": lambda v, c: MandoTime(c.times, v),
    "forma": lambda v, c: Forma(int(v)),
    "animo": lambda v, c: Animo(int(v)),
    "motivacao": lambda v, c: Motivacao(float(v)),
    "confronto": lambda v, c: ConfrontoDireto(int(v)),
    "estilo": lambda v, c: Estilo(int(v)),
    "finalizacoes": lambda v, c: Finalizacoes(int(v)),
    "cansaco": lambda v, c: Cansaco(int(v)),
    "tecnico": lambda v, c: Tecnico(c.trocas, int(v)),
}


def construir(spec: dict, ctx: Contexto):
    """spec = {"nome", "base": elo|dc|mercado, "fatores": [(fator, valor), ...]}"""
    if spec["base"] == "mercado":
        return Mercado("proporcional", nome=spec["nome"])
    if not spec["fatores"]:
        return Elo(**ELO, nome=spec["nome"]) if spec["base"] == "elo" else \
            DixonColes(**DIXON_COLES, nome=spec["nome"])
    camadas = [FABRICA[f](v, ctx) for f, v in spec["fatores"]]
    return ComFatores(spec["base"], camadas, spec["nome"], estat=ctx.estat)


def job_backtest(spec: dict, ate: int, inicio: int, fim: int) -> dict:
    t0 = time.time()
    ctx = CTX[ate]
    m = construir(spec, ctx)
    prev, _ = rodar_backtest(ctx.jogos, [m], inicio, fim)
    nome = spec["nome"]
    cols = ["jogo_id", "temporada", "rodada", "resultado", "gols_mandante", "gols_visitante"]
    extra = [c for c in prev.columns if c.startswith(nome + "_")]
    beta = None
    base = getattr(m, "base", None)
    if isinstance(base, DixonColes) and base.parametros is not None:
        beta = dict(zip(base.cov_mandante, map(float, base.parametros["beta"])))
    return {"spec": spec, "prev": prev[cols + extra].copy(), "segundos": time.time() - t0,
            "beta_dc_final": beta}


def job_replay(spec: dict, ate: int, temporadas: list, n_sim: int, incerteza: float = 0.0) -> dict:
    t0 = time.time()
    ctx = CTX[ate]
    m = construir(spec, ctx)
    linhas = []
    for t in temporadas:
        for corte in CORTES:
            linhas += replay_tabela(ctx.jogos, m, t, corte, ALVOS, n_sim, incerteza=incerteza)
    return {"spec": spec, "linhas": linhas, "segundos": time.time() - t0, "incerteza": incerteza}


# ---------------------------------------------------------------------------
# Contas
# ---------------------------------------------------------------------------
def perdas(prev: pd.DataFrame, nome: str) -> tuple[np.ndarray, np.ndarray]:
    y = codificar(prev["resultado"])
    p = probs_do_modelo(prev, nome)
    if not np.isfinite(p).all():
        raise SystemExit(f"{nome}: jogo sem probabilidade")
    return rps(p, y), log_loss(p, y)


def parear(a: pd.DataFrame, nome_a: str, b: pd.DataFrame, nome_b: str, periodo) -> dict:
    """Diferença pareada de RPS (A menos B) nos jogos do período."""
    ja = a[(a["temporada"] >= periodo[0]) & (a["temporada"] <= periodo[1])]
    jb = b.set_index("jogo_id").loc[ja["jogo_id"]].reset_index()
    ra, la = perdas(ja, nome_a)
    rb, lb = perdas(jb, nome_b)
    d = diferenca_pareada(ra, rb, ja["temporada"], ja["rodada"])
    d["log_loss_a"], d["log_loss_b"] = float(la.mean()), float(lb.mean())
    d["periodo"] = list(periodo)
    return d


def resumo_replay(linhas: list, temporadas=None) -> dict:
    tab = pd.DataFrame(linhas)
    if temporadas is not None:
        tab = tab[tab["temporada"].between(*temporadas)]
    g = tab.groupby("alvo")[list(METRICAS_REPLAY)].mean()
    por_corte = tab.groupby(["alvo", "corte"])["cobertura_90"].mean()
    return {"por_alvo": {int(a): {k: float(v) for k, v in g.loc[a].items()} for a in g.index},
            "cobertura_por_corte": {f"{a}_{c}": float(v) for (a, c), v in por_corte.items()}}


def delta_replay(linhas_a: list, linhas_b: list, periodo, alvo: int = 33) -> dict:
    """Erro de pontos de A menos o de B, pareado por (temporada, corte), com
    IC 95% por bootstrap de temporadas."""
    a = pd.DataFrame(linhas_a)
    b = pd.DataFrame(linhas_b)
    chave = ["temporada", "corte", "alvo"]
    j = a.merge(b, on=chave, suffixes=("_a", "_b"))
    j = j[j["temporada"].between(*periodo) & (j["alvo"] == alvo)]
    saida = {}
    for met in ("erro_pontos", "erro_posicao"):
        d = (j[f"{met}_a"] - j[f"{met}_b"]).to_numpy()
        por_t = j.assign(d=d).groupby("temporada")["d"].mean().to_numpy()
        rng = np.random.default_rng(SEMENTE)
        boot = por_t[rng.integers(0, len(por_t), (REPETICOES, len(por_t)))].mean(axis=1)
        saida[met] = {"a": float(j[f"{met}_a"].mean()), "b": float(j[f"{met}_b"].mean()),
                      "diferenca": float(d.mean()),
                      "ic95_bootstrap_temporadas": [float(np.percentile(boot, 2.5)),
                                                    float(np.percentile(boot, 97.5))]}
    return saida


def para_json(x):
    if isinstance(x, dict):
        return {str(k): para_json(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [para_json(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return float(x)
    if isinstance(x, np.ndarray):
        return para_json(x.tolist())
    if isinstance(x, (np.bool_,)):
        return bool(x)
    return x


def gravar_secao(secao: str, conteudo) -> Path:
    destino = RAIZ / "analise" / "resultados_fase2.json"
    dados = json.loads(destino.read_text(encoding="utf-8")) if destino.exists() else {}
    dados[secao] = para_json(conteudo)
    destino.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    return destino


def spec_fator(f: str, valor, base: str | None = None, sufixo: str = "") -> dict:
    base = base or GRADES[f]["base"]
    return {"nome": f"{base}_{f}{sufixo}", "base": base, "fatores": [(f, valor)]}


def periodo_validacao(fatores) -> tuple:
    return VALIDACAO_ESPN if any(GRADES[f]["escolha"] == ESCOLHA_ESPN for f in fatores) else VALIDACAO


# ---------------------------------------------------------------------------
# Programa
# ---------------------------------------------------------------------------
def main() -> None:
    log("lendo o banco (cortes 2011, 2014 e 2025; 2026 não é lido)")
    ctx, sem_data = {}, None
    for ate in (2011, 2014, ULTIMA):
        ctx[ate], sem_data = carregar(ate)
        log(f"  até {ate}: {len(ctx[ate].jogos)} jogos, {len(ctx[ate].estat)} linhas de estatística, "
            f"{len(ctx[ate].trocas)} trocas com data")
    base_specs = {"elo": {"nome": "elo", "base": "elo", "fatores": []},
                  "dc": {"nome": "dc", "base": "dc", "fatores": []},
                  "mercado": {"nome": "mercado", "base": "mercado", "fatores": []}}
    temporadas_val = list(range(VALIDACAO[0], VALIDACAO[1] + 1))
    temporadas_calib = list(range(ESCOLHA_ANTIGA[0], ESCOLHA_ANTIGA[1] + 1))

    with ProcessPoolExecutor(max_workers=os.cpu_count(), initializer=_iniciar, initargs=(ctx,)) as ex:
        def esperar(futuros: dict, rotulo: str) -> dict:
            out = {}
            for k, fut in futuros.items():
                r = fut.result()
                out[k] = r
                log(f"  {rotulo} {k}: {r['segundos']:.0f} s")
            return out

        # --- rodada 1: escolha dos hiperparâmetros + bases + grade da Tarefa B ---
        log("rodada 1: grades dos fatores, bases da validação e grade de incerteza (2005-2011)")
        f_sel = {}
        for f, g in GRADES.items():
            ate = 2011 if g["escolha"] == ESCOLHA_ANTIGA else 2014
            for v in g["valores"]:
                f_sel[(f, v)] = ex.submit(job_backtest, spec_fator(f, v, sufixo=f"_{v}"), ate, *g["escolha"])
        f_sel_base = {(b, per): ex.submit(job_backtest, base_specs[b], 2011 if per == ESCOLHA_ANTIGA else 2014, *per)
                      for b in ("elo", "dc") for per in (ESCOLHA_ANTIGA, ESCOLHA_ESPN)}
        f_val_base = {b: ex.submit(job_backtest, base_specs[b], ULTIMA, *VALIDACAO)
                      for b in ("elo", "dc", "mercado")}
        f_rep_base = {b: ex.submit(job_replay, base_specs[b], ULTIMA, temporadas_val, SIMULACOES)
                      for b in ("elo", "dc")}
        f_inc = {(b, s): ex.submit(job_replay, base_specs[b], 2011, temporadas_calib, SIMULACOES, s)
                 for b in ("elo", "dc") for s in GRADE_INCERTEZA[b]}

        sel = esperar(f_sel, "escolha")
        sel_base = esperar(f_sel_base, "escolha base")
        escolha = {}
        for f, g in GRADES.items():
            ate_per = g["escolha"]
            linhas = []
            for v in g["valores"]:
                r = sel[(f, v)]
                rr, ll = perdas(r["prev"], r["spec"]["nome"])
                linhas.append({g["param"]: v, "rps": float(rr.mean()), "log_loss": float(ll.mean()),
                               "jogos": int(len(rr))})
            br = sel_base[(g["base"], ate_per)]
            rb, lb = perdas(br["prev"], g["base"])
            melhor = min(linhas, key=lambda x: x["rps"])
            v = melhor[g["param"]]
            borda = v in (g["valores"][0], g["valores"][-1])
            escolha[f] = {"base": g["base"], "periodo_escolha": list(ate_per), "param": g["param"],
                          "grade": g["valores"], "resultados": linhas, "rps_base": float(rb.mean()),
                          "escolhido": v, "na_borda_da_grade": borda}
            log(f"escolha {f}: " + ", ".join(f"{x[g['param']]}={x['rps']:.5f}" for x in linhas)
                + f" | base {rb.mean():.5f} -> {g['param']}={v}{' (BORDA)' if borda else ''}")

        # --- rodada 2: validação de cada fator (+ sensibilidade no DC) e replays ---
        log("rodada 2: validação dos fatores e replays")
        f_val, f_rep, f_sens = {}, {}, {}
        for f, g in GRADES.items():
            per = periodo_validacao([f])
            v = escolha[f]["escolhido"]
            f_val[f] = ex.submit(job_backtest, spec_fator(f, v), ULTIMA, *per)
            f_rep[f] = ex.submit(job_replay, spec_fator(f, v), ULTIMA, list(range(per[0], per[1] + 1)), SIMULACOES)
            if g["base"] == "elo":
                f_sens[f] = ex.submit(job_backtest, spec_fator(f, v, base="dc"), ULTIMA, *per)

        val_base = esperar(f_val_base, "validação base")
        rep_base = esperar(f_rep_base, "replay base")
        val = esperar(f_val, "validação")
        sens = esperar(f_sens, "sensibilidade DC")
        rep = esperar(f_rep, "replay")

        resultado_fatores = {}
        passaram = []
        for f, g in GRADES.items():
            per = periodo_validacao([f])
            nome = val[f]["spec"]["nome"]
            d = parear(val[f]["prev"], nome, val_base[g["base"]]["prev"], g["base"], per)
            entra = d["ic95"][1] < 0
            if entra:
                passaram.append(f)
            dr = delta_replay(rep[f]["linhas"], rep_base[g["base"]]["linhas"], per)
            item = {"numero": NUMERO[f], "base": g["base"], "periodo_validacao": list(per),
                    "hiperparametro": {g["param"]: escolha[f]["escolhido"]},
                    "rps_fator": d["media_a"], "rps_base": d["media_b"], "diferenca_rps": d,
                    "entra": bool(entra), "replay": resumo_replay(rep[f]["linhas"]),
                    "replay_base": resumo_replay(rep_base[g["base"]]["linhas"], per),
                    "delta_replay_alvo33": dr, "delta_replay_alvo38": delta_replay(
                        rep[f]["linhas"], rep_base[g["base"]]["linhas"], per, 38)}
            coefs = [c for c in val[f]["prev"].columns if c.startswith(f"{nome}_coef_")]
            if coefs:
                pv = val[f]["prev"]
                item["coeficiente_elo"] = {c.replace(f"{nome}_coef_", ""): {
                    "mediana": float(pv[c].median()), "p10": float(pv[c].quantile(0.1)),
                    "p90": float(pv[c].quantile(0.9)), "ultimo": float(pv[c].iloc[-1])} for c in coefs}
            if val[f]["beta_dc_final"] is not None and f != "mando_time":
                item["beta_dc_ultimo_ajuste"] = val[f]["beta_dc_final"]
            if f in sens:
                ds = parear(sens[f]["prev"], sens[f]["spec"]["nome"], val_base["dc"]["prev"], "dc", per)
                item["sensibilidade_dc"] = {"diferenca_rps": ds, "decide": False,
                                            "beta_dc_ultimo_ajuste": sens[f]["beta_dc_final"]}
            if f == "estilo":
                item["dois_times_fechados"] = analise_estilo(val[f]["prev"], nome, val_base["dc"]["prev"], per)
            resultado_fatores[f] = item
            log(f"fator {NUMERO[f]} {f} ({g['base']}, {per[0]}-{per[1]}): dRPS {d['diferenca']:+.5f} "
                f"[{d['ic95'][0]:+.5f}, {d['ic95'][1]:+.5f}] | replay alvo 33 d erro pts "
                f"{dr['erro_pontos']['diferenca']:+.3f} | entra: {'sim' if entra else 'não'}")

        # --- rodada 3: conjunto(s) ---
        log(f"rodada 3: conjunto dos que passaram: {passaram or 'nenhum'}")
        conjuntos = {}
        elo_f = [f for f in passaram if GRADES[f]["base"] == "elo"]
        if elo_f:
            conjuntos["conjunto_elo"] = {"nome": "conjunto_elo", "base": "elo",
                                         "fatores": [(f, escolha[f]["escolhido"]) for f in elo_f]}
        if passaram:
            conjuntos["conjunto_dc"] = {"nome": "conjunto_dc", "base": "dc",
                                        "fatores": [(f, escolha[f]["escolhido"]) for f in passaram]}
        f_cv, f_cr = {}, {}
        for k, spec in conjuntos.items():
            per = periodo_validacao([f for f, _ in spec["fatores"]])
            f_cv[k] = ex.submit(job_backtest, spec, ULTIMA, *per)
            f_cr[k] = ex.submit(job_replay, spec, ULTIMA, list(range(per[0], per[1] + 1)), SIMULACOES)

        # Tarefa B: escolha da escala (2005-2011) e aplicação na validação
        inc = esperar(f_inc, "incerteza 2005-2011")
        escala, curva_inc = {}, {}
        for b in ("elo", "dc"):
            curva = []
            for s in GRADE_INCERTEZA[b]:
                tab = pd.DataFrame(inc[(b, s)]["linhas"])
                curva.append({"escala": s, "cobertura_90": float(tab["cobertura_90"].mean()),
                              "cobertura_alvo33": float(tab.loc[tab["alvo"] == 33, "cobertura_90"].mean()),
                              "cobertura_alvo38": float(tab.loc[tab["alvo"] == 38, "cobertura_90"].mean()),
                              "erro_pontos_alvo33": float(tab.loc[tab["alvo"] == 33, "erro_pontos"].mean())})
            melhor = min(curva, key=lambda x: abs(x["cobertura_90"] - 0.90))
            escala[b] = melhor["escala"]
            curva_inc[b] = curva
            log(f"incerteza {b}: " + ", ".join(f"{c['escala']}={c['cobertura_90']:.3f}" for c in curva)
                + f" -> escala {escala[b]}")
        f_inc_val = {b: ex.submit(job_replay, base_specs[b], ULTIMA, temporadas_val, SIMULACOES, escala[b])
                     for b in ("elo", "dc")}
        # conjunto: escala própria se todos os fatores têm dado em 2005-2011
        f_inc_conj, escala_conj = {}, {}
        for k, spec in conjuntos.items():
            fs = [f for f, _ in spec["fatores"]]
            if all(GRADES[f]["escolha"] == ESCOLHA_ANTIGA for f in fs):
                for s in GRADE_INCERTEZA[spec["base"]]:
                    f_inc_conj[(k, s)] = ex.submit(job_replay, spec, 2011, temporadas_calib, SIMULACOES, s)
            else:
                escala_conj[k] = {"escala": escala[spec["base"]],
                                  "origem": f"escala do {spec['base']} base (fatores sem dado em 2005-2011)"}

        cval = esperar(f_cv, "validação conjunto")
        crep = esperar(f_cr, "replay conjunto")
        resultado_conjunto = {}
        for k, spec in conjuntos.items():
            per = periodo_validacao([f for f, _ in spec["fatores"]])
            pv = cval[k]["prev"]
            item = {"fatores": spec["fatores"], "base": spec["base"], "periodo_validacao": list(per),
                    "contra_base": parear(pv, k, val_base[spec["base"]]["prev"], spec["base"], per),
                    "contra_elo": parear(pv, k, val_base["elo"]["prev"], "elo", per),
                    "contra_dc": parear(pv, k, val_base["dc"]["prev"], "dc", per),
                    "contra_mercado": parear(pv, k, val_base["mercado"]["prev"], "mercado", per),
                    "replay": resumo_replay(crep[k]["linhas"]),
                    "delta_replay_alvo33_contra_base": delta_replay(crep[k]["linhas"],
                                                                    rep_base[spec["base"]]["linhas"], per),
                    "delta_replay_alvo33_contra_elo": delta_replay(crep[k]["linhas"],
                                                                   rep_base["elo"]["linhas"], per)}
            if cval[k]["beta_dc_final"] is not None:
                item["beta_dc_ultimo_ajuste"] = {c: b for c, b in cval[k]["beta_dc_final"].items()
                                                 if not c.startswith("casa_")}
            resultado_conjunto[k] = item
            cb = item["contra_base"]
            log(f"{k}: RPS {cb['media_a']:.5f} | contra base {cb['diferenca']:+.5f} "
                f"[{cb['ic95'][0]:+.5f}, {cb['ic95'][1]:+.5f}] | contra mercado "
                f"{item['contra_mercado']['diferenca']:+.5f}")

        # --- Fator 10: mistura com o mercado sobre o melhor modelo ---
        candidatos = {"elo": val_base["elo"]["prev"], "dc": val_base["dc"]["prev"]}
        candidatos.update({k: cval[k]["prev"] for k in conjuntos})
        per_mix = max((periodo_validacao([f for f, _ in s["fatores"]]) for s in conjuntos.values()),
                      default=VALIDACAO)
        rps_cand = {}
        for k, pv in candidatos.items():
            j = pv[pv["temporada"].between(*per_mix)]
            rps_cand[k] = float(perdas(j, k)[0].mean())
        melhor = min(rps_cand, key=rps_cand.get)
        mistura = avaliar_mistura(candidatos[melhor], melhor, val_base["mercado"]["prev"], per_mix)
        mistura["rps_candidatos"] = rps_cand
        mistura["modelo"] = melhor
        log(f"mistura com o mercado sobre {melhor} ({per_mix[0]}-{per_mix[1]}): peso {mistura['peso_escolhido']}, "
            f"RPS {mistura['rps_mistura']:.5f} (mercado {mistura['rps_mercado']:.5f}); "
            f"mistura - mercado {mistura['contra_mercado']['diferenca']:+.5f} "
            f"[{mistura['contra_mercado']['ic95'][0]:+.5f}, {mistura['contra_mercado']['ic95'][1]:+.5f}]")

        # --- Tarefa B: resto ---
        inc_conj = esperar(f_inc_conj, "incerteza conjunto 2005-2011") if f_inc_conj else {}
        curva_conj = {}
        for k in conjuntos:
            if k in escala_conj:
                continue
            curva = []
            for s in GRADE_INCERTEZA[conjuntos[k]["base"]]:
                tab = pd.DataFrame(inc_conj[(k, s)]["linhas"])
                curva.append({"escala": s, "cobertura_90": float(tab["cobertura_90"].mean())})
            m = min(curva, key=lambda x: abs(x["cobertura_90"] - 0.90))
            escala_conj[k] = {"escala": m["escala"], "origem": "replay do conjunto em 2005-2011"}
            curva_conj[k] = curva
        f_inc_cval = {}
        for k, spec in conjuntos.items():
            per = periodo_validacao([f for f, _ in spec["fatores"]])
            f_inc_cval[k] = ex.submit(job_replay, spec, ULTIMA, list(range(per[0], per[1] + 1)),
                                      SIMULACOES, escala_conj[k]["escala"])
        inc_val = esperar(f_inc_val, "incerteza validação")
        inc_cval = esperar(f_inc_cval, "incerteza validação conjunto")

    cobertura = {}
    for b in ("elo", "dc"):
        cobertura[b] = {"escala": escala[b], "antes": resumo_replay(rep_base[b]["linhas"]),
                        "depois": resumo_replay(inc_val[b]["linhas"])}
    for k in conjuntos:
        cobertura[k] = {"escala": escala_conj[k]["escala"], "origem_escala": escala_conj[k]["origem"],
                        "antes": resumo_replay(crep[k]["linhas"]),
                        "depois": resumo_replay(inc_cval[k]["linhas"])}
    for k, c in cobertura.items():
        log(f"cobertura 90% {k}: antes " + ", ".join(f"alvo {a} {v['cobertura_90']:.3f}"
                                                    for a, v in c["antes"]["por_alvo"].items())
            + " | depois " + ", ".join(f"alvo {a} {v['cobertura_90']:.3f}" for a, v in c["depois"]["por_alvo"].items())
            + f" (escala {c['escala']})")

    saida = {
        "gerado_por": "analise/fase2_fatores.py",
        "regras": {
            "dados": "só 2003-2025; 2026 não é lido (carregar_jogos sem permitir_teste)",
            "escolha": "hiperparâmetro de cada fator pelo menor RPS: 2005-2011 (base lida até 2011); "
                       "estilo, finalizações e técnico em 2012-2014 (base lida até 2014) e validação só "
                       "em 2015-2025",
            "entrada": "fator sozinho contra o seu modelo base; entra se o IC 95% da diferença pareada de "
                       "RPS (bootstrap por (temporada, rodada), semente 2027) fica todo abaixo de zero",
            "replay": f"cortes {list(CORTES)}, alvos {list(ALVOS)}, {SIMULACOES} simulações; fatores "
                      "dinâmicos congelados no corte (horizonte = data do corte); cansaço e técnico usam "
                      "o calendário dos jogos futuros, mas só trocas anteriores ao corte; mercado fora",
            "cansaco": "só jogos de Série A na base: copas e estaduais não contam no descanso",
            "tecnico": f"dados/manuais/trocas_tecnico.csv até 2025; {sem_data} linhas sem data ficaram "
                       "de fora; só trocas durante a temporada (pré-temporada não marca técnico novo, "
                       "porque 2012-2019 não listam trocas de pré-temporada)",
            "diferenca": "fator menos base; negativo = fator melhor",
        },
        "grades": GRADES,
        "historico_grades": HISTORICO_GRADES,
        "escolha_hiperparametros": escolha,
        "fatores": resultado_fatores,
        "passaram": passaram,
        "conjunto": resultado_conjunto,
        "mercado_mistura": mistura,
        "incerteza_replay": {"grade": GRADE_INCERTEZA, "criterio": "cobertura média da faixa de 90% "
                             "(4 cortes x alvos 33 e 38) mais perto de 0,90 no replay de 2005-2011",
                             "curva_2005_2011": curva_inc, "curva_conjunto_2005_2011": curva_conj,
                             "escala": escala, "cobertura_validacao": cobertura},
        "simulacoes_replay": SIMULACOES,
        "segundos_total": round(time.time() - T0, 1),
    }
    destino = gravar_secao("fatores", saida)
    log(f"resultados em {destino.relative_to(RAIZ)} (seção 'fatores'); total {time.time() - T0:.0f} s")


def analise_estilo(prev_f: pd.DataFrame, nome: str, prev_b: pd.DataFrame, per) -> dict:
    """Jogos em que os dois times são 'fechados' (aberto < 0) pelo perfil
    pré-jogo: diferença de RPS, empates e gols previstos contra observados."""
    j = prev_f[prev_f["temporada"].between(*per)].copy()
    b = prev_b.set_index("jogo_id").loc[j["jogo_id"]].reset_index()
    fech = ((j[f"{nome}_estilo_aberto_m"] < 0) & (j[f"{nome}_estilo_aberto_v"] < 0)).to_numpy()
    out = {"jogos": int(fech.sum())}
    if fech.sum() < 30:
        return out
    ra, _ = perdas(j[fech], nome)
    rb, _ = perdas(b[fech], "dc")
    out["diferenca_rps"] = diferenca_pareada(ra, rb, j["temporada"][fech], j["rodada"][fech])
    emp = (j["resultado"] == "E").to_numpy()[fech]
    gols = (j["gols_mandante"] + j["gols_visitante"]).to_numpy()[fech]
    out["empates_observados"] = float(emp.mean())
    out["empate_previsto_fator"] = float(j[f"{nome}_e"].to_numpy()[fech].mean())
    out["empate_previsto_base"] = float(b["dc_e"].to_numpy()[fech].mean())
    out["gols_observados"] = float(gols.mean())
    out["gols_previstos_fator"] = float((j[f"{nome}_lam_m"] + j[f"{nome}_lam_v"]).to_numpy()[fech].mean())
    out["gols_previstos_base"] = float((b["dc_lam_m"] + b["dc_lam_v"]).to_numpy()[fech].mean())
    return out


def avaliar_mistura(prev_m: pd.DataFrame, nome: str, prev_k: pd.DataFrame, per) -> dict:
    j = prev_m[prev_m["temporada"].between(*per)]
    k = prev_k.set_index("jogo_id").loc[j["jogo_id"]].reset_index()
    y = codificar(j["resultado"])
    pm, pk = probs_do_modelo(j, nome), probs_do_modelo(k, "mercado")
    temps = j["temporada"].to_numpy()
    curva, perdas_w = [], {}
    for w in PESOS_MERCADO:
        r = rps(misturar(pm, pk, w), y)
        perdas_w[w] = r
        curva.append({"peso_mercado": w, "rps": float(r.mean()),
                      "log_loss": float(log_loss(misturar(pm, pk, w), y).mean())})
    w_best = min(curva, key=lambda x: x["rps"])["peso_mercado"]
    r_mix, r_k = perdas_w[w_best], rps(pk, y)
    # conferência honesta: peso escolhido sem a temporada avaliada
    loso, pesos_loso = np.empty(len(y)), {}
    for t in np.unique(temps):
        fora = temps != t
        w_t = min(PESOS_MERCADO, key=lambda w: perdas_w[w][fora].mean())
        pesos_loso[int(t)] = w_t
        loso[~fora] = perdas_w[w_t][~fora]
    obs = None
    if w_best == 1.0:
        obs = ("peso 1 = só o mercado: o modelo não acrescenta nada às odds de fechamento "
               "nesta validação (a grade não passa de 1, que seria apostar contra o modelo)")
    return {"periodo": list(per), "curva": curva, "peso_escolhido": w_best, "observacao": obs,
            "rps_mistura": float(r_mix.mean()), "rps_mercado": float(r_k.mean()),
            "rps_modelo": float(perdas_w[0.0].mean()),
            "contra_mercado": diferenca_pareada(r_mix, r_k, j["temporada"], j["rodada"]),
            "contra_modelo": diferenca_pareada(r_mix, perdas_w[0.0], j["temporada"], j["rodada"]),
            "deixando_uma_temporada_de_fora": {
                "pesos": pesos_loso, "rps": float(loso.mean()),
                "contra_mercado": diferenca_pareada(loso, r_k, j["temporada"], j["rodada"])}}


if __name__ == "__main__":
    main()

"""Fase 2: fatores 1 a 9 como camadas sobre os modelos base (Elo e Dixon-Coles).

Ideia geral
-----------
Cada fator é uma "camada" que calcula colunas novas para um jogo a partir de
três fontes, sempre com um horizonte h (data):
- Historia: jogos com resultado conhecido e data < h (placar, Elo pré-jogo,
  estatísticas da ESPN desses jogos);
- Calendario: datas e adversários dos jogos (sem placar). O calendário de uma
  rodada é conhecido antes dela, então cansaço e "jogos desde a troca de
  técnico" podem usar a data do próprio jogo;
- tabelas externas (trocas de técnico) filtradas por data < h.

O embrulho `ComFatores` faz isso dentro de prever(), com o horizonte certo:
- jogos do bloco: h = primeira data do bloco (regra do backtest);
- jogos passados, usados no ajuste dos coeficientes: h = primeira data do
  bloco (temporada, rodada) de cada um, calculada dentro do próprio passado.
  O valor fica guardado por jogo_id (é função só do que veio antes).
No replay de tabela o bloco é o resto da temporada depois do corte, e todos os
jogos recebem h = data do corte: forma, ânimo, motivação, confronto e estilo
ficam congelados no valor do corte. Cansaço e técnico usam o calendário dos
jogos futuros (datas conhecidas no corte), mas só trocas anteriores ao corte.

Como as camadas entram nos modelos
----------------------------------
- Elo: covariáveis z somadas ao preditor do logit ordenado,
  s = b x + g . z, com g ajustado por máxima verossimilhança junto com os
  cortes, nas mesmas 5 temporadas do logit (sem regularização).
- Dixon-Coles: covariáveis cov_mandante / cov_visitante do modelo base, com
  ridge próprio por coluna (vetor ridge_cov).

Fatores
-------
1. MandoTime: vantagem de casa própria de cada time (uma coluna por time,
   +1 nos gols do mandante e -1 nos do visitante quando o time manda),
   encolhida para a média da liga (o mando do modelo) pelo ridge.
2. Forma: soma de (S - E) nos últimos n jogos da temporada, S = 1/0,5/0 e
   E = expectativa do Elo pré-jogo (mando de 100 pontos, que reproduz a
   pontuação média do mandante de 2003 a 2011, 0,641).
3. Animo: sequência atual de vitórias (+) ou derrotas (-) na temporada,
   limitada a +-teto; empate zera.
4. Motivacao: 1 se o time não tem mais nada a disputar (a melhor e a pior
   posição alcançáveis caem na mesma faixa: título, 2-6, 7-12, meio, Z4),
   com a tabela antes do horizonte e um fator de realismo alfa nos pontos
   ainda em jogo (alfa = 1 é a conta matemática).
5. ConfrontoDireto: resíduo (S - E) do mandante nos últimos m confrontos com o
   mesmo adversário, em qualquer mando, dividido por (confrontos + 1).
6. Estilo (ESPN): perfil de cada time nos últimos n jogos com estatística:
   "aberto" = chutes feitos + cedidos por jogo (contra a média da liga nos
   365 dias anteriores, em unidades de 5 chutes) e posse (em unidades de 10
   pontos acima de 50%). Covariáveis: aberto_m + aberto_v e
   aberto_m x aberto_v (as duas nos dois lados) e posse do atacante x aberto
   do defensor (time que propõe contra time aberto ou fechado).
7. Finalizacoes (ESPN): log da razão entre os chutes (e os chutes no gol)
   feitos pelo atacante e cedidos pelo defensor nos últimos n jogos e a média
   da liga, encolhidos com 3 jogos de média da liga.
8. Cansaco: dias desde o jogo anterior do time, limitado a `teto`. Limite: só
   há jogos de Série A na base (copas e estaduais não entram).
11. CansacoCopas: o mesmo, contando também os jogos de Libertadores,
   Sul-Americana e Copa do Brasil (modelos/copas.py; estaduais não entram).
12. CopaDepois: 1 se o time tem jogo de copa até `dias` dias depois do jogo
   da Série A. A data dos jogos de copa seguintes vem do calendário (é
   conhecida antes da rodada).
9. Tecnico: 1 se o time está nos primeiros k jogos depois de uma troca de
   técnico feita durante a temporada (data da troca < horizonte e >= primeiro
   jogo do time na temporada). Data da troca = data_saida (ou data_entrada,
   se faltar a saída); linhas sem as duas ficam de fora.

Uso:
    from modelos.fatores import ComFatores, Forma
    m = ComFatores("elo", [Forma(5)], nome="elo_forma")
    prev, _ = rodar_backtest(jogos, [m], 2012, 2025)
"""
from __future__ import annotations

import itertools
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit

from modelos.backtest import Previsao
from modelos.dixon_coles import DixonColes
from modelos.elo import LOGIT_INICIAL, MINIMO_JOGOS_LOGIT, Elo
from modelos.hiperparametros import DIXON_COLES, ELO

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO_TROCAS = RAIZ / "dados" / "manuais" / "trocas_tecnico.csv"
PRIMEIRA_TESTE = 2026
COLS_CALENDARIO = ["jogo_id", "temporada", "rodada", "data", "mandante_id", "visitante_id"]
MANDO_ESPERADO = 100.0   # pontos de Elo; E(mandante) médio = 0,641 em 2003-2011
UM_DIA = np.timedelta64(1, "D")


# ---------------------------------------------------------------------------
# Dados externos (ESPN e trocas de técnico), sempre sem 2026
# ---------------------------------------------------------------------------
def carregar_estatisticas(ate_temporada: int, permitir_teste: bool = False) -> pd.DataFrame:
    """Uma linha por (jogo_id, time_id): chutes, chutes no gol e posse do time
    e os chutes e chutes no gol cedidos (do adversário). Nulo = sem dado."""
    if ate_temporada >= PRIMEIRA_TESTE and not permitir_teste:
        raise ValueError(f"{PRIMEIRA_TESTE} é o teste final")
    from modelos.carga import _consultar
    sql = ("select jogo_id, time_id, adversario_id, posse_pct, chutes, chutes_no_gol "
           "from marts.fct_estatisticas_jogo where temporada <= %s")
    linhas = _consultar(sql, (ate_temporada,))
    e = pd.DataFrame(linhas, columns=["jogo_id", "time_id", "adversario_id", "posse",
                                      "chutes_f", "sot_f"])
    for c in ("posse", "chutes_f", "sot_f"):
        e[c] = pd.to_numeric(e[c], errors="coerce").astype(float)
    return preparar_estatisticas(e)


def preparar_estatisticas(e: pd.DataFrame) -> pd.DataFrame:
    """Junta os cedidos (linha do adversário no mesmo jogo)."""
    adv = e[["jogo_id", "time_id", "chutes_f", "sot_f"]].rename(
        columns={"time_id": "adversario_id", "chutes_f": "chutes_c", "sot_f": "sot_c"})
    out = e.merge(adv, on=["jogo_id", "adversario_id"], how="left")
    return out[["jogo_id", "time_id", "posse", "chutes_f", "sot_f", "chutes_c", "sot_c"]]


def carregar_trocas(ate_temporada: int, arquivo: Path = ARQUIVO_TROCAS) -> tuple[pd.DataFrame, int]:
    """Trocas com data (saída, ou entrada se faltar a saída). Devolve a tabela
    (time_id, data_troca) e quantas linhas ficaram de fora por não ter data."""
    if ate_temporada >= PRIMEIRA_TESTE:
        raise ValueError(f"{PRIMEIRA_TESTE} é o teste final")
    t = pd.read_csv(arquivo)
    t = t[t["temporada"] <= ate_temporada].copy()
    t["data_troca"] = pd.to_datetime(t["data_saida"]).fillna(pd.to_datetime(t["data_entrada"]))
    sem_data = int(t["data_troca"].isna().sum())
    t = t.dropna(subset=["data_troca"])
    return t[["time_id", "data_troca"]].sort_values(["time_id", "data_troca"]).reset_index(drop=True), sem_data


# ---------------------------------------------------------------------------
# Estruturas de consulta
# ---------------------------------------------------------------------------
def inicio_dos_blocos(jogos: pd.DataFrame) -> np.ndarray:
    """Primeira data do bloco (temporada, rodada) de cada linha."""
    return jogos.groupby(["temporada", "rodada"])["data"].transform("min").to_numpy()


def _fatias(chave: np.ndarray) -> dict:
    vals, inicio = np.unique(chave, return_index=True)
    ordem = np.argsort(inicio)
    vals, inicio = vals[ordem], inicio[ordem]
    fim = np.r_[inicio[1:], len(chave)]
    return {v: (int(a), int(b)) for v, a, b in zip(vals, inicio, fim)}


_SERIAL = itertools.count()


class Historia:
    """Jogos com resultado conhecido, uma linha por (time, jogo), em ordem de
    time e data. `we_mandante`: expectativa do Elo pré-jogo do mandante."""

    def __init__(self, H: pd.DataFrame, we_mandante: np.ndarray, estat: pd.DataFrame | None = None):
        n = len(H)
        gm = H["gols_mandante"].to_numpy(dtype=float)
        gv = H["gols_visitante"].to_numpy(dtype=float)
        s_m = np.where(gm > gv, 1.0, np.where(gm == gv, 0.5, 0.0))
        datas = H["data"].to_numpy()
        longo = pd.DataFrame({
            "time": np.r_[H["mandante_id"].to_numpy(), H["visitante_id"].to_numpy()],
            "adv": np.r_[H["visitante_id"].to_numpy(), H["mandante_id"].to_numpy()],
            "data": np.r_[datas, datas],
            "temporada": np.r_[H["temporada"].to_numpy(), H["temporada"].to_numpy()].astype(int),
            "jogo_id": np.r_[H["jogo_id"].to_numpy(), H["jogo_id"].to_numpy()],
            "S": np.r_[s_m, 1.0 - s_m],
            "E": np.r_[we_mandante, 1.0 - we_mandante],
        })
        longo["pontos"] = np.where(longo["S"] == 1.0, 3, np.where(longo["S"] == 0.5, 1, 0))
        cols_est = ["posse", "chutes_f", "sot_f", "chutes_c", "sot_c"]
        if estat is not None and n:
            longo = longo.merge(estat.rename(columns={"time_id": "time"}),
                                on=["jogo_id", "time"], how="left")
        else:
            for c in cols_est:
                longo[c] = np.nan
        longo = longo.sort_values(["time", "data", "jogo_id"], kind="mergesort").reset_index(drop=True)
        self.L = {c: longo[c].to_numpy() for c in longo.columns}
        self.n = len(longo)
        self.fatia = _fatias(self.L["time"]) if self.n else {}
        self._liga = {}
        self.serial = next(_SERIAL)

    def antes(self, time, h) -> tuple[int, int]:
        """Índices [a, b) dos jogos do time com data < h."""
        if time not in self.fatia:
            return 0, 0
        a, b = self.fatia[time]
        return a, a + int(np.searchsorted(self.L["data"][a:b], h, side="left"))

    def liga(self, h, coluna: str) -> float:
        """Média da coluna por (time, jogo) nos 365 dias antes de h (nan se vazio)."""
        chave = (h, coluna)
        if chave not in self._liga:
            d = self.L["data"]
            v = self.L[coluna] if coluna != "aberto" else self.L["chutes_f"] + self.L["chutes_c"]
            m = (d < h) & (d >= h - 365 * UM_DIA) & np.isfinite(v)
            self._liga[chave] = float(v[m].mean()) if m.any() else np.nan
        return self._liga[chave]


class Calendario:
    """Datas dos jogos (sem placar) de H e do bloco, por time."""

    def __init__(self, cal: pd.DataFrame):
        datas = cal["data"].to_numpy()
        longo = pd.DataFrame({
            "time": np.r_[cal["mandante_id"].to_numpy(), cal["visitante_id"].to_numpy()],
            "data": np.r_[datas, datas],
            "temporada": np.r_[cal["temporada"].to_numpy(), cal["temporada"].to_numpy()].astype(int),
        }).sort_values(["time", "data"], kind="mergesort").reset_index(drop=True)
        self.L = {c: longo[c].to_numpy() for c in longo.columns}
        self.fatia = _fatias(self.L["time"]) if len(longo) else {}
        self.times_temp: dict[int, set] = {}
        for t, m, v in zip(cal["temporada"].to_numpy(), cal["mandante_id"].to_numpy(),
                           cal["visitante_id"].to_numpy()):
            self.times_temp.setdefault(int(t), set()).update((m, v))

    def _datas(self, time):
        if time not in self.fatia:
            return np.array([], dtype="datetime64[ns]"), np.array([], dtype=int)
        a, b = self.fatia[time]
        return self.L["data"][a:b], self.L["temporada"][a:b]

    def anterior(self, time, d):
        datas, _ = self._datas(time)
        k = int(np.searchsorted(datas, d, side="left"))
        return datas[k - 1] if k else None

    def jogos_entre(self, time, d0, d1) -> int:
        datas, _ = self._datas(time)
        return int(np.searchsorted(datas, d1, side="left") - np.searchsorted(datas, d0, side="left"))

    def primeiro_da_temporada(self, time, temporada):
        datas, temps = self._datas(time)
        m = temps == temporada
        return datas[m].min() if m.any() else None


# ---------------------------------------------------------------------------
# Camadas
# ---------------------------------------------------------------------------
class Camada:
    """Interface: calcular(hist, R, horizonte, cal) -> DataFrame com as colunas
    da camada para as linhas de R (mesmo índice). cov_elo() e cov_dc() dizem
    quais colunas entram em cada modelo. `temporadas_historia`: quantas
    temporadas anteriores a camada precisa (None = todas)."""
    nome = "camada"
    temporadas_historia: int | None = 0
    so_dc = False
    relatorio: tuple = ()   # colunas exportadas junto com a previsão


    def calcular(self, hist: Historia, R: pd.DataFrame, horizonte: np.ndarray,
                 cal: Calendario) -> pd.DataFrame:
        raise NotImplementedError

    def cov_elo(self) -> list[str]:
        return [f"{self.nome}_dif"]

    def cov_dc(self) -> tuple[list[str], list[str], list[float]]:
        return [f"{self.nome}_dif"], [f"{self.nome}_neg"], [1.0]


class CamadaDiferenca(Camada):
    """Valor por time; a covariável é mandante menos visitante."""

    @property
    def relatorio(self):
        return (f"{self.nome}_m", f"{self.nome}_v")

    def valor(self, hist, cal, time, h, temporada, data_jogo) -> float:
        raise NotImplementedError

    def calcular(self, hist, R, horizonte, cal):
        vm = np.empty(len(R))
        vv = np.empty(len(R))
        memo = {}
        for i, (t, m, v, h, d) in enumerate(zip(R["temporada"].to_numpy(), R["mandante_id"].to_numpy(),
                                                 R["visitante_id"].to_numpy(), horizonte,
                                                 R["data"].to_numpy())):
            for time, alvo in ((m, vm), (v, vv)):
                chave = (time, h, d)
                if chave not in memo:
                    memo[chave] = self.valor(hist, cal, time, h, int(t), d)
                alvo[i] = memo[chave]
        dif = vm - vv
        return pd.DataFrame({f"{self.nome}_m": vm, f"{self.nome}_v": vv,
                             f"{self.nome}_dif": dif, f"{self.nome}_neg": -dif}, index=R.index)


class MandoTime(Camada):
    """Fator 1. `times`: universo fixo de times (só ids, sem resultado)."""
    nome = "mando_time"
    so_dc = True

    def __init__(self, times, ridge: float = 10.0):
        self.times = sorted(times)
        self.ridge = ridge

    def calcular(self, hist, R, horizonte, cal):
        mand = R["mandante_id"].to_numpy()
        dados = {}
        for t in self.times:
            col = (mand == t).astype(float)
            dados[f"casa_{t}"] = col
            dados[f"casa_{t}_neg"] = -col
        return pd.DataFrame(dados, index=R.index)

    def cov_elo(self):
        raise ValueError("mando por time é só do Dixon-Coles")

    def cov_dc(self):
        return ([f"casa_{t}" for t in self.times], [f"casa_{t}_neg" for t in self.times],
                [self.ridge] * len(self.times))


class Forma(CamadaDiferenca):
    """Fator 2."""
    nome = "forma"

    def __init__(self, n: int = 5):
        self.n = n

    def valor(self, hist, cal, time, h, temporada, data_jogo):
        a, b = hist.antes(time, h)
        a = max(a, b - self.n)
        m = hist.L["temporada"][a:b] == temporada
        return float((hist.L["S"][a:b][m] - hist.L["E"][a:b][m]).sum())


class Animo(CamadaDiferenca):
    """Fator 3."""
    nome = "animo"

    def __init__(self, teto: int = 4):
        self.teto = teto

    def valor(self, hist, cal, time, h, temporada, data_jogo):
        a, b = hist.antes(time, h)
        S, T = hist.L["S"], hist.L["temporada"]
        k = b - 1
        if k < a or T[k] != temporada or S[k] == 0.5:
            return 0.0
        alvo, seq = S[k], 0
        while k >= a and T[k] == temporada and S[k] == alvo and seq < self.teto:
            seq += 1
            k -= 1
        return float(seq if alvo == 1.0 else -seq)


def faixa(pos: int, n: int) -> int:
    """0 título, 1 posições 2-6, 2 posições 7-12, 3 meio, 4 Z4."""
    if pos == 1:
        return 0
    if pos <= 6:
        return 1
    if pos <= 12:
        return 2
    if pos <= n - 4:
        return 3
    return 4


class Motivacao(CamadaDiferenca):
    """Fator 4."""
    nome = "motivacao"

    def __init__(self, alfa: float = 1.0):
        self.alfa = alfa
        self._tab = {}

    def tabela(self, hist, cal, temporada, h) -> dict:
        chave = (hist.serial, temporada, h)
        if chave in self._tab:
            return self._tab[chave]
        times = sorted(cal.times_temp.get(temporada, set()))
        n = len(times)
        pts = dict.fromkeys(times, 0)
        jog = dict.fromkeys(times, 0)
        for t in times:
            a, b = hist.antes(t, h)
            m = hist.L["temporada"][a:b] == temporada
            pts[t] = int(hist.L["pontos"][a:b][m].sum())
            jog[t] = int(m.sum())
        total = 2 * (n - 1)
        p = np.array([pts[t] for t in times], dtype=float)
        rest = np.array([max(total - jog[t], 0) for t in times], dtype=float)
        alc = p + self.alfa * 3 * rest
        sem = {}
        for i, t in enumerate(times):
            outros = np.arange(n) != i
            melhor = 1 + int((p[outros] > alc[i]).sum())
            pior = 1 + int((alc[outros] >= p[i]).sum())
            sem[t] = 1.0 if faixa(melhor, n) == faixa(pior, n) else 0.0
        if len(self._tab) > 5000:
            self._tab.clear()
        self._tab[chave] = sem
        return sem

    def valor(self, hist, cal, time, h, temporada, data_jogo):
        return self.tabela(hist, cal, temporada, h).get(time, 0.0)


class ConfrontoDireto(Camada):
    """Fator 5."""
    nome = "confronto"
    temporadas_historia = None
    relatorio = ("confronto_dif",)

    def __init__(self, m: int = 5):
        self.m = m

    def calcular(self, hist, R, horizonte, cal):
        out = np.zeros(len(R))
        for i, (tm, tv, h) in enumerate(zip(R["mandante_id"].to_numpy(), R["visitante_id"].to_numpy(),
                                            horizonte)):
            a, b = hist.antes(tm, h)
            sel = np.where(hist.L["adv"][a:b] == tv)[0][-self.m:]
            if len(sel):
                r = hist.L["S"][a:b][sel] - hist.L["E"][a:b][sel]
                out[i] = r.sum() / (len(sel) + 1.0)
        return pd.DataFrame({"confronto_dif": out, "confronto_neg": -out}, index=R.index)


class Cansaco(CamadaDiferenca):
    """Fator 8. Só jogos de Série A (copas não estão na base)."""
    nome = "cansaco"

    def __init__(self, teto: int = 7):
        self.teto = teto

    def valor(self, hist, cal, time, h, temporada, data_jogo):
        ant = cal.anterior(time, data_jogo)
        if ant is None:
            return float(self.teto)
        return float(min((data_jogo - ant) / UM_DIA, self.teto))


class _Copas(CamadaDiferenca):
    """Base dos fatores 11 e 12: datas dos jogos de copa de cada time
    (modelos/copas.py: Libertadores, Sul-Americana, Copa do Brasil)."""

    def __init__(self, copas: pd.DataFrame):
        self.datas = {t: np.sort(g["data"].to_numpy().astype("datetime64[ns]"))
                      for t, g in copas.groupby("time_id")}

    def _copas(self, time):
        return self.datas.get(time, np.array([], dtype="datetime64[ns]"))


class CansacoCopas(_Copas):
    """Fator 11. Cansaço com o calendário completo: dias desde o jogo anterior
    do time na Série A ou numa copa, limitado a `teto`."""
    nome = "cansaco_copas"

    def __init__(self, copas: pd.DataFrame, teto: int = 7):
        super().__init__(copas)
        self.teto = teto

    def valor(self, hist, cal, time, h, temporada, data_jogo):
        antes = [cal.anterior(time, data_jogo)]
        datas = self._copas(time)
        k = int(np.searchsorted(datas, data_jogo, side="left"))
        if k:
            antes.append(datas[k - 1])
        antes = [a for a in antes if a is not None]
        if not antes:
            return float(self.teto)
        return float(min((data_jogo - max(antes)) / UM_DIA, self.teto))


class CopaDepois(_Copas):
    """Fator 12. 1 se o time tem jogo de copa até `dias` dias depois deste
    (rodízio de titulares antes da copa)."""
    nome = "copa_depois"

    def __init__(self, copas: pd.DataFrame, dias: int = 3):
        super().__init__(copas)
        self.dias = dias

    def valor(self, hist, cal, time, h, temporada, data_jogo):
        datas = self._copas(time)
        k = int(np.searchsorted(datas, data_jogo, side="right"))
        return float(k < len(datas) and (datas[k] - data_jogo) / UM_DIA <= self.dias)


class Tecnico(CamadaDiferenca):
    """Fator 9. `trocas`: DataFrame (time_id, data_troca)."""
    nome = "tecnico"

    def __init__(self, trocas: pd.DataFrame, k: int = 5):
        self.k = k
        self.por_time = {t: g["data_troca"].to_numpy(dtype="datetime64[ns]")
                         for t, g in trocas.groupby("time_id")}

    def valor(self, hist, cal, time, h, temporada, data_jogo):
        datas = self.por_time.get(time)
        if datas is None:
            return 0.0
        datas = datas[datas < h]       # só trocas conhecidas antes do horizonte
        if not len(datas):
            return 0.0
        ultima = datas[-1]
        primeiro = cal.primeiro_da_temporada(time, temporada)
        if primeiro is None or ultima < primeiro:
            return 0.0                 # troca de pré-temporada ou de outra temporada
        return 1.0 if cal.jogos_entre(time, ultima, data_jogo) < self.k else 0.0


class _PerfilESPN(Camada):
    temporadas_historia = 3
    so_dc = True

    def __init__(self, n: int = 19):
        self.n = n

    def _ultimos(self, hist, time, h, coluna):
        a, b = hist.antes(time, h)
        v = hist.L[coluna][a:b]
        v = v[np.isfinite(v)]
        return v[-self.n:]


class Estilo(_PerfilESPN):
    """Fator 6."""
    nome = "estilo"
    relatorio = ("estilo_aberto_m", "estilo_aberto_v", "estilo_posse_m", "estilo_posse_v")

    def _perfil(self, hist, time, h):
        a, b = hist.antes(time, h)
        tot = hist.L["chutes_f"][a:b] + hist.L["chutes_c"][a:b]
        tot = tot[np.isfinite(tot)][-self.n:]
        liga = hist.liga(h, "aberto")
        aberto = (tot.mean() - liga) / 5.0 if len(tot) >= 3 and np.isfinite(liga) else 0.0
        posse = self._ultimos(hist, time, h, "posse")
        posse = (posse.mean() - 50.0) / 10.0 if len(posse) >= 3 else 0.0
        return aberto, posse

    def calcular(self, hist, R, horizonte, cal):
        memo, linhas = {}, []
        for tm, tv, h in zip(R["mandante_id"].to_numpy(), R["visitante_id"].to_numpy(), horizonte):
            for t in (tm, tv):
                if (t, h) not in memo:
                    memo[(t, h)] = self._perfil(hist, t, h)
            am, pm = memo[(tm, h)]
            av, pv = memo[(tv, h)]
            linhas.append((am, av, pm, pv, am + av, am * av, pm * av, pv * am))
        cols = ["estilo_aberto_m", "estilo_aberto_v", "estilo_posse_m", "estilo_posse_v",
                "estilo_soma", "estilo_prod", "estilo_prop_m", "estilo_prop_v"]
        return pd.DataFrame(linhas, columns=cols, index=R.index)

    def cov_elo(self):
        raise ValueError("estilo é só do Dixon-Coles")

    def cov_dc(self):
        return (["estilo_soma", "estilo_prod", "estilo_prop_m"],
                ["estilo_soma", "estilo_prod", "estilo_prop_v"], [1.0, 1.0, 1.0])


class Finalizacoes(_PerfilESPN):
    """Fator 7."""
    nome = "finalizacoes"
    ENCOLHE = 3.0

    def _razao(self, hist, time, h, coluna):
        liga = hist.liga(h, coluna)
        if not np.isfinite(liga) or liga <= 0:
            return 0.0
        v = self._ultimos(hist, time, h, coluna)
        return float(np.log((v.sum() + self.ENCOLHE * liga) / (len(v) + self.ENCOLHE) / liga))

    def calcular(self, hist, R, horizonte, cal):
        memo, linhas = {}, []
        for tm, tv, h in zip(R["mandante_id"].to_numpy(), R["visitante_id"].to_numpy(), horizonte):
            for t in (tm, tv):
                if (t, h) not in memo:
                    memo[(t, h)] = tuple(self._razao(hist, t, h, c)
                                         for c in ("sot_f", "sot_c", "chutes_f", "chutes_c"))
            sf_m, sc_m, cf_m, cc_m = memo[(tm, h)]
            sf_v, sc_v, cf_v, cc_v = memo[(tv, h)]
            linhas.append((sf_m, sc_v, cf_m, cc_v, sf_v, sc_m, cf_v, cc_m))
        cols = ["fin_sot_atq_m", "fin_sot_def_v", "fin_ch_atq_m", "fin_ch_def_v",
                "fin_sot_atq_v", "fin_sot_def_m", "fin_ch_atq_v", "fin_ch_def_m"]
        return pd.DataFrame(linhas, columns=cols, index=R.index)

    def cov_elo(self):
        raise ValueError("finalizações é só do Dixon-Coles")

    def cov_dc(self):
        return (["fin_sot_atq_m", "fin_sot_def_v", "fin_ch_atq_m", "fin_ch_def_v"],
                ["fin_sot_atq_v", "fin_sot_def_m", "fin_ch_atq_v", "fin_ch_def_m"], [1.0] * 4)


# ---------------------------------------------------------------------------
# Elo com covariáveis no logit ordenado
# ---------------------------------------------------------------------------
def ajustar_logit_cov(X: np.ndarray, y: np.ndarray, inicio: np.ndarray) -> np.ndarray:
    """MLE do logit ordenado com preditor s = X . beta.
    theta = (c1, log(c2 - c1), beta...). y: 0 = M, 1 = E, 2 = V."""

    def nll(theta):
        c1, lg, beta = theta[0], theta[1], theta[2:]
        c2 = c1 + np.exp(lg)
        s = X @ beta
        pv, pve = expit(c1 - s), expit(c2 - s)
        p = np.where(y == 2, pv, np.where(y == 1, pve - pv, 1.0 - pve))
        p = np.clip(p, 1e-12, 1.0)
        dpv, dpve = pv * (1 - pv), pve * (1 - pve)
        dA = np.where(y == 2, dpv, np.where(y == 1, -dpv, 0.0))     # dp/dc1
        dB = np.where(y == 2, 0.0, np.where(y == 1, dpve, -dpve))   # dp/dc2
        g = np.empty_like(theta)
        g[0] = -((dA + dB) / p).sum()
        g[1] = -(dB / p).sum() * np.exp(lg)
        g[2:] = -X.T @ ((-dA - dB) / p)
        return -np.log(p).sum(), g

    return minimize(nll, inicio, jac=True, method="L-BFGS-B").x


def probs_logit_cov(s: np.ndarray, c1: float, c2: float) -> np.ndarray:
    pv, pve = expit(c1 - s), expit(c2 - s)
    return np.column_stack([1.0 - pve, pve - pv, pv])


class EloCov(Elo):
    """Elo base com covariáveis z no logit: s = b x + g . z."""

    def __init__(self, cov: list[str], **kw):
        self.cov = list(cov)
        super().__init__(**kw)

    def _zerar(self) -> None:
        super()._zerar()
        self.hist_z: list = []
        self.theta_cov = np.concatenate([LOGIT_INICIAL, np.zeros(len(self.cov))])
        self._cov_em = None

    def ajustar(self, jogos_passados: pd.DataFrame) -> None:
        super().ajustar(jogos_passados)
        n0 = len(self.hist_z)
        if n0 < self.processados:
            z = jogos_passados[self.cov].iloc[n0:self.processados].to_numpy(dtype=float)
            if not np.isfinite(z).all():
                raise ValueError("covariável com valor ausente")
            self.hist_z.extend(z.tolist())

    def _logit_cov(self, t: int) -> np.ndarray:
        chave = (len(self.hist_x), t)
        if self._cov_em != chave:
            ht = np.asarray(self.hist_t)
            m = ht >= t - self.temporadas_logit
            if m.sum() >= MINIMO_JOGOS_LOGIT:
                X = np.column_stack([np.asarray(self.hist_x)[m],
                                     np.asarray(self.hist_z, dtype=float).reshape(len(ht), -1)[m]])
                self.theta_cov = ajustar_logit_cov(X, np.asarray(self.hist_y)[m], self.theta_cov)
            self._cov_em = chave
        return self.theta_cov

    def prever(self, jogos_do_bloco: pd.DataFrame) -> Previsao:
        ts = jogos_do_bloco["temporada"].astype(int).to_numpy()
        x = np.empty(len(ts))
        for i, (t, m, v) in enumerate(zip(ts, jogos_do_bloco["mandante_id"],
                                          jogos_do_bloco["visitante_id"])):
            self._nova_temporada(int(t))
            self._garantir_time(m, int(t))
            self._garantir_time(v, int(t))
            x[i] = self._x(m, v)
        th = self._logit_cov(int(ts.max()))
        c1, c2, beta = th[0], th[0] + np.exp(th[1]), th[2:]
        z = jogos_do_bloco[self.cov].to_numpy(dtype=float)
        s = np.column_stack([x, z]) @ beta
        extras = {"diferenca": x * 100.0 - self.mando}
        for k, c in enumerate(self.cov):
            extras[f"coef_{c}"] = np.full(len(ts), beta[1 + k])
        return Previsao(probs_logit_cov(s, c1, c2), extras=extras)


# ---------------------------------------------------------------------------
# Embrulho: modelo base + camadas
# ---------------------------------------------------------------------------
class ComFatores:
    """Modelo base ('elo' ou 'dc') com camadas de fatores, sem vazamento."""

    def __init__(self, base: str, camadas: list[Camada], nome: str,
                 estat: pd.DataFrame | None = None, params_base: dict | None = None):
        self.nome, self.camadas, self.estat = nome, list(camadas), estat
        self.tipo = base
        if base == "elo":
            cols = [c for cam in camadas for c in cam.cov_elo()]
            self.base = EloCov(cols, nome=nome, **(params_base or ELO))
        elif base == "dc":
            cm, cv, rg = [], [], []
            for cam in camadas:
                a, b, r = cam.cov_dc()
                cm += a
                cv += b
                rg += r
            self.base = DixonColes(**(params_base or DIXON_COLES), cov_mandante=cm,
                                   cov_visitante=cv, ridge_cov=np.array(rg), nome=nome)
        else:
            raise ValueError(base)
        hs = [c.temporadas_historia for c in camadas]
        self.temporadas_historia = None if any(h is None for h in hs) else max(hs + [0]) + 1
        self.sombra = Elo(**ELO, nome="sombra")
        self.cache: pd.DataFrame | None = None
        self.passados = None
        self._hist, self._hist_chave = None, None

    def ajustar(self, jogos_passados: pd.DataFrame) -> None:
        self.passados = jogos_passados

    def _calcular(self, hist, R, horizonte, cal) -> pd.DataFrame:
        partes = [c.calcular(hist, R, horizonte, cal) for c in self.camadas]
        return pd.concat(partes, axis=1) if partes else pd.DataFrame(index=R.index)

    def _janela(self, df: pd.DataFrame, temporada_min: int) -> pd.DataFrame:
        if self.temporadas_historia is None:
            return df
        return df[df["temporada"] >= temporada_min - self.temporadas_historia]

    def _historia(self, H: pd.DataFrame, temporada_min: int) -> Historia:
        chave = (len(H), H["jogo_id"].iat[-1] if len(H) else None, temporada_min)
        if self._hist_chave == chave:
            return self._hist
        self.sombra.ajustar(H)
        x = np.asarray(self.sombra.hist_x[:len(H)])
        # expectativa do Elo com mando de 100 pontos (o do modelo é 150)
        we = 1.0 / (1.0 + 10.0 ** (-(x * 100.0 - ELO["mando"] + MANDO_ESPERADO) / 400.0))
        m = (H["temporada"] >= temporada_min - self.temporadas_historia).to_numpy() \
            if self.temporadas_historia is not None else np.ones(len(H), dtype=bool)
        self._hist = Historia(H[m], we[m], self.estat)
        self._hist_chave = chave
        return self._hist

    def recursos_do_passado(self, H: pd.DataFrame) -> pd.DataFrame:
        """Colunas dos jogos passados, cada um com o horizonte do seu bloco."""
        vistos = self.cache.index if self.cache is not None else pd.Index([])
        novos_m = ~H["jogo_id"].isin(vistos).to_numpy()
        if novos_m.any():
            inicio = inicio_dos_blocos(H)
            novos = H[novos_m]
            tmin = int(novos["temporada"].min())
            hist = self._historia(H, tmin)
            cal = Calendario(self._janela(H[COLS_CALENDARIO], tmin - 1))
            f = self._calcular(hist, novos, inicio[novos_m], cal)
            f.index = novos["jogo_id"].to_numpy()
            self.cache = f if self.cache is None else pd.concat([self.cache, f])
        return self.cache.loc[H["jogo_id"].to_numpy()]

    def colunas_do_bloco(self, H: pd.DataFrame, bloco: pd.DataFrame) -> pd.DataFrame:
        h = bloco["data"].min().to_datetime64()
        tmin = int(bloco["temporada"].min())
        hist = self._historia(H, tmin)
        cal_df = pd.concat([H[COLS_CALENDARIO], bloco[COLS_CALENDARIO]], ignore_index=True)
        cal = Calendario(self._janela(cal_df, tmin - 1))
        return self._calcular(hist, bloco, np.full(len(bloco), h), cal)

    def prever(self, jogos_do_bloco: pd.DataFrame) -> Previsao:
        H = self.passados.iloc[:0] if self.passados is None else self.passados
        if len(H):
            fH = self.recursos_do_passado(H)
            Hx = pd.concat([H.reset_index(drop=True), fH.reset_index(drop=True)], axis=1)
        else:
            Hx = H
        fB = self.colunas_do_bloco(H, jogos_do_bloco)
        Bx = pd.concat([jogos_do_bloco, fB], axis=1)
        self.base.ajustar(Hx)
        prev = self.base.prever(Bx)
        for cam in self.camadas:
            for c in cam.relatorio:
                prev.extras[c] = fB[c].to_numpy()
        return prev


# ---------------------------------------------------------------------------
# Fator 10: mistura com o mercado (log-odds)
# ---------------------------------------------------------------------------
def misturar(p_modelo: np.ndarray, p_mercado: np.ndarray, peso_mercado: float) -> np.ndarray:
    """Média ponderada dos logs das probabilidades, renormalizada."""
    lm = np.log(np.clip(p_modelo, 1e-12, 1.0))
    lk = np.log(np.clip(p_mercado, 1e-12, 1.0))
    z = (1.0 - peso_mercado) * lm + peso_mercado * lk
    z -= z.max(axis=1, keepdims=True)
    p = np.exp(z)
    return p / p.sum(axis=1, keepdims=True)

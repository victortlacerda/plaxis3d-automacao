# -*- coding: utf-8 -*-
"""
soiltest_calibracao.py  -  Calibracao de parametros contra ensaios triaxiais de laboratorio, usando o PLAXIS SoilTest.

O script roda no SoilTest os mesmos ensaios do laboratorio (mesma pressao confinante e drenagem), mede o erro entre
as curvas simuladas e as medidas (q x eps_a e, no nao drenado, du x eps_a) e ajusta os parametros livres sozinho:
primeiro uma amostragem do espaco de parametros, depois um refinamento Nelder-Mead. Nao depende de scipy.

ENTRADA: um CSV (separador ";") com uma linha por ponto de laboratorio e as colunas
    ensaio ; drenagem (U = nao drenado, D = drenado) ; sigma3_kPa ; eps_a_pct ; q_kPa ; du_kPa (U) ou ev_pct (D)
Convencao de laboratorio: compressao positiva, q = sigma1 - sigma3, du = excesso de poropressao, ev contracao +.

SAIDA em soiltest_saida/calibracao_<modelo>_<data>/ : historico.csv (todas as avaliacoes), melhor.json, um CSV por
ensaio simulado, graficos lab x simulacao (um PNG por grafico), relatorio.html e log.txt. O material calibrado fica
no PLAXIS Input com o nome CONFIG["nome_material"].

COMO RODAR: PLAXIS 3D Input aberto com um projeto e o servidor ativo; rode pelo Executar_script_PLAXIS.bat.
Precisa do plaxis_soiltest_auto.py na mesma pasta (ou na pasta acima). Senha: variavel PLAXIS_PASSWORD.
"""
import csv
import datetime
import json
import math
import os
import random
import time
import traceback

AQUI = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()

# =========================== CONFIG ===========================
CONFIG = {
    "lab_csv": os.path.join(AQUI, "dados_laboratorio", "lab_ciu.csv"),
    "nome_material": "CAL_HS",
    "descricao": "",                    # texto livre que vai para o relatorio (amostra, obra, laudo)
    "modelo": "HS",                     # por enquanto: HS (Hardening Soil) e MC (Mohr-Coulomb)
    "drenagem": "D",                    # drenagem do MATERIAL; o ensaio usa a coluna "drenagem" do CSV
    # Parametros fixos (chaves do plaxis_soiltest_auto)
    "fixos": {"nuur": 0.2, "pref": 100},
    # Parametros livres: chave -> (minimo, maximo, inicial). Chaves especiais:
    #   Eoed_E50  : razao Eoedref/E50ref        Eur_E50 : razao Eurref/E50ref
    #   sigma_p   : tensao vertical de pre-adensamento em kPa (em cada ensaio vale max(sigma_p, sigma3))
    "livres": {
        "E50ref":   (3000, 80000, 15000),
        "Eoed_E50": (0.5, 1.5, 1.0),
        "Eur_E50":  (2.2, 8.0, 3.0),
        "m":        (0.3, 1.0, 0.6),
        "cref":     (0.0, 40.0, 13.0),
        "phi":      (26.0, 38.0, 32.0),
        "psi":      (0.0, 12.0, 3.0),
        "sigma_p":  (50.0, 600.0, 250.0),
    },
    "eps_max_ajuste_pct": 15.0,         # ajusta ate esta deformacao axial
    "peso_du": 1.0,                     # peso do erro de poropressao (ou de ev no drenado) frente ao de q
    "passos_busca": 60,                 # Steps do triaxial durante a busca (menos = mais rapido)
    "passos_final": 150,                # Steps na rodada final do melhor conjunto
    "amostras_iniciais": 40,            # avaliacoes da amostragem inicial
    "max_avaliacoes": 280,              # total de avaliacoes (amostragem + refinamento)
    "tempo_max_min": 40,                # para a busca ao atingir este tempo
    "semente": 1,
    "referencia_laudo": {},             # opcional, so para o relatorio. Ex.: {"phi": 32.0, "c": 13.4}
}
# ==============================================================
PENALIDADE = 3.0        # erro de uma avaliacao que falhou; tambem e o teto do erro de cada ensaio


def carregar_auto():
    for nome in ("plaxis_soiltest_auto.py", os.path.join("..", "plaxis_soiltest_auto.py"), "plaxis_soiltest_auto_dev.py"):
        cam = os.path.normpath(os.path.join(AQUI, nome))
        if os.path.isfile(cam):
            break
    else:
        raise FileNotFoundError("Nao achei plaxis_soiltest_auto.py nesta pasta nem na pasta acima.")
    ns = {"__name__": "soiltest_auto", "__file__": cam, "__builtins__": __builtins__}
    if "g_i" in globals():
        ns["g_i"], ns["s_i"] = globals()["g_i"], globals().get("s_i")
    with open(cam, "rb") as f:
        exec(compile(f.read(), cam, "exec"), ns, ns)
    return ns


# ------------------------------------------------------------------ laboratorio
def ler_lab(caminho):
    """Devolve {ensaio: {"dren": "U"/"D", "s3": float, "eps": [...], "q": [...], "du": [...] ou "ev": [...]}}."""
    def n(x):
        x = (x or "").strip().replace(",", ".")
        return float(x) if x != "" else None
    ens = {}
    with open(caminho, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            e = ens.setdefault(r["ensaio"].strip(), {"dren": (r.get("drenagem") or "U").strip().upper()[:1],
                                                     "s3": n(r["sigma3_kPa"]), "eps": [], "q": [], "du": [], "ev": []})
            e["eps"].append(n(r["eps_a_pct"]))
            e["q"].append(n(r["q_kPa"]))
            e["du"].append(n(r.get("du_kPa")))
            e["ev"].append(n(r.get("ev_pct")))
    for e in ens.values():
        ordem = sorted(range(len(e["eps"])), key=lambda i: e["eps"][i])
        for k in ("eps", "q", "du", "ev"):
            e[k] = [e[k][i] for i in ordem]
    return ens


def interp(x, y, xv):
    if xv <= x[0]:
        return y[0]
    for i in range(1, len(x)):
        if x[i] >= xv:
            if x[i] == x[i - 1]:
                return y[i]
            return y[i - 1] + (y[i] - y[i - 1]) * (xv - x[i - 1]) / (x[i] - x[i - 1])
    return y[-1]


def envoltoria(pontos):
    """Regressao t = m + s' tan(alfa) em pontos (s', t) -> (phi' em graus, c' em kPa)."""
    n = len(pontos)
    if n < 2:
        return None
    sx = sum(p[0] for p in pontos); sy = sum(p[1] for p in pontos)
    sxx = sum(p[0] ** 2 for p in pontos); sxy = sum(p[0] * p[1] for p in pontos)
    den = n * sxx - sx * sx
    if den == 0:
        return None
    a = (n * sxy - sx * sy) / den
    m = (sy - a * sx) / n
    if not -1 < a < 1:
        return None
    phi = math.asin(a)
    return math.degrees(phi), m / math.cos(phi)


def interpretar_lab(lab):
    """Pontos de ruptura por tres criterios e envoltorias efetivas (so ensaios nao drenados com du)."""
    crit = {"q máximo": [], "razão σ'1/σ'3 máxima": [], "fim do ensaio": []}
    linhas = []
    for nome, e in lab.items():
        if e["dren"] != "U" or any(v is None for v in e["du"]):
            continue
        pts = []
        for ea, q, du in zip(e["eps"], e["q"], e["du"]):
            s3e = e["s3"] - du
            if ea > 0 and s3e > 0:
                pts.append((ea, q, du, (2 * s3e + q) / 2.0, q / 2.0, (s3e + q) / s3e))
        if not pts:
            continue
        a = max(pts, key=lambda p: p[1]); b = max(pts, key=lambda p: p[5]); c = pts[-1]
        crit["q máximo"].append((a[3], a[4])); crit["razão σ'1/σ'3 máxima"].append((b[3], b[4])); crit["fim do ensaio"].append((c[3], c[4]))
        linhas.append((nome, e["s3"], a[1], a[0], a[2], max(p[2] for p in pts), c[2]))
    return linhas, {k: envoltoria(v) for k, v in crit.items()}


# ------------------------------------------------------------------ parametros
def montar_valores(cfg, x):
    """Vetor de parametros livres (dict) -> (valores do material, sigma_p)."""
    v = dict(cfg["fixos"])
    for k, val in x.items():
        if k not in ("Eoed_E50", "Eur_E50", "sigma_p"):
            v[k] = val
    if "Eoed_E50" in x:
        v["Eoedref"] = x["Eoed_E50"] * v["E50ref"]
    if "Eur_E50" in x:
        v["Eurref"] = x["Eur_E50"] * v["E50ref"]
    return v, x.get("sigma_p", 0.0)


class Sessao(object):
    """Mantem o Input, o material e a janela do SoilTest; aplica parametros e roda os ensaios do laboratorio."""

    def __init__(self, A, cfg, lab):
        self.A, self.cfg, self.lab = A, cfg, lab
        self.modelo, self.dren = cfg["modelo"], cfg["drenagem"]
        self.gi = A["obter_input"](A["CONFIG"])
        self.g = None
        self.rapido = None            # True: muda parametros direto no Material do SoilTest; False: reabre o SoilTest
        self.log_real = A["log"]
        self.silencio = []

    def _quieto(self, on):
        if on:
            self.silencio = []
            self.A["log"] = lambda m="": self.silencio.append(str(m))
        else:
            self.A["log"] = self.log_real

    def abrir(self, valores):
        A = self.A
        completos = {c: valores.get(c) for c, _a, _r, _v in A["parametros"](self.modelo, self.dren)}
        mat = A["criar_material"](self.gi, self.cfg["nome_material"], self.modelo, self.dren, completos, None)
        if mat is None:
            return False
        if self.g is not None:
            A["fechar_soiltest"](self.g)
        self.g, _porta = A["abrir_soiltest"](self.gi, mat, A["CONFIG"]["espera_soiltest_s"], A["CONFIG"]["porta_input"], self.modelo)
        return self.g is not None

    def aplicar(self, valores):
        """Aplica os parametros. Modo rapido: setproperties no Material do SoilTest, tudo numa chamada."""
        A = self.A
        if not self.rapido:
            return self.abrir(valores)
        flat = []
        for chave, aliases, _r, _v in A["parametros"](self.modelo, self.dren):
            if valores.get(chave) is None:
                continue
            attr = A["achar_attr"](self.g.Material, aliases)
            if attr is None:
                raise RuntimeError("Material do SoilTest sem o atributo de " + chave)
            flat += [attr, valores[chave]]
        self.g.Material.setproperties(*flat)
        if valores.get("phi") is not None and valores.get("K0nc") is None:
            attr = A["achar_attr"](self.g.Material, ["k0nc"])
            if attr:
                try:
                    self.g.Material.setproperties(attr, 1.0 - math.sin(math.radians(valores["phi"])))
                except Exception:
                    pass
        return True

    def simular(self, valores, sigma_p, passos, so=None):
        """Roda os ensaios do laboratorio com os parametros dados. Devolve {ensaio: dados} (None se falhar)."""
        A = self.A
        if not self.aplicar(valores):
            return None
        out = {}
        for nome, e in self.lab.items():
            if so and nome not in so:
                continue
            emax = min(max(e["eps"]), self.cfg["eps_max_ajuste_pct"]) * 1.02
            cfg_t = {"MaximumStrain": round(emax, 3), "Steps": int(passos)}
            pc = max(float(sigma_p or 0), e["s3"]) if A["MODELOS"][self.modelo]["precons"] and sigma_p else 0.0
            ctx = {"modelo": self.modelo, "dren": self.dren, "consolidacao": {"tipo": "Isotropic"}, "k0": None,
                   "preadensamento": {"modo": "pressao", "valor": pc} if pc else {"modo": "nenhum", "valor": 0},
                   "pc_usados": set(), "pc_fases_kPa": 0}
            d, _ext = A["rodar_ensaio"](self.g, "Triaxial", nome, cfg_t, "Undrained" if e["dren"] == "U" else "Drained", e["s3"], ctx)
            if d is None:
                return None
            out[nome] = d
        return out

    def detectar_modo(self, valores, sigma_p):
        """Confere se mudar parametros direto no SoilTest tem efeito (muito mais rapido do que reabrir a janela)."""
        nome = sorted(self.lab, key=lambda k: self.lab[k]["s3"])[0]
        chave = "E50ref" if "E50ref" in valores else "ERef"
        self.rapido = False
        a = self.simular(valores, sigma_p, 20, so=[nome])
        if a is None:
            return
        try:
            self.rapido = True
            v2 = dict(valores)
            v2[chave] = valores[chave] * 0.5
            for k in ("Eoedref", "Eurref"):
                if k in v2:
                    v2[k] = valores[k] * 0.5
            b = self.simular(v2, sigma_p, 20, so=[nome])
            qa, qb = a[nome]["q_kPa"][3], (b[nome]["q_kPa"][3] if b else None)
            self.rapido = bool(b) and abs(qb - qa) > 0.05 * abs(qa)
            self.detalhe_modo = "q no 3o passo: {:.2f} -> {:.2f} kPa ao reduzir a rigidez a metade no SoilTest".format(qa, qb if qb is not None else float("nan"))
        except Exception as ex:
            self.rapido = False
            self.detalhe_modo = "setproperties no Material do SoilTest falhou: {}".format(str(ex).splitlines()[0][:120])


def erro_ensaio(cfg, e, d):
    """Erro normalizado de um ensaio: RMSE(q)/q_max_lab + peso x RMSE(du ou ev)/escala."""
    emax = cfg["eps_max_ajuste_pct"]
    idx = [i for i, ea in enumerate(e["eps"]) if 0 < ea <= emax and ea <= d["eps_a_pct"][-1] * 1.001]
    if len(idx) < 3:
        return PENALIDADE, PENALIDADE, PENALIDADE
    qref = max(abs(v) for v in e["q"]) or 1.0
    eq = math.sqrt(sum(((interp(d["eps_a_pct"], d["q_kPa"], e["eps"][i]) - e["q"][i]) / qref) ** 2 for i in idx) / len(idx))
    e2 = 0.0
    if e["dren"] == "U" and all(e["du"][i] is not None for i in idx):
        e2 = math.sqrt(sum(((interp(d["eps_a_pct"], d["du_kPa"], e["eps"][i]) - e["du"][i]) / qref) ** 2 for i in idx) / len(idx))
    elif e["dren"] == "D" and all(e["ev"][i] is not None for i in idx):
        esc = max(max(abs(e["ev"][i]) for i in idx), 0.5)
        e2 = math.sqrt(sum(((interp(d["eps_a_pct"], d["ev_pct"], e["eps"][i]) - e["ev"][i]) / esc) ** 2 for i in idx) / len(idx))
    return min(PENALIDADE, eq + cfg["peso_du"] * e2), eq, e2


def nelder_mead(f, x0, passo, continuar, n_max):
    """Nelder-Mead no cubo unitario (valores cortados em [0, 1]). f recebe lista; devolve (melhor x, melhor f)."""
    corta = lambda x: [min(1.0, max(0.0, v)) for v in x]
    n = len(x0)
    simplex = [corta(x0)]
    for i in range(n):
        x = list(x0)
        x[i] = x[i] + passo if x[i] + passo <= 1 else x[i] - passo
        simplex.append(corta(x))
    vals = []
    for x in simplex:
        if not continuar():
            break
        vals.append(f(x))
    simplex = simplex[:len(vals)]
    if len(vals) < n + 1:
        i = min(range(len(vals)), key=lambda k: vals[k])
        return simplex[i], vals[i]
    it = 0
    while continuar() and it < n_max:
        it += 1
        ordem = sorted(range(n + 1), key=lambda k: vals[k])
        simplex = [simplex[k] for k in ordem]; vals = [vals[k] for k in ordem]
        if vals[-1] - vals[0] < 1e-4:
            break
        c = [sum(s[j] for s in simplex[:-1]) / n for j in range(n)]
        xr = corta([c[j] + (c[j] - simplex[-1][j]) for j in range(n)]); fr = f(xr)
        if fr < vals[0]:
            xe = corta([c[j] + 2 * (c[j] - simplex[-1][j]) for j in range(n)]); fe = f(xe)
            simplex[-1], vals[-1] = (xe, fe) if fe < fr else (xr, fr)
        elif fr < vals[-2]:
            simplex[-1], vals[-1] = xr, fr
        else:
            xc = corta([c[j] + 0.5 * (simplex[-1][j] - c[j]) for j in range(n)]); fc = f(xc)
            if fc < vals[-1]:
                simplex[-1], vals[-1] = xc, fc
            else:
                for k in range(1, n + 1):
                    if not continuar():
                        break
                    simplex[k] = corta([simplex[0][j] + 0.5 * (simplex[k][j] - simplex[0][j]) for j in range(n)])
                    vals[k] = f(simplex[k])
    i = min(range(len(vals)), key=lambda k: vals[k])
    return simplex[i], vals[i]


def graficos(A, pasta, lab, sim, titulo):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        A["log"]("Graficos nao gerados: {}".format(e))
        return []
    os.makedirs(os.path.join(pasta, "graficos"), exist_ok=True)
    nomes = sorted(lab, key=lambda k: lab[k]["s3"])
    cores = plt.get_cmap("viridis")
    specs = [("calibracao_q_x_eps_a", "q", "q_kPa", "eps_a (%)", "q (kPa)", "Tensão desviadora"),
             ("calibracao_du_x_eps_a", "du", "du_kPa", "eps_a (%)", "du (kPa) [acrescimo +]", "Excesso de poropressão"),
             ("calibracao_ev_x_eps_a", "ev", "ev_pct", "eps_a (%)", "eps_v (%) [contracao +]", "Deformação volumétrica"),
             ("calibracao_trajetoria_p_q", None, None, "p' (kPa)", "q (kPa)", "Trajetória de tensões efetivas")]
    out = []
    for arq, kl, ks, xl, yl, tit in specs:
        fig, ax = plt.subplots(figsize=(7.5, 5.2))
        desenhou = False
        for i, nome in enumerate(nomes):
            e, d = lab[nome], sim.get(nome)
            cor = cores(i / max(1, len(nomes) - 1) * 0.85)
            if kl is None:
                if e["dren"] != "U" or any(v is None for v in e["du"]):
                    continue
                ax.plot([e["s3"] - du + q / 3.0 for q, du in zip(e["q"], e["du"])], e["q"], "o", ms=3.5, color=cor)
                if d:
                    ax.plot(d["p_kPa"], d["q_kPa"], "-", color=cor, label="σ'3 = {} kPa".format(A["fmt_num"](e["s3"])))
            else:
                if any(v is None for v in e[kl]):
                    continue
                ax.plot(e["eps"], e[kl], "o", ms=3.5, color=cor)
                if d:
                    ax.plot(d["eps_a_pct"], d[ks], "-", color=cor, label="σ'3 = {} kPa".format(A["fmt_num"](e["s3"])))
            desenhou = True
        if not desenhou:
            plt.close(fig)
            continue
        ax.plot([], [], "o", ms=3.5, color="0.4", label="laboratório (pontos)")
        ax.plot([], [], "-", color="0.4", label="PLAXIS SoilTest (linhas)")
        ax.set_xlabel(A["ROTULOS"].get(xl, xl)); ax.set_ylabel(A["ROTULOS"].get(yl, yl))
        ax.set_title("{}: laboratório × simulação\n{}".format(tit, titulo), fontsize=10)
        ax.grid(True, alpha=0.3); ax.legend(fontsize=8)
        fig.tight_layout()
        cam = os.path.join(pasta, "graficos", arq + ".png")
        fig.savefig(cam, dpi=150); plt.close(fig)
        out.append(cam)
    return out


def main():
    A = carregar_auto()
    log = A["log"]
    cfg = CONFIG
    random.seed(cfg["semente"])
    if not os.path.isfile(cfg["lab_csv"]):
        log("CSV de laboratorio nao encontrado: {}".format(cfg["lab_csv"]))
        return 1
    lab = ler_lab(cfg["lab_csv"])
    modelo = cfg["modelo"]
    nomes_livres = list(cfg["livres"])
    lim = cfg["livres"]
    pasta = os.path.join(AQUI, "soiltest_saida", "calibracao_{}_{}".format(modelo, datetime.datetime.now().strftime("%Y%m%d_%H%M%S")))
    os.makedirs(pasta, exist_ok=True)
    log("Calibracao {} contra {} ensaio(s): {}".format(A["MODELOS"][modelo]["nome"], len(lab), ", ".join(
        "{} ({}, {} kPa, {} pontos)".format(k, e["dren"], A["fmt_num"](e["s3"]), len(e["eps"])) for k, e in lab.items())))
    log("Parametros livres: {}".format(", ".join("{} [{} a {}]".format(k, lim[k][0], lim[k][1]) for k in nomes_livres)))
    linhas_lab, envs = interpretar_lab(lab)
    for k, v in envs.items():
        if v:
            log("Laboratorio, envoltoria efetiva ({}): phi' = {:.1f} graus, c' = {:.1f} kPa".format(k, v[0], v[1]))

    de_unit = lambda u: {k: lim[k][0] + u[i] * (lim[k][1] - lim[k][0]) for i, k in enumerate(nomes_livres)}
    para_unit = lambda x: [(x[k] - lim[k][0]) / float(lim[k][1] - lim[k][0]) for k in nomes_livres]
    x0 = {k: lim[k][2] for k in nomes_livres}

    S = Sessao(A, cfg, lab)
    if S.gi is None:
        return 1
    v0, sp0 = montar_valores(cfg, x0)
    S._quieto(True)
    try:
        S.detectar_modo(v0, sp0)
    finally:
        S._quieto(False)
    if S.g is None:
        log("Nao consegui abrir o SoilTest com os parametros iniciais:\n   " + "\n   ".join(S.silencio[-8:]))
        return 1
    log("Modo de troca de parametros: {} ({})".format("RAPIDO (direto no SoilTest)" if S.rapido else "LENTO (reabre o SoilTest a cada avaliacao)",
                                                      getattr(S, "detalhe_modo", "")))

    modo_rapido = bool(S.rapido)
    t0 = time.time()
    hist = []
    melhor = {"erro": float("inf")}
    fh = open(os.path.join(pasta, "historico.csv"), "w", encoding="utf-8")
    fh.write(";".join(["n", "fase", "erro", "tempo_s"] + nomes_livres + ["erro_" + k for k in lab]) + "\n")

    def continuar():
        return len(hist) < cfg["max_avaliacoes"] and (time.time() - t0) < cfg["tempo_max_min"] * 60

    fase = ["amostragem"]

    def f(u):
        x = de_unit(u)
        valores, sp = montar_valores(cfg, x)
        S._quieto(True)
        try:
            sim = S.simular(valores, sp, cfg["passos_busca"])
        except Exception as ex:
            sim = None
            S.silencio.append("EXC: " + str(ex).splitlines()[0][:200])
        finally:
            S._quieto(False)
        if sim is None:
            err, partes = PENALIDADE, {k: PENALIDADE for k in lab}
            motivo = next((l for l in reversed(S.silencio) if "ERR" in l or "EXC" in l), "")
        else:
            partes = {k: erro_ensaio(cfg, lab[k], sim[k])[0] for k in lab}
            err = sum(partes.values()) / len(partes)
            motivo = ""
        hist.append(err)
        fh.write(";".join([str(len(hist)), fase[0], "{:.5f}".format(err), "{:.0f}".format(time.time() - t0)] +
                          ["{:.6g}".format(x[k]) for k in nomes_livres] + ["{:.5f}".format(partes[k]) for k in lab]) + "\n")
        fh.flush()
        if err < melhor["erro"]:
            melhor.update({"erro": err, "x": x, "partes": partes, "n": len(hist)})
        log("[{:3d}] {} erro {:.4f} (melhor {:.4f} na {}) {}{}".format(
            len(hist), fase[0][:5], err, melhor["erro"], melhor.get("n", "-"),
            " ".join("{}={:.4g}".format(k, x[k]) for k in nomes_livres), ("  <- " + motivo[:110]) if motivo else ""))
        return err

    # 1) ponto inicial + amostragem estratificada (hipercubo latino)
    f(para_unit(x0))
    n_am = max(0, cfg["amostras_iniciais"] - 1)
    col = [random.sample(range(n_am), n_am) for _ in nomes_livres] if n_am else []
    for j in range(n_am):
        if not continuar():
            break
        f([(col[i][j] + random.random()) / n_am for i in range(len(nomes_livres))])
    # 2) refinamento: Nelder-Mead a partir do melhor, com um reinicio menor
    for passo in (0.12, 0.05):
        if not continuar() or "x" not in melhor:
            break
        fase[0] = "refino" if passo > 0.1 else "refino2"
        nelder_mead(f, para_unit(melhor["x"]), passo, continuar, 400)
    fh.close()
    if "x" not in melhor or melhor["erro"] >= PENALIDADE:
        log("Nenhuma avaliacao valida. Veja o historico e o log.")
        return 1
    log("\nBusca encerrada: {} avaliacoes em {:.1f} min. Melhor erro {:.4f} (avaliacao {}).".format(
        len(hist), (time.time() - t0) / 60, melhor["erro"], melhor["n"]))

    # 3) rodada final com mais passos, material atualizado no Input e saidas
    valores, sp = montar_valores(cfg, melhor["x"])
    S._quieto(True)
    try:
        sim = S.simular(valores, sp, cfg["passos_final"])
        S.rapido = False
        S.abrir(valores)                     # grava o conjunto calibrado no material do Input
        if S.g is not None:
            A["fechar_soiltest"](S.g)
    finally:
        S._quieto(False)
    if sim is None:
        log("A rodada final falhou:\n   " + "\n   ".join(S.silencio[-8:]))
        return 1
    erros = {k: erro_ensaio(cfg, lab[k], sim[k]) for k in lab}
    for k, d in sim.items():
        A["gravar_csv"](os.path.join(pasta, "simulado_{}.csv".format(k)), d)
    log("\nParametros calibrados ({}):".format(A["MODELOS"][modelo]["nome"]))
    rot = {c: r for c, _a, r, _v in A["parametros"](modelo, cfg["drenagem"])}
    tab_par = []
    for k, v in valores.items():
        origem = "calibrado" if (k in melhor["x"] or k in ("Eoedref", "Eurref")) else "fixo"
        tab_par.append((rot.get(k, k), A["_num"](v, 3), origem))
        log("   {:28s} = {:.5g}  ({})".format(rot.get(k, k), v, origem))
    if "sigma_p" in melhor["x"]:
        tab_par.append(("σ'p, tensão vertical de pré-adensamento (kPa)", A["_num"](sp, 1), "calibrado"))
        log("   {:28s} = {:.5g}  (calibrado; em cada ensaio vale max(sigma_p, sigma3))".format("sigma_p (kPa)", sp))
    na_borda = [k for k in nomes_livres if min(melhor["x"][k] - lim[k][0], lim[k][1] - melhor["x"][k]) < 0.02 * (lim[k][1] - lim[k][0])]
    if na_borda:
        log("ATENCAO: parametro(s) no limite da faixa de busca: {} (o otimo pode estar fora da faixa).".format(", ".join(na_borda)))
    log("\nErro por ensaio (RMSE normalizado pelo q maximo do laboratorio):")
    tab_err = []
    for k in sorted(lab, key=lambda n: lab[n]["s3"]):
        e, d = lab[k], sim[k]
        tot, eq, e2 = erros[k]
        ql, qs = max(e["q"]), max(d["q_kPa"])
        tab_err.append((k, A["fmt_num"](e["s3"]), "{:.1f} %".format(100 * eq), "{:.1f} %".format(100 * e2),
                        A["_num"](ql, 1), A["_num"](qs, 1)))
        log("   {:12s} q: {:5.1f} %   {}: {:5.1f} %   q_max lab {:.1f} / sim {:.1f} kPa".format(
            k, 100 * eq, "du" if e["dren"] == "U" else "ev", 100 * e2, ql, qs))
    with open(os.path.join(pasta, "melhor.json"), "w", encoding="utf-8") as f2:
        json.dump({"modelo": modelo, "parametros_material": valores, "sigma_p_kPa": sp, "livres": melhor["x"],
                   "erro": melhor["erro"], "avaliacoes": len(hist), "modo_rapido": modo_rapido,
                   "erros_por_ensaio": {k: {"total": v[0], "q": v[1], "du_ou_ev": v[2]} for k, v in erros.items()}}, f2, indent=2, ensure_ascii=False)

    titulo = "{} | {}".format(A["MODELOS"][modelo]["nome"], cfg["descricao"] or os.path.basename(cfg["lab_csv"]))
    gerados = graficos(A, pasta, lab, sim, titulo)
    sec = [("Ensaios de laboratório", A["html_tabela"](
        ["Ensaio", "σ'3 (kPa)", "q máx (kPa)", "ε_a em q máx (%)", "Δu em q máx (kPa)", "Δu máx (kPa)", "Δu final (kPa)"],
        [(n, A["fmt_num"](s3), A["_num"](a, 1), A["_num"](b, 1), A["_num"](c, 0), A["_num"](dm, 0), A["_num"](dfim, 0)) for n, s3, a, b, c, dm, dfim in linhas_lab])
        + A["html_tabela"](["Critério de ruptura", "φ' (graus)", "c' (kPa)"],
                           [(k, A["_num"](v[0], 1), A["_num"](v[1], 1)) for k, v in envs.items() if v]
                           + ([("informado no laudo", A["_num"](cfg["referencia_laudo"].get("phi"), 1), A["_num"](cfg["referencia_laudo"].get("c"), 1))] if cfg["referencia_laudo"] else []))
        + '<p class="nota">Envoltórias efetivas por regressão nos pontos (s\', t) de cada corpo de prova, por critério de ruptura.</p>'),
        ("Parâmetros calibrados", A["html_tabela"](["Parâmetro", "Valor", "Origem"], tab_par)
         + '<p class="nota">Material gravado no PLAXIS Input como "{}". σ\'p é aplicada em cada ensaio como max(σ\'p, σ\'3). {}</p>'.format(
             A["_esc"](cfg["nome_material"]), ("<b>Atenção:</b> no limite da faixa de busca: " + ", ".join(na_borda) + ".") if na_borda else "")),
        ("Qualidade do ajuste", A["html_tabela"](["Ensaio", "σ'3 (kPa)", "Erro em q", "Erro em Δu ou ε_v", "q máx lab (kPa)", "q máx simulado (kPa)"], tab_err)
         + '<p class="nota">Erro = RMSE entre simulação e laboratório até ε_a = {} %, dividido pelo q máximo do ensaio. '
           '{} avaliações em {:.0f} min; erro médio final {:.1f} %.</p>'.format(
               A["fmt_num"](cfg["eps_max_ajuste_pct"]), len(hist), (time.time() - t0) / 60, 100 * sum(v[0] for v in erros.values()) / len(erros))),
        ("Laboratório × simulação", '<div class="figs">' + "".join(A["html_imagem"](c, os.path.basename(c)) for c in gerados) + "</div>")]
    rel = A["relatorio_html"](os.path.join(pasta, "relatorio.html"), "Calibração contra laboratório: " + A["MODELOS"][modelo]["nome"],
                              cfg["descricao"] or os.path.basename(cfg["lab_csv"]), sec)
    log("\nRelatorio: {}\nSaida: {}".format(rel, pasta))
    with open(os.path.join(pasta, "log.txt"), "w", encoding="utf-8") as f3:
        f3.write("\n".join(A["_linhas"]))
    return 0


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(traceback.format_exc())

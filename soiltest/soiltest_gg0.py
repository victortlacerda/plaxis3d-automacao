# -*- coding: utf-8 -*-
"""
soiltest_gg0.py  -  Curvas de degradacao do modulo (G/G0 x gamma) e de amortecimento (D x gamma) pelo SoilTest.

Roda o CDSS (cisalhamento simples ciclico, drenado, controle por deformacao) em varias amplitudes de distorcao e,
no ultimo ciclo de cada uma, calcula o modulo secante G e o amortecimento D (area do laco / 4 pi W).
Compara com:
  - o backbone teorico do HS small: G/G0 = 1 / (1 + 0,385 gamma/gamma0.7), com o corte em Gur, e o
    amortecimento de Masing correspondente (so para HS small);
  - a correlacao de Darendeli (2001), em funcao de PI, OCR, tensao efetiva media, N e frequencia.

COMO RODAR: PLAXIS 3D Input aberto com um projeto e o servidor ativo; rode pelo Executar_script_PLAXIS.bat.
Precisa do plaxis_soiltest_auto.py na mesma pasta (ou na pasta acima). Senha: variavel PLAXIS_PASSWORD.
Saida: soiltest_saida/gg0_<modelo>_<data>/ (gg0.csv, CSV de cada amplitude, graficos, relatorio.html, log.txt).
"""
import copy
import datetime
import math
import os
import traceback

AQUI = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()

# =========================== ESTUDO ===========================
ESTUDO = {
    "modelo": "HSsmall",
    "drenagem": "D",
    "valores": {},                          # vazio = valores de teste do plaxis_soiltest_auto (G0ref 120000, gamma0.7 2e-4)
    "sigma_v0_kPa": 100,                     # tensao vertical efetiva do CDSS
    "consolidacao": {"tipo": "Isotropic", "K0": None},
    "amplitudes_pct": [0.0001, 0.0003, 0.001, 0.003, 0.01, 0.03, 0.1, 0.3],   # distorcao gamma em %
    "ciclos": 2,
    "passos_por_quarto": 20,
    # Darendeli (2001)
    "darendeli": {"PI": 0, "OCR": 1, "N": 10, "f_Hz": 1.0},
}
# ==============================================================


ROT_COLS = {"gamma_pct": "γ (%)", "G_sec_kPa": "G secante (kPa)", "G_G0_sim": "G/G0 SoilTest", "D_pct": "D SoilTest (%)",
            "G_G0_hssmall": "G/G0 HS small teórico", "D_masing_hssmall_pct": "D Masing HS small (%)",
            "G_G0_darendeli": "G/G0 Darendeli", "D_darendeli_pct": "D Darendeli (%)"}


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


def darendeli(gamma_pct, sigma_m_kPa, PI=0.0, OCR=1.0, N=10, f_Hz=1.0):
    """Darendeli (2001): (G/Gmax, D em %) para a distorcao gamma (%)."""
    sm = sigma_m_kPa / 101.325                              # atm
    gr = (0.0352 + 0.0010 * PI * OCR ** 0.3246) * sm ** 0.3483
    a = 0.9190
    ggm = 1.0 / (1.0 + (gamma_pct / gr) ** a)
    dmin = (0.8005 + 0.0129 * PI * OCR ** -0.1069) * sm ** -0.2889 * (1 + 0.2919 * math.log(f_Hz))
    g = gamma_pct
    d1 = (100.0 / math.pi) * (4 * (g - gr * math.log((g + gr) / gr)) / (g * g / (g + gr)) - 2)
    c1 = -1.1143 * a * a + 1.8618 * a + 0.2523
    c2 = 0.0805 * a * a - 0.0710 * a - 0.0095
    c3 = -0.0005 * a * a + 0.0002 * a + 0.0003
    dmas = c1 * d1 + c2 * d1 ** 2 + c3 * d1 ** 3
    b = 0.6329 - 0.0057 * math.log(N)
    return ggm, b * ggm ** 0.1 * dmas + dmin


def hssmall_backbone(gamma_frac, g07, gur_g0):
    """HS small: G/G0 secante e amortecimento de Masing (%) para a amplitude gamma (fracao)."""
    a = 0.385
    gs = max(1.0 / (1.0 + a * gamma_frac / g07), gur_g0)
    # Masing: D = (4/pi) * integral(tau dgamma)/(tau_a gamma_a) - 2/pi, com tau = G0 g / (1 + a g/g07) (sem o corte)
    n = 400
    h = gamma_frac / n
    integ = sum(0.5 * h * (t(i * h, a, g07) + t((i + 1) * h, a, g07)) for i in range(n))
    ta = t(gamma_frac, a, g07)
    dm = 100.0 * ((4.0 / math.pi) * integ / (ta * gamma_frac) - 2.0 / math.pi) if ta > 0 else 0.0
    return gs, max(dm, 0.0)


def t(g, a, g07):
    return g / (1.0 + a * g / g07)       # tau/G0


def main():
    A = carregar_auto()
    log = A["log"]
    E = ESTUDO
    modelo, dren = E["modelo"], E["drenagem"]
    valores = {c: E["valores"].get(c, v) for c, _a, _r, v in A["parametros"](modelo, dren)}
    p = {k: float(x) for k, x in valores.items() if x is not None}
    pasta = os.path.join(AQUI, "soiltest_saida", "gg0_{}_{}".format(modelo, datetime.datetime.now().strftime("%Y%m%d_%H%M%S")))
    os.makedirs(os.path.join(pasta, "graficos"), exist_ok=True)
    log("Curvas G/G0 e D: {} {}, sigma'v0 = {} kPa, amplitudes {} %".format(modelo, dren, E["sigma_v0_kPa"], E["amplitudes_pct"]))
    gi = A["obter_input"](A["CONFIG"])
    if gi is None:
        return 1
    mat = A["criar_material"](gi, "GG0_{}_{}".format(modelo, dren), modelo, dren, valores, None)
    if mat is None:
        return 1
    g, porta = A["abrir_soiltest"](gi, mat, A["CONFIG"]["espera_soiltest_s"], A["CONFIG"]["porta_input"], modelo)
    if g is None:
        return 1
    cons = dict(E["consolidacao"])
    k0 = (float(cons["K0"]) if cons.get("K0") is not None else A["k0_automatico"](modelo, p)[0]) if cons["tipo"] == "K0" else None
    ctx = {"modelo": modelo, "dren": dren, "consolidacao": cons, "k0": k0, "preadensamento": {"modo": "nenhum", "valor": 0},
           "pc_usados": set(), "pc_fases_kPa": 0}
    sv0 = float(E["sigma_v0_kPa"])
    sm = sv0 * (1 + 2 * (k0 or 1.0)) / 3.0              # tensao efetiva media inicial
    # referencias do HS small (rigidez dependente da tensao; sigma'3 = menor tensao principal inicial)
    ref = {}
    if modelo == "HSsmall":
        s3 = sv0 * (k0 or 1.0)
        c, phi = p.get("cref", 0.0), math.radians(p.get("phi", 30.0))
        fat = ((c * math.cos(phi) + s3 * math.sin(phi)) / (c * math.cos(phi) + p["pref"] * math.sin(phi))) ** p["m"]
        ref["G0"] = p["G0ref"] * fat
        ref["Gur"] = p["Eurref"] / (2 * (1 + p["nuur"])) * fat
        log("HS small: G0 esperado = {:.0f} kPa; Gur = {:.0f} kPa (Gur/G0 = {:.3f}); gamma0.7 = {}".format(
            ref["G0"], ref["Gur"], ref["Gur"] / ref["G0"], p["gamma07"]))
    pontos = []
    for amp in E["amplitudes_pct"]:
        cfg_t = {"pressoes_kPa": [sv0], "comportamentos": ["Drained"], "InitialStaticShear": 0, "controle": "Strain",
                 "amplitude": amp, "ciclos": E["ciclos"], "passos_por_quarto": E["passos_por_quarto"], "duracao_por_ciclo": 1}
        nome = "gamma_{}pct".format(A["fmt_num"](amp).replace(".", "p"))
        log("\n-- CDSS amplitude {} % --".format(amp))
        d, ext = A["rodar_ensaio"](g, "CDSS", nome, cfg_t, "Drained", sv0, ctx)
        if d is None:
            continue
        A["gravar_csv"](os.path.join(pasta, "cdss_{}.csv".format(nome)), d)
        chk = A["checagem_ciclico"]("CDSS", d, modelo, dren, p, "Drained", cfg_t)
        m = chk.get("ultimo_ciclo")
        if not m:
            log("   sem laco valido")
            continue
        pontos.append({"gamma_pct": amp, "G_sec_kPa": m["modulo_secante_kPa"], "D_pct": m["amortecimento_pct"] or 0.0})
        log("   G_sec = {:.0f} kPa; D = {:.2f} %".format(m["modulo_secante_kPa"], m["amortecimento_pct"] or 0.0))
    A["fechar_soiltest"](g)
    if not pontos:
        log("Nenhuma amplitude rodou.")
        return 1
    g0_sim = pontos[0]["G_sec_kPa"]
    dar = E["darendeli"]
    for pt in pontos:
        pt["G_G0_sim"] = pt["G_sec_kPa"] / g0_sim
        pt["G_G0_darendeli"], pt["D_darendeli_pct"] = darendeli(pt["gamma_pct"], sm, dar["PI"], dar["OCR"], dar["N"], dar["f_Hz"])
        if ref:
            pt["G_G0_hssmall"], pt["D_masing_hssmall_pct"] = hssmall_backbone(pt["gamma_pct"] / 100.0, p["gamma07"], ref["Gur"] / ref["G0"])
    cols = ["gamma_pct", "G_sec_kPa", "G_G0_sim", "D_pct"] + (["G_G0_hssmall", "D_masing_hssmall_pct"] if ref else []) + ["G_G0_darendeli", "D_darendeli_pct"]
    with open(os.path.join(pasta, "gg0.csv"), "w", encoding="utf-8") as f:
        f.write(";".join(cols) + "\n")
        for pt in pontos:
            f.write(";".join(str(pt.get(c, "")) for c in cols) + "\n")
    log("\ngamma (%) | G (kPa) | G/G0 sim | D sim (%)" + (" | G/G0 HSsmall | D Masing (%)" if ref else "") + " | G/G0 Darendeli | D Darendeli (%)")
    for pt in pontos:
        log("   " + " | ".join(A["_num"](pt[c], 4) for c in cols))
    if ref:
        log("G0 simulado (menor amplitude) = {:.0f} kPa; esperado {:.0f} kPa".format(g0_sim, ref["G0"]))

    gerados = []
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        gx = [pt["gamma_pct"] for pt in pontos]
        for arq, serie, yl, tit in (
                ("gg0_x_gamma", [("SoilTest (CDSS)", "G_G0_sim", "o-"), ("HS small teórico", "G_G0_hssmall", "--"), ("Darendeli (2001)", "G_G0_darendeli", ":")],
                 "G/G0", "Degradação do módulo de cisalhamento"),
                ("D_x_gamma", [("SoilTest (CDSS)", "D_pct", "o-"), ("Masing com backbone HS small (sem o corte em Gur)", "D_masing_hssmall_pct", "--"), ("Darendeli (2001)", "D_darendeli_pct", ":")],
                 "D – amortecimento (%)", "Amortecimento"),
                ("G_x_gamma", [("SoilTest (CDSS)", "G_sec_kPa", "o-")], "G – módulo secante (kPa)", "Módulo de cisalhamento secante")):
            fig, ax = plt.subplots(figsize=(7, 5))
            for rot, chave, est in serie:
                ys = [pt.get(chave) for pt in pontos]
                if all(y is not None for y in ys):
                    ax.semilogx(gx, ys, est, label=rot)
            ax.set_xlabel(r"$\gamma$ – amplitude de distorção (%)")
            ax.set_ylabel(yl)
            ax.set_title("{}\n{} | σ'v0 = {} kPa | PI = {}, OCR = {}".format(tit, A["MODELOS"][modelo]["nome"], A["fmt_num"](sv0), dar["PI"], dar["OCR"]), fontsize=10)
            ax.grid(True, which="both", alpha=0.3)
            ax.legend(fontsize=8)
            fig.tight_layout()
            cam = os.path.join(pasta, "graficos", arq + ".png")
            fig.savefig(cam, dpi=150)
            plt.close(fig)
            gerados.append(cam)
    except Exception as e:
        log("Graficos nao gerados: {}".format(e))

    linhas = [[A["_num"](pt.get(c), 4) for c in cols] for pt in pontos]
    sec = [("Ensaio", A["html_tabela"](["Item", "Valor"], [
        ("Modelo", A["MODELOS"][modelo]["nome"]), ("Tensão vertical efetiva", "{} kPa".format(A["fmt_num"](sv0))),
        ("Tensão efetiva média", "{} kPa".format(A["_num"](sm, 1))), ("Ciclos por amplitude", E["ciclos"]),
        ("Darendeli", "PI = {PI}, OCR = {OCR}, N = {N}, f = {f_Hz} Hz".format(**dar))]
        + ([("G0 esperado (HS small)", "{} kPa".format(A["_num"](ref["G0"], 0))), ("G0 simulado (menor amplitude)", "{} kPa".format(A["_num"](g0_sim, 0))),
            ("Gur / G0", A["_num"](ref["Gur"] / ref["G0"], 3))] if ref else []))),
        ("Resultados", A["html_tabela"]([ROT_COLS.get(c, c) for c in cols], linhas) + '<p class="nota">G/G0 simulado usa como G0 o módulo da menor amplitude. '
         "O backbone do HS small é G/G0 = 1/(1 + 0,385 γ/γ0,7), limitado por Gur/G0; aqui γ é a amplitude de γxy do CDSS.</p>"),
        ("Gráficos", '<div class="figs">' + "".join(A["html_imagem"](c, os.path.basename(c)) for c in gerados) + "</div>")]
    rel = A["relatorio_html"](os.path.join(pasta, "relatorio.html"), "Curvas G/G0 e amortecimento ({})".format(A["MODELOS"][modelo]["nome"]),
                              "CDSS drenado em {} amplitudes".format(len(pontos)), sec)
    log("\nRelatorio: {}\nSaida: {}".format(rel, pasta))
    with open(os.path.join(pasta, "log.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(A["_linhas"]))
    return 0


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(traceback.format_exc())

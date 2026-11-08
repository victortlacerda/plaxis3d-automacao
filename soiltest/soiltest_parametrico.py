# -*- coding: utf-8 -*-
"""
soiltest_parametrico.py  -  Estudo parametrico no PLAXIS SoilTest: varia UM parametro do material numa faixa,
roda os mesmos ensaios para cada valor e entrega as curvas sobrepostas, uma tabela-resumo e um relatorio HTML.

Exemplo (padrao): Mohr-Coulomb drenado, phi' = 28, 30, 32, 34, 36 graus, triaxial drenado em sigma3 = 100 kPa.

COMO RODAR: PLAXIS 3D Input aberto com um projeto e o servidor ativo; rode pelo Executar_script_PLAXIS.bat.
Precisa do plaxis_soiltest_auto.py na mesma pasta (ou na pasta acima). Senha: variavel PLAXIS_PASSWORD.
Edite o bloco ESTUDO abaixo. Cada valor do parametro abre uma janela do SoilTest (pode fecha-las no fim).
Saida: soiltest_saida/parametrico_<modelo>_<parametro>_<data>/ (CSV, graficos, resumo.csv, relatorio.html, log.txt).
"""
import copy
import datetime
import os
import traceback

AQUI = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()

# =========================== ESTUDO ===========================
ESTUDO = {
    "modelo": "MC",                       # MC | LE | HS | HSsmall | MCC | SS
    "drenagem": "D",
    "valores_base": {"ERef": 30000, "nu": 0.3, "cRef": 5, "phi": 30, "psi": 0},   # o que nao estiver aqui usa o padrao
    "parametro": "phi",                   # chave do parametro (como em valores_base)
    "valores": [28, 30, 32, 34, 36],
    # ensaios: mesmas chaves do CONFIG do plaxis_soiltest_auto.py ("rodar" liga o ensaio)
    "ensaios": {
        "triaxial": {"rodar": True, "pressoes_kPa": [100], "comportamentos": ["Drained"], "MaximumStrain": 15, "Steps": 100},
        "oedometer": {"rodar": False},
    },
    "consolidacao": {"tipo": "Isotropic", "K0": None},
    "preadensamento": {"modo": "nenhum", "valor": 0},
}
# ==============================================================


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


def grafico_sobreposto(A, caminho, curvas, cx, cy, xl, yl, titulo, invy=False):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7, 5))
    cmap = plt.get_cmap("viridis")
    for i, (rot, d) in enumerate(curvas):
        ax.plot(d[cx], d[cy], label=rot, color=cmap(i / max(1, len(curvas) - 1)))
    ax.set_xlabel(A["ROTULOS"].get(xl, xl))
    ax.set_ylabel(A["ROTULOS"].get(yl, yl))
    ax.set_title(titulo, fontsize=10)
    if invy:
        ax.invert_yaxis()
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(caminho, dpi=150)
    plt.close(fig)
    return caminho


def main():
    A = carregar_auto()
    log = A["log"]
    E = ESTUDO
    modelo, dren, par = E["modelo"], E["drenagem"], E["parametro"]
    chaves = [c for c, _a, _r, _v in A["parametros"](modelo, dren)]
    if par not in chaves:
        raise ValueError("Parametro '{}' nao existe no {} {}. Opcoes: {}".format(par, modelo, dren, chaves))
    rotulo_par = {c: r for c, _a, r, _v in A["parametros"](modelo, dren)}[par]
    pasta = os.path.join(AQUI, "soiltest_saida", "parametrico_{}_{}_{}".format(
        modelo, par, datetime.datetime.now().strftime("%Y%m%d_%H%M%S")))
    os.makedirs(os.path.join(pasta, "graficos"), exist_ok=True)
    log("Estudo parametrico: {} {} variando {} em {}".format(modelo, dren, par, E["valores"]))
    gi = A["obter_input"](A["CONFIG"])
    if gi is None:
        return 1
    tabela = []
    por_ensaio = {}      # (tipo, curva) -> [(rotulo, dados)]
    for v in E["valores"]:
        log("\n" + "#" * 60 + "\n# {} = {}\n".format(par, v) + "#" * 60)
        cfg = copy.deepcopy(A["CONFIG"])
        cfg["interativo"] = False
        for t in ("triaxial", "oedometer", "crs", "dss", "cdss", "triaxial_ciclico"):
            cfg[t]["rodar"] = False
        for t, c in E["ensaios"].items():
            cfg[t].update(copy.deepcopy(c))
        base = dict(E["valores_base"])
        base[par] = v
        valores = {c: base.get(c, pad) for c, _a, _r, pad in A["parametros"](modelo, dren)}
        mat = A["criar_material"](gi, "PAR_{}_{}".format(modelo, dren), modelo, dren, valores, None)
        if mat is None:
            return 1
        g, porta = A["abrir_soiltest"](gi, mat, cfg["espera_soiltest_s"], cfg["porta_input"], modelo)
        if g is None:
            tabela.append({"valor": v, "erro": "SoilTest recusou o material"})
            continue
        p = {k: float(x) for k, x in valores.items() if x is not None}
        cons = dict(E["consolidacao"])
        k0 = None
        if cons["tipo"] == "K0":
            k0 = float(cons["K0"]) if cons.get("K0") is not None else A["k0_automatico"](modelo, p)[0]
        ctx = {"modelo": modelo, "dren": dren, "consolidacao": cons, "k0": k0,
               "preadensamento": dict(E["preadensamento"]), "pc_usados": set(),
               "pc_fases_kPa": float(cfg.get("sigma_p_padrao_fases_kPa") or 0)}
        sub = os.path.join(pasta, "{}_{}".format(par, A["fmt_num"](v).replace(".", "p")))
        os.makedirs(sub, exist_ok=True)
        resumo = {}
        todas = A["executar_ensaios"](g, cfg, modelo, dren, p, ctx, sub, resumo)
        A["fechar_soiltest"](g)
        linha = {"valor": v}
        for tipo, series in todas.items():
            for nome, d in series.items():
                por_ensaio.setdefault((tipo, nome), []).append(("{} = {}".format(par, A["fmt_num"](v)), d))
        for nome, chk in (resumo.get("triaxial") or {}).items():
            linha["q_max " + nome] = chk.get("q_max_kPa")
            if chk.get("esperado"):
                linha["q teorico " + nome] = chk["esperado"]["kPa"]
            if chk.get("E50_simulado_kPa"):
                linha["E50 " + nome] = chk["E50_simulado_kPa"]
            linha["dilatacao max " + nome] = chk.get("dilatacao_max_pct")
        for nome, chk in (resumo.get("dss") or {}).items():
            linha["tau_max " + nome] = chk.get("tau_max_kPa")
        for chave in ("oedometer", "crs"):
            if resumo.get(chave):
                linha["eps_v max " + chave] = resumo[chave].get("eps_v_max_pct")
        tabela.append(linha)

    # graficos sobrepostos (um PNG por ensaio e grandeza)
    gerados = []
    specs = {"Triaxial": [("q_x_eps_a", "eps_a_pct", "q_kPa", "eps_a (%)", "q (kPa)", False),
                          ("ev_x_eps_a", "eps_a_pct", "ev_pct", "eps_a (%)", "eps_v (%) [contracao +]", False),
                          ("trajetoria_p_q", "p_kPa", "q_kPa", "p' (kPa)", "q (kPa)", False)],
             "Oedometer": [("sigv_x_epsv", "ev_pct", "sig_v_kPa", "eps_v (%)", "sigma_v' (kPa)", True)],
             "CRS": [("sigv_x_epsv", "ev_pct", "sig_v_kPa", "eps_v (%)", "sigma_v' (kPa)", False)],
             "DSS": [("tau_x_gamma", "gamma_pct", "tau_kPa", "gamma_xy (%)", "tau_xy (kPa)", False)]}
    try:
        for (tipo, nome), curvas in por_ensaio.items():
            for arq, cx, cy, xl, yl, invy in specs.get(tipo, []):
                cam = os.path.join(pasta, "graficos", "{}_{}_{}.png".format(A["PREFIXO_ARQ"][tipo], nome if nome != tipo else "", arq).replace("__", "_"))
                gerados.append(grafico_sobreposto(A, cam, curvas, cx, cy, xl, yl,
                                                  "{} {}: variando {}".format(A["ENSAIOS_NOMES"][tipo], nome if nome != tipo else "", rotulo_par), invy))
    except Exception as e:
        log("Graficos nao gerados: {}".format(e))

    # tabela-resumo
    cols = ["valor"] + sorted({k for l in tabela for k in l if k != "valor"})
    with open(os.path.join(pasta, "resumo.csv"), "w", encoding="utf-8") as f:
        f.write(";".join([par if c == "valor" else c for c in cols]) + "\n")
        for l in tabela:
            f.write(";".join("" if l.get(c) is None else str(l.get(c)) for c in cols) + "\n")
    log("\nResumo:")
    for l in tabela:
        log("   " + "; ".join("{}={}".format(c, A["_num"](l[c], 2) if c != "valor" else l[c]) for c in cols if c in l))

    linhas = [[A["_num"](l.get(c), 3) if c != "valor" else str(l["valor"]) for c in cols] for l in tabela]
    figs = "".join(A["html_imagem"](c, os.path.basename(c)) for c in gerados)
    sec = [("Estudo", A["html_tabela"](["Item", "Valor"], [
        ("Modelo", A["MODELOS"][modelo]["nome"]), ("Drenagem", A["DRENAGENS"][dren]["rotulo"]),
        ("Parâmetro variado", rotulo_par), ("Valores", ", ".join(A["fmt_num"](x) for x in E["valores"])),
        ("Demais parâmetros", ", ".join("{} = {}".format(k, v) for k, v in E["valores_base"].items() if k != par))])),
        ("Resultados", A["html_tabela"]([rotulo_par if c == "valor" else c for c in cols], linhas)
         + '<p class="nota">Tensões em kPa, deformações em %. "q teorico" é a solução de Mohr-Coulomb quando se aplica.</p>'),
        ("Gráficos", '<div class="figs">' + figs + "</div>")]
    rel = A["relatorio_html"](os.path.join(pasta, "relatorio.html"), "Estudo paramétrico: {} ({})".format(rotulo_par, A["MODELOS"][modelo]["nome"]),
                              "Variação de {} em {} valores".format(par, len(E["valores"])), sec)
    log("\nRelatorio: {}\nSaida: {}".format(rel, pasta))
    with open(os.path.join(pasta, "log.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(A["_linhas"]))
    return 0


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(traceback.format_exc())

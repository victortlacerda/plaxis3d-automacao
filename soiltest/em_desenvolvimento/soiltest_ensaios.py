# -*- coding: utf-8 -*-
"""
soiltest_ensaios.py - Driver de ensaios Oedometer, CRS e DSS no PLAXIS SoilTest.

Fluxo: ajusta Material (opcional) e ensaio -> validate -> calculate -> le Results -> CSV + PNG + JSON
       -> (opcional) compara com dados de laboratorio (RMSE, R2).

Rode pelo Executar_script_PLAXIS.bat com o SoilTest aberto. Edite so o bloco CONFIG.
Para o Triaxial use soiltest_triaxial.py.

Confirmado no SoilTest 2024.2 (passo 3):
  - Oedometer: tabela de fases com Duration (dia), Siginc (kPa, NEGATIVO = compressao, incremento da fase), Steps.
  - CRS: tabela de fases com Duration (dia), Epsinc (em %, NEGATIVO = compressao, incremento total da fase), Steps.
  - DSS: AbsSigyyinit (kPa), MaximumShearStrain (%), Steps; Consolidation/K0/Behaviour como no triaxial.
  - Results: listas por passo (n = Steps + 1; com varias fases, a soma de passos + 1). Compressao negativa.

Convencoes das colunas de saida (compressao positiva):
  Oedometer / CRS : tempo_dia, sig_v_kPa (=-SigyyE), sig_h_kPa (=-SigxxE), eps_v_pct (=-Epsyy*100), du_kPa, e (se e0)
  DSS             : gamma_pct (=Gamxy*100), tau_kPa (=Sigxy), sig_v_kPa, eps_v_pct (=-TotalVolumetricStrain*100), du_kPa
"""
import os
import sys
import csv
import json
import math
import datetime
import traceback

# =========================== CONFIG (edite aqui) ===========================
CONFIG = {
    "tipo": "Oedometer",     # "Oedometer" | "CRS" | "DSS"
    "nome": "ensaio",
    # Material Mohr-Coulomb. None = nao altera o valor atual.
    "material": {"ERef": None, "nu": None, "cRef": None, "phi": None, "psi": None},
    # Indice de vazios inicial (opcional; so para gerar a coluna e no oedometro/CRS)
    "e0": None,
    # Oedometer: fases de carregamento. Siginc = incremento de tensao vertical da fase (kPa, negativo = compressao)
    "oedometer": [
        {"Duration": 1, "Siginc": -25, "Steps": 10},
        {"Duration": 1, "Siginc": -25, "Steps": 10},
        {"Duration": 1, "Siginc": -50, "Steps": 10},
        {"Duration": 1, "Siginc": -100, "Steps": 10},
    ],
    # CRS: Epsinc = deformacao axial da fase em % (negativo = compressao)
    "crs": [
        {"Duration": 1, "Epsinc": -5, "Steps": 50},
    ],
    # DSS
    "dss": {
        "Behaviour": "Drained",       # "Drained" | "Undrained"
        "Consolidation": "Isotropic", # "Isotropic" | "K0"
        "K0": 1.0,                    # so enviado se Consolidation == "K0"
        "AbsSigyyinit": 100,          # kPa
        "MaximumShearStrain": 5,      # %
        "Steps": 100,
    },
    # CSV de laboratorio (separador ; ou , e decimal com virgula). Colunas aceitas:
    #   Oedometer: sig_v_kPa + eps_v_pct      CRS: eps_v_pct + sig_v_kPa
    #   DSS: gamma_pct + tau_kPa (opcionais: eps_v_pct, du_kPa)
    "lab_csv": None,
}
# ===========================================================================

AQUI = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
_linhas = []

# Pares (x, y) comparaveis por tipo de ensaio
PARES = {
    "Oedometer": [("sig_v_kPa", "eps_v_pct")],
    "CRS": [("eps_v_pct", "sig_v_kPa")],
    "DSS": [("gamma_pct", "tau_kPa"), ("gamma_pct", "eps_v_pct"), ("gamma_pct", "du_kPa")],
}


def log(msg=""):
    msg = str(msg)
    print(msg)
    _linhas.append(msg)


def conectar():
    if "g_i" in globals() and "s_i" in globals():
        log("Usando a conexao ja aberta pelo executor.")
        return globals()["g_i"]
    import getpass
    from plxscripting.easy import new_server
    senha = os.environ.get("PLAXIS_PASSWORD") or getpass.getpass("Senha do servidor (nao sera exibida): ")
    return new_server("localhost", 10000, password=senha)[1]


def serie(obj):
    return [float(v) for v in obj]


def aplicar_material(g, mat):
    args = [x for k, v in mat.items() if v is not None for x in (k, v)]
    if args:
        log("Material.setproperties({}) -> {}".format(", ".join(map(repr, args)), g.Material.setproperties(*args)))


def configurar_tabela(g, t, fases):
    """Ajusta o numero de linhas da PhaseTable e grava Duration/Siginc|Epsinc/Steps de cada fase."""
    n_alvo = len(fases)
    while len(t.PhaseTable) < n_alvo:
        t.addphase()
    while len(t.PhaseTable) > n_alvo:
        t.deletephase(len(t.PhaseTable) - 1)
    for i, fase in enumerate(fases):
        flat = [x for kv in fase.items() for x in kv]
        r = t.PhaseTable[i].setproperties(*flat)
        log("  PhaseTable[{}].setproperties({}) -> {}".format(i, fase, r))
    log("  {}".format(t.PhaseTable.echo()))


def configurar_dss(t, cfg):
    ordem = ["Behaviour", "Consolidation", "AbsSigyyinit", "MaximumShearStrain", "Steps"]
    base = [(k, cfg[k]) for k in ordem if cfg.get(k) is not None]
    if str(cfg.get("Consolidation")) == "K0" and cfg.get("K0") is not None:
        base.append(("K0", cfg["K0"]))  # K0 e somente-leitura com consolidacao isotropica
    flat = [x for kv in base for x in kv]
    try:
        log("DSS.setproperties(...) -> {}".format(t.setproperties(*flat)))
    except Exception as e:
        log("setproperties conjunto falhou ({}); aplicando um a um:".format(e))
        for k, v in base:
            try:
                t.setproperties(k, v)
                log("  {} = {} OK".format(k, v))
            except Exception as e2:
                log("  {} = {} ERRO: {}".format(k, v, e2))


def ler_oed_crs(t, e0):
    r = t.Results
    sig_v = [-v for v in serie(r.SigyyE)]
    eps_v = [-v * 100.0 for v in serie(r.Epsyy)]
    d = {
        "tempo_dia": serie(r.Time),
        "sig_v_kPa": sig_v,
        "sig_h_kPa": [-v for v in serie(r.SigxxE)],
        "eps_v_pct": eps_v,
    }
    try:
        du = serie(r.PExcess)
        d["du_kPa"] = [-v for v in du] if len(du) == len(sig_v) else [0.0] * len(sig_v)  # du = -PExcess (sinal PLAXIS)
    except Exception:
        d["du_kPa"] = [0.0] * len(sig_v)
    if e0 is not None:
        d["e"] = [e0 - (v / 100.0) * (1.0 + e0) for v in eps_v]
    return d


def ler_dss(t):
    r = t.Results
    gam = serie(r.Gamxy)
    n = len(gam)
    d = {
        "gamma_pct": [v * 100.0 for v in gam],
        "tau_kPa": serie(r.Sigxy),
        "sig_v_kPa": [-v for v in serie(r.SigyyE)],
        "eps_v_pct": [-v * 100.0 for v in serie(r.TotalVolumetricStrain)],
    }
    try:
        du = serie(r.PExcess)
        d["du_kPa"] = [-v for v in du] if len(du) == n else [0.0] * n  # du = -PExcess (sinal PLAXIS)
    except Exception:
        d["du_kPa"] = [0.0] * n
    return d


def ler_lab(caminho):
    with open(caminho, "r", encoding="utf-8-sig", newline="") as f:
        cab = f.readline()
        f.seek(0)
        delim = ";" if ";" in cab else ("\t" if "\t" in cab else ",")
        dados = {}
        for linha in csv.DictReader(f, delimiter=delim):
            for k, v in linha.items():
                if k is None or v is None or not v.strip():
                    continue
                txt = v.strip().replace(",", ".") if delim in (";", "\t") else v.strip()
                try:
                    dados.setdefault(k.strip(), []).append(float(txt))
                except ValueError:
                    pass
    return dados


def metricas(np, sx, sy, lx, ly):
    sx, sy = np.asarray(sx, dtype=float), np.asarray(sy, dtype=float)
    if len(sx) < 2 or np.any(np.diff(sx) < -1e-9):
        return {"aviso": "curva simulada nao monotonica em x (ex.: descarregamento); comparacao ignorada"}
    n = min(len(lx), len(ly))
    lx, ly = np.asarray(lx[:n], dtype=float), np.asarray(ly[:n], dtype=float)
    m = (lx >= sx.min()) & (lx <= sx.max())
    if m.sum() < 2:
        return {"aviso": "menos de 2 pontos de laboratorio dentro da faixa simulada"}
    ys = np.interp(lx[m], sx, sy)
    res = ly[m] - ys
    sst = float(((ly[m] - ly[m].mean()) ** 2).sum())
    return {"n_pontos": int(m.sum()), "RMSE": float(math.sqrt((res ** 2).mean())),
            "R2": float(1 - (res ** 2).sum() / sst) if sst > 0 else None}


def checagens_teoricas(tipo, cfg, dados):
    """Compara com solucoes fechadas do Mohr-Coulomb / elasticidade (sanidade)."""
    out = {}
    mat = cfg["material"]
    try:
        if tipo in ("Oedometer", "CRS") and None not in (mat.get("ERef"), mat.get("nu")):
            E, nu = float(mat["ERef"]), float(mat["nu"])
            Eoed = E * (1 - nu) / ((1 + nu) * (1 - 2 * nu))
            k0 = nu / (1 - nu)
            sv, ev = dados["sig_v_kPa"][-1], dados["eps_v_pct"][-1] / 100.0
            out["E_oed_teorico_kPa"] = Eoed
            out["E_oed_simulado_kPa"] = sv / ev if ev else None
            out["K0_elastico_teorico"] = k0
            out["K0_simulado"] = dados["sig_h_kPa"][-1] / sv if sv else None
        if tipo == "DSS" and None not in (mat.get("cRef"), mat.get("phi")) \
                and str(cfg["dss"].get("Behaviour")) == "Drained" and str(cfg["dss"].get("Consolidation")) == "Isotropic":
            c, phi = float(mat["cRef"]), math.radians(float(mat["phi"]))
            p = float(cfg["dss"]["AbsSigyyinit"])
            out["tau_max_MC_teorico_kPa"] = c * math.cos(phi) + p * math.sin(phi)
            out["tau_max_simulado_kPa"] = max(dados["tau_kPa"])
    except Exception as e:
        out["erro_checagem"] = str(e)
    return out


def main():
    g = conectar()
    cfg = CONFIG
    tipo = cfg["tipo"]
    if tipo not in ("Oedometer", "CRS", "DSS"):
        raise ValueError("tipo deve ser Oedometer, CRS ou DSS")
    t = getattr(g, tipo)
    pasta = os.path.join(AQUI, "soiltest_saida", "{}_{}_{}".format(
        cfg["nome"], tipo, datetime.datetime.now().strftime("%Y%m%d_%H%M%S")))
    os.makedirs(pasta, exist_ok=True)
    log("Ensaio: {}   Saida: {}".format(tipo, pasta))

    aplicar_material(g, cfg["material"])
    if tipo == "Oedometer":
        configurar_tabela(g, t, cfg["oedometer"])
    elif tipo == "CRS":
        configurar_tabela(g, t, cfg["crs"])
    else:
        configurar_dss(t, cfg["dss"])
    log("validate -> {}".format(g.validate(g.Material)))
    log("calculate -> {}".format(g.calculate(t)))

    dados = ler_dss(t) if tipo == "DSS" else ler_oed_crs(t, cfg.get("e0"))
    n = len(next(iter(dados.values())))
    log("Resultados lidos: {} pontos.".format(n))
    resumo = {"config": cfg, "tipo": tipo, "pontos": n}
    chk = checagens_teoricas(tipo, cfg, dados)
    if chk:
        resumo["checagens_teoricas"] = chk
        for k, v in chk.items():
            log("  {}: {}".format(k, v))

    cols = list(dados.keys())
    csv_path = os.path.join(pasta, "{}_simulado.csv".format(cfg["nome"]))
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["passo"] + cols)
        for i in range(n):
            w.writerow([i] + [dados[c][i] for c in cols])
    log("CSV: {}".format(csv_path))

    lab = None
    if cfg.get("lab_csv"):
        try:
            import numpy as np
            lab = ler_lab(cfg["lab_csv"])
            log("Laboratorio: colunas = {}".format(list(lab.keys())))
            comp = {}
            for x, y in PARES[tipo]:
                if x in lab and y in lab:
                    mt = metricas(np, dados[x], dados[y], lab[x], lab[y])
                    comp["{} x {}".format(y, x)] = mt
                    log("  {} x {}: {}".format(y, x, mt))
            if not comp:
                log("  Aviso: nenhuma coluna de laboratorio corresponde aos pares {}".format(PARES[tipo]))
            resumo["comparacao_lab"] = comp
        except Exception as e:
            log("Falha ao comparar com laboratorio: {}".format(e))

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        def sobrepor(ax, x, y):
            if lab and x in lab and y in lab:
                k = min(len(lab[x]), len(lab[y]))
                ax.plot(lab[x][:k], lab[y][:k], "o", ms=3, label="Laboratorio")

        fig, axs = plt.subplots(1, 2, figsize=(11, 4.5))
        if tipo == "Oedometer":
            axs[0].plot(dados["sig_v_kPa"], dados["eps_v_pct"], label="SoilTest")
            sobrepor(axs[0], "sig_v_kPa", "eps_v_pct")
            axs[0].set_xlabel("sigma'v (kPa)"); axs[0].set_ylabel("eps_v (%)"); axs[0].invert_yaxis()
            pos = [(a, b) for a, b in zip(dados["sig_v_kPa"], dados["eps_v_pct"]) if a > 0]
            axs[1].semilogx([a for a, _ in pos], [b for _, b in pos], label="SoilTest")
            if lab and "sig_v_kPa" in lab and "eps_v_pct" in lab:
                k = min(len(lab["sig_v_kPa"]), len(lab["eps_v_pct"]))
                axs[1].semilogx(lab["sig_v_kPa"][:k], lab["eps_v_pct"][:k], "o", ms=3, label="Laboratorio")
            axs[1].set_xlabel("sigma'v (kPa, log)"); axs[1].set_ylabel("eps_v (%)"); axs[1].invert_yaxis()
        elif tipo == "CRS":
            axs[0].plot(dados["eps_v_pct"], dados["sig_v_kPa"], label="SoilTest")
            sobrepor(axs[0], "eps_v_pct", "sig_v_kPa")
            axs[0].set_xlabel("eps_v (%)"); axs[0].set_ylabel("sigma'v (kPa)")
            axs[1].plot(dados["tempo_dia"], dados["eps_v_pct"], label="SoilTest")
            axs[1].set_xlabel("tempo (dia)"); axs[1].set_ylabel("eps_v (%)")
        else:
            axs[0].plot(dados["gamma_pct"], dados["tau_kPa"], label="SoilTest")
            sobrepor(axs[0], "gamma_pct", "tau_kPa")
            axs[0].set_xlabel("gamma_xy (%)"); axs[0].set_ylabel("tau_xy (kPa)")
            axs[1].plot(dados["gamma_pct"], dados["eps_v_pct"], label="SoilTest (eps_v)")
            axs[1].plot(dados["gamma_pct"], dados["du_kPa"], label="SoilTest (du, kPa)")
            axs[1].set_xlabel("gamma_xy (%)"); axs[1].set_ylabel("eps_v (%) / du (kPa)")
        for a in axs:
            a.grid(True, alpha=0.3); a.legend()
        fig.tight_layout()
        png = os.path.join(pasta, "{}_graficos.png".format(cfg["nome"]))
        fig.savefig(png, dpi=150)
        plt.close(fig)
        log("PNG: {}".format(png))
    except Exception as e:
        log("Graficos nao gerados ({}). O CSV foi gravado.".format(e))

    with open(os.path.join(pasta, "{}_resumo.json".format(cfg["nome"])), "w", encoding="utf-8") as f:
        json.dump(resumo, f, indent=2, ensure_ascii=False, default=str)
    with open(os.path.join(pasta, "{}_log.txt".format(cfg["nome"])), "w", encoding="utf-8") as f:
        f.write("\n".join(_linhas))
    log("Concluido.")
    return 0


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        log("ERRO:\n" + traceback.format_exc())
        rc = 1
    if "g_i" not in globals():
        input("\nPressione Enter para fechar...")
        sys.exit(rc)

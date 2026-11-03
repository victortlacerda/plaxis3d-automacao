# -*- coding: utf-8 -*-
"""
soiltest_triaxial.py - Driver de ensaio triaxial no PLAXIS SoilTest.

Fluxo: ajusta o Material (Mohr-Coulomb) e o Triaxial -> validate -> calculate ->
       le Results -> grava CSV + PNG + JSON -> (opcional) compara com dados de laboratorio.

Como rodar: SoilTest aberto com servidor de scripting ativo (porta 10000) e executar este
arquivo pelo Executar_script_PLAXIS.bat. Edite apenas o bloco CONFIG abaixo.

Convencoes de saida (geotecnia: compressao positiva):
  eps_a_pct = -Epsyy * 100        deformacao axial (%)
  ev_pct    = -TotalVolumetricStrain * 100   deformacao volumetrica (%), contracao positiva
  q_kPa     = DeviatoricStress    tensao desviadora
  p_kPa     = -MeanEffStress      tensao efetiva media
  du_kPa    = -PExcess            excesso de poropressao (positivo = acrescimo de poropressao)
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
    # Parametros do Material (Mohr-Coulomb). Use None para nao alterar o valor atual.
    # Unidades do projeto do SoilTest: kN/m2 e graus.
    "material": {
        "ERef": 160000,
        "nu": 0.3,
        "cRef": 10,
        "phi": 25,
        "psi": 0,
    },
    # Ensaio triaxial
    "ensaio": {
        "Behaviour": "Drained",          # "Drained" | "Undrained"
        "Consolidation": "Isotropic",    # "Isotropic" | "K0"
        "K0": 1.0,                       # so e aplicado se Consolidation == "K0"
        "Direction": "Compression",      # "Compression" | "Extension"
        "CellPressure": 100,             # kPa
        "MaximumStrain": 15,             # %
        "Steps": 100,
        "PreconsolidationPressure": 0,   # kPa
    },
    # Dados de laboratorio (CSV com colunas eps_a_pct e q_kPa; opcionais: ev_pct, du_kPa).
    # Aceita separador ";" ou "," e decimal com virgula. Deixe None para nao comparar.
    "lab_csv": None,
    # Nome base dos arquivos de saida
    "nome": "triaxial",
}
# ===========================================================================

AQUI = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
_linhas = []


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
    s, g = new_server("localhost", 10000, password=senha)
    return g


def serie(obj):
    """Converte um campo de Results (PlxValuesWithUnit) em lista de floats."""
    return [float(v) for v in obj]


def aplicar_material(g, mat):
    args = []
    for k, v in mat.items():
        if v is not None:
            args += [k, v]
    if not args:
        return
    r = g.Material.setproperties(*args)
    log("Material.setproperties({}) -> {}".format(", ".join(map(repr, args)), r))


def aplicar_ensaio(t, ens):
    base = [(k, ens[k]) for k in ("Behaviour", "Consolidation", "Direction", "CellPressure",
                                 "MaximumStrain", "Steps") if ens.get(k) is not None]
    # PreconsolidationPressure e somente-leitura no Mohr-Coulomb: so e enviado se for diferente de zero
    # (relevante para modelos como Hardening Soil/Cam-Clay).
    if ens.get("PreconsolidationPressure"):
        base.append(("PreconsolidationPressure", ens["PreconsolidationPressure"]))
    if str(ens.get("Consolidation")) == "K0" and ens.get("K0") is not None:
        base.append(("K0", ens["K0"]))  # K0 e somente-leitura quando a consolidacao e isotropica
    flat = [x for par in base for x in par]
    try:
        r = t.setproperties(*flat)
        log("Triaxial.setproperties(...) -> {}".format(r))
    except Exception as e:
        log("setproperties conjunto falhou ({}); aplicando propriedade por propriedade:".format(e))
        for k, v in base:
            try:
                t.setproperties(k, v)
                log("  {} = {}  OK".format(k, v))
            except Exception as e2:
                log("  {} = {}  ERRO: {}".format(k, v, e2))


def ler_resultados(t):
    r = t.Results
    eps_yy = serie(r.Epsyy)
    d = {
        "eps_a_pct": [-v * 100.0 for v in eps_yy],
        "ev_pct": [-v * 100.0 for v in serie(r.TotalVolumetricStrain)],
        "q_kPa": serie(r.DeviatoricStress),
        "p_kPa": [-v for v in serie(r.MeanEffStress)],
        "sig_a_kPa": [-v for v in serie(r.SigyyE)],
        "sig_r_kPa": [-v for v in serie(r.SigxxE)],
    }
    try:
        du = serie(r.PExcess)
        d["du_kPa"] = [-v for v in du] if len(du) == len(eps_yy) else [0.0] * len(eps_yy)  # PExcess usa o sinal do PLAXIS (compressao negativa): du = -PExcess
    except Exception:
        d["du_kPa"] = [0.0] * len(eps_yy)
    return d


def q_ruptura_mc(mat, sigma3):
    """Solucao fechada Mohr-Coulomb (drenado, compressao): q_f."""
    try:
        phi = math.radians(float(mat["phi"]))
        c = float(mat["cRef"])
        s = math.sin(phi)
        return 2 * s / (1 - s) * sigma3 + 2 * c * math.cos(phi) / (1 - s)
    except Exception:
        return None


def ler_lab(caminho):
    with open(caminho, "r", encoding="utf-8-sig", newline="") as f:
        cabecalho = f.readline()
        f.seek(0)
        # O separador e decidido pelo cabecalho (as virgulas decimais dos numeros enganariam a contagem).
        delim = ";" if ";" in cabecalho else ("\t" if "\t" in cabecalho else ",")
        leitor = csv.DictReader(f, delimiter=delim)
        dados = {}
        for linha in leitor:
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
    sx, sy = np.asarray(sx), np.asarray(sy)
    ordem = np.argsort(sx)
    sx, sy = sx[ordem], sy[ordem]
    lx, ly = np.asarray(lx), np.asarray(ly)
    n = min(len(lx), len(ly))
    lx, ly = lx[:n], ly[:n]
    m = (lx >= sx.min()) & (lx <= sx.max())
    if m.sum() < 2:
        return None
    ys = np.interp(lx[m], sx, sy)
    res = ly[m] - ys
    sst = float(((ly[m] - ly[m].mean()) ** 2).sum())
    return {
        "n_pontos": int(m.sum()),
        "RMSE": float(math.sqrt((res ** 2).mean())),
        "R2": float(1 - (res ** 2).sum() / sst) if sst > 0 else None,
    }


def main():
    g = conectar()
    cfg = CONFIG
    t = g.Triaxial
    carimbo = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    pasta = os.path.join(AQUI, "soiltest_saida", "{}_{}".format(cfg["nome"], carimbo))
    os.makedirs(pasta, exist_ok=True)
    log("Saida: {}".format(pasta))

    aplicar_material(g, cfg["material"])
    aplicar_ensaio(t, cfg["ensaio"])
    log("validate -> {}".format(g.validate(g.Material)))
    log("calculate -> {}".format(g.calculate(t)))

    dados = ler_resultados(t)
    n = len(dados["eps_a_pct"])
    log("Resultados lidos: {} pontos. q_max = {:.3f} kPa em eps_a = {:.2f} %".format(
        n, max(dados["q_kPa"]), dados["eps_a_pct"][dados["q_kPa"].index(max(dados["q_kPa"]))]))

    resumo = {"config": cfg, "q_max_kPa": max(dados["q_kPa"]), "pontos": n}
    if str(cfg["ensaio"]["Behaviour"]) == "Drained" and str(cfg["ensaio"]["Direction"]) == "Compression":
        qf = q_ruptura_mc(cfg["material"], float(cfg["ensaio"]["CellPressure"]))
        if qf is not None:
            resumo["q_ruptura_MC_teorico_kPa"] = qf
            log("Checagem Mohr-Coulomb (drenado/compressao): q_f teorico = {:.3f} kPa; simulado = {:.3f} kPa".format(
                qf, max(dados["q_kPa"])))

    # CSV
    csv_path = os.path.join(pasta, "{}_simulado.csv".format(cfg["nome"]))
    cols = ["eps_a_pct", "ev_pct", "q_kPa", "p_kPa", "du_kPa", "sig_a_kPa", "sig_r_kPa"]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["passo"] + cols)
        for i in range(n):
            w.writerow([i] + [dados[c][i] for c in cols])
    log("CSV: {}".format(csv_path))

    # Laboratorio
    lab = None
    if cfg.get("lab_csv"):
        try:
            import numpy as np
            lab = ler_lab(cfg["lab_csv"])
            log("Laboratorio: colunas lidas = {}".format(list(lab.keys())))
            comp = {}
            if "eps_a_pct" in lab:
                for campo in ("q_kPa", "ev_pct", "du_kPa"):
                    if campo in lab:
                        mt = metricas(np, dados["eps_a_pct"], dados[campo], lab["eps_a_pct"], lab[campo])
                        if mt:
                            comp[campo] = mt
                            log("  {}: RMSE = {:.4g}, R2 = {}".format(
                                campo, mt["RMSE"], "n/d" if mt["R2"] is None else "{:.4f}".format(mt["R2"])))
            else:
                log("  Aviso: o CSV de laboratorio precisa da coluna eps_a_pct.")
            resumo["comparacao_lab"] = comp
        except Exception as e:
            log("Falha ao comparar com laboratorio: {}".format(e))

    # Graficos
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(2, 2, figsize=(11, 8))
        a = ax.ravel()
        a[0].plot(dados["eps_a_pct"], dados["q_kPa"], label="SoilTest")
        a[0].set_xlabel("eps_a (%)"); a[0].set_ylabel("q (kPa)"); a[0].set_title("q x eps_a")
        a[1].plot(dados["eps_a_pct"], dados["ev_pct"], label="SoilTest")
        a[1].set_xlabel("eps_a (%)"); a[1].set_ylabel("eps_v (%) [contracao +]"); a[1].set_title("eps_v x eps_a")
        a[2].plot(dados["eps_a_pct"], dados["du_kPa"], label="SoilTest")
        a[2].set_xlabel("eps_a (%)"); a[2].set_ylabel("du (kPa)"); a[2].set_title("excesso de poropressao")
        a[3].plot(dados["p_kPa"], dados["q_kPa"], label="SoilTest")
        a[3].set_xlabel("p' (kPa)"); a[3].set_ylabel("q (kPa)"); a[3].set_title("trajetoria p'-q")
        if lab and "eps_a_pct" in lab:
            if "q_kPa" in lab:
                a[0].plot(lab["eps_a_pct"][:len(lab["q_kPa"])], lab["q_kPa"], "o", ms=3, label="Laboratorio")
            if "ev_pct" in lab:
                a[1].plot(lab["eps_a_pct"][:len(lab["ev_pct"])], lab["ev_pct"], "o", ms=3, label="Laboratorio")
            if "du_kPa" in lab:
                a[2].plot(lab["eps_a_pct"][:len(lab["du_kPa"])], lab["du_kPa"], "o", ms=3, label="Laboratorio")
        for x in a:
            x.grid(True, alpha=0.3); x.legend()
        fig.tight_layout()
        png = os.path.join(pasta, "{}_graficos.png".format(cfg["nome"]))
        fig.savefig(png, dpi=150)
        plt.close(fig)
        log("PNG: {}".format(png))
    except Exception as e:
        log("Graficos nao gerados ({}). O CSV foi gravado normalmente.".format(e))

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

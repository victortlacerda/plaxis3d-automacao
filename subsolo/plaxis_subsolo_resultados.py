# -*- coding: utf-8 -*-
"""
PLAXIS 3D - Subsolo com radier (Caso B): resultados.

Pré-requisito: plaxis_subsolo_interativo.py já rodado (projeto calculado e aberto no PLAXIS Input).
Lê "ultimo_modelo_subsolo.json" (mesma pasta) para saber os pontos de leitura e a geometria.

Gera na mesma pasta deste script:
  - subsolo_deslocamentos.csv     (Uz de cada ponto no fim de cada fase, em mm)
  - subsolo_piso.csv              (x, y, z, Uz [mm], M11, M22 nos nós do piso, no fim da última fase)
  - subsolo_perfil_uz.csv         (Uz do solo ao longo da linha da coluna, na superfície e no nível do piso)
  - subsolo_grafico_perfil.png    (perfil de recalque)
  - subsolo_grafico_M11.png       (mapa de momentos M11 no piso)
E imprime um resumo (recalque sob a coluna, máx./mín. de M11 e Uz no piso).

NÃO TESTADO no PLAXIS real. A leitura de resultados de plates e de nós do solo usa
g_o.getresults(...) com alternativas; cada bloco falha isoladamente (o resto continua) e imprime o
motivo, para ajustar com base no log.

Convenção: Uz em mm, positivo para CIMA (como no PLAXIS); recalque = Uz negativo.
"""
import os
import json
import getpass

from plxscripting.easy import new_server

HOST = "localhost"
DECIMAL_VIRGULA = True        # True: Excel em português (vírgula). False: ponto decimal
TOL = 1e-6

PASTA = os.path.dirname(os.path.abspath(globals().get("__file__", ".")))
ARQUIVO_JSON = os.path.join(PASTA, "ultimo_modelo_subsolo.json")
CSV_DESLOC = os.path.join(PASTA, "subsolo_deslocamentos.csv")
CSV_PISO = os.path.join(PASTA, "subsolo_piso.csv")
CSV_PERFIL = os.path.join(PASTA, "subsolo_perfil_uz.csv")
PNG_PERFIL = os.path.join(PASTA, "subsolo_grafico_perfil.png")
PNG_M11 = os.path.join(PASTA, "subsolo_grafico_M11.png")


def obter_senha():
    pw = globals().get("PLAXIS_PASSWORD") or os.environ.get("PLAXIS_PASSWORD")
    if not pw:
        pw = getpass.getpass("Senha do servidor PLAXIS: ")
    return pw


def valor(x):
    return x.value if hasattr(x, "value") else x


def num(x, casas):
    if x is None:
        return ""
    t = "{:.{}f}".format(x, casas)
    return t.replace(".", ",") if DECIMAL_VIRGULA else t


def ultima_msg(e):
    t = str(e).strip().splitlines()
    return t[-1] if t else repr(e)


# ----------------------------------------------------------------------------
# Dados do modelo
# ----------------------------------------------------------------------------
if not os.path.exists(ARQUIVO_JSON):
    raise RuntimeError("Não achei {}. Rode antes o plaxis_subsolo_interativo.py.".format(ARQUIVO_JSON))
with open(ARQUIVO_JSON, encoding="utf-8") as fh:
    M = json.load(fh)
print(">>> Parâmetros lidos de", ARQUIVO_JSON)
SUB, PONTOS = M["subsolo"], M["pontos"]
X0, Y0, LB, WB, HB = SUB["x0"], SUB["y0"], SUB["L"], SUB["W"], SUB["Hb"]
COL = M.get("coluna")
NOMES_FASES = M.get("fases", ["Excavation", "Construction", "Loading"])

print(">>> Abrindo o Output da última fase")
porta_out = g_i.view(g_i.Phases[-1])
s_o, g_o = new_server(HOST, porta_out, password=obter_senha())

try:
    fases = list(g_o.Phases)
except Exception:
    fases = [g_o.Phases[i] for i in range(-len(NOMES_FASES), 0)]
fases_calc = fases[-len(NOMES_FASES):]          # sem a Initial phase
fase_final = fases[-1]
passo_final = fase_final.Steps.value[-1]
RT = g_o.ResultTypes


def nome_fase(f):
    try:
        return str(valor(f.Identification))
    except Exception:
        return str(f)


print("    Fases lidas:", [nome_fase(f) for f in fases_calc])

# ----------------------------------------------------------------------------
# 1) Uz dos pontos selecionados no fim de cada fase
# ----------------------------------------------------------------------------
tabela = []          # (rótulo, x, y, z, [Uz por fase em mm])
try:
    for i, p in enumerate(PONTOS):
        no = g_o.Nodes[i]
        uzs = []
        for f in fases_calc:
            passo = f.Steps.value[-1]
            uzs.append(float(g_o.getcurveresults(no, passo, RT.Soil.Uz)) * 1000.0)
        tabela.append((p["rotulo"], p["x"], p["y"], p["z"], uzs))
    print("\n" + "=" * 70)
    print("DESLOCAMENTO VERTICAL Uz (mm; negativo = recalque), total acumulado no fim de cada fase")
    print("=" * 70)
    for rot, x, y, z, uzs in tabela:
        print("{:<26} ({:g}, {:g}, {:g})".format(rot, x, y, z))
        for f, u in zip(fases_calc, uzs):
            print("    {:<14} {:>10.2f} mm".format(nome_fase(f), u))
    with open(CSV_DESLOC, "w") as fh:
        fh.write("Ponto;x;y;z;" + ";".join("Uz_{}_mm".format(nome_fase(f)) for f in fases_calc) + "\n")
        for rot, x, y, z, uzs in tabela:
            fh.write("{};{};{};{};{}\n".format(rot, num(x, 3), num(y, 3), num(z, 3),
                                              ";".join(num(u, 3) for u in uzs)))
    print("    salvo em", CSV_DESLOC)
except Exception as e:  # noqa
    print("\n(FALHOU) Uz dos pontos selecionados: {}".format(ultima_msg(e)))


# ----------------------------------------------------------------------------
# 2) Leitura genérica de resultados por nó
# ----------------------------------------------------------------------------
def ler(obj, rt, loc="node"):
    """getresults com a ordem (obj, fase|passo, tipo, loc); obj=None para o solo todo."""
    erros = []
    for alvo in (fase_final, passo_final):
        for args in (((obj, alvo, rt, loc) if obj is not None else (alvo, rt, loc)),
                     ((obj, alvo, rt) if obj is not None else (alvo, rt))):
            try:
                r = g_o.getresults(*args)
                return [float(v) for v in r]
            except Exception as e:  # noqa
                erros.append(ultima_msg(e))
    raise RuntimeError("; ".join(sorted(set(erros))))


# ----------------------------------------------------------------------------
# 3) Piso: Uz, M11 e M22 nos nós
# ----------------------------------------------------------------------------
piso = None
try:
    candidatos = []
    nome_json = (M.get("piso") or {}).get("nome")
    if nome_json:
        candidatos.append(nome_json)
    try:
        candidatos += [str(getattr(p_, "Name", p_)) for p_ in g_o.Plates]
    except Exception:
        pass
    candidatos += ["Plate_{}".format(i) for i in range(1, 8)]
    vistos = set()
    for nome in candidatos:
        if nome in vistos:
            continue
        vistos.add(nome)
        try:
            objp = getattr(g_o, nome)
            xs = ler(objp, RT.Plate.X)
            ys = ler(objp, RT.Plate.Y)
            zs = ler(objp, RT.Plate.Z)
        except Exception:
            continue
        if zs and all(abs(z + HB) < 1e-4 for z in zs) and (max(xs) - min(xs)) > 0.5 * LB:
            piso = (nome, objp, xs, ys, zs)
            break
    if piso is None:
        raise RuntimeError("não encontrei a plate do piso (z = {:g}) em g_o".format(-HB))
    nome, objp, xs, ys, zs = piso
    uz = [v * 1000.0 for v in ler(objp, RT.Plate.Uz)]
    m11 = ler(objp, RT.Plate.M11)
    try:
        m22 = ler(objp, RT.Plate.M22)
    except Exception:
        m22 = [None] * len(xs)
    n = min(len(xs), len(ys), len(uz), len(m11))
    print("\n" + "=" * 70)
    print("PISO ({}), fim da fase {} - {} nós".format(nome, nome_fase(fase_final), n))
    print("=" * 70)
    i_max, i_min = max(range(n), key=lambda i: m11[i]), min(range(n), key=lambda i: m11[i])
    j_min = min(range(n), key=lambda i: uz[i])
    print("M11 máximo : {:>10.1f} kNm/m em ({:.2f}, {:.2f})".format(m11[i_max], xs[i_max], ys[i_max]))
    print("M11 mínimo : {:>10.1f} kNm/m em ({:.2f}, {:.2f})".format(m11[i_min], xs[i_min], ys[i_min]))
    print("Uz mínimo  : {:>10.2f} mm     em ({:.2f}, {:.2f})  (maior recalque do piso)".format(
        uz[j_min], xs[j_min], ys[j_min]))
    print("Uz máximo  : {:>10.2f} mm".format(max(uz[:n])))
    with open(CSV_PISO, "w") as fh:
        fh.write("x;y;z;Uz_mm;M11;M22\n")
        for i in range(n):
            fh.write("{};{};{};{};{};{}\n".format(num(xs[i], 4), num(ys[i], 4), num(zs[i], 4), num(uz[i], 4),
                                                 num(m11[i], 3), num(m22[i], 3)))
    print("    salvo em", CSV_PISO)
except Exception as e:  # noqa
    piso = None
    print("\n(FALHOU) resultados do piso: {}".format(ultima_msg(e)))

# ----------------------------------------------------------------------------
# 4) Perfil de Uz do solo ao longo da linha da coluna (y = yc)
# ----------------------------------------------------------------------------
perfil = {}
try:
    yc = COL["y"] if COL else Y0 + WB / 2.0
    sx, sy, sz = ler(None, RT.Soil.X), ler(None, RT.Soil.Y), ler(None, RT.Soil.Z)
    suz = [v * 1000.0 for v in ler(None, RT.Soil.Uz)]
    n = min(len(sx), len(sy), len(sz), len(suz))
    for rot, zalvo in (("superficie z = 0", 0.0), ("nivel do piso z = {:g}".format(-HB), -HB)):
        sel = []
        for tol in (0.05, 0.25, 0.75, 1.5, 3.0):
            sel = sorted((sx[i], suz[i]) for i in range(n) if abs(sz[i] - zalvo) < 1e-4 and abs(sy[i] - yc) <= tol)
            if len(sel) >= 6:
                break
        perfil[rot] = sel
    with open(CSV_PERFIL, "w") as fh:
        fh.write("Nivel;x;Uz_mm\n")
        for rot, pts in perfil.items():
            for x, u in pts:
                fh.write("{};{};{}\n".format(rot, num(x, 4), num(u, 4)))
    print("\n    perfil de Uz do solo (linha y = {:g}) salvo em {}".format(yc, CSV_PERFIL))
except Exception as e:  # noqa
    print("\n(FALHOU) perfil de Uz do solo: {}".format(ultima_msg(e)))

# ----------------------------------------------------------------------------
# 5) Gráficos
# ----------------------------------------------------------------------------
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception as e:  # noqa
    plt = None
    print("\n(sem gráficos: matplotlib indisponível: {})".format(e))

if plt is not None:
    print("\n>>> Gerando gráficos")
    try:
        if any(perfil.values()):
            fig, ax = plt.subplots(figsize=(9, 5))
            for rot, pts in perfil.items():
                if pts:
                    ax.plot([p_[0] for p_ in pts], [p_[1] for p_ in pts], "o-", ms=4, label=rot)
            ax.set_xlabel("x (m)")
            ax.set_ylabel("Uz (mm)")
            ax.set_title("Deslocamento vertical ao longo da linha da coluna (fim da fase {})".format(
                nome_fase(fase_final)))
            ax.grid(True, alpha=0.3)
            ax.legend()
            fig.tight_layout()
            fig.savefig(PNG_PERFIL, dpi=150)
            plt.close(fig)
            print("    gráfico salvo em", PNG_PERFIL)
    except Exception as e:  # noqa
        print("    (FALHOU) gráfico do perfil: {}".format(ultima_msg(e)))
    try:
        if piso is not None:
            nome, objp, xs, ys, zs = piso
            m11 = ler(objp, RT.Plate.M11)
            n = min(len(xs), len(ys), len(m11))
            fig, ax = plt.subplots(figsize=(7, 6))
            try:
                cs = ax.tricontourf(xs[:n], ys[:n], m11[:n], levels=14, cmap="coolwarm")
            except Exception:
                cs = ax.scatter(xs[:n], ys[:n], c=m11[:n], cmap="coolwarm", s=18)
            fig.colorbar(cs, ax=ax, label="M11 (kNm/m)")
            ax.set_aspect("equal")
            ax.set_xlabel("x (m)")
            ax.set_ylabel("y (m)")
            ax.set_title("Momentos fletores M11 no piso (fim da fase {})".format(nome_fase(fase_final)))
            fig.tight_layout()
            fig.savefig(PNG_M11, dpi=150)
            plt.close(fig)
            print("    gráfico salvo em", PNG_M11)
    except Exception as e:  # noqa
        print("    (FALHOU) gráfico de M11: {}".format(ultima_msg(e)))

try:
    g_o.close()
except Exception:
    pass

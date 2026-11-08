# -*- coding: utf-8 -*-
"""
Exemplo 2 - Resultados: força/tensão para impor 2,5 cm de recalque (deslocamento prescrito).

Pré-requisito: nichirvan_taher_exemplo2_modelo.py rodado (projeto calculado e aberto no PLAXIS Input).
Roda pelo executor externo (s_i e g_i já existem).

O deslocamento (uz do nó sob a sapata) vem da curva pré-selecionada, como no Exemplo 1.
A FORÇA que o deslocamento prescrito exige é lida do Output tentando as grandezas de força
disponíveis; esta parte é "não testada": o script LISTA tudo o que encontrou e o valor de cada
candidato no último passo, e escolhe automaticamente só se houver uma opção inequívoca.
Se não achar, leia a força no Output (Structures > Surface displacement) e preencha FORCA_MANUAL_KN.

Gera na pasta do script:
  - exemplo2_curva.csv            (SumMstage, recalque [mm], força [kN] e tensão [kN/m2], se houver)
  - exemplo2_grafico.png          (tensão x recalque, ou recalque x SumMstage se não houver força)
E imprime qa = F / (L x B) para o recalque prescrito.
"""
import os
import re
import json
import getpass

from plxscripting.easy import new_server

HOST = "localhost"
FORCA_MANUAL_KN = None        # ex.: 3173.0 (kN, lido no Output no último passo); None = tentar ler por script
DECIMAL_VIRGULA = True        # True: Excel em português (vírgula)

PASTA = os.path.dirname(os.path.abspath(globals().get("__file__", ".")))
ARQUIVO_JSON = os.path.join(PASTA, "exemplo2_modelo.json")
CSV = os.path.join(PASTA, "exemplo2_curva.csv")
PNG = os.path.join(PASTA, "exemplo2_grafico.png")


def obter_senha():
    pw = globals().get("PLAXIS_PASSWORD") or os.environ.get("PLAXIS_PASSWORD")
    if not pw:
        pw = getpass.getpass("Senha do servidor PLAXIS: ")
    return pw


def valor(x):
    return x.value if hasattr(x, "value") else x


def mstage_do_passo(step):
    reached = step.Reached
    for nome in ("SumMstage", "SumMStage", "Mstage", "SigmaMstage"):
        if hasattr(reached, nome):
            return float(valor(getattr(reached, nome)))
    raise RuntimeError("Não achei SumMstage em step.Reached.")


def ultima_linha(e):
    m = str(e).strip().splitlines()
    return m[-1] if m else repr(e)


# ----------------------------------------------------------------------------
# Parâmetros do modelo
# ----------------------------------------------------------------------------
if os.path.exists(ARQUIVO_JSON):
    with open(ARQUIVO_JSON, encoding="utf-8") as fh:
        M = json.load(fh)
    print(">>> Parâmetros lidos de", ARQUIVO_JSON)
else:
    print(">>> exemplo2_modelo.json não encontrado: usando sapata 3 x 3 m e 2,5 cm")
    M = dict(area=9.0, B=3.0, desloc_m=0.025)
AREA = float(M["area"])
DESLOC_MM = float(M["desloc_m"]) * 1000.0

# ----------------------------------------------------------------------------
# Output da última fase
# ----------------------------------------------------------------------------
print(">>> Abrindo o Output da última fase")
porta_out = g_i.view(g_i.Phases[-1])
s_o, g_o = new_server(HOST, porta_out, password=obter_senha())
fase = g_o.Phases[-1]
print("    Fase:", valor(fase.Identification) if hasattr(fase, "Identification") else fase)
passos = list(fase.Steps.value)
print("    {} passos".format(len(passos)))

try:
    no = g_o.Nodes[0]
except Exception as e:
    raise RuntimeError("Não achei o nó pré-selecionado em g_o.Nodes: {}".format(e))

# ----------------------------------------------------------------------------
# Procura de grandezas de força
# ----------------------------------------------------------------------------
PADRAO_FORCA = re.compile(r"force|reaction|resultant|^f[xyz]$|^sum", re.I)


def listar_tipos_forca():
    achados = []
    rt = g_o.ResultTypes
    for cat in dir(rt):
        if cat.startswith("_"):
            continue
        try:
            c = getattr(rt, cat)
        except Exception:
            continue
        for nome in dir(c):
            if nome.startswith("_") or not PADRAO_FORCA.search(nome):
                continue
            try:
                achados.append((cat, nome, getattr(c, nome)))
            except Exception:
                pass
    return achados


def objetos_candidatos():
    objs = []
    for nome in ("SurfaceDisplacements", "PrescribedDisplacements", "SurfaceDisplacement_1",
                 "PrescribedDisplacement_1", "SurfDispl_1", "Plates", "Plate_1", "Polygon_1"):
        try:
            o = getattr(g_o, nome)
        except Exception:
            continue
        try:
            if hasattr(o, "__getitem__") and not isinstance(o, str):
                o = o[0]
        except Exception:
            pass
        objs.append((nome, o))
    return objs


def tentar_ler(obj, passo, rt):
    """Soma o resultado nos nós/pontos do objeto; devolve float ou levanta."""
    erros = []
    for loc in ("node", None):
        try:
            r = g_o.getresults(obj, passo, rt, loc) if loc else g_o.getresults(obj, passo, rt)
            try:
                return float(sum(float(v) for v in r))
            except TypeError:
                return float(r)
        except Exception as e:  # noqa
            erros.append(ultima_linha(e))
    try:
        return float(g_o.getcurveresults(obj, passo, rt))
    except Exception as e:  # noqa
        erros.append(ultima_linha(e))
    raise RuntimeError("; ".join(erros))


leitor_forca = None   # (nome_objeto, obj, categoria, nome_tipo, rt)
if FORCA_MANUAL_KN is None:
    print("\n>>> Procurando a força do deslocamento prescrito (não testado)")
    tipos = listar_tipos_forca()
    print("    Grandezas de força/reação no Output: {}".format(
        ", ".join("{}.{}".format(c, n) for c, n, _ in tipos) or "nenhuma"))
    funcionaram = []
    for nome_obj, obj in objetos_candidatos():
        for cat, nome_t, rt in tipos:
            try:
                v = tentar_ler(obj, passos[-1], rt)
            except Exception:
                continue
            funcionaram.append((nome_obj, obj, cat, nome_t, rt, v))
    if funcionaram:
        print("    Leituras que funcionaram no último passo:")
        for nome_obj, _, cat, nome_t, _, v in funcionaram:
            print("      {:<24} {:<28} = {:.1f}".format(nome_obj, "{}.{}".format(cat, nome_t), v))
        # No PLAXIS 3D 2024.2: PrescribedDisplacement.ReactionForceZ (soma dos nós = força vertical total)
        pref = [f for f in funcionaram
                if f[3].lower() in ("reactionforcez", "fz", "sumfz", "totalforce") and abs(f[5]) > 1e-6
                and re.search(r"displ|surface", f[0] + f[2], re.I)]
        pref.sort(key=lambda f: 0 if f[3].lower() == "reactionforcez" else 1)
        if len(pref) >= 1:
            leitor_forca = pref[0][:5]
            print("    -> usando {} / {}.{} (compare com o valor do Output; no PDF: 3173 kN)".format(
                pref[0][0], pref[0][2], pref[0][3]))
        else:
            print("    -> nenhuma opção inequívoca. Escolha pelo valor (compare com o Output) e preencha "
                  "FORCA_MANUAL_KN, ou me mande esta lista.")
    else:
        print("    Nenhuma leitura funcionou. Veja a força no Output (Structures > Surface displacement) "
              "e preencha FORCA_MANUAL_KN.")

# ----------------------------------------------------------------------------
# Extrair curva
# ----------------------------------------------------------------------------
print("\n>>> Lendo passos de cálculo")
linhas = [(0.0, 0.0, None)]          # (SumMstage, recalque mm, força kN)
for step in passos:
    m = mstage_do_passo(step)
    uz = float(g_o.getcurveresults(no, step, g_o.ResultTypes.Soil.Uz))
    forca = None
    if leitor_forca is not None:
        try:
            forca = abs(tentar_ler(leitor_forca[1], step, leitor_forca[4]))
        except Exception:
            forca = None
    linhas.append((m, -uz * 1000.0, forca))
linhas = sorted(set(linhas), key=lambda r: r[0])

s_final = linhas[-1][1]
m_final = linhas[-1][0]
print("    Recalque no último passo: {:.2f} mm (prescrito: {:.1f} mm; ΣMstage = {:.3f})".format(
    s_final, DESLOC_MM, m_final))

tem_forca_curva = all(l[2] is not None for l in linhas[1:]) and len(linhas) > 1
if tem_forca_curva:
    linhas[0] = (0.0, 0.0, 0.0)
F_final = linhas[-1][2] if tem_forca_curva else FORCA_MANUAL_KN


def num(x, casas):
    t = "{:.{}f}".format(x, casas)
    return t.replace(".", ",") if DECIMAL_VIRGULA else t


with open(CSV, "w") as f:
    f.write("SumMstage;Recalque_mm;Forca_kN;Tensao_kN_m2\n")
    for m, s_, F in linhas:
        f.write("{};{};{};{}\n".format(num(m, 6), num(s_, 4),
                                       num(F, 3) if F is not None else "",
                                       num(F / AREA, 3) if F is not None else ""))
print("    {} pontos salvos em {}".format(len(linhas), CSV))

# ----------------------------------------------------------------------------
# Resumo
# ----------------------------------------------------------------------------
print("\n" + "=" * 70)
print("RESUMO (sapata de área {:.2f} m², recalque prescrito {:.1f} mm)".format(AREA, DESLOC_MM))
print("=" * 70)
if F_final is not None:
    print("Força para impor {:.1f} mm de recalque: {:.1f} kN".format(s_final, F_final))
    print("Tensão média = F / A = {:.1f} kN/m²  (= {:.2f} kgf/cm²)".format(F_final / AREA, F_final / AREA / 98.0665))
    print("Esta é a tensão admissível por recalque (o recalque de {:.0f} mm já é o limite adotado).".format(DESLOC_MM))
    print("No PDF: 3173 kN / 9 m² = 352,5 kN/m² (3,5 kgf/cm²).")
else:
    print("Força não obtida por script: leia no Output e preencha FORCA_MANUAL_KN para ter F/A.")
print("=" * 70)

# ----------------------------------------------------------------------------
# Gráfico
# ----------------------------------------------------------------------------
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception as e:
    plt = None
    print("(sem gráfico: matplotlib indisponível: {})".format(e))

if plt is not None:
    fig, ax = plt.subplots(figsize=(8.5, 5.8))
    s_v = [l[1] for l in linhas]
    if tem_forca_curva:
        q_v = [l[2] / AREA for l in linhas]
        ax.plot(q_v, s_v, "-", color="#1f4e9c", lw=2.2, label="PLAXIS (deslocamento prescrito)")
        ax.plot([q_v[-1]], [s_v[-1]], "o", color="#c0392b", ms=8, zorder=5)
        ax.annotate("q = {:.1f} kN/m²\n(F = {:.0f} kN, recalque {:.1f} mm)".format(q_v[-1], F_final, s_v[-1]),
                    xy=(q_v[-1], s_v[-1]), xytext=(q_v[-1] * 0.35, s_v[-1] * 0.6),
                    arrowprops=dict(arrowstyle="->", color="#c0392b"), color="#c0392b")
        ax.set_xlabel("Tensão média sob a sapata (kN/m²)")
        ax.set_xlim(0, max(q_v) * 1.1)
        ax.legend(loc="lower left")
    else:
        ax.plot([l[0] for l in linhas], s_v, "-", color="#1f4e9c", lw=2.2)
        ax.set_xlabel("ΣMstage")
        if F_final is not None:
            ax.set_title("Força final {:.0f} kN -> q = {:.1f} kN/m²".format(F_final, F_final / AREA))
    ax.set_ylabel("Recalque (mm)")
    ax.set_ylim(max(s_v) * 1.05, 0)
    ax.grid(True, alpha=0.3)
    if not ax.get_title():
        ax.set_title("Exemplo 2 - recalque de {:.0f} mm por deslocamento prescrito".format(DESLOC_MM))
    fig.tight_layout()
    fig.savefig(PNG, dpi=150)
    plt.close(fig)
    print("    gráfico salvo em", PNG)

try:
    g_o.close()
except Exception:
    pass

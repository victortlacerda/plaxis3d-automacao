# -*- coding: utf-8 -*-
"""
Exemplo 1 - Resultados: curva carga x recalque e critérios de capacidade de carga.

Pré-requisito: exemplo1_modelo.py já rodado (projeto calculado e aberto no PLAXIS Input).
Roda pelo executor externo (s_i e g_i já existem).

Gera na mesma pasta deste script:
  - exemplo1_curva.csv               (SumMstage, carga [kN/m2], recalque [mm])
  - exemplo1_grafico_tangentes.png   (curva + retas tangentes + qu pela interseção)
  - exemplo1_grafico_10pctB.png      (qu quando o recalque = 10% de B)
  - exemplo1_grafico_25mm.png        (tensão que causa 25 mm - Terzaghi e Peck, 1948)
E imprime um resumo com os três critérios.
"""
import os
import getpass

from plxscripting.easy import new_server

HOST = "localhost"
CARGA_TOTAL = 1000.0          # kN/m2 aplicada na fase Load
B_SAPATA = 1.0                # menor lado da sapata (m)
FS = 3.0                      # fator de segurança (qa = qu / FS)
FRACAO_B = 0.10               # critério: recalque = 10% de B
RECALQUE_ADM_MM = 25.0        # critério: recalque admissível (Terzaghi e Peck, 1948)
N_PONTOS_INICIAIS = 5         # pontos usados na tangente inicial
N_PONTOS_FINAIS = 5           # pontos usados na tangente final
DECIMAL_VIRGULA = True        # True: Excel em português (vírgula). False: ponto decimal (Excel em inglês)

PASTA = os.path.dirname(os.path.abspath(globals().get("__file__", ".")))
CSV = os.path.join(PASTA, "exemplo1_curva.csv")
PNG_TANGENTES = os.path.join(PASTA, "exemplo1_grafico_tangentes.png")
PNG_10B = os.path.join(PASTA, "exemplo1_grafico_10pctB.png")
PNG_25MM = os.path.join(PASTA, "exemplo1_grafico_25mm.png")


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
    raise RuntimeError("Não achei SumMstage em step.Reached. Atributos: {}".format(
        [a for a in dir(reached) if not a.startswith("_")][:40]))


# ----------------------------------------------------------------------------
# Conectar no Output da última fase
# ----------------------------------------------------------------------------
print(">>> Abrindo o Output da fase Load")
fase_in = g_i.Phases[-1]
porta_out = g_i.view(fase_in)
s_o, g_o = new_server(HOST, porta_out, password=obter_senha())

fase = g_o.Phases[-1]
print("    Fase:", valor(fase.Identification) if hasattr(fase, "Identification") else fase)

try:
    no = g_o.Nodes[0]
except Exception as e:
    raise RuntimeError("Não achei o nó pré-selecionado em g_o.Nodes (rodou o exemplo1_modelo.py "
                       "até o fim, com o ponto de curva em (0,0,0)?): {}".format(e))

# ----------------------------------------------------------------------------
# Extrair (SumMstage, uz) de cada passo
# ----------------------------------------------------------------------------
print(">>> Lendo passos de cálculo")
linhas = [(0.0, 0.0, 0.0)]    # origem, como na planilha do vídeo
for step in fase.Steps.value:
    m = mstage_do_passo(step)
    uz = float(g_o.getcurveresults(no, step, g_o.ResultTypes.Soil.Uz))
    linhas.append((m, m * CARGA_TOTAL, -uz * 1000.0))   # recalque positivo para baixo, em mm

# remove duplicados e ordena por carga
linhas = sorted(set(linhas), key=lambda r: r[1])


def num(x, casas):
    """Formata número para o CSV. Excel em português precisa de vírgula decimal."""
    t = "{:.{}f}".format(x, casas)
    return t.replace(".", ",") if DECIMAL_VIRGULA else t


with open(CSV, "w") as f:
    f.write("SumMstage;Carga_kN_m2;Recalque_mm\n")
    for m, q_, s_ in linhas:
        f.write("{};{};{}\n".format(num(m, 6), num(q_, 4), num(s_, 4)))
print("    {} pontos salvos em {}".format(len(linhas), CSV))

q = [l[1] for l in linhas]    # carga (kN/m2)
s = [l[2] for l in linhas]    # recalque (mm, positivo para baixo)
q_max, s_max = max(q), max(s)


# ----------------------------------------------------------------------------
# Funções de análise
# ----------------------------------------------------------------------------
def regressao(x, y):
    n = float(len(x))
    mx, my = sum(x) / n, sum(y) / n
    sxx = sum((a - mx) ** 2 for a in x)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    c = sxy / sxx
    return c, my - c * mx


def carga_no_recalque(s_alvo):
    """Interpola a carga em que a curva cruza o recalque s_alvo (mm). None se não chegou lá."""
    for (q0, s0), (q1, s1) in zip(zip(q, s), zip(q[1:], s[1:])):
        if s1 != s0 and (s0 - s_alvo) * (s1 - s_alvo) <= 0:
            return q0 + (q1 - q0) * (s_alvo - s0) / (s1 - s0)
    return None


def recalque_na_carga(q_alvo):
    for (q0, s0), (q1, s1) in zip(zip(q, s), zip(q[1:], s[1:])):
        if q1 > q0 and q0 <= q_alvo <= q1:
            return s0 + (s1 - s0) * (q_alvo - q0) / (q1 - q0)
    return None


# --- Critério 1: interseção das tangentes (inicial: q = k*s ; final: q = c*s + d)
qu_tang = s_int = k = c = d = None
if len(q) > N_PONTOS_INICIAIS + N_PONTOS_FINAIS:
    ini = slice(1, 1 + N_PONTOS_INICIAIS)          # ignora o ponto (0,0)
    fim = slice(-N_PONTOS_FINAIS, None)
    k = sum(a * b for a, b in zip(s[ini], q[ini])) / sum(a * a for a in s[ini])   # tangente inicial pela origem
    c, d = regressao(s[fim], q[fim])                                              # tangente final (quase vertical)
    if abs(k - c) > 1e-9:
        s_int = d / (k - c)
        qu_tang = k * s_int

# --- Critério 2: recalque = 10% de B
s_10b = FRACAO_B * B_SAPATA * 1000.0
q_10b = carga_no_recalque(s_10b)

# --- Critério 3: tensão que causa 25 mm (Terzaghi e Peck, 1948)
q_25 = carga_no_recalque(RECALQUE_ADM_MM)

# ----------------------------------------------------------------------------
# Resumo
# ----------------------------------------------------------------------------
print("\n" + "=" * 70)
print("RESUMO DOS CRITÉRIOS (B = {:.2f} m, FS = {})".format(B_SAPATA, FS))
print("=" * 70)
print("Carga máxima atingida no cálculo : {:.1f} kN/m2 (recalque {:.1f} mm)".format(q_max, s_max))

if qu_tang is not None:
    qa = qu_tang / FS
    sa = recalque_na_carga(qa)
    print("\n1) Interseção das tangentes")
    print("   qu = {:.0f} kN/m2  (recalque na interseção ~ {:.1f} mm)".format(qu_tang, s_int))
    print("   qa = qu/FS = {:.1f} kN/m2  (recalque em qa ~ {})".format(
        qa, "{:.1f} mm".format(sa) if sa is not None else "n/d"))
else:
    print("\n1) Interseção das tangentes: não foi possível calcular (poucos pontos).")

print("\n2) Recalque = {:.0f}% de B = {:.0f} mm".format(FRACAO_B * 100, s_10b))
if q_10b is not None:
    sa = recalque_na_carga(q_10b / FS)
    print("   qu = {:.0f} kN/m2".format(q_10b))
    print("   qa = qu/FS = {:.1f} kN/m2  (recalque em qa ~ {})".format(
        q_10b / FS, "{:.1f} mm".format(sa) if sa is not None else "n/d"))
else:
    print("   A curva só chegou a {:.1f} mm; não atinge {:.0f} mm.".format(s_max, s_10b))

print("\n3) Recalque de {:.0f} mm (Terzaghi e Peck, 1948)".format(RECALQUE_ADM_MM))
if q_25 is not None:
    print("   tensão que causa {:.0f} mm = {:.1f} kN/m2  (já é uma tensão admissível por recalque, sem FS)".format(
        RECALQUE_ADM_MM, q_25))
else:
    print("   A curva só chegou a {:.1f} mm; não atinge {:.0f} mm.".format(s_max, RECALQUE_ADM_MM))
print("=" * 70)

# ----------------------------------------------------------------------------
# Gráficos
# ----------------------------------------------------------------------------
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception as e:
    plt = None
    print("\n(sem gráficos: matplotlib indisponível: {})".format(e))

COR_CURVA = "#1f4e9c"
COR_A = "#d9730d"      # tangente inicial / marcação
COR_B = "#2a8c4a"      # tangente final
COR_MARCA = "#c0392b"


ZOOM = True    # True: eixo vertical focado na região de interesse; False: mostra a curva inteira


def limite_s(s_lim):
    """Limite do eixo de recalque: com ZOOM usa s_lim; sem zoom, mostra até o recalque final."""
    if ZOOM and s_lim is not None:
        return min(s_lim, s_max * 1.05)
    return s_max * 1.05


def figura_base(titulo, s_lim=None):
    fig, ax = plt.subplots(figsize=(8.5, 5.8))
    ax.plot(q, s, "-", color=COR_CURVA, lw=2.2, label="Curva do PLAXIS (nó sob a sapata)")
    ax.set_xlabel("Carga (kN/m²)")
    ax.set_ylabel("Recalque (mm)")
    ax.set_title(titulo)
    ax.set_xlim(0, q_max * 1.1)
    ax.set_ylim(limite_s(s_lim), 0)       # recalque cresce para baixo, como no PLAXIS
    ax.grid(True, alpha=0.3)
    return fig, ax


def grafico_tangentes():
    s_lim = max(6 * s_int, 80.0) if s_int else None
    fig, ax = figura_base("Exemplo 1 - qu pela interseção das tangentes", s_lim)
    if qu_tang is not None:
        s_topo = limite_s(s_lim)
        # tangente inicial: q = k*s  ->  s = q/k
        q_fim_ini = q_max * 1.08
        ax.plot([0, q_fim_ini], [0, q_fim_ini / k], "--", color=COR_A, lw=1.8, label="Tangente inicial")
        # tangente final: q = c*s + d
        s_ini_fin = max(s_int * 0.4, 0.0)
        ax.plot([c * s_ini_fin + d, c * s_topo + d], [s_ini_fin, s_topo], "--", color=COR_B, lw=1.8,
                label="Tangente final")
        ax.plot([qu_tang], [s_int], "o", color=COR_MARCA, ms=8, zorder=5)
        ax.annotate("qu = {:.0f} kN/m²\n(recalque {:.1f} mm)".format(qu_tang, s_int),
                    xy=(qu_tang, s_int), xytext=(qu_tang * 0.45, s_int + s_topo * 0.3),
                    arrowprops=dict(arrowstyle="->", color=COR_MARCA), color=COR_MARCA)
        ax.axvline(qu_tang, color=COR_MARCA, ls=":", lw=1)
    ax.legend(loc="lower left")
    fig.tight_layout()
    fig.savefig(PNG_TANGENTES, dpi=150)
    plt.close(fig)
    print("    gráfico salvo em", PNG_TANGENTES)


def grafico_criterio(arquivo, titulo, s_alvo, q_alvo, rotulo):
    s_lim = 2.2 * s_alvo
    fig, ax = figura_base(titulo, s_lim)
    ax.axhline(s_alvo, color=COR_A, ls="--", lw=1.5,
               label="Recalque = {:.0f} mm".format(s_alvo))
    if q_alvo is not None:
        ax.plot([q_alvo, q_alvo], [0, s_alvo], ":", color=COR_MARCA, lw=1.5)
        ax.plot([q_alvo], [s_alvo], "o", color=COR_MARCA, ms=8, zorder=5)
        ax.annotate("{} = {:.0f} kN/m²".format(rotulo, q_alvo),
                    xy=(q_alvo, s_alvo), xytext=(q_alvo * 0.3, s_alvo + limite_s(s_lim) * 0.25),
                    arrowprops=dict(arrowstyle="->", color=COR_MARCA), color=COR_MARCA)
    else:
        ax.text(0.5, 0.5, "A curva não atinge {:.0f} mm".format(s_alvo),
                transform=ax.transAxes, ha="center", color=COR_MARCA)
    ax.legend(loc="lower left")
    fig.tight_layout()
    fig.savefig(arquivo, dpi=150)
    plt.close(fig)
    print("    gráfico salvo em", arquivo)


if plt is not None:
    print("\n>>> Gerando gráficos")
    grafico_tangentes()
    grafico_criterio(PNG_10B, "Exemplo 1 - critério de {:.0f}% de B ({:.0f} mm)".format(FRACAO_B * 100, s_10b),
                     s_10b, q_10b, "qu")
    grafico_criterio(PNG_25MM, "Exemplo 1 - tensão para {:.0f} mm de recalque (Terzaghi e Peck, 1948)".format(
        RECALQUE_ADM_MM), RECALQUE_ADM_MM, q_25, "q")

try:
    g_o.close()
except Exception:
    pass

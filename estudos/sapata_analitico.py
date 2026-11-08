# -*- coding: utf-8 -*-
"""
Capacidade de carga e recalque elástico de sapatas por métodos clássicos (sem PLAXIS).

Usado pelos scripts de estudo (lote, sensibilidade, relatório) para colocar ao lado da curva do PLAXIS:
  - Terzaghi (1943), com fatores de forma usuais (1,3 c Nc e 0,4 γ B Nγ na sapata quadrada) e Nγ pela
    aproximação de Coduto (2001); sem fatores de profundidade.
  - Meyerhof (1963), com fatores de forma e de profundidade.
  - Vesić (1973/1975), com fatores de forma de De Beer e de profundidade de Hansen (1970).
  - Recalque elástico imediato de sapata rígida em meio semi-infinito homogêneo:
    s = q B (1 - ν²) Iw / E   (Iw de sapata rígida, tabela de Bowles, 1996).

Hipóteses (as mesmas para os três métodos): ruptura geral, parâmetros drenados (c', φ'), carga vertical
centrada, terreno horizontal, solo homogêneo abaixo da base. O nível d'água corrige q e γ (γ' = γsat - γw
abaixo do N.A., interpolação linear no Nγ quando o N.A. está entre a base e a profundidade B).

Este arquivo NÃO usa o PLAXIS: pode ser testado sozinho (python sapata_analitico.py).
"""
import math

GAMMA_W = 10.0

# Fator de influência Iw de sapata RÍGIDA em meio semi-infinito (Bowles, 1996), por L/B
IW_RIGIDA = ((1.0, 0.82), (1.5, 1.06), (2.0, 1.20), (3.0, 1.42), (5.0, 1.70), (10.0, 2.10))


def _interp(tabela, x):
    if x <= tabela[0][0]:
        return tabela[0][1]
    for (x0, y0), (x1, y1) in zip(tabela, tabela[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return tabela[-1][1]


def tensoes_efetivas(D, gamma, gamma_sat, prof_na, B):
    """Sobrecarga efetiva q na cota da base e peso específico efetivo para o termo de Nγ."""
    g_sub = gamma_sat - GAMMA_W
    dw = prof_na if prof_na is not None else 1e9
    if dw >= D:
        q = gamma * D
    else:
        q = gamma * dw + g_sub * (D - dw)
    if dw <= D:
        g_eff = g_sub
    elif dw < D + B:
        g_eff = g_sub + (dw - D) / B * (gamma - g_sub)
    else:
        g_eff = gamma
    return q, g_eff


def fatores_meyerhof_vesic(phi_graus):
    phi = math.radians(phi_graus)
    if phi_graus <= 1e-9:
        return 5.14, 1.0
    Nq = math.exp(math.pi * math.tan(phi)) * math.tan(math.pi / 4 + phi / 2) ** 2
    Nc = (Nq - 1.0) / math.tan(phi)
    return Nc, Nq


def terzaghi(B, L, D, c, phi_graus, gamma, gamma_sat, prof_na):
    phi = math.radians(phi_graus)
    if phi_graus <= 1e-9:
        Nq, Nc, Ng = 1.0, 5.7, 0.0
    else:
        a = math.exp((0.75 * math.pi - phi / 2.0) * math.tan(phi))
        Nq = a * a / (2.0 * math.cos(math.pi / 4 + phi / 2.0) ** 2)
        Nc = (Nq - 1.0) / math.tan(phi)
        Ng = 2.0 * (Nq + 1.0) * math.tan(phi) / (1.0 + 0.4 * math.sin(4.0 * phi))   # Coduto (2001)
    q, g = tensoes_efetivas(D, gamma, gamma_sat, prof_na, B)
    r = B / L
    sc, sg = 1.0 + 0.3 * r, 1.0 - 0.2 * r          # 1,3 e 0,8 (0,4 γ B Nγ) na quadrada
    termos = (c * Nc * sc, q * Nq, 0.5 * g * B * Ng * sg)
    return dict(metodo="Terzaghi (1943)", qu=sum(termos), Nc=Nc, Nq=Nq, Ng=Ng, q=q, gamma_ef=g,
                termos=termos, fatores=dict(sc=sc, sq=1.0, sg=sg, dc=1.0, dq=1.0, dg=1.0))


def meyerhof(B, L, D, c, phi_graus, gamma, gamma_sat, prof_na):
    phi = math.radians(phi_graus)
    Nc, Nq = fatores_meyerhof_vesic(phi_graus)
    Ng = (Nq - 1.0) * math.tan(1.4 * phi)
    Kp = math.tan(math.pi / 4 + phi / 2.0) ** 2
    r, k = B / L, D / B
    sc = 1.0 + 0.2 * Kp * r
    dc = 1.0 + 0.2 * math.sqrt(Kp) * k
    if phi_graus > 10.0:
        sq = sg = 1.0 + 0.1 * Kp * r
        dq = dg = 1.0 + 0.1 * math.sqrt(Kp) * k
    else:
        sq = sg = dq = dg = 1.0
    q, g = tensoes_efetivas(D, gamma, gamma_sat, prof_na, B)
    termos = (c * Nc * sc * dc, q * Nq * sq * dq, 0.5 * g * B * Ng * sg * dg)
    return dict(metodo="Meyerhof (1963)", qu=sum(termos), Nc=Nc, Nq=Nq, Ng=Ng, q=q, gamma_ef=g,
                termos=termos, fatores=dict(sc=sc, sq=sq, sg=sg, dc=dc, dq=dq, dg=dg))


def vesic(B, L, D, c, phi_graus, gamma, gamma_sat, prof_na):
    phi = math.radians(phi_graus)
    Nc, Nq = fatores_meyerhof_vesic(phi_graus)
    Ng = 2.0 * (Nq + 1.0) * math.tan(phi)
    r = B / L
    sc = 1.0 + r * Nq / Nc
    sq = 1.0 + r * math.tan(phi)
    sg = max(0.6, 1.0 - 0.4 * r)
    k = D / B if D <= B else math.atan(D / B)
    dc = 1.0 + 0.4 * k
    dq = 1.0 + 2.0 * math.tan(phi) * (1.0 - math.sin(phi)) ** 2 * k
    dg = 1.0
    q, g = tensoes_efetivas(D, gamma, gamma_sat, prof_na, B)
    termos = (c * Nc * sc * dc, q * Nq * sq * dq, 0.5 * g * B * Ng * sg * dg)
    return dict(metodo="Vesić (1975)", qu=sum(termos), Nc=Nc, Nq=Nq, Ng=Ng, q=q, gamma_ef=g,
                termos=termos, fatores=dict(sc=sc, sq=sq, sg=sg, dc=dc, dq=dq, dg=dg))


def iw_rigida(B, L):
    return _interp(IW_RIGIDA, max(L, B) / min(L, B))


def recalque_elastico_mm(q, B, L, E, nu):
    """Recalque imediato (mm) de sapata rígida para a tensão q (kN/m²)."""
    return q * min(B, L) * (1.0 - nu * nu) * iw_rigida(B, L) / E * 1000.0


def tensao_para_recalque(s_mm, B, L, E, nu):
    """Inverso: tensão (kN/m²) que causa s_mm no modelo elástico."""
    return s_mm / 1000.0 * E / (min(B, L) * (1.0 - nu * nu) * iw_rigida(B, L))


def calcular(B, L, D, c, phi, gamma, gamma_sat, prof_na, E, nu, FS=3.0):
    """Todos os métodos. B e L em m (qualquer ordem), D = profundidade da base (m, >= 0),
    prof_na = profundidade do N.A. a partir da superfície (m, positiva; None = sem N.A.)."""
    Bm, Lm = min(B, L), max(B, L)
    D = max(0.0, D)
    args = (Bm, Lm, D, c, phi, gamma, gamma_sat, prof_na)
    metodos = [terzaghi(*args), meyerhof(*args), vesic(*args)]
    for m in metodos:
        m["qa"] = m["qu"] / FS
        m["recalque_qa_mm"] = recalque_elastico_mm(m["qa"], Bm, Lm, E, nu)
    return dict(
        metodos=metodos, FS=FS, Iw=iw_rigida(Bm, Lm), B=Bm, L=Lm, D=D,
        q_25mm=tensao_para_recalque(25.0, Bm, Lm, E, nu),
        hipoteses=("ruptura geral; parâmetros drenados; carga vertical centrada; solo homogêneo abaixo da base; "
                   "recalque elástico de sapata rígida em meio semi-infinito (Iw de Bowles)"),
    )


def tabela_texto(res, qu_plaxis=None, unid="kN/m²"):
    linhas = ["{:<18}{:>12}{:>12}{:>16}".format("Método", "qu", "qa=qu/FS", "s(qa) elást.")]
    for m in res["metodos"]:
        linhas.append("{:<18}{:>12.0f}{:>12.0f}{:>13.1f} mm".format(m["metodo"], m["qu"], m["qa"],
                                                                   m["recalque_qa_mm"]))
    if qu_plaxis:
        linhas.append("{:<18}{:>12.0f}{:>12.0f}".format("PLAXIS (tangentes)", qu_plaxis, qu_plaxis / res["FS"]))
    linhas.append("Tensão para 25 mm (elástico, Iw = {:.2f}): {:.0f} {}".format(res["Iw"], res["q_25mm"], unid))
    return "\n".join(linhas)


if __name__ == "__main__":
    # Conferências com valores de livro
    import sys
    erros = 0

    def confere(nome, valor, esperado, tol):
        global erros
        ok = abs(valor - esperado) <= tol
        erros += 0 if ok else 1
        print("{:<46} {:>10.2f}  (esperado {:>8.2f})  {}".format(nome, valor, esperado, "ok" if ok else "ERRO"))

    t = terzaghi(1, 1, 0, 0, 30, 18, 20, None)
    confere("Terzaghi Nc φ=30 (tabela: 37,16)", t["Nc"], 37.16, 0.05)
    confere("Terzaghi Nq φ=30 (tabela: 22,46)", t["Nq"], 22.46, 0.05)
    confere("Terzaghi Nγ φ=30 Coduto (tabela: 20,1)", t["Ng"], 20.1, 0.05)
    nc, nq = fatores_meyerhof_vesic(30)
    confere("Meyerhof/Vesić Nc φ=30 (30,14)", nc, 30.14, 0.02)
    confere("Meyerhof/Vesić Nq φ=30 (18,40)", nq, 18.40, 0.02)
    confere("Meyerhof Nγ φ=30 (15,67)", meyerhof(1, 1, 0, 0, 30, 18, 20, None)["Ng"], 15.67, 0.05)
    confere("Vesić Nγ φ=30 (22,40)", vesic(1, 1, 0, 0, 30, 18, 20, None)["Ng"], 22.40, 0.02)
    confere("Meyerhof/Vesić Nc φ=20 (14,83)", fatores_meyerhof_vesic(20)[0], 14.83, 0.02)
    confere("Iw rígida L/B=2 (1,20)", iw_rigida(1, 2), 1.20, 1e-9)
    r = calcular(1, 1, 0, 30, 20, 18, 20, 6, 40000, 0.3)
    print()
    print("Exemplo 1 das notas (1x1 m na superfície, c'=30, φ'=20):")
    print(tabela_texto(r, qu_plaxis=792))
    sys.exit(1 if erros else 0)

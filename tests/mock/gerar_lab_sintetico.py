# -*- coding: utf-8 -*-
"""Gera ensaios triaxiais SINTETICOS com resposta conhecida, para testar o soiltest_interpretacao.py.

Uso: python3 gerar_lab_sintetico.py <pasta_saida>
Grava <pasta_saida>/lab_interpretacao_sintetico.csv (formato estendido do laboratorio) e gabarito.json (valores
que a interpretacao tem que devolver).

Construcao (convencao de laboratorio: compressao +, q = sigma1 - sigma3, du = excesso de poropressao, ev contracao +):
- UU: q chega a 2 Su em eps_a = 5 % e fica constante; Su igual em todos os CPs -> phi_u = 0, c_u = Su.
- CIU/CAU: q e du crescem juntos e ficam constantes a partir de 5 %. O q de ruptura e calculado para o ponto cair
  exatamente na envoltoria efetiva (c', phi') com A de Skempton conhecido:
      q_f = (c' cos phi' + sigma'3c sin phi' + A q0 sin phi') / (0,5 (1 - sin phi') + A sin phi'),  du_f = A (q_f - q0)
  Como q e du crescem e depois ficam constantes, q maximo, sigma'1/sigma'3 maxima, eps_a limite e fim do ensaio
  caem no mesmo ponto: as quatro envoltorias tem que devolver (c', phi').
- CID: q_f = 2 (c' cos phi' + sigma'3 sin phi') / (1 - sin phi'). eps_v contrai ate 2 %, dilata com taxa constante
  ate 10 % (taxa do angulo de dilatancia de pico) e a taxa cai linearmente a zero em 15 % (estado critico).
      d eps_v / d eps_a = -2 sin psi / (1 - sin psi)     (contracao +)
- PROBLEMAS: serie CIU com amolecimento pos-pico e com q maximo que cai com sigma3 (para os alertas).
- DILATANTE: CIU sem pico (q sobe ate o fim, du negativo), para o alerta de nao drenado sem pico.
Nada aqui e dado real.
"""
import json
import math
import os
import sys

C_EF, PHI_EF = 10.0, 30.0          # envoltoria efetiva das series CIU, CAU e CID
A_CIU, A_CAU = 0.30, 0.20          # A de Skempton na ruptura
K_CAU = 0.6                        # sigma'3c / sigma'1c no adensamento anisotropico
SU = 40.0                          # resistencia nao drenada da serie UU
PSI_PICO = 8.0                     # angulo de dilatancia de pico da serie CID
EPS = [0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 15.0, 17.5, 20.0]
EPS_F = 5.0                        # deformacao em que q (e du) chegam ao valor de ruptura


def forma(e):
    """0 em eps = 0, 1 a partir de EPS_F, crescente e suave."""
    return 1.0 if e >= EPS_F else 1.0 - (1.0 - e / EPS_F) ** 2


def q_ruptura_cu(s3c, q0, A, c=C_EF, phi=PHI_EF):
    s, co = math.sin(math.radians(phi)), math.cos(math.radians(phi))
    return (c * co + s3c * s + A * q0 * s) / (0.5 * (1 - s) + A * s)


def ev_cid(e, r):
    """eps_v (%) com contracao ate 2 %, dilatacao com taxa r ate 10 %, taxa caindo a zero em 15 %."""
    ev_c = 0.4
    if e <= 2.0:
        return ev_c * (1 - (1 - e / 2.0) ** 2)
    if e <= 10.0:
        return ev_c + r * (e - 2.0)
    x = min(e, 15.0) - 10.0
    return ev_c + r * 8.0 + r * (x - x * x / 10.0)


def gerar(pasta):
    os.makedirs(pasta, exist_ok=True)
    linhas = ["ensaio;tipo;serie;drenagem;sigma3_kPa;eps_a_pct;q_kPa;sigma1_kPa;du_kPa;ev_pct;u0_kPa"]
    f = lambda v: "{:.6f}".format(v).rstrip("0").rstrip(".")
    gab = {"c_ef": C_EF, "phi_ef": PHI_EF, "Su": SU, "psi_pico": PSI_PICO, "A_CIU": A_CIU, "A_CAU": A_CAU, "q_f": {}}

    # UU: pressao de camara total; q entra pela coluna sigma1_kPa num CP (testa a coluna alternativa)
    for s3 in (100.0, 200.0, 300.0):
        nome = "UU_{:g}".format(s3)
        for e in EPS:
            q = 2 * SU * forma(e)
            if s3 == 300.0:
                linhas.append(";".join([nome, "UU", "SINT_UU", "U", f(s3), f(e), "", f(s3 + q), "", "", ""]))
            else:
                linhas.append(";".join([nome, "UU", "SINT_UU", "U", f(s3), f(e), f(q), "", "", "", ""]))
        gab["q_f"][nome] = 2 * SU

    # CIU com contrapressao (u0 informativo); virgula decimal num CP para testar a leitura
    for s3 in (50.0, 100.0, 200.0):
        nome = "CIU_{:g}".format(s3)
        qf = q_ruptura_cu(s3, 0.0, A_CIU)
        for e in EPS:
            q, du = qf * forma(e), A_CIU * qf * forma(e)
            l = ";".join([nome, "CIU", "SINT_CIU", "U", f(s3), f(e), f(q), "", f(du), "", "300"])
            linhas.append(l.replace(".", ",") if s3 == 100.0 else l)
        gab["q_f"][nome] = qf

    # CAU: sigma3_kPa = sigma'3c (lateral); q parte de q0
    for s3 in (50.0, 100.0, 200.0):
        nome = "CAU_{:g}".format(s3)
        q0 = s3 / K_CAU - s3
        qf = q_ruptura_cu(s3, q0, A_CAU)
        for e in EPS:
            q = q0 + (qf - q0) * forma(e)
            du = A_CAU * (q - q0)
            linhas.append(";".join([nome, "CAU", "SINT_CAU", "U", f(s3), f(e), f(q), "", f(du), "", ""]))
        gab["q_f"][nome] = qf

    # CID
    sp = math.sin(math.radians(PSI_PICO))
    r = -2 * sp / (1 - sp)
    s, co = math.sin(math.radians(PHI_EF)), math.cos(math.radians(PHI_EF))
    for s3 in (50.0, 100.0, 200.0):
        nome = "CID_{:g}".format(s3)
        qf = 2 * (C_EF * co + s3 * s) / (1 - s)
        for e in EPS:
            linhas.append(";".join([nome, "CID", "SINT_CID", "D", f(s3), f(e), f(qf * forma(e)), "", "", f(ev_cid(e, r)), ""]))
        gab["q_f"][nome] = qf
    r_med = r * 10.5 / 13.0                       # secante de 2 % (contracao maxima) a 15 % (eps_v minimo)
    gab["psi_medio"] = math.degrees(math.asin(-r_med / (2 - r_med)))

    # PROBLEMAS: CIU com amolecimento de 25 % e q maximo que cai de 100 para 200 kPa
    for s3, fator in ((50.0, 1.0), (100.0, 1.0), (200.0, 0.40)):
        nome = "PROB_{:g}".format(s3)
        qp = q_ruptura_cu(s3, 0.0, A_CIU) * fator
        for e in EPS:
            mult = forma(e) if e <= EPS_F else 1.0 - 0.25 * min(1.0, (e - EPS_F) / 10.0)
            linhas.append(";".join([nome, "CIU", "SINT_PROBLEMAS", "U", f(s3), f(e), f(qp * mult), "",
                                    f(A_CIU * qp * forma(e)), "", ""]))

    # DILATANTE: CIU de areia densa sem drenagem, q sobe ate o fim e du fica negativo (sem pico)
    for s3 in (50.0, 100.0, 200.0):
        nome = "DIL_{:g}".format(s3)
        for e in EPS:
            q = s3 * (0.08 * e)
            linhas.append(";".join([nome, "CIU", "SINT_DILATANTE", "U", f(s3), f(e), f(q), "", f(-0.3 * q), "", ""]))

    cam = os.path.join(pasta, "lab_interpretacao_sintetico.csv")
    with open(cam, "w", encoding="utf-8") as fh:
        fh.write("\n".join(linhas) + "\n")
    with open(os.path.join(pasta, "gabarito.json"), "w", encoding="utf-8") as fh:
        json.dump(gab, fh, indent=1, ensure_ascii=False)
    return cam, gab


if __name__ == "__main__":
    print(gerar(sys.argv[1] if len(sys.argv) > 1 else ".")[0])

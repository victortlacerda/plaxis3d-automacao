# -*- coding: utf-8 -*-
"""Teste do soiltest_interpretacao.py com ensaios sinteticos de resposta conhecida (usado pela regressao).

Uso: python3 interpretar_sintetico.py <raiz_do_repositorio> <pasta_de_trabalho>
Gera os CPs (gerar_lab_sintetico.py), interpreta junto com a simulacao exemplos/HS_K0_OCR2 (HS: c' = 1, phi' = 35,
psi = 5, K0 = 0,5) e confere cada valor contra o gabarito. Imprime o log e uma linha OK/FALHA por conferencia."""
import json
import os
import sys

RAIZ, PASTA = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.join(RAIZ, "tests", "mock"))
import gerar_lab_sintetico as G  # noqa: E402

csv_lab, gab = G.gerar(PASTA)
cam = os.path.join(RAIZ, "soiltest", "em_desenvolvimento", "interpretacao", "soiltest_interpretacao.py")
I = {"__name__": "interpretacao", "__file__": cam, "__builtins__": __builtins__}
with open(cam, "rb") as f:
    exec(compile(f.read(), cam, "exec"), I, I)
I["CONFIG"]["pasta_saida"] = os.path.join(PASTA, "saida")
sim = os.path.join(RAIZ, "soiltest", "exemplos", "HS_K0_OCR2")
rc = I["main"]([csv_lab, sim])

with open(os.path.join(PASTA, "saida", "interpretacao.json"), encoding="utf-8") as f:
    res = {s["serie"]: s for s in json.load(f)["series"]}
falhas = 0


def confere(rotulo, obtido, esperado, tol):
    global falhas
    ok = obtido is not None and abs(obtido - esperado) <= tol
    falhas += 0 if ok else 1
    print("{:6s} {}: obtido {} esperado {:.4f}".format("OK" if ok else "FALHA", rotulo,
                                                     "-" if obtido is None else "{:.4f}".format(obtido), esperado))


print("")
print("Conferencia contra o gabarito")
for serie in ("SINT_CIU", "SINT_CAU", "SINT_CID", "SIM HS_K0_OCR2 CAD"):
    c_esp, phi_esp = (1.0, 35.0) if serie.startswith("SIM") else (gab["c_ef"], gab["phi_ef"])
    for crit, e in res[serie]["envoltorias"]["efetiva"].items():
        confere("{} efetiva {} c'".format(serie, crit), e["c"], c_esp, 0.01)
        confere("{} efetiva {} phi'".format(serie, crit), e["phi"], phi_esp, 0.01)
for crit, e in res["SINT_UU"]["envoltorias"]["total"].items():
    confere("SINT_UU total {} c_u".format(crit), e["c"], gab["Su"], 0.01)
    confere("SINT_UU total {} phi_u".format(crit), e["phi"], 0.0, 0.01)
confere("SINT_UU Su medio", res["SINT_UU"]["Su_medio"], gab["Su"], 0.01)
for serie, a_esp in (("SINT_CIU", gab["A_CIU"]), ("SINT_CAU", gab["A_CAU"])):
    for cp in res[serie]["cps"]:
        confere("{} A_f".format(cp["nome"]), cp["ruptura"]["q máximo"]["A"], a_esp, 1e-4)
        confere("{} q_f".format(cp["nome"]), cp["ruptura"]["q máximo"]["q"], gab["q_f"][cp["nome"]], 0.01)
for cp in res["SINT_CID"]["cps"]:
    confere("{} psi pico".format(cp["nome"]), cp["dilatancia"]["psi_pico"], gab["psi_pico"], 0.01)
    confere("{} psi medio".format(cp["nome"]), cp["dilatancia"]["psi_medio"], gab["psi_medio"], 0.01)
for cp in res["SIM HS_K0_OCR2 CAD"]["cps"]:
    confere("{} psi pico".format(cp["nome"]), cp["dilatancia"]["psi_pico"], 5.0, 0.05)
    tipo_ok = cp["tipo"] == "CAD"
    falhas += 0 if tipo_ok else 1
    print("{:6s} {} reconhecido como {} (esperado CAD)".format("OK" if tipo_ok else "FALHA", cp["nome"], cp["tipo"]))
al = " ".join(res["SINT_PROBLEMAS"]["alertas"])
for trecho in ("amolecimento pós-pico", "q máximo não cresce", "ajuste ruim"):
    ok = trecho in al
    falhas += 0 if ok else 1
    print("{:6s} alerta '{}' na serie SINT_PROBLEMAS".format("OK" if ok else "FALHA", trecho))
for s in ("SINT_UU", "SINT_CIU", "SINT_CAU", "SINT_CID"):
    ok = not res[s]["alertas"]
    falhas += 0 if ok else 1
    print("{:6s} serie {} sem alertas".format("OK" if ok else "FALHA", s))
saida = os.path.join(PASTA, "saida")
print("relatorio.html gerado" if os.path.isfile(os.path.join(saida, "relatorio.html")) else "relatorio.html FALTANDO")
print("{} PNG(s)".format(len([n for n in os.listdir(os.path.join(saida, "graficos")) if n.endswith(".png")])))
print("main = {}, falhas = {}".format(rc, falhas))
sys.exit(1 if falhas or rc else 0)

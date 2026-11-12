# -*- coding: utf-8 -*-
"""Lancador de teste do soiltest_extrair.py dentro do mock rodar_ferramenta.py (usado pela regressao).
Caso em EXTRAIR_CASO:
  material  - material "Argila" do projeto (Mohr-Coulomb drenado do mock), CIU + CID, isotropico
  k0        - mesmo material, so drenado, consolidacao K0 automatica (CAD)
  aberto    - SoilTest ja aberto, roda os ensaios do CONFIG (so nao drenado)
  leitura   - SoilTest ja aberto, so le o triaxial calculado na janela: duas execucoes (50 e 100 kPa) acumulando
              na mesma pasta"""
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
caso = os.environ.get("EXTRAIR_CASO", "material")
cam = os.path.join(AQUI, "soiltest_extrair.py")


def carregar():
    ns = {"__name__": "extrair", "__file__": cam, "__builtins__": __builtins__, "g_i": g_i, "s_i": s_i}
    with open(cam, "rb") as f:
        exec(compile(f.read(), cam, "exec"), ns, ns)
    ns["CONFIG"]["pasta_ensaios"] = os.path.join(AQUI, "saida_" + caso)
    return ns


easy = sys.modules["plxscripting.easy"]
if caso in ("material", "k0"):
    ns = carregar()
    ns["CONFIG"].update({"material": "Argila", "Steps": 40})
    if caso == "k0":
        ns["CONFIG"].update({"consolidacao": "K0", "comportamentos": ["Drained"]})
    ns["main"]()
else:
    g_i.soiltest(g_i.Soils[0])                      # o mock precisa do material da janela
    st = easy.new_server("localhost", 10001)[1]
    easy.new_server = lambda h, p, **k: (None, st) if p > 10000 else (_ for _ in ()).throw(ConnectionError())
    if caso == "aberto":
        ns = carregar()
        ns["CONFIG"].update({"modo": "aberto", "comportamentos": ["Undrained"], "Steps": 40})
        ns["main"]()
    else:
        for pr in (50, 100):
            st.Triaxial.setproperties("Behaviour", "Undrained", "CellPressure", pr, "MaximumStrain", 20, "Steps", 40)
            st.calculate(st.Triaxial)
            ns = carregar()
            ns["CONFIG"].update({"modo": "aberto", "rodar_ensaios": False})
            print("---- execucao com o triaxial de {} kPa calculado na janela ----".format(pr))
            ns["main"]()
for raiz, _d, arqs in sorted(os.walk(os.path.join(AQUI, "saida_" + caso))):
    for a in sorted(arqs):
        if not a.endswith(".png"):
            print("arquivo:", os.path.relpath(os.path.join(raiz, a), AQUI))
print("PNGs:", sum(1 for r, _d, a in os.walk(os.path.join(AQUI, "saida_" + caso)) for x in a if x.endswith(".png")))

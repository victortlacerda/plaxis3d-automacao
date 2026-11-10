# -*- coding: utf-8 -*-
"""Lancador de teste: calibra contra o ensaio sintetico com poucas avaliacoes (usado pela regressao)."""
import os
AQUI = os.path.dirname(os.path.abspath(__file__))
cam = os.path.join(AQUI, "soiltest_calibracao.py")
ns = {"__name__": "calibracao", "__file__": cam, "__builtins__": __builtins__, "g_i": g_i, "s_i": s_i}
with open(cam, "rb") as f:
    exec(compile(f.read(), cam, "exec"), ns, ns)
ns["CONFIG"].update({"lab_csv": os.path.join(AQUI, "lab_sintetico.csv"), "nome_material": "CAL_TESTE",
                     "descricao": "ensaio sintetico", "max_avaliacoes": 25, "amostras_iniciais": 8, "tempo_max_min": 5})
ns["time"].time = lambda c=[0.0]: c.__setitem__(0, c[0] + 1.0) or c[0]     # relogio falso: saida repetivel
ns["main"]()

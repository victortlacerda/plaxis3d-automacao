# -*- coding: utf-8 -*-
"""Roda o soiltest_campanha.py com a planilha de erros (tests/dados/campanha_erros.csv), so com materiais do projeto."""
import os, sys
AQUI = os.getcwd()
cam = os.path.join(AQUI, "soiltest_campanha.py")
ns = {"__name__": "campanha", "__file__": cam, "__builtins__": __builtins__, "g_i": globals()["g_i"], "s_i": globals()["s_i"]}
exec(compile(open(cam, encoding="utf-8").read(), cam, "exec"), ns, ns)
ns["PLANILHA_ENSAIOS"] = os.path.join(AQUI, "campanha_erros.csv")
ns["PLANILHA_MATERIAIS"] = None
ns["main"]()

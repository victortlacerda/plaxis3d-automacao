# -*- coding: utf-8 -*-
"""
Diagnóstico 2 (só leitura): procura onde fica o 'coarseness factor' da sapata.
Usa os comandos 'info' e 'commands' do PLAXIS e tenta LER a propriedade em vários objetos.
Rode com o projeto Exemplo1_Sapata aberto no PLAXIS Input.
"""
import traceback

try:
    g_i.gotomesh()
except Exception as e:
    print("gotomesh falhou:", e)


def ultima_linha():
    return traceback.format_exc().strip().splitlines()[-1]


objetos = [
    ("Polygon_1", lambda: g_i.Polygon_1),
    ("Plate_1", lambda: g_i.Plate_1),
    ("Plates[0]", lambda: g_i.Plates[0]),
    ("SurfaceLoad_1", lambda: g_i.SurfaceLoad_1),
    ("Soils[0]", lambda: g_i.Soils[0]),
]

for nome, get in objetos:
    print("\n" + "=" * 70)
    print(nome)
    try:
        obj = get()
    except Exception:
        print("   não existe:", ultima_linha())
        continue

    for rotulo, chamada in (("info", lambda: g_i.info(obj)),
                            ("commands", lambda: g_i.commands(obj))):
        print("--- {} ---".format(rotulo))
        try:
            print(chamada())
        except Exception:
            print("   erro:", ultima_linha())

    print("--- leitura direta de CoarsenessFactor ---")
    for prop in ("CoarsenessFactor", "Coarseness", "coarseness"):
        try:
            print("   {} = {}".format(prop, getattr(obj, prop)))
        except Exception:
            print("   {}: {}".format(prop, ultima_linha()))

print("\n>>> Fim do diagnóstico.")

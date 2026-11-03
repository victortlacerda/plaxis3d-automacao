# -*- coding: utf-8 -*-
"""
Diagnóstico (só leitura): rode com o projeto Exemplo1_Sapata aberto no PLAXIS Input.
Mostra (1) onde fica a propriedade de coarseness da sapata e (2) o estado das fases após o cálculo.
Não altera nada além de trocar para o modo Mesh.
"""
import traceback

print(">>> Modo Mesh (apenas para listar propriedades)")
try:
    g_i.gotomesh()
except Exception as e:
    print("   gotomesh falhou:", e)

print("\n>>> Propriedades dos objetos da sapata")
tentativas = [
    ("Polygon_1", lambda: g_i.Polygon_1),
    ("Plate_1", lambda: g_i.Plate_1),
    ("Plates[0]", lambda: g_i.Plates[0]),
    ("Polygon_1.Plate", lambda: g_i.Polygon_1.Plate),
    ("SurfaceLoad_1", lambda: g_i.SurfaceLoad_1),
]
for nome, get in tentativas:
    print("\n" + "=" * 60)
    print(nome)
    try:
        print(get().echo())
    except Exception:
        print("   erro:", traceback.format_exc().strip().splitlines()[-1])

print("\n" + "=" * 60)
print(">>> Fases: linhas de log / multiplicadores / passos")
for i, ph in enumerate(g_i.Phases):
    print("\n--- Fase {} ---".format(i))
    try:
        txt = str(ph.echo())
        for linha in txt.splitlines():
            if any(k in linha for k in ("Identification", "Log", "Mstage", "Reached", "Step", "Calc")):
                print(linha)
    except Exception:
        print("   erro:", traceback.format_exc().strip().splitlines()[-1])

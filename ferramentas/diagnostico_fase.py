# -*- coding: utf-8 -*-
"""
Diagnóstico (só leitura): mostra as propriedades reais da última fase e do seu bloco Deform,
para descobrir o nome da propriedade 'max steps stored'. Não altera nada.
Rode com o projeto do Exemplo 2 aberto no PLAXIS Input.
"""
fase = g_i.Phases[-1]

print("===== fase.echo() =====")
print(fase.echo())

print("\n===== fase.Deform.echo() =====")
print(fase.Deform.echo())

print("\n===== linhas com 'step' / 'stor' / 'max' =====")
for rotulo, obj in (("fase", fase), ("Deform", fase.Deform)):
    try:
        for linha in str(obj.echo()).splitlines():
            if any(k in linha.lower() for k in ("step", "stor", "max")):
                print("[{}] {}".format(rotulo, linha))
    except Exception as e:
        print("[{}] erro: {}".format(rotulo, e))

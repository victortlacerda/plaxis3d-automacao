# -*- coding: utf-8 -*-
"""
RELATÓRIO DE UM CASO: resultados + comparação com métodos analíticos + memorial de cálculo.

Use no lugar do plaxis_sapata_resultados.py, depois de calcular um modelo com o plaxis_sapata_interativo.py
(projeto aberto no PLAXIS). Ele:
  1. roda o plaxis_sapata_resultados.py validado (mesmos CSV, gráficos e critérios de sempre);
  2. calcula qu por Terzaghi, Meyerhof e Vesić e o recalque elástico, e gera sapata_comparacao_analitico.png;
  3. gera o memorial de cálculo em Word (.docx) e HTML (Ctrl+P no navegador salva em PDF).

Os parâmetros do solo vêm do ultimo_modelo.json (chave "entrada", gravada pelo script interativo desta versão).
Se o JSON for de uma versão anterior, o script pergunta os parâmetros da camada da base.
"""
import os
import sys
import json
import getpass

PASTA = os.path.dirname(os.path.abspath(globals().get("__file__", "sapata_relatorio.py")))
if PASTA not in sys.path:
    sys.path.insert(0, PASTA)

import sapata_motor as MT          # noqa: E402
import sapata_analitico as AN      # noqa: E402
import sapata_memorial as MEM      # noqa: E402


def _ler(prompt, padrao):
    r = input("  {} [{}]: ".format(prompt, padrao)).strip()
    return r or str(padrao)


def _f(prompt, padrao):
    return float(_ler(prompt, padrao).replace(",", "."))


def entrada_do_json():
    dados = json.load(open(os.path.join(PASTA, "ultimo_modelo.json"), encoding="utf-8"))
    P = dados.get("entrada")
    if P:
        return P
    print("\n  ultimo_modelo.json não tem os parâmetros do solo (versão anterior do script interativo).")
    print("  Informe os parâmetros da camada onde está a base da sapata:")
    S = dados["sapata"]
    camada = dict(nome="Solo", espessura=100.0, gamma_unsat=_f("γ não saturado (kN/m³)", 18),
                  gamma_sat=_f("γ saturado (kN/m³)", 20), E=_f("E' (kN/m²)", 40000), nu=_f("ν'", 0.3),
                  c=_f("c' (kN/m²)", 30), phi=_f("φ' (graus)", 20), psi=0.0)
    na = -_f("Profundidade do N.A. (m)", 6)
    return dict(dominio=dict(xmin=0, xmax=0, ymin=0, ymax=0, H=0), camadas=[camada], nivel_agua=na,
                sapata=dict(cx=S["cx"], cy=S["cy"], cz=S["cz"], L=S["L"], W=S["W"], B=S["B"], d=S.get("d", 0),
                            gamma=S.get("gamma", 24), E=0, nu=0, modelo=S.get("modelo", "placa")),
                carga=dados["carga"], malha=dict(nome="-", fator=0, refinar=False, coarseness=0),
                projeto=dados.get("projeto", "modelo"))


def principal():
    P = entrada_do_json()
    if P["carga"]["modo"] not in ("carga", "deslocamento"):
        print("(aviso) a comparação analítica e o memorial foram feitos para os módulos 'só carga' e "
              "'só deslocamento' com carga vertical; seguindo mesmo assim.")
    senha = globals().get("PLAXIS_PASSWORD") or os.environ.get("PLAXIS_PASSWORD") or \
        getpass.getpass("Senha do servidor PLAXIS: ")
    motor = MT.Motor(g_i, s_i, PASTA, senha)
    print(">>> Resultados (plaxis_sapata_resultados.py)")
    R = motor.resultados(PASTA)
    FS = R.get("FS", 3.0)
    A = MT.analitico_completo(P, FS)
    print("\n" + "=" * 70)
    print("COMPARAÇÃO COM MÉTODOS ANALÍTICOS")
    print("=" * 70)
    print(AN.tabela_texto(A, R.get("qu_tang")))
    print()
    print(AN.memoria_texto(A))
    with open(os.path.join(PASTA, "sapata_memoria_analitica.txt"), "w", encoding="utf-8") as f:
        f.write(AN.memoria_texto(A))
    fig = MT.grafico_comparacao(R["q"], R["s"], A, R, os.path.join(PASTA, "sapata_comparacao_analitico.png"))
    print("    gráfico salvo em", fig)
    nome = MT._seguro(os.path.splitext(os.path.basename(P.get("projeto", "modelo")))[0])
    R2 = {k: v for k, v in R.items() if k not in ("q", "s", "texto")}
    titulo = "Memorial de cálculo - sapata {}".format(nome)
    blocos = MEM.memorial_sapata(dict(caso=nome, entrada=P, elementos=None, resultados=R2, analitico=A,
                                      figuras=dict(R["figuras"], comparacao=fig), titulo=titulo))
    base = os.path.join(PASTA, "memorial_{}".format(nome))
    MEM.salvar_docx(blocos, base + ".docx", titulo)
    MEM.salvar_html(blocos, base + ".html", titulo)
    print("\n>>> Memorial: {}.docx e {}.html".format(base, base))
    try:
        import webbrowser
        webbrowser.open("file:///" + (base + ".html").replace("\\", "/"))
    except Exception:
        pass


principal()

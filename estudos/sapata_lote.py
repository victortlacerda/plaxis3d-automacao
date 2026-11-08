# -*- coding: utf-8 -*-
"""
ESTUDO PARAMÉTRICO EM LOTE de sapatas no PLAXIS 3D.

Lê uma planilha (sapatas_lote.xlsx, aba "Sapatas", ou um .csv com ";") com uma sapata por linha, roda cada
caso sozinho no PLAXIS com os scripts VALIDADOS (plaxis_sapata_interativo.py e plaxis_sapata_resultados.py)
e entrega, numa pasta lote_<data>/:
  - <caso>/ : projeto .p3d, curva (CSV), gráficos, comparação com Terzaghi/Meyerhof/Vesić e memorial (.docx e .html)
  - resumo_lote.xlsx e resumo_lote.csv : qu e qa de cada caso por todos os critérios e métodos
  - resumo_lote.html : painel com a tabela, o gráfico comparativo e os links para os memoriais
  - memorial_lote.docx : memorial consolidado

Como rodar: deixe na mesma pasta plaxis_sapata_interativo.py, plaxis_sapata_resultados.py, sapata_motor.py,
sapata_analitico.py, sapata_memorial.py e a planilha; rode este script pelo executor externo.
Se um caso falhar, ele é registrado e o lote continua.
"""
import os
import sys
import time
import json
import getpass
import datetime
import traceback

PASTA = os.path.dirname(os.path.abspath(globals().get("__file__", "sapata_lote.py")))
if PASTA not in sys.path:
    sys.path.insert(0, PASTA)

import sapata_motor as MT          # noqa: E402
import sapata_memorial as MEM      # noqa: E402
import sapata_analitico as AN      # noqa: E402

PLANILHA_PADRAO = os.path.join(PASTA, "sapatas_lote.xlsx")

def obter_senha():
    pw = globals().get("PLAXIS_PASSWORD") or os.environ.get("PLAXIS_PASSWORD")
    return pw or getpass.getpass("Senha do servidor PLAXIS: ")


def _ler(prompt, padrao):
    r = input("  {} [{}]: ".format(prompt, padrao)).strip()
    return r or padrao


def rodar_caso(motor, cd, pasta_lote):
    pasta = os.path.join(pasta_lote, MT._seguro(cd["caso"]))
    os.makedirs(pasta, exist_ok=True)
    P = MT.montar_P(cd["caso"], pasta, cd["B"], cd["L"], cd["Df"], cd["esp"], cd["solo"], cd["na"], cd["modo"],
                    cd["valor"], cd["passos"], cd["malha"], cd["refino"], cd["coarseness"], cd["borda"], cd["H"])
    MT.salvar_json(os.path.join(pasta, "entrada.json"), P)
    t0 = time.time()
    _, elementos = motor.construir(P, pasta)
    problema = motor.problema_calculo(cd["modo"])
    if problema:
        print("\n    (AVISO) cálculo não terminou como esperado: {}. Os resultados deste caso não entram na "
              "qa adotada.".format(problema))
    R = motor.resultados(pasta)
    A = MT.analitico_completo(P, cd["FS"])
    with open(os.path.join(pasta, "memoria_analitica.txt"), "w", encoding="utf-8") as f:
        f.write(AN.memoria_texto(A))
    fig_cmp = MT.grafico_comparacao(R["q"], R["s"], A, R, os.path.join(pasta, "comparacao_analitico.png"),
                                    "Caso {}: PLAXIS x métodos analíticos".format(cd["caso"]))
    R2 = {k: v for k, v in R.items() if k not in ("q", "s", "texto")}
    dados_mem = dict(caso=cd["caso"], entrada=P, elementos=elementos, resultados=R2, analitico=A,
                     figuras=dict(R["figuras"], comparacao=fig_cmp),
                     titulo="Memorial de cálculo - sapata {}".format(cd["caso"]))
    blocos = MEM.memorial_sapata(dados_mem)
    base = os.path.join(pasta, "memorial_{}".format(MT._seguro(cd["caso"])))
    MEM.salvar_docx(blocos, base + ".docx", dados_mem["titulo"])
    MEM.salvar_html(blocos, base + ".html", dados_mem["titulo"])
    with open(os.path.join(pasta, "saida_resultados.txt"), "w", encoding="utf-8") as f:
        f.write(R["texto"])
    MT.salvar_json(os.path.join(pasta, "resultado.json"),
                   dict(resultados=R2, analitico={k: v for k, v in A.items() if not k.startswith("_")},
                        elementos=elementos, minutos=(time.time() - t0) / 60.0))
    return dict(P=P, R=R, A=A, elementos=elementos, pasta=pasta, memorial=base, minutos=(time.time() - t0) / 60.0,
                problema=problema)


def qa_adotada(R, FS, modo="carga"):
    cands = []
    # com deslocamento prescrito a curva raramente forma patamar: a interseção das tangentes não é usada
    if R.get("qu_tang") is not None and modo == "carga":
        cands.append(("tangentes/FS", R["qu_tang"] / FS))
    if R.get("q_10b") is not None:
        cands.append(("10%B/FS", R["q_10b"] / FS))
    if R.get("q_25") is not None:
        cands.append(("25 mm", R["q_25"]))
    return min(cands, key=lambda t: t[1]) if cands else (None, None)


CAB_RESUMO = ["Caso", "B (m)", "L (m)", "Df (m)", "Modo", "Malha", "Elementos", "qu tangentes", "qa tangentes",
              "qu 10%B", "q 25 mm", "qa adotada", "Critério", "qu Terzaghi", "qu Meyerhof", "qu Vesić",
              "PLAXIS/Vesić", "Tempo (min)", "Status"]


def linha_resumo(cd, out=None, erro=None):
    base = [cd["caso"], cd["B"], cd["L"], cd["Df"], cd["modo"], cd["malha"]]
    if erro:
        return base + [None] * 12 + ["ERRO: " + erro]
    R, A = out["R"], out["A"]
    crit, qa = qa_adotada(R, cd["FS"], cd["modo"])
    if out.get("problema"):
        crit, qa = None, None
    qv = A["metodos"][2]["qu"]
    return base + [out["elementos"], R.get("qu_tang"), (R["qu_tang"] / cd["FS"]) if R.get("qu_tang") else None,
                   R.get("q_10b"), R.get("q_25"), qa, crit,
                   A["metodos"][0]["qu"], A["metodos"][1]["qu"], qv,
                   (R["qu_tang"] / qv) if R.get("qu_tang") and qv else None, round(out["minutos"], 1),
                   "AVISO: " + out["problema"] if out.get("problema") else "ok"]


def grafico_lote(linhas, caminho):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ok = [l for l in linhas if l[-1] == "ok"]
    if not ok:
        return None
    nomes = [str(l[0]) for l in ok]
    series = [("PLAXIS (tangentes)", 7, "#1f4e9c"), ("Terzaghi", 13, "#c0392b"), ("Meyerhof", 14, "#e67e22"),
              ("Vesić", 15, "#16a085")]
    import numpy as np
    x = np.arange(len(nomes))
    larg = 0.2
    fig, ax = plt.subplots(figsize=(max(7, 1.6 * len(nomes) + 3), 5))
    for k, (rot, col, cor) in enumerate(series):
        ax.bar(x + (k - 1.5) * larg, [l[col] or 0 for l in ok], larg, label=rot, color=cor)
    ax.set_xticks(x)
    ax.set_xticklabels(nomes, rotation=0)
    ax.set_ylabel("qu (kN/m²)")
    ax.set_title("Capacidade de carga por caso: PLAXIS x métodos analíticos")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(caminho, dpi=150)
    plt.close(fig)
    return caminho


def painel_html(caminho, linhas, saidas, grafico, planilha, inicio):
    import html as H
    ok = sum(1 for l in linhas if l[-1] == "ok")

    def cel(v):
        if v is None:
            return "-"
        if isinstance(v, float):
            return MEM.fmt_num(v, 0 if abs(v) >= 100 else 2)
        return H.escape(str(v))
    corpo = []
    for l in linhas:
        caso = l[0]
        link = ""
        if caso in saidas:
            rel = os.path.relpath(saidas[caso]["memorial"] + ".html", os.path.dirname(caminho)).replace("\\", "/")
            link = '<a href="{}">memorial</a>'.format(H.escape(rel))
        cls = "" if l[-1] == "ok" else ' class="erro"'
        corpo.append("<tr{}>{}<td>{}</td></tr>".format(cls, "".join("<td>{}</td>".format(cel(v)) for v in l), link))
    graf = ""
    if grafico:
        graf = '<figure><img src="{}" alt="comparação"></figure>'.format(
            H.escape(os.path.relpath(grafico, os.path.dirname(caminho)).replace("\\", "/")))
    doc = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Lote de sapatas</title><style>
:root{{--azul:#0d2b4e;--linha:#d3dce8}} body{{margin:0;background:#f4f7fb;font:14px/1.5 'Segoe UI',Arial,sans-serif;color:#1d2733}}
header{{background:linear-gradient(135deg,#0d2b4e,#1d5b96);color:#fff;padding:24px 32px}} h1{{margin:0;font-size:26px}}
.sub{{color:#cfe0f3}} main{{padding:20px 32px}} .cards{{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:16px}}
.card{{background:#fff;border:1px solid var(--linha);border-radius:10px;padding:12px 18px;min-width:150px}}
.card b{{display:block;font-size:24px;color:var(--azul)}} .tab{{overflow-x:auto;background:#fff;border:1px solid var(--linha);border-radius:10px}}
table{{border-collapse:collapse;width:100%;font-size:13px}} th,td{{padding:6px 8px;border-bottom:1px solid var(--linha);text-align:right;white-space:nowrap}}
th{{background:#dce6f2;position:sticky;top:0}} td:first-child,th:first-child,td:nth-child(5),td:nth-child(6),td:nth-child(13){{text-align:left}}
tr.erro td{{background:#fdecea}} figure{{background:#fff;border:1px solid var(--linha);border-radius:10px;margin:16px 0;padding:10px;text-align:center}}
figure img{{max-width:100%}} .nota{{color:#5b6878;font-size:12.5px}}
@media (max-width:640px){{header,main{{padding:16px}}}}
</style></head><body><header><h1>Estudo paramétrico de sapatas</h1>
<div class="sub">Planilha: {pl} · início {ini} · PLAXIS 3D + Terzaghi, Meyerhof e Vesić</div></header><main>
<div class="cards"><div class="card"><b>{n}</b>casos</div><div class="card"><b>{ok}</b>calculados</div>
<div class="card"><b>{er}</b>com erro</div></div>
<div class="tab"><table><thead><tr>{cab}<th>Memorial</th></tr></thead><tbody>{corpo}</tbody></table></div>
{graf}<p class="nota">Cargas em kN/m². qa adotada = menor entre qu(tangentes)/FS (só no modo carga), qu(10% de B)/FS e a tensão para 25 mm.
Valores para revisão do responsável técnico.</p></main></body></html>""".format(
        pl=H.escape(os.path.basename(planilha)), ini=inicio, n=len(linhas), ok=ok, er=len(linhas) - ok,
        cab="".join("<th>{}</th>".format(H.escape(c)) for c in CAB_RESUMO), corpo="".join(corpo), graf=graf)
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(doc)
    return caminho


def memorial_lote(caminho, linhas, grafico, planilha):
    blocos = [("titulo", "Estudo paramétrico de sapatas - resumo"),
              ("p", "Planilha: {}\nData: {}".format(os.path.basename(planilha),
                                                   datetime.date.today().strftime("%d/%m/%Y"))),
              ("h1", "1. Resultados por caso"),
              ("tabela", ["Caso", "B x L (m)", "Df (m)", "Modo", "qu tang.", "qu 10%B", "q 25 mm", "qa adotada",
                          "Critério", "Vesić"],
               [[l[0], "{} x {}".format(MEM.fmt_num(l[1], 2), MEM.fmt_num(l[2], 2)), MEM.fmt_num(l[3], 2), l[4],
                 MEM.fmt_num(l[7], 0), MEM.fmt_num(l[9], 0), MEM.fmt_num(l[10], 0), MEM.fmt_num(l[11], 0),
                 l[12] or l[-1], MEM.fmt_num(l[15], 0)] for l in linhas])]
    if grafico:
        blocos.append(("img", grafico, "Capacidade de carga por caso: PLAXIS x métodos analíticos", 16.0))
    blocos.append(("nota", "Cargas em kN/m². O memorial completo de cada caso está na pasta do caso."))
    MEM.salvar_docx(blocos, caminho, "Estudo paramétrico de sapatas")
    return caminho


def principal():
    print("=" * 70)
    print(" PLAXIS 3D - ESTUDO PARAMÉTRICO EM LOTE (sapatas)")
    print("=" * 70)
    planilha = _ler("Planilha com as sapatas (.xlsx ou .csv)", PLANILHA_PADRAO).strip('"')
    if not os.path.isabs(planilha):
        planilha = os.path.join(PASTA, planilha)
    casos, erros = MT.ler_casos(planilha)
    for e in erros:
        print("    (ignorado) " + e)
    if not casos:
        print("Nenhum caso válido na planilha.")
        return
    print("\n  {} caso(s):".format(len(casos)))
    for cd in casos:
        print("    - {:<14} B={} L={} Df={}  {} {} {}  malha {}".format(
            cd["caso"], cd["B"], cd["L"], cd["Df"], cd["modo"], cd["valor"],
            "kN/m²" if cd["modo"] == "carga" else "mm", cd["malha"]))
    print("\n  ATENÇÃO: cada caso cria um NOVO projeto no PLAXIS (o projeto aberto agora será descartado).")
    if _ler("Continuar? (s/n)", "s").lower() not in ("s", "sim"):
        print("Cancelado.")
        return
    senha = obter_senha()
    inicio = datetime.datetime.now()
    pasta_lote = os.path.join(PASTA, "lote_" + inicio.strftime("%Y%m%d_%H%M"))
    os.makedirs(pasta_lote, exist_ok=True)
    motor = MT.Motor(g_i, s_i, PASTA, senha)
    linhas, saidas = [], {}
    for k, cd in enumerate(casos, 1):
        print("\n" + "#" * 70)
        print("# CASO {}/{}: {}".format(k, len(casos), cd["caso"]))
        print("#" * 70)
        try:
            out = rodar_caso(motor, cd, pasta_lote)
            saidas[cd["caso"]] = out
            linhas.append(linha_resumo(cd, out))
        except Exception as e:  # noqa
            msg = str(e).strip().splitlines()[-1] if str(e).strip() else repr(e)
            print("\n    (ERRO no caso {}) {}".format(cd["caso"], msg))
            with open(os.path.join(pasta_lote, "erro_{}.txt".format(MT._seguro(cd["caso"]))), "w",
                      encoding="utf-8") as f:
                f.write(traceback.format_exc())
            linhas.append(linha_resumo(cd, erro=msg))
        MT.salvar_csv(os.path.join(pasta_lote, "resumo_lote.csv"), CAB_RESUMO, linhas)   # parcial, a cada caso

    MT.salvar_xlsx(os.path.join(pasta_lote, "resumo_lote.xlsx"), CAB_RESUMO, linhas)
    graf = None
    try:
        graf = grafico_lote(linhas, os.path.join(pasta_lote, "resumo_lote.png"))
    except Exception as e:  # noqa
        print("    (aviso) gráfico do lote: {}".format(e))
    painel = painel_html(os.path.join(pasta_lote, "resumo_lote.html"), linhas, saidas, graf, planilha,
                         inicio.strftime("%d/%m/%Y %H:%M"))
    memorial_lote(os.path.join(pasta_lote, "memorial_lote.docx"), linhas, graf, planilha)

    print("\n" + "=" * 70)
    print("RESUMO DO LOTE (kN/m²)")
    print("=" * 70)
    print("{:<14}{:>10}{:>10}{:>10}{:>11}{:>10}  {}".format("caso", "qu tang", "qu 10%B", "q 25mm", "qa adot.",
                                                             "Vesić", "status"))
    for l in linhas:
        f0 = lambda v: "{:.0f}".format(v) if isinstance(v, float) else "-"   # noqa: E731
        print("{:<14}{:>10}{:>10}{:>10}{:>11}{:>10}  {}".format(str(l[0])[:13], f0(l[7]), f0(l[9]), f0(l[10]),
                                                                 f0(l[11]), f0(l[15]), l[-1][:40]))
    print("\nResultados em: " + pasta_lote)
    print("Painel: " + painel)
    try:
        import webbrowser
        webbrowser.open("file:///" + painel.replace("\\", "/"))
    except Exception:
        pass


principal()

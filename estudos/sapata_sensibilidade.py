# -*- coding: utf-8 -*-
"""
SENSIBILIDADE DE MALHA E DE DOMÍNIO de uma sapata no PLAXIS 3D.

Roda o MESMO caso várias vezes, mudando uma coisa por vez:
  - malha: very coarse -> very fine (domínio fixo);
  - largura lateral do domínio: distância da sapata ao contorno = k x maior lado (malha fixa);
  - profundidade do domínio: H abaixo da base = k x maior lado (malha e largura fixas).
Para cada rodada lê o resultado (qu pelas tangentes no modo carga; tensão no recalque prescrito no modo
deslocamento), e diz a partir de onde ele estabiliza: diferença para a rodada mais refinada/maior <= tolerância.

Caso base: uma linha da planilha do lote (sapatas_lote.xlsx) ou o último modelo do script interativo
(ultimo_modelo.json, gravado pelo plaxis_sapata_interativo.py a partir desta versão).

Saída: pasta sensibilidade_<data>/ com cada rodada, sensibilidade.csv/.xlsx, gráficos e relatório
(sensibilidade.html e sensibilidade.docx).
"""
import os
import sys
import copy
import json
import getpass
import datetime
import traceback

PASTA = os.path.dirname(os.path.abspath(globals().get("__file__", "sapata_sensibilidade.py")))
if PASTA not in sys.path:
    sys.path.insert(0, PASTA)

import sapata_motor as MT          # noqa: E402
import sapata_memorial as MEM      # noqa: E402

ORDEM_MALHAS = ["very coarse", "coarse", "medium", "fine", "very fine"]


def _ler(prompt, padrao):
    r = input("  {} [{}]: ".format(prompt, padrao)).strip()
    return r or str(padrao)


def _lista_num(txt):
    return [float(x.replace(",", ".")) for x in txt.replace(";", " ").split() if x.strip()]


def obter_senha():
    pw = globals().get("PLAXIS_PASSWORD") or os.environ.get("PLAXIS_PASSWORD")
    return pw or getpass.getpass("Senha do servidor PLAXIS: ")


def caso_base():
    print("\n  Caso base:")
    print("    1) uma linha da planilha do lote (sapatas_lote.xlsx)")
    print("    2) o último modelo do script interativo (ultimo_modelo.json)")
    op = _ler("Opção", "1")
    if op == "2":
        arq = os.path.join(PASTA, "ultimo_modelo.json")
        dados = json.load(open(arq, encoding="utf-8"))
        P = dados.get("entrada")
        if not P:
            raise RuntimeError("ultimo_modelo.json sem a chave 'entrada'. Rode de novo o plaxis_sapata_interativo.py "
                               "desta versão ou use a planilha.")
        if P["carga"]["modo"] not in ("carga", "deslocamento"):
            raise RuntimeError("A sensibilidade só trata os módulos 'só carga' e 'só deslocamento'.")
        return P, os.path.splitext(os.path.basename(P.get("projeto", "modelo")))[0], 3.0
    planilha = _ler("Planilha", os.path.join(PASTA, "sapatas_lote.xlsx")).strip('"')
    if not os.path.isabs(planilha):
        planilha = os.path.join(PASTA, planilha)
    casos, erros = MT.ler_casos(planilha)
    for e in erros:
        print("    (ignorado) " + e)
    for i, cd in enumerate(casos, 1):
        print("    {}) {}  B={} L={} {} {}".format(i, cd["caso"], cd["B"], cd["L"], cd["modo"], cd["valor"]))
    i = int(_ler("Qual caso", "1")) - 1
    cd = casos[i]
    P = MT.montar_P(cd["caso"], PASTA, cd["B"], cd["L"], cd["Df"], cd["esp"], cd["solo"], cd["na"], cd["modo"],
                    cd["valor"], cd["passos"], cd["malha"], cd["refino"], cd["coarseness"], cd["borda"], cd["H"])
    return P, cd["caso"], cd["FS"]


def dims(P):
    f = P["sapata"]
    return f["L"], f["W"], max(f["L"], f["W"]), -f["cz"]


def com_lateral(P, k):
    Q = copy.deepcopy(P)
    L, W, Bmax, _ = dims(P)
    f = Q["sapata"]
    Q["dominio"].update(xmin=f["cx"] - L / 2.0 - k * Bmax, xmax=f["cx"] + L / 2.0 + k * Bmax,
                        ymin=f["cy"] - W / 2.0 - k * Bmax, ymax=f["cy"] + W / 2.0 + k * Bmax)
    return Q


def com_profundidade(P, k):
    Q = copy.deepcopy(P)
    _, _, Bmax, D = dims(P)
    H = D + k * Bmax
    Q["dominio"]["H"] = H
    Q["camadas"] = [dict(Q["camadas"][0], espessura=H)] if len(Q["camadas"]) == 1 else Q["camadas"]
    if len(P["camadas"]) > 1:
        raise RuntimeError("estudo de profundidade só para solo de 1 camada")
    Q["nivel_agua"] = max(Q["nivel_agua"], -H)
    return Q


def com_malha(P, nome):
    Q = copy.deepcopy(P)
    Q["malha"].update(nome=nome, fator=MT.PRESETS_MALHA[nome])
    return Q


def metrica(R, modo):
    if modo == "carga":
        return R.get("qu_tang") if R.get("qu_tang") is not None else R.get("q_max")
    return R.get("q_max")


def estabiliza(valores, tol):
    """Índice a partir do qual todos ficam a no máximo tol da última rodada (referência)."""
    validos = [(i, v) for i, v in enumerate(valores) if v]
    if len(validos) < 2:
        return None, None
    ref = validos[-1][1]
    desv = [abs(v - ref) / abs(ref) if v else None for v in valores]
    for i, _ in validos:                       # rodadas descartadas (None) não entram no critério
        if all(desv[j] <= tol for j, _ in validos if j >= i):
            return i, desv
    return None, desv


def grafico(estudo, xs, ys, xlabel, caminho, i_est, tol, rotulos=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 5))
    pts = [(x, y) for x, y in zip(xs, ys) if x is not None and y]
    if pts:
        ax.plot([p[0] for p in pts], [p[1] for p in pts], "o-", color="#1f4e9c", lw=2)
        ref = pts[-1][1]
        ax.axhspan(ref * (1 - tol), ref * (1 + tol), color="#2ecc71", alpha=0.15,
                   label="faixa de ±{:.0f}% da última rodada".format(tol * 100))
        if i_est is not None and xs[i_est] is not None:
            ax.axvline(xs[i_est], color="#c0392b", ls="--", label="estabiliza a partir daqui")
        if rotulos:
            for (x, y), r in zip(pts, [r for r, yy in zip(rotulos, ys) if yy]):
                ax.annotate(r, (x, y), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=8)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Resultado (kN/m²)")
    ax.set_title("Sensibilidade - " + estudo)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(caminho, dpi=150)
    plt.close(fig)
    return caminho


def principal():
    print("=" * 70)
    print(" PLAXIS 3D - SENSIBILIDADE DE MALHA E DE DOMÍNIO (sapata)")
    print("=" * 70)
    P0, nome, FS = caso_base()
    modo = P0["carga"]["modo"]
    _, _, Bmax, D = dims(P0)
    print("\n  Caso '{}' ({}): malha base {}, domínio x [{:.1f}, {:.1f}], H = {:.1f} m".format(
        nome, modo, P0["malha"]["nome"], P0["dominio"]["xmin"], P0["dominio"]["xmax"], P0["dominio"]["H"]))
    estudos = []
    if _ler("Estudar a MALHA? (s/n)", "s").lower().startswith("s"):
        ms = _ler("Malhas (separadas por vírgula)", "coarse, medium, fine, very fine")
        malhas = [m.strip().lower() for m in ms.split(",") if m.strip()]
        malhas = sorted([m for m in malhas if m in MT.PRESETS_MALHA], key=ORDEM_MALHAS.index)
        estudos.append(("malha", [(m, com_malha(P0, m)) for m in malhas]))
    if _ler("Estudar a LARGURA do domínio? (s/n)", "s").lower().startswith("s"):
        ks = _lista_num(_ler("Distância da sapata ao contorno (x maior lado)", "1 2 3 4.5 6"))
        estudos.append(("largura", [("k={:g}".format(k), com_lateral(P0, k)) for k in sorted(ks)]))
    if _ler("Estudar a PROFUNDIDADE do domínio? (s/n)", "n").lower().startswith("s"):
        ks = _lista_num(_ler("Solo abaixo da base (x maior lado)", "3 5 7 10"))
        estudos.append(("profundidade", [("k={:g}".format(k), com_profundidade(P0, k)) for k in sorted(ks)]))
    tol = float(_ler("Tolerância para considerar estável (%)", "2").replace(",", ".")) / 100.0
    n = sum(len(e[1]) for e in estudos)
    if not n:
        print("Nada a rodar.")
        return
    print("\n  {} rodada(s). Cada uma cria um NOVO projeto no PLAXIS (o aberto agora será descartado).".format(n))
    if _ler("Continuar? (s/n)", "s").lower() not in ("s", "sim"):
        return
    senha = obter_senha()
    inicio = datetime.datetime.now()
    pasta = os.path.join(PASTA, "sensibilidade_" + inicio.strftime("%Y%m%d_%H%M"))
    os.makedirs(pasta, exist_ok=True)
    motor = MT.Motor(g_i, s_i, PASTA, senha)
    linhas, blocos_rel, figs = [], [], []
    for estudo, rodadas in estudos:
        vals, elems, xs, rot = [], [], [], []
        for rotulo, P in rodadas:
            sub = os.path.join(pasta, "{}_{}".format(estudo, MT._seguro(rotulo)))
            os.makedirs(sub, exist_ok=True)
            P = copy.deepcopy(P)
            P["projeto"] = os.path.join(sub, "{}_{}.p3d".format(estudo, MT._seguro(rotulo)))
            P["info"]["titulo"] = "Sensibilidade {} - {}".format(estudo, rotulo)
            print("\n" + "#" * 70 + "\n# {}: {}\n".format(estudo.upper(), rotulo) + "#" * 70)
            try:
                _, ne = motor.construir(P, sub)
                problema = motor.problema_calculo(modo)
                R = motor.resultados(sub)
                v = metrica(R, modo)
                if problema:
                    print("    (AVISO) rodada descartada: {}".format(problema))
                    v = None
                linhas.append([estudo, rotulo, ne, P["dominio"]["xmax"] - P["dominio"]["xmin"], P["dominio"]["H"],
                               v, R.get("q_25") if not problema else None,
                               "descartada: " + problema if problema else "ok"])
            except Exception as e:  # noqa
                ne, v = None, None
                msg = str(e).strip().splitlines()[-1] if str(e).strip() else repr(e)
                print("    (ERRO) " + msg)
                with open(os.path.join(sub, "erro.txt"), "w", encoding="utf-8") as f:
                    f.write(traceback.format_exc())
                linhas.append([estudo, rotulo, None, None, None, None, None, "ERRO: " + msg])
            vals.append(v)
            elems.append(ne)
            rot.append(rotulo)
            if estudo == "malha":
                xs.append(ne)
            else:
                xs.append(float(rotulo.split("=")[1]))
            MT.salvar_csv(os.path.join(pasta, "sensibilidade.csv"), CAB, linhas)
        i_est, desv = estabiliza(vals, tol)
        xlabel = {"malha": "Número de elementos", "largura": "Distância ao contorno lateral (x maior lado)",
                  "profundidade": "Solo abaixo da base (x maior lado)"}[estudo]
        fig = grafico(estudo, xs, vals, xlabel, os.path.join(pasta, "sensibilidade_{}.png".format(estudo)),
                      i_est, tol, rot)
        figs.append(fig)
        if i_est is not None:
            concl = "estabiliza a partir de {} (diferença <= {:.0f}% da rodada mais {}).".format(
                rot[i_est], tol * 100, "refinada" if estudo == "malha" else "ampla")
        elif sum(1 for v in vals if v) < 2:
            concl = "menos de duas rodadas válidas: não dá para concluir (veja as rodadas descartadas)."
        else:
            concl = "não estabilizou dentro de {:.0f}% nas rodadas feitas: amplie a lista.".format(tol * 100)
        print("\n>>> {}: {}".format(estudo.upper(), concl))
        blocos_rel.append(("h1", "Estudo de {}".format(estudo)))
        blocos_rel.append(("p", "Resultado: " + concl))
        blocos_rel.append(("tabela", ["Rodada", "Elementos", "Resultado (kN/m²)", "Diferença p/ última"],
                           [[r, e or "-", MEM.fmt_num(v, 1), "{:.1f}%".format(d * 100) if d is not None else "-"]
                            for r, e, v, d in zip(rot, elems, vals, desv or [None] * len(vals))]))
        blocos_rel.append(("img", fig, "Sensibilidade - {}".format(estudo), 14.0))
    MT.salvar_xlsx(os.path.join(pasta, "sensibilidade.xlsx"), CAB, linhas)
    blocos = [("titulo", "Sensibilidade de malha e domínio - {}".format(nome)),
              ("p", "Modo: {}. Resultado comparado: {}. Tolerância: {:.0f}%.\nData: {}".format(
                  modo, "qu pela interseção das tangentes" if modo == "carga"
                  else "tensão média no recalque prescrito", tol * 100, inicio.strftime("%d/%m/%Y %H:%M")))]
    blocos += blocos_rel
    MEM.salvar_docx(blocos, os.path.join(pasta, "sensibilidade.docx"), "Sensibilidade")
    rel = MEM.salvar_html(blocos, os.path.join(pasta, "sensibilidade.html"), "Sensibilidade")
    print("\nResultados em: " + pasta)
    try:
        import webbrowser
        webbrowser.open("file:///" + rel.replace("\\", "/"))
    except Exception:
        pass


CAB = ["Estudo", "Rodada", "Elementos", "Largura do domínio (m)", "H (m)", "Resultado (kN/m²)", "q 25 mm",
       "Status"]

principal()

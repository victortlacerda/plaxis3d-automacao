# -*- coding: utf-8 -*-
"""
soiltest_biblioteca.py  -  Biblioteca de materiais: le uma planilha CSV (uma linha por material) e cria ou atualiza
os materiais no PLAXIS 3D Input. Opcionalmente confere cada material no SoilTest (triaxial drenado em 3 pressoes e
edometro) e gera um relatorio.

Planilha (veja materiais_modelo.csv): separador ";", virgula ou ponto decimal.
  nome      : Identification do material no PLAXIS (se ja existir, e atualizado)
  modelo    : MC | LE | HS | HSsmall | MCC | SS
  drenagem  : D | UA | UB | UC | NP (as validas dependem do modelo)
  conferir  : s/n  (s = roda o SoilTest para esse material)
  demais colunas: parametros. As chaves do plaxis_soiltest_auto (ERef, nu, cRef, phi, psi, E50ref, Eoedref, Eurref, m,
  nuur, pref, cref, G0ref, gamma07, K0nc, Rf, lambda, kappa, M, eInit, PhiInter, lambdaModified, kappaModified, sURef,
  nuU) e qualquer outro atributo do material no PLAXIS pelo nome (ex.: gammaUnsat, gammaSat). Celula vazia = nao mexe.

COMO RODAR: PLAXIS 3D Input aberto com o projeto onde os materiais devem entrar; rode pelo Executar_script_PLAXIS.bat.
Precisa do plaxis_soiltest_auto.py na mesma pasta (ou na pasta acima). Senha: variavel PLAXIS_PASSWORD.
"""
import copy
import csv
import datetime
import os
import traceback

AQUI = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
PLANILHA = os.path.join(AQUI, "materiais_modelo.csv")      # troque pelo caminho da sua planilha
PRESSOES_CONFERENCIA = [50, 100, 200]
FIXAS = ("nome", "modelo", "drenagem", "conferir")


def carregar_auto():
    for nome in ("plaxis_soiltest_auto.py", os.path.join("..", "plaxis_soiltest_auto.py"), "plaxis_soiltest_auto_dev.py"):
        cam = os.path.normpath(os.path.join(AQUI, nome))
        if os.path.isfile(cam):
            break
    else:
        raise FileNotFoundError("Nao achei plaxis_soiltest_auto.py nesta pasta nem na pasta acima.")
    ns = {"__name__": "soiltest_auto", "__file__": cam, "__builtins__": __builtins__}
    if "g_i" in globals():
        ns["g_i"], ns["s_i"] = globals()["g_i"], globals().get("s_i")
    with open(cam, "rb") as f:
        exec(compile(f.read(), cam, "exec"), ns, ns)
    return ns


def ler_planilha(caminho):
    with open(caminho, encoding="utf-8-sig") as f:
        linhas = [l for l in csv.reader(f, delimiter=";") if any(c.strip() for c in l)]
    cab = [c.strip() for c in linhas[0]]
    out = []
    for l in linhas[1:]:
        reg = {}
        for c, v in zip(cab, l):
            v = v.strip()
            if c.lower() in FIXAS:
                reg[c.lower()] = v
            elif v != "":
                try:
                    reg[c] = float(v.replace(",", "."))
                except ValueError:
                    reg[c] = v
        out.append(reg)
    return out


def main():
    A = carregar_auto()
    log = A["log"]
    if not os.path.isfile(PLANILHA):
        log("Planilha nao encontrada: {}".format(PLANILHA))
        return 1
    regs = ler_planilha(PLANILHA)
    log("Biblioteca de materiais: {} material(is) em {}".format(len(regs), PLANILHA))
    gi = A["obter_input"](A["CONFIG"])
    if gi is None:
        return 1
    pasta = os.path.join(AQUI, "soiltest_saida", "biblioteca_{}".format(datetime.datetime.now().strftime("%Y%m%d_%H%M%S")))
    os.makedirs(pasta, exist_ok=True)
    tabela, secoes_mat = [], []
    for r in regs:
        nome, modelo, dren = r.get("nome"), (r.get("modelo") or "").strip(), (r.get("drenagem") or "D").strip().upper()
        log("\n" + "=" * 60 + "\n{} ({} / {})\n".format(nome, modelo, dren) + "=" * 60)
        if modelo not in A["MODELOS"] or dren not in A["MODELOS"][modelo]["dren"]:
            msg = "modelo/drenagem invalidos (modelos: {}; drenagens do modelo: {})".format(
                list(A["MODELOS"]), A["MODELOS"].get(modelo, {}).get("dren"))
            log("   " + msg)
            tabela.append((nome, modelo, dren, '<span class="erro">{}</span>'.format(A["_esc"](msg)), "-"))
            continue
        lista = A["parametros"](modelo, dren)
        chaves = {c.lower(): c for c, _a, _r, _v in lista}
        valores = {c: None for c, _a, _r, _v in lista}
        extras = {}
        for k, v in r.items():
            if k in FIXAS:
                continue
            if k.lower() in chaves:
                valores[chaves[k.lower()]] = v
            else:
                extras[k] = v
        n_antes = len(A["_linhas"])
        mat = A["criar_material"](gi, nome, modelo, dren, valores, None)
        if mat is None:
            tabela.append((nome, modelo, dren, '<span class="erro">nao criado</span>', "-"))
            continue
        for k, v in extras.items():
            attr = A["achar_attr"](mat, [k])
            if attr is None:
                log("[ERR] atributo '{}' nao existe neste material".format(k))
                continue
            A["tentar"]("{} = {}".format(attr, v), lambda a=attr, v=v: mat.setproperties(a, v))
        falhas = [l for l in A["_linhas"][n_antes:] if l.startswith("[ERR]") or l.startswith("ATENCAO")]
        status = '<span class="ok">criado/atualizado</span>' if not falhas else '<span class="alerta">{} aviso(s): {}</span>'.format(
            len(falhas), A["_esc"]("; ".join(falhas)[:300]))
        conf = "-"
        if (r.get("conferir") or "").lower().startswith("s"):
            g, porta = A["abrir_soiltest"](gi, mat, A["CONFIG"]["espera_soiltest_s"], A["CONFIG"]["porta_input"], modelo)
            if g is None:
                conf = '<span class="erro">SoilTest recusou o material</span>'
            else:
                cfg = copy.deepcopy(A["CONFIG"])
                for t in ("crs", "dss", "cdss", "triaxial_ciclico"):
                    cfg[t]["rodar"] = False
                cfg["triaxial"].update({"rodar": True, "pressoes_kPa": PRESSOES_CONFERENCIA, "comportamentos": ["Drained"]})
                cfg["oedometer"]["rodar"] = True
                p = {k: float(v) for k, v in valores.items() if isinstance(v, (int, float))}
                ctx = {"modelo": modelo, "dren": dren, "consolidacao": {"tipo": "Isotropic"}, "k0": None,
                       "preadensamento": {"modo": "nenhum", "valor": 0}, "pc_usados": set(),
                       "pc_fases_kPa": float(cfg.get("sigma_p_padrao_fases_kPa") or 0)}
                sub = os.path.join(pasta, str(nome))
                os.makedirs(sub, exist_ok=True)
                resumo = {"modelo": modelo, "drenagem": dren, "parametros": valores, "consolidacao": {"tipo": "Isotropic"},
                          "preadensamento": {"modo": "nenhum"}}
                todas = A["executar_ensaios"](g, cfg, modelo, dren, p, ctx, sub, resumo)
                A["fechar_soiltest"](g)
                gerados = A["graficos"](sub, "{} ({})".format(nome, A["MODELOS"][modelo]["nome"]), todas)
                A["relatorio_auto"](sub, "{} ({})".format(nome, A["MODELOS"][modelo]["nome"]), resumo, gerados)
                qs = ["{}: {}".format(k, A["_num"](v.get("q_max_kPa"), 1)) for k, v in (resumo.get("triaxial") or {}).items()]
                conf = '<a href="{}/relatorio.html">relatorio</a> | q_max {}'.format(A["_esc"](nome), A["_esc"](", ".join(qs)))
                if gerados:
                    secoes_mat.append(("{}: q × ε_a".format(nome), A["html_imagem"](gerados[0], os.path.basename(gerados[0]))))
        tabela.append((nome, A["MODELOS"][modelo]["nome"], dren, status, conf))
    sec = [("Materiais", A["html_tabela"](["Material", "Modelo", "Drenagem", "Situação no PLAXIS", "Conferência no SoilTest"], tabela)
            + '<p class="nota">Planilha: {}. Conferência: triaxial drenado em {} kPa e edômetro; o relatório de cada material '
              'está na subpasta com o nome dele.</p>'.format(A["_esc"](PLANILHA), ", ".join(str(x) for x in PRESSOES_CONFERENCIA)))] + secoes_mat
    rel = A["relatorio_html"](os.path.join(pasta, "relatorio.html"), "Biblioteca de materiais", "{} material(is)".format(len(regs)), sec)
    log("\nRelatorio: {}\nSaida: {}".format(rel, pasta))
    with open(os.path.join(pasta, "log.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(A["_linhas"]))
    return 0


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(traceback.format_exc())

# -*- coding: utf-8 -*-
"""
soiltest_auditoria.py  -  Auditoria dos materiais do projeto aberto no PLAXIS 3D Input.

Para cada material de solo do projeto:
  1. le o modelo, a drenagem e os parametros;
  2. confere a coerencia dos parametros com faixas usuais e regras de cada modelo (ERRO / ALERTA / INFO);
  3. opcionalmente roda o SoilTest (triaxial em 50/100/200 kPa e edometro) e compara com a teoria;
  4. entrega um relatorio HTML com o resumo de todos os materiais e o detalhe de cada um.

As faixas sao valores usuais de literatura e servem de alerta, nao de regra: um ALERTA pede conferencia, nao
significa erro. ERRO indica combinacao que o PLAXIS nao aceita ou que nao tem sentido fisico.

COMO RODAR: PLAXIS 3D Input aberto com o projeto a auditar; rode pelo Executar_script_PLAXIS.bat.
Precisa do plaxis_soiltest_auto.py na mesma pasta (ou na pasta acima). Senha: variavel PLAXIS_PASSWORD.
"""
import copy
import datetime
import math
import os
import traceback

AQUI = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
RODAR_SOILTEST = True          # False = so confere os parametros (rapido, nao abre o SoilTest)
PRESSOES = [50, 100, 200]
SO_ESTES = []                  # nomes de materiais para auditar; vazio = todos


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


def faixa(v, lo, hi):
    return v is not None and (v < lo or v > hi)


def regras(modelo, dren, p):
    """Lista de (nivel, mensagem). nivel: ERRO | ALERTA | INFO."""
    r = []
    phi, psi = p.get("phi"), p.get("psi")
    c = p.get("cRef", p.get("cref"))
    if faixa(phi, 15, 45):
        r.append(("ALERTA", "φ' = {:.1f}° fora da faixa usual (15 a 45°).".format(phi)))
    if phi is not None and psi is not None:
        lim = max(0.0, phi - 30.0)
        if psi > lim + 2:
            r.append(("ALERTA", "ψ = {:.1f}° alto para φ' = {:.1f}° (regra de Bolton: ψ ≈ φ' − 30° = {:.1f}°).".format(psi, phi, lim)))
    if c is not None and c > 30:
        r.append(("INFO", "Coesão efetiva de {:.1f} kPa (> 30 kPa): confirme que é efetiva e não total.".format(c)))
    for k in ("ERef", "E50ref", "Eoedref", "Eurref", "G0ref"):
        if p.get(k) is not None and p[k] <= 0:
            r.append(("ERRO", "{} deve ser positivo.".format(k)))
    if modelo in ("MC", "LE") and faixa(p.get("nu"), 0.1, 0.45):
        r.append(("ALERTA", "ν' = {:.3f} fora da faixa usual (0,10 a 0,45).".format(p["nu"])))
    if dren == "UC" and p.get("nuU") is not None and p["nuU"] < 0.45:
        r.append(("ALERTA", "ν_u = {:.3f}: em análise com parâmetros totais use próximo de 0,5 (ex.: 0,495).".format(p["nuU"])))
    if dren in ("UB", "UC") and (p.get("sURef") is None or p["sURef"] <= 0):
        r.append(("ERRO", "Drenagem {} precisa de su > 0.".format(dren)))
    if dren == "UA":
        r.append(("INFO", "Undrained A: a resistência não drenada resulta dos parâmetros efetivos e do caminho de tensões; "
                          "confira o su com um triaxial não drenado (a auditoria roda um)."))
    if modelo in ("HS", "HSsmall"):
        e50, eoed, eur = p.get("E50ref"), p.get("Eoedref"), p.get("Eurref")
        if e50 and eoed and not 0.5 <= eoed / e50 <= 2.0:
            r.append(("ALERTA", "Eoedref/E50ref = {:.2f} (usual 0,5 a 2; em areias ≈ 1).".format(eoed / e50)))
        if e50 and eur and not 2.0 <= eur / e50 <= 6.0:
            r.append(("ALERTA", "Eurref/E50ref = {:.2f} (usual 2 a 6; padrão 3).".format(eur / e50)))
        if faixa(p.get("m"), 0.3, 1.0):
            r.append(("ALERTA", "m = {:.2f} fora da faixa usual (0,5 em areias a 1,0 em argilas).".format(p["m"])))
        if faixa(p.get("nuur"), 0.1, 0.3):
            r.append(("ALERTA", "ν_ur = {:.2f} fora da faixa usual (0,15 a 0,25; padrão 0,2).".format(p["nuur"])))
        if p.get("pref") is not None and abs(p["pref"] - 100) > 1e-6:
            r.append(("INFO", "pref = {:.0f} kPa (padrão 100): os módulos de referência valem nessa tensão.".format(p["pref"])))
    if modelo == "HSsmall":
        g0, eur, nuur = p.get("G0ref"), p.get("Eurref"), p.get("nuur", 0.2)
        if g0 and eur:
            gur = eur / (2 * (1 + nuur))
            if g0 < gur:
                r.append(("ERRO", "G0ref = {:.0f} < Gur,ref = {:.0f} kPa: o HS small exige G0 ≥ Gur.".format(g0, gur)))
            elif g0 / gur > 10:
                r.append(("ALERTA", "G0ref/Gur,ref = {:.1f} (usual 2,5 a 10).".format(g0 / gur)))
        if faixa(p.get("gamma07"), 5e-5, 1e-3):
            r.append(("ALERTA", "γ0,7 = {:.2e} fora da faixa usual (5e-5 a 1e-3).".format(p["gamma07"])))
    if modelo == "MCC":
        lam, kap, M = p.get("lambda"), p.get("kappa"), p.get("M")
        if lam is not None and kap is not None:
            if lam <= kap:
                r.append(("ERRO", "λ = {} ≤ κ = {}: λ precisa ser maior que κ.".format(lam, kap)))
            elif not 0.05 <= kap / lam <= 0.5:
                r.append(("ALERTA", "κ/λ = {:.2f} (usual 0,1 a 0,3).".format(kap / lam)))
        if M is not None:
            if faixa(M, 0.8, 1.8):
                r.append(("ALERTA", "M = {:.2f} fora da faixa usual (0,8 a 1,8).".format(M)))
            s = 3 * M / (6 + M)
            if 0 < s < 1:
                r.append(("INFO", "M = {:.2f} equivale a φ'cs = {:.1f}° (compressão triaxial).".format(M, math.degrees(math.asin(s)))))
        if faixa(p.get("eInit"), 0.3, 3.0):
            r.append(("ALERTA", "e_init = {:.2f} fora da faixa usual (0,3 a 3).".format(p["eInit"])))
    if modelo == "SS":
        lam, kap = p.get("lambdaModified"), p.get("kappaModified")
        if lam is not None and kap is not None:
            if lam <= kap:
                r.append(("ERRO", "λ* = {} ≤ κ* = {}: λ* precisa ser maior que κ*.".format(lam, kap)))
            elif not 2.5 <= lam / kap <= 10:
                r.append(("ALERTA", "λ*/κ* = {:.1f} (usual 2,5 a 10; ≈ 5 é comum).".format(lam / kap)))
        if faixa(p.get("nuur"), 0.1, 0.25):
            r.append(("ALERTA", "ν_ur = {:.2f} fora da faixa usual (0,10 a 0,20; padrão 0,15).".format(p["nuur"])))
    return r


def ler_material(A, mat):
    ident = str(A["valor"](mat.Identification))
    sm = A["linha_echo"](mat, "SoilModel")
    dr = A["linha_echo"](mat, "DrainageType")
    num_mod = sm[1] if sm else None
    modelo = next((k for k, v in A["MODELOS"].items() if v["numero"] == num_mod), None)
    dren = next((k for k, v in A["DRENAGENS"].items() if dr and v["nomes"][1] == dr[1]), None)
    p = {}
    if modelo and dren:
        for chave, aliases, _r, _v in A["parametros"](modelo, dren):
            attr = A["achar_attr"](mat, aliases)
            if attr is None:
                continue
            try:
                p[chave] = float(A["valor"](getattr(mat, attr)))
            except Exception:
                pass
    return ident, (sm[0] if sm else "?"), modelo, dren, p


def main():
    A = carregar_auto()
    log = A["log"]
    gi = A["obter_input"](A["CONFIG"])
    if gi is None:
        return 1
    mats = []
    for lista in ("Soils", "Materials"):
        try:
            mats = [m for m in getattr(gi, lista)]
            if mats:
                break
        except Exception:
            continue
    log("Auditoria: {} material(is) no projeto".format(len(mats)))
    pasta = os.path.join(AQUI, "soiltest_saida", "auditoria_{}".format(datetime.datetime.now().strftime("%Y%m%d_%H%M%S")))
    os.makedirs(pasta, exist_ok=True)
    resumo_tab, secoes = [], []
    for mat in mats:
        try:
            ident, nome_mod, modelo, dren, p = ler_material(A, mat)
        except Exception as e:
            log("Material ignorado (nao li os dados): {}".format(e))
            continue
        if SO_ESTES and ident not in SO_ESTES:
            continue
        log("\n" + "=" * 60 + "\n{}: {} / {}\n".format(ident, nome_mod, dren) + "=" * 60)
        if modelo is None or dren is None:
            achados = [("INFO", "Modelo '{}' fora dos 6 modelos mapeados (MC, LE, HS, HS small, MCC, Soft Soil): não auditado.".format(nome_mod))]
        else:
            achados = regras(modelo, dren, p)
        for nivel, msg in achados:
            log("   {}: {}".format(nivel, msg))
        link = "-"
        if RODAR_SOILTEST and modelo and dren:
            g, porta = A["abrir_soiltest"](gi, mat, A["CONFIG"]["espera_soiltest_s"], A["CONFIG"]["porta_input"], modelo)
            if g is None:
                achados.append(("ERRO", "O SoilTest recusou o material (veja o log)."))
            else:
                cfg = copy.deepcopy(A["CONFIG"])
                for t in ("crs", "dss", "cdss", "triaxial_ciclico"):
                    cfg[t]["rodar"] = False
                comps = {"D": ["Drained"], "NP": ["Drained"], "UA": ["Drained", "Undrained"], "UB": ["Undrained"], "UC": ["Undrained"]}[dren]
                cfg["triaxial"].update({"rodar": True, "pressoes_kPa": PRESSOES, "comportamentos": comps})
                cfg["oedometer"]["rodar"] = modelo not in () and dren not in ("UB", "UC")
                ctx = {"modelo": modelo, "dren": dren, "consolidacao": {"tipo": "Isotropic"}, "k0": None,
                       "preadensamento": {"modo": "nenhum", "valor": 0}, "pc_usados": set(),
                       "pc_fases_kPa": float(cfg.get("sigma_p_padrao_fases_kPa") or 0)}
                sub = os.path.join(pasta, ident)
                os.makedirs(sub, exist_ok=True)
                res = {"modelo": modelo, "drenagem": dren, "parametros": p, "consolidacao": {"tipo": "Isotropic"},
                       "preadensamento": {"modo": "nenhum"}}
                todas = A["executar_ensaios"](g, cfg, modelo, dren, p, ctx, sub, res)
                A["fechar_soiltest"](g)
                gerados = A["graficos"](sub, "{} ({})".format(ident, nome_mod), todas)
                A["relatorio_auto"](sub, "{} ({})".format(ident, nome_mod), res, gerados)
                link = '<a href="{0}/relatorio.html">{0}/relatorio.html</a>'.format(A["_esc"](ident))
                for nome, chk in (res.get("triaxial") or {}).items():
                    esp = chk.get("esperado")
                    if esp and esp.get("kPa"):
                        d = 100.0 * (chk["q_max_kPa"] - esp["kPa"]) / esp["kPa"]
                        if "pode nao chegar" in esp["descricao"]:
                            achados.append(("INFO", "Triaxial {}: q_max {:.1f} kPa; o estado crítico ({:.1f} kPa) é um limite que o "
                                                    "ensaio pode não atingir até a deformação máxima.".format(nome, chk["q_max_kPa"], esp["kPa"])))
                        elif abs(d) > 5:
                            achados.append(("ALERTA", "Triaxial {}: q_max {:.1f} kPa difere {:.1f} % de {} ({:.1f} kPa).".format(
                                nome, chk["q_max_kPa"], d, esp["descricao"], esp["kPa"])))
                    if nome.startswith("CU"):
                        achados.append(("INFO", "Triaxial {}: q_max = {:.1f} kPa → su ≈ q_max/2 = {:.1f} kPa.".format(
                            nome, chk["q_max_kPa"], chk["q_max_kPa"] / 2)))
        n = {k: sum(1 for a in achados if a[0] == k) for k in ("ERRO", "ALERTA", "INFO")}
        sit = '<span class="erro">{} erro(s)</span>'.format(n["ERRO"]) if n["ERRO"] else (
            '<span class="alerta">{} alerta(s)</span>'.format(n["ALERTA"]) if n["ALERTA"] else '<span class="ok">sem alertas</span>')
        resumo_tab.append((ident, nome_mod, dren or "?", sit, n["INFO"], link))
        cls = {"ERRO": "erro", "ALERTA": "alerta", "INFO": "nota"}
        lista_html = "<ul>" + "".join('<li><span class="{}">{}</span>: {}</li>'.format(cls[nv], nv, A["_esc"](m)) for nv, m in achados) + "</ul>"
        rot = {c: r for c, _a, r, _v in A["parametros"](modelo, dren)} if modelo and dren else {}
        par_html = A["html_tabela"](["Parâmetro", "Valor"], [(rot.get(k, k), A["_num"](v, 4)) for k, v in p.items()]) if p else ""
        secoes.append(("{} ({} / {})".format(ident, nome_mod, dren or "?"), par_html + (lista_html if achados else '<p class="ok">Sem alertas.</p>')))
    sec = [("Resumo", A["html_tabela"](["Material", "Modelo", "Drenagem", "Situação", "Notas", "Ensaios no SoilTest"], resumo_tab)
            + '<p class="nota">ERRO: combinação que o PLAXIS não aceita ou sem sentido físico. ALERTA: fora da faixa usual de '
              'literatura; confira. INFO: observação. As faixas são referências, não regras.</p>')] + secoes
    rel = A["relatorio_html"](os.path.join(pasta, "relatorio.html"), "Auditoria de materiais", "{} material(is) auditado(s)".format(len(resumo_tab)), sec)
    log("\nRelatorio: {}\nSaida: {}".format(rel, pasta))
    with open(os.path.join(pasta, "log.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(A["_linhas"]))
    return 0


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(traceback.format_exc())

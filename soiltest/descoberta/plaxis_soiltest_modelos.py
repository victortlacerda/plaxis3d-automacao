# -*- coding: utf-8 -*-
"""
plaxis_soiltest_modelos.py  -  DESCOBERTA dos modelos constitutivos no PLAXIS 3D Input + SoilTest.

Para cada combinacao (modelo + drenagem) o script:
  0. mapeia os numeros de SoilModel do Input (0..16 -> nome do modelo)
  1. cria o material no Input, define modelo e drenagem (confere pelo echo) e aplica parametros de teste
  2. abre o SoilTest (g_i.soiltest devolve a porta), confere modelo, valida o material (mostra as mensagens)
  3. roda Triaxial drenado e nao drenado, testa se PreconsolidationPressure e editavel e roda um Oedometer
  4. escreve tudo em plaxis_modelos_relatorio.txt e um quadro-resumo no fim.

Combinacoes: MC_D, MC_UA, MC_UB, MC_UC, LE_D, LE_NP, HS, HSsmall, MCC.
Nomes de parametros que nao existirem sao listados (com todos os atributos do material) para ajustarmos depois.

COMO RODAR: PLAXIS 3D Input aberto com projeto e servidor ativo (porta 10000); rode pelo
Executar_script_PLAXIS.bat. Senha do SoilTest: variavel PLAXIS_PASSWORD ou digitada quando pedida.
Cada g_i.soiltest abre um SoilTest; feche as janelas depois (fechar_soiltest=True tenta fechar por comando).
Para rodar so algumas combinacoes edite "rodar".
"""
import os
import re
import sys
import json
import math
import time
import getpass
import datetime
import traceback

# =========================== CONFIG ===========================
CONFIG = {
    # "novos" = combinacoes ainda nao testadas (+ as que precisavam de ajuste); "todos" = as 21 (19 + 2 variantes com corte de dilatancia); ou uma lista de ids.
    "rodar": "novos",
    "porta_input": 10000,
    "espera_soiltest_s": 90,
    "fechar_soiltest": False,     # True: tenta g.close() ao terminar cada combinacao (comportamento ainda nao testado)
    "pressao_triaxial_kPa": 100,
    "def_max_triaxial_pct": 15,
    "passos_triaxial": 50,
}
NOVOS = ["SS_D", "SS_UA"]   # o resto passou na rodada 2; use "todos" para repetir tudo

# marcador (regex no nome do modelo, em minusculas), regex a excluir, nomes alternativos para tentar
MODELOS = {
    "MC":    {"marca": r"mohr", "excluir": None, "nomes": ["Mohr-Coulomb"]},
    "LE":    {"marca": r"linear", "excluir": None, "nomes": ["Linear Elastic", "Linear elastic"]},
    "HS":    {"marca": r"hardening", "excluir": r"small", "nomes": ["Hardening Soil"]},
    "HSs":   {"marca": r"small", "excluir": None, "nomes": ["HS small", "Hardening Soil with small-strain stiffness"]},
    "MCC":   {"marca": r"cam", "excluir": None, "nomes": ["Modified Cam-Clay", "Modified Cam Clay"]},
    "SS":    {"marca": r"soft soil", "excluir": r"creep", "nomes": ["Soft Soil"]},
}
# O echo mostra "Undrained A (1)", sem parenteses em volta da letra.
DRENAGENS = {
    "D":  {"marca": r"^drained", "nomes": ["Drained", 0]},
    "UA": {"marca": r"^undrained\s*\(?a\)?", "nomes": ["Undrained A", "Undrained (A)", 1]},
    "UB": {"marca": r"^undrained\s*\(?b\)?", "nomes": ["Undrained B", "Undrained (B)", 2]},
    "UC": {"marca": r"^undrained\s*\(?c\)?", "nomes": ["Undrained C", "Undrained (C)", 3]},
    "NP": {"marca": r"non.?porous", "nomes": ["Non-porous", "Non porous", 4]},
}
# Opcoes de "Drainage type" de cada modelo no Input (conferido nas telas do usuario)
DREN_POR_MODELO = {"MC": ["D", "UA", "UB", "UC", "NP"], "LE": ["D", "UA", "UC", "NP"], "HS": ["D", "UA", "UB"],
                   "HSs": ["D", "UA", "UB"], "MCC": ["D", "UA"], "SS": ["D", "UA"]}
NOME_ID = {"MC": "MC", "LE": "LE", "HS": "HS", "HSs": "HSsmall", "MCC": "MCC", "SS": "SS"}
IDENT_ANTIGO = {"HS_D": "T_HS", "HSsmall_D": "T_HSsmall", "MCC_D": "T_MCC"}   # materiais ja criados na rodada 1

# parametro canonico -> (aliases de atributo em minusculas, valor de teste[, True = opcional])
# nu/nuU, psi, cRef, phi mudam de nome ou deixam de existir conforme a drenagem (visto nos atributos reais).


def _hs_base():
    return {"E50ref": (["e50ref"], 40000), "Eoedref": (["eoedref"], 40000), "Eurref": (["eurref"], 120000),
            "m": (["powerm"], 0.5), "nuur": (["nuur"], 0.2), "pref": (["pref"], 100)}


def parametros(modelo, dren):
    su = {"sURef": (["suref"], 50)}
    if modelo == "MC":
        if dren == "UB":
            return dict({"ERef": (["eref"], 30000), "nu": (["nu"], 0.3)}, **su)
        if dren == "UC":
            return dict({"ERef": (["eref"], 30000), "nuU": (["nuu"], 0.495)}, **su)
        return {"ERef": (["eref"], 30000), "nu": (["nu"], 0.3), "cRef": (["cref"], 5), "phi": (["phi"], 30),
                "psi": (["psi"], 0)}
    if modelo == "LE":
        if dren == "UC":
            return {"ERef": (["eref"], 30000), "nuU": (["nuu"], 0.495)}
        return {"ERef": (["eref"], 30000), "nu": (["nu"], 0.3)}
    if modelo in ("HS", "HSs"):
        p = _hs_base()
        if dren == "UB":
            p.update(su)
        else:
            p.update({"cref": (["cref"], 1), "phi": (["phi"], 35), "psi": (["psi"], 5)})
        if modelo == "HSs":
            p.update({"G0ref": (["g0ref"], 120000), "gamma07": (["gamma07", "gamma0_7", "gamma_07"], 2e-4)})
        return p
    if modelo == "MCC":
        # O SoilTest recusa o material se PhiInter e CInter forem ambos zero (erro visto na rodada 1).
        return {"lambda": (["lambda", "lambdastar"], 0.1), "kappa": (["kappa", "kappastar"], 0.02),
                "M": (["m"], 1.2), "nuur": (["nuur"], 0.2), "eInit": (["einit"], 1.0),
                "PhiInter": (["phiinter"], 25)}
    if modelo == "SS":
        # Soft Soil usa lambda* e kappa* (atributos lambdaModified/kappaModified, com lambda* > kappa* > 0);
        # no MCC os atributos sao lambda e kappa.
        return {"lambdaModified": (["lambdamodified"], 0.1), "kappaModified": (["kappamodified"], 0.02),
                "cRef": (["cref"], 1), "phi": (["phi"], 25), "psi": (["psi"], 0), "nuur": (["nuur"], 0.15),
                "PhiInter": (["phiinter"], 25, True)}
    return {}


COMBOS = {}
for _m, _lista in DREN_POR_MODELO.items():
    for _d in _lista:
        _id = "{}_{}".format(NOME_ID[_m], _d)
        COMBOS[_id] = {"modelo": _m, "dren": _d, "params": parametros(_m, _d), "ident": IDENT_ANTIGO.get(_id, "T_" + _id)}

# Variantes com Dilatancy cut-off ligado (eInit 0,5 e eMax 0,52: o corte atua com cerca de 1,3 % de dilatacao).
# Como o Behaviour do SoilTest independe do DrainageType, cada combinacao roda drenado e nao drenado.
CORTE = {"DilatancyCutOff": (["dilatancycutoff"], True), "eInit": (["einit"], 0.5), "eMax": (["emax"], 0.52)}
for _n, _b in (("HS_corte", "HS_D"), ("HSsmall_corte", "HSsmall_D")):
    COMBOS[_n] = dict(COMBOS[_b], params=dict(COMBOS[_b]["params"], **CORTE), ident="T_" + _n, corte=True)
# Resultados da rodada 1 (sem corte), para comparar: q_max drenado, dilatacao max (eps_v), q_max nao drenado, PExcess max
REF_SEM_CORTE = {"HS_corte": "sem corte (rodada 1): drenado q_max 272,88 kPa, eps_v max +0,02199; nao drenado q_max 1901,73 kPa, PExcess max +605,5",
                 "HSsmall_corte": "sem corte (rodada 1): drenado q_max 272,88 kPa, eps_v max +0,02181; nao drenado q_max 1885,91 kPa, PExcess max +599,6"}
# ==============================================================

AQUI = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
RELATORIO = os.path.join(AQUI, "plaxis_modelos_relatorio.txt")
RESUMO_JSON = os.path.join(AQUI, "plaxis_modelos_resumo.json")


def log(msg=""):
    msg = str(msg)
    print(msg)
    try:
        with open(RELATORIO, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass


def tentar(rotulo, fn, limite=1800):
    try:
        v = fn()
        r = repr(v)
        log("[OK ] {} -> {}".format(rotulo, r if len(r) <= limite else r[:limite] + "...<cortado>"))
        return True, v
    except Exception as e:
        log("[ERR] {} -> {}: {}".format(rotulo, type(e).__name__, str(e).replace("\n", " | ")))
        return False, None


def valor(x):
    try:
        return x.value
    except Exception:
        return x


def nomes(obj):
    try:
        return sorted(n for n in dir(obj) if not n.startswith("_"))
    except Exception:
        return []


def achar_attr(obj, aliases):
    mapa = {n.lower(): n for n in nomes(obj)}
    for a in aliases:
        if a.lower() in mapa:
            return mapa[a.lower()]
    return None


def pedir_senha(texto):
    s = os.environ.get("PLAXIS_PASSWORD")
    if s:
        return s
    try:
        return getpass.getpass(texto)
    except Exception:
        return input(texto)


def linha_echo(mat, chave):
    """Devolve (nome, numero) de uma linha 'Chave: Nome (n)' do echo do material."""
    try:
        txt = str(mat.echo())
    except Exception:
        return None
    m = re.search(r"\b{}:\s*(.+?)\s*\((-?\d+)\)".format(re.escape(chave)), txt)
    return (m.group(1).strip(), int(m.group(2))) if m else None


def estat(r, campo):
    if not hasattr(r, campo):
        return "nao exposto"
    try:
        v = [float(i) for i in getattr(r, campo)]
    except Exception as e:
        return "erro: {}".format(e)
    if not v:
        return "vazio"
    return "n={} ini={:.6g} fim={:.6g} min={:.6g} max={:.6g}".format(len(v), v[0], v[-1], min(v), max(v))


# ------------------------------------------------------------------ passo 0: mapa dos SoilModel
def mapear_modelos(gi):
    log("\n=== Passo 0: mapa SoilModel (numero -> nome) ===")
    ok, mat = tentar("g_i.soilmat() [material de varredura]", lambda: gi.soilmat())
    mapa = {}
    if not ok:
        return mapa
    for n in range(0, 17):
        try:
            mat.setproperties("SoilModel", n)
        except Exception as e:
            log("  {:>2} -> recusado ({})".format(n, str(e).splitlines()[0][:80] if str(e) else type(e).__name__))
            continue
        r = linha_echo(mat, "SoilModel")
        if r:
            mapa[n] = r[0]
            log("  {:>2} -> {}".format(n, r[0]))
        else:
            log("  {:>2} -> aceito, mas o echo nao mostrou o nome".format(n))
    tentar("apagar material de varredura", lambda: gi.delete(mat))
    return mapa


def numeros_do_modelo(mapa, chave):
    m = MODELOS[chave]
    achados = []
    for n, nome in mapa.items():
        t = nome.lower()
        if re.search(m["marca"], t) and not (m["excluir"] and re.search(m["excluir"], t)):
            achados.append(n)
    return achados + m["nomes"]


# ------------------------------------------------------------------ passo 1: material no Input
def procurar_existente(gi, ident):
    for lista in ("Soils", "Materials"):
        try:
            for m in getattr(gi, lista):
                if str(valor(m.Identification)) == ident:
                    return m
        except Exception:
            continue
    return None


def definir_com_candidatos(mat, atributo, candidatos, marca, exclui=None):
    for c in candidatos:
        try:
            mat.setproperties(atributo, c)
        except Exception as e:
            log("    {}={!r} recusado ({})".format(atributo, c, str(e).splitlines()[0][:80]))
            continue
        r = linha_echo(mat, atributo)
        txt = (r[0] if r else "").lower()
        if r and re.search(marca, txt) and not (exclui and re.search(exclui, txt)):
            log("[OK ] {} = {!r} -> {} ({})".format(atributo, c, r[0], r[1]))
            return True, r
        log("    {}={!r} aceito, mas o echo mostra {}".format(atributo, c, r))
    return False, None


def criar_material(gi, cid, combo, mapa, res):
    ident = combo.get("ident", "T_" + cid)
    mat = procurar_existente(gi, ident)
    if mat is None:
        ok, mat = tentar("g_i.soilmat()", lambda: gi.soilmat())
        if not ok:
            res["input"] = "ERRO: soilmat"
            return None
        tentar("Identification = " + ident, lambda: mat.setproperties("Identification", ident))
    else:
        log("Material {} ja existe: reutilizando.".format(ident))
    mod = MODELOS[combo["modelo"]]
    ok, r = definir_com_candidatos(mat, "SoilModel", numeros_do_modelo(mapa, combo["modelo"]), mod["marca"], mod["excluir"])
    res["modelo_input"] = "{} ({})".format(r[0], r[1]) if ok else "NAO DEFINIDO"
    if not ok:
        log("Nao consegui definir o modelo; pulando esta combinacao.")
        res["input"] = "ERRO: modelo"
        return None
    dr = DRENAGENS[combo["dren"]]
    ok, r = definir_com_candidatos(mat, "DrainageType", dr["nomes"], dr["marca"])
    res["drenagem_input"] = "{} ({})".format(r[0], r[1]) if ok else "NAO DEFINIDA"
    log("Atributos do material: {}".format(", ".join(nomes(mat))))
    faltando, falhas = [], []
    for canon, spec in combo["params"].items():
        aliases, v = spec[0], spec[1]
        opcional = len(spec) > 2 and spec[2]
        attr = achar_attr(mat, aliases)
        if attr is None:
            if opcional:
                log("[--] parametro opcional {} nao existe neste modelo (ok).".format(canon))
            else:
                faltando.append(canon)
                log("[ERR] parametro {} nao existe (aliases {})".format(canon, aliases))
            continue
        ok, _ = tentar("{} ({}) = {}".format(canon, attr, v), lambda a=attr, v=v: mat.setproperties(a, v))
        if not ok:
            falhas.append(canon)
    tentar("echo do material", lambda: mat.echo(), 7000)
    res["params_inexistentes"] = faltando
    res["params_recusados"] = falhas
    res["input"] = "OK" if not faltando and not falhas and res["drenagem_input"] != "NAO DEFINIDA" else "PARCIAL"
    return mat


# ------------------------------------------------------------------ passo 2: SoilTest
def conectar_soiltest(porta, senha, espera):
    from plxscripting.easy import new_server
    limite = time.time() + espera
    ultimo = None
    while time.time() < limite:
        try:
            s, g = new_server("localhost", int(porta), password=senha)
            if hasattr(g, "Triaxial"):
                return g
            ultimo = "a porta nao e o SoilTest"
        except Exception as e:
            ultimo = str(e)
        time.sleep(2)
    raise RuntimeError("sem conexao ao SoilTest na porta {}: {}".format(porta, ultimo))


def valor_param(cid, canon):
    spec = COMBOS[cid]["params"].get(canon)
    return None if spec is None else float(spec[1])


def esperado(cid, comportamento, p3):
    """Valor teorico de q no fim do ensaio (informativo). None quando nao ha formula simples."""
    try:
        modelo = COMBOS[cid]["modelo"]
        su = valor_param(cid, "sURef")
        if su is not None:
            return ("2 x su", 2 * su)
        if comportamento != "Drained":
            return None
        if modelo in ("MC", "HS", "HSs", "SS"):
            phi = math.radians(valor_param(cid, "phi"))
            c = valor_param(cid, "cRef") if valor_param(cid, "cRef") is not None else valor_param(cid, "cref")
            s = math.sin(phi)
            return ("q_f Mohr-Coulomb", 2 * s / (1 - s) * (p3 + c / math.tan(phi)))
        if modelo == "LE":
            return ("E x eps_a (linear)", valor_param(cid, "ERef") * CONFIG["def_max_triaxial_pct"] / 100.0)
        if modelo == "MCC":
            M = valor_param(cid, "M")
            return ("q no estado critico (3 M s3/(3-M))", 3 * M * p3 / (3 - M))
    except Exception:
        return None
    return None


def testar_soiltest(g, cid, res):
    ok, sm = tentar("Material.SoilModel no SoilTest", lambda: valor(g.Material.SoilModel))
    res["modelo_soiltest"] = sm if ok else "ERRO"
    if ok and not str(res.get("modelo_input", "")).endswith("({})".format(sm)):
        log("ATENCAO: o SoilTest abriu o modelo {} mas o Input definiu {}.".format(sm, res.get("modelo_input")))
    tentar("Material.echo()", lambda: g.Material.echo(), 7000)
    log("Atributos do Material no SoilTest: {}".format(", ".join(nomes(g.Material))))
    if COMBOS[cid].get("corte"):
        log("Referencia: {}".format(REF_SEM_CORTE.get(cid, "-")))
        achados = {}
        for canon, spec in CORTE.items():
            a = achar_attr(g.Material, spec[0])
            if a is None:
                achados[canon] = "nao existe no Material do SoilTest"
                log("[--] {} nao existe no Material do SoilTest.".format(canon))
                continue
            ok_a, _ = tentar("SoilTest Material.{} = {}".format(a, spec[1]), lambda a=a, v=spec[1]: g.Material.setproperties(a, v))
            achados[canon] = "editavel" if ok_a else "somente leitura/recusado"
        res["corte_no_soiltest"] = achados
        tentar("Material.echo() depois do corte", lambda: g.Material.echo(), 7000)
    okv, txt = tentar("validate (all)", lambda: g.validate(g.Material, "all"))
    if not okv:
        okv, txt = tentar("validate", lambda: g.validate(g.Material))
    res["validate"] = str(txt).replace("\n", " | ")[:300] if okv else "ERRO"

    t = g.Triaxial
    p3 = CONFIG["pressao_triaxial_kPa"]
    for comp in ("Drained", "Undrained"):
        log("\n-- Triaxial {} ({} kPa, {} %, {} passos) --".format(comp, p3, CONFIG["def_max_triaxial_pct"], CONFIG["passos_triaxial"]))
        ok, _ = tentar("setproperties", lambda c=comp: t.setproperties(
            "Behaviour", c, "Consolidation", "Isotropic", "Direction", "Compression", "CellPressure", p3,
            "MaximumStrain", CONFIG["def_max_triaxial_pct"], "Steps", CONFIG["passos_triaxial"]))
        if not ok:
            res["triaxial_" + comp] = "ERRO: setproperties"
            continue
        ok, _ = tentar("calculate", lambda: g.calculate(t))
        if not ok:
            res["triaxial_" + comp] = "ERRO: calculate"
            continue
        for c in ("Epsyy", "TotalVolumetricStrain", "DeviatoricStress", "MeanEffStress", "PExcess", "SigyyE", "SigxxE"):
            log("   Results.{:<22} {}".format(c, estat(t.Results, c)))
        try:
            q = [float(v) for v in t.Results.DeviatoricStress]
            res["triaxial_" + comp] = "OK q_max={:.2f} kPa".format(max(q))
            try:
                ev = [float(v) for v in t.Results.TotalVolumetricStrain]
                pe = [float(v) for v in t.Results.PExcess]
                res["triaxial_" + comp] += " | eps_v max {:+.5f} | PExcess min {:.1f} max {:.1f}".format(max(ev), min(pe), max(pe))
            except Exception:
                pass
            ex = esperado(cid, comp, p3)
            if ex:
                log("   Esperado ({}): {:.2f} kPa; simulado q_max {:.2f} kPa".format(ex[0], ex[1], max(q)))
        except Exception as e:
            res["triaxial_" + comp] = "OK (sem leitura de q: {})".format(e)

    okp, _ = tentar("Triaxial.PreconsolidationPressure = 150 [teste de escrita]",
                    lambda: t.setproperties("PreconsolidationPressure", 150))
    res["preconsolidacao_editavel"] = bool(okp)
    if okp:
        tentar("restaurar PreconsolidationPressure = 0", lambda: t.setproperties("PreconsolidationPressure", 0))
    tentar("restaurar Triaxial", lambda: t.setproperties(
        "Behaviour", "Drained", "Consolidation", "Isotropic", "Direction", "Compression",
        "CellPressure", 100, "MaximumStrain", 10, "Steps", 100))

    log("\n-- Oedometer (1 fase: Siginc -100 kPa, 20 passos) --")
    o = g.Oedometer
    ok, _ = tentar("PhaseTable[0].setproperties", lambda: o.PhaseTable[0].setproperties("Duration", 1, "Siginc", -100, "Steps", 20))
    if ok:
        ok, _ = tentar("calculate Oedometer", lambda: g.calculate(o))
    if ok:
        for c in ("Time", "Epsyy", "SigyyE", "SigxxE", "PExcess"):
            log("   Results.{:<22} {}".format(c, estat(o.Results, c)))
        try:
            ey = [float(v) for v in o.Results.Epsyy]
            res["oedometer"] = "OK eps_final={:.6g}".format(ey[-1])
        except Exception as e:
            res["oedometer"] = "OK (sem leitura: {})".format(e)
    else:
        res["oedometer"] = "ERRO"
    tentar("restaurar Oedometer", lambda: o.PhaseTable[0].setproperties("Duration", 1, "Siginc", 0, "Steps", 100))


# ------------------------------------------------------------------ principal
def lista_rodar():
    r = CONFIG["rodar"]
    if r == "todos":
        return list(COMBOS)
    if r == "novos":
        return list(NOVOS)
    return list(r)


def main():
    open(RELATORIO, "w", encoding="utf-8").close()
    log("Descoberta de modelos - PLAXIS 3D Input + SoilTest ({})".format(datetime.datetime.now().isoformat(timespec="seconds")))
    if "g_i" in globals() and "s_i" in globals():
        gi = globals()["g_i"]
    else:
        from plxscripting.easy import new_server
        gi = new_server("localhost", CONFIG["porta_input"], password=pedir_senha("Senha do servidor Input: "))[1]
    if hasattr(gi, "Triaxial"):
        log("Conectado ao SoilTest em vez do Input. Use o servidor do PLAXIS 3D Input (porta {}).".format(CONFIG["porta_input"]))
        return 1

    mapa = mapear_modelos(gi)
    senha = pedir_senha("Senha do servidor do SoilTest: ")
    resumo = {"mapa_modelos": mapa}
    portas = []
    for cid in lista_rodar():
        if cid not in COMBOS:
            log("\nCombinacao desconhecida: {}".format(cid))
            continue
        res = resumo.setdefault(cid, {})
        log("\n" + "=" * 70 + "\n== {} ==\n".format(cid) + "=" * 70)
        try:
            mat = criar_material(gi, cid, COMBOS[cid], mapa, res)
            if mat is None:
                continue
            ok, porta = tentar("g_i.soiltest(material)", lambda: gi.soiltest(mat))
            if not ok:
                res["soiltest"] = "ERRO: soiltest"
                continue
            porta = int(valor(porta))
            res["porta_soiltest"] = porta
            log("SoilTest na porta {} ({}).".format(porta, "porta repetida" if porta in portas else "porta nova"))
            portas.append(porta)
            g = conectar_soiltest(porta, senha, CONFIG["espera_soiltest_s"])
            testar_soiltest(g, cid, res)
            if CONFIG["fechar_soiltest"]:
                tentar("g.close()", lambda: g.close())
        except Exception:
            log("ERRO nesta combinacao:\n" + traceback.format_exc())
            res["erro"] = traceback.format_exc().splitlines()[-1]

    log("\n" + "=" * 70 + "\n== QUADRO-RESUMO ==\n" + "=" * 70)
    for cid in lista_rodar():
        r = resumo.get(cid)
        if not r:
            continue
        log("{:<8} input={:<8} modelo='{}' dren='{}' | SoilTest modelo={} porta={}".format(
            cid, r.get("input", "-"), r.get("modelo_input", "-"), r.get("drenagem_input", "-"),
            r.get("modelo_soiltest", "-"), r.get("porta_soiltest", "-")))
        log("         validate: {}".format(r.get("validate", "-")))
        log("         triaxial D: {} | U: {} | preconsolidacao editavel: {} | oedometer: {}".format(
            r.get("triaxial_Drained", "-"), r.get("triaxial_Undrained", "-"),
            r.get("preconsolidacao_editavel", "-"), r.get("oedometer", "-")))
        if r.get("corte_no_soiltest"):
            log("         corte de dilatancia no Material do SoilTest: {}".format(r["corte_no_soiltest"]))
        if r.get("params_inexistentes") or r.get("params_recusados"):
            log("         parametros inexistentes: {} | recusados: {}".format(
                r.get("params_inexistentes"), r.get("params_recusados")))
        if r.get("erro"):
            log("         erro: {}".format(r["erro"]))
    with open(RESUMO_JSON, "w", encoding="utf-8") as f:
        json.dump(resumo, f, indent=2, ensure_ascii=False, default=str)
    log("\nRelatorio: {}".format(RELATORIO))
    return 0


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        log("ERRO:\n" + traceback.format_exc())
        rc = 1
    if "g_i" not in globals():
        input("\nPressione Enter para fechar...")
        sys.exit(rc)

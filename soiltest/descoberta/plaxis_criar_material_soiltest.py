# -*- coding: utf-8 -*-
"""
plaxis_criar_material_soiltest.py
Cria (no PLAXIS 3D Input) um material Hardening Soil ou HS small com parametros de TESTE e abre o SoilTest
com esse material. Depois procura o servidor de scripting do SoilTest recem-aberto, confirma o modelo e roda
um triaxial rapido de verificacao.

COMO RODAR
  1. Abra o PLAXIS 3D Input com um projeto aberto e o servidor de scripting ativo (porta 10000).
     (Este script cria materiais no projeto aberto e NAO apaga nada; veja "novo_projeto" abaixo.)
  2. Rode pelo Executar_script_PLAXIS.bat (que conecta no Input e injeta s_i/g_i).
  3. Edite so o bloco CONFIG (modelo a abrir, parametros).
O relatorio e gravado ao lado do script: criar_material_soiltest_relatorio.txt

OBSERVACOES
  - Os valores em CONFIG sao de teste. Depois eles virao do usuario (entrada de dados).
  - Os nomes de parametros do Input sao procurados por nome (sem diferenciar maiusculas/minusculas) entre
    os atributos reais do material; o relatorio lista todos os atributos para ajustarmos.
  - Senha: variavel de ambiente PLAXIS_PASSWORD (ou sera pedida) - usada so para procurar o SoilTest.
"""
import os
import sys
import time
import getpass
import traceback
import datetime

# =========================== CONFIG (edite aqui) ===========================
CONFIG = {
    "modelo_abrir": "HS",          # "HS" ou "HSsmall": material que sera aberto no SoilTest
    "novo_projeto": False,         # True chama s_i.new() e APAGA o projeto aberto no Input. Mantenha False.
    "abrir_soiltest": True,
    "porta_input": 10000,
    "portas_soiltest": list(range(10000, 10031)),   # portas testadas (a porta do Input e ignorada se nao tiver Triaxial)
    "espera_max_s": 90,
    "materiais": {
        "HS": {
            "Identification": "HS_teste",
            "SoilModel": 3,
            "DrainageType": "Drained",
            "params": {"E50ref": 40000, "Eoedref": 40000, "Eurref": 120000, "m": 0.5, "cref": 1,
                       "phi": 35, "psi": 5, "nuur": 0.2, "pref": 100, "K0nc": None, "Rf": 0.9},
        },
        "HSsmall": {
            "Identification": "HSsmall_teste",
            "SoilModel": 4,
            "DrainageType": "Drained",
            "params": {"E50ref": 40000, "Eoedref": 40000, "Eurref": 120000, "m": 0.5, "cref": 1,
                       "phi": 35, "psi": 5, "nuur": 0.2, "pref": 100, "K0nc": None, "Rf": 0.9,
                       "G0ref": 120000, "gamma07": 2e-4},
        },
    },
}
# ===========================================================================

# Nome canonico -> nomes possiveis no Input (comparados em minusculas)
ALIASES = {
    "E50ref": ["e50ref"], "Eoedref": ["eoedref"], "Eurref": ["eurref"],
    "m": ["powerm", "m"], "cref": ["cref"], "phi": ["phi"], "psi": ["psi"],
    "nuur": ["nuur", "nu_ur", "nuun"], "pref": ["pref"], "K0nc": ["k0nc"], "Rf": ["rf"],
    "G0ref": ["g0ref"], "gamma07": ["gamma07", "gamma0_7", "gamma_07", "gamma0.7"],
}
MARCADORES = {"HS": "hardening", "HSsmall": "small"}

AQUI = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
RELATORIO = os.path.join(AQUI, "criar_material_soiltest_relatorio.txt")
_linhas = []


def pedir_senha(texto):
    senha = os.environ.get("PLAXIS_PASSWORD")
    if senha:
        return senha
    try:
        return getpass.getpass(texto)
    except Exception:
        return input(texto)


def log(msg=""):
    msg = str(msg)
    print(msg)
    _linhas.append(msg)
    try:
        with open(RELATORIO, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass


def tentar(rotulo, fn, limite=2500):
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


def achar_attr(obj, candidatos):
    mapa = {n.lower(): n for n in nomes(obj)}
    for c in candidatos:
        if c.lower() in mapa:
            return mapa[c.lower()]
    return None


def procurar_existente(g, ident):
    for lista in ("Soils", "Materials"):
        try:
            for m in getattr(g, lista):
                if str(valor(m.Identification)) == ident:
                    return m
        except Exception:
            continue
    return None


def criar_material(g, cfg):
    ident = cfg["Identification"]
    mat = procurar_existente(g, ident)
    if mat is not None:
        log("Material '{}' ja existe no projeto: reutilizando e atualizando.".format(ident))
    else:
        ok, mat = tentar("g_i.soilmat()", lambda: g.soilmat())
        if not ok:
            log("Nao consegui criar o material. Confirme que ha um projeto aberto no Input "
                "(ou use \"novo_projeto\": True, que apaga o projeto atual).")
            return None
        tentar("Identification = {!r}".format(ident), lambda: mat.setproperties("Identification", ident))
    tentar("SoilModel = {}".format(cfg["SoilModel"]), lambda: mat.setproperties("SoilModel", cfg["SoilModel"]))
    if cfg.get("DrainageType"):
        tentar("DrainageType = {}".format(cfg["DrainageType"]),
               lambda: mat.setproperties("DrainageType", cfg["DrainageType"]))
    log("Atributos do material apos definir o modelo: {}".format(", ".join(nomes(mat))[:3000]))
    falhas = []
    for canon, v in cfg["params"].items():
        if v is None:
            continue
        attr = achar_attr(mat, ALIASES.get(canon, [canon]))
        if attr is None:
            log("[ERR] parametro {} nao encontrado entre os atributos (aliases {})".format(canon, ALIASES.get(canon)))
            falhas.append(canon)
            continue
        ok, _ = tentar("{} ({}) = {}".format(canon, attr, v), lambda a=attr, v=v: mat.setproperties(a, v))
        if not ok:
            falhas.append(canon)
    tentar("Material.echo()", lambda: mat.echo(), 6000)
    if falhas:
        log("ATENCAO: parametros nao aplicados: {}".format(falhas))
    return mat


def conectar_input():
    if "g_i" in globals() and "s_i" in globals():
        return globals()["s_i"], globals()["g_i"]
    from plxscripting.easy import new_server
    senha = pedir_senha("Senha do servidor Input: ")
    return new_server("localhost", CONFIG["porta_input"], password=senha)


def procurar_soiltest(senha):
    from plxscripting.easy import new_server
    limite = time.time() + CONFIG["espera_max_s"]
    tentativa = 0
    avisadas = set()
    while time.time() < limite:
        tentativa += 1
        for porta in CONFIG["portas_soiltest"]:
            try:
                s, g = new_server("localhost", porta, password=senha)
            except Exception:
                continue
            if hasattr(g, "Triaxial"):
                return porta, g
            if porta not in avisadas:
                avisadas.add(porta)
                log("  porta {} responde, mas nao e o SoilTest (sem 'Triaxial').".format(porta))
        log("  aguardando o SoilTest... (tentativa {})".format(tentativa))
        time.sleep(3)
    return None, None


def verificar_soiltest(g, modelo):
    ok, sm = tentar("SoilModel.value", lambda: valor(g.Material.SoilModel))
    ok2, eco = tentar("Material.echo()", lambda: g.Material.echo(), 6000)
    if ok2 and MARCADORES[modelo] not in str(eco).lower():
        log("ATENCAO: o echo do material nao menciona '{}'; confira se o modelo esta correto.".format(MARCADORES[modelo]))
    tentar("validate", lambda: g.validate(g.Material))
    t = g.Triaxial
    tentar("Triaxial.setproperties(drenado, 100 kPa, 15 %, 50 passos)", lambda: t.setproperties(
        "Behaviour", "Drained", "Consolidation", "Isotropic", "Direction", "Compression",
        "CellPressure", 100, "MaximumStrain", 15, "Steps", 50))
    ok3, _ = tentar("calculate Triaxial", lambda: g.calculate(t))
    if ok3:
        for campo in ("Epsyy", "DeviatoricStress", "TotalVolumetricStrain"):
            try:
                v = [float(i) for i in getattr(t.Results, campo)]
                log("   Results.{:<22} n={} ini={:.6g} fim={:.6g} min={:.6g} max={:.6g}".format(
                    campo, len(v), v[0], v[-1], min(v), max(v)))
            except Exception as e:
                log("   Results.{} -> erro {}".format(campo, e))


def main():
    open(RELATORIO, "w", encoding="utf-8").close()
    log("Criar material e abrir SoilTest  ({})".format(datetime.datetime.now().isoformat(timespec="seconds")))
    modelo = CONFIG["modelo_abrir"]
    if modelo not in CONFIG["materiais"]:
        raise ValueError("modelo_abrir deve ser um de {}".format(list(CONFIG["materiais"])))
    s, g = conectar_input()
    if hasattr(g, "Triaxial"):
        log("O servidor conectado e o SoilTest (tem 'Triaxial'), nao o Input. Feche o SoilTest, abra o PLAXIS 3D Input "
            "com o servidor na porta {} e rode de novo.".format(CONFIG["porta_input"]))
        return 1
    if CONFIG["novo_projeto"]:
        tentar("s_i.new()  (APAGA o projeto aberto)", lambda: s.new())

    mat = criar_material(g, CONFIG["materiais"][modelo])
    if mat is None:
        return 1
    if not CONFIG["abrir_soiltest"]:
        log("abrir_soiltest = False: material criado, SoilTest nao aberto.")
        return 0

    log("\n== Abrindo o SoilTest com o material {} ==".format(CONFIG["materiais"][modelo]["Identification"]))
    ok = False
    for rotulo, fn in (("g_i.soiltest(mat)", lambda: g.soiltest(mat)),
                       ("g_i.st(mat)", lambda: g.st(mat))):
        ok, _ = tentar(rotulo, fn)
        if ok:
            break
    if not ok:
        log("Nao consegui disparar o comando soiltest por script. Abra o SoilTest pelo botao do material no Input "
            "e rode soiltest_material.py.")
        return 1

    senha = pedir_senha("Senha do servidor do SoilTest (a mesma do Input?): ")
    log("Procurando o servidor do SoilTest nas portas {}-{} (ate {} s)...".format(
        CONFIG["portas_soiltest"][0], CONFIG["portas_soiltest"][-1], CONFIG["espera_max_s"]))
    porta, gst = procurar_soiltest(senha)
    if gst is None:
        log("SoilTest nao encontrado nas portas testadas. Abra o servidor de scripting do SoilTest (anote a porta) "
            "e rode soiltest_material.py.")
        return 1
    log("SoilTest encontrado na porta {}.".format(porta))
    verificar_soiltest(gst, modelo)
    log("\nPara os outros scripts (soiltest_triaxial.py etc.), conecte o executor na porta {} do SoilTest.".format(porta))
    return 0


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        log("ERRO:\n" + traceback.format_exc())
        rc = 1
    log("\nRelatorio: {}".format(RELATORIO))
    if "g_i" not in globals():
        input("\nPressione Enter para fechar...")
        sys.exit(rc)

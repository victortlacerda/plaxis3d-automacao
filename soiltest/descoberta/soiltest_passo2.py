# -*- coding: utf-8 -*-
"""
soiltest_passo2.py - Passo 2 da descoberta do SoilTest.
Objetivos:
  (a) ver o objeto Material e a lista Tests;
  (b) rodar um Triaxial curto (calculate) e descobrir COMO ler Results.<campo>;
  (c) restaurar os valores originais do Triaxial ao final.

Rode pelo Executar_script_PLAXIS.bat com o SoilTest aberto (porta 10000), como no passo 1.
ATENCAO: altera temporariamente o Triaxial da sessao aberta (restaura no fim) e NAO salva arquivos
do SoilTest. O relatorio e gravado ao lado do script: soiltest_passo2_relatorio.txt
"""
import os
import sys
import getpass
import traceback
import datetime

from plxscripting.easy import new_server

HOST = "localhost"
PORT = 10000
for _a in sys.argv[1:]:
    if _a.isdigit():
        PORT = int(_a)

AQUI = os.path.dirname(os.path.abspath(__file__))
RELATORIO = os.path.join(AQUI, "soiltest_passo2_relatorio.txt")
_linhas = []

CAMPOS = ["Time", "Epsyy", "Epsxx", "SigyyE", "SigxxE", "PExcess", "PActive",
          "TotalVolumetricStrain", "DeviatoricStress", "MeanEffStress",
          "SigmaEffective1", "SigmaEffective3", "Eps1", "Eps3", "DeviatoricStrain"]
PROPS_TRIAXIAL = ["Behaviour", "Direction", "Consolidation", "K0", "CellPressure",
                   "MaximumStrain", "Steps", "PreconsolidationPressure"]


def log(msg=""):
    msg = str(msg)
    print(msg)
    _linhas.append(msg)


def tentar(rotulo, fn, limite=1200):
    try:
        v = fn()
        r = repr(v)
        log("[OK ] {} -> {}".format(rotulo, r if len(r) <= limite else r[:limite] + "...<cortado>"))
        return True, v
    except Exception as e:
        log("[ERR] {} -> {}: {}".format(rotulo, type(e).__name__, e))
        return False, None


def nomes_publicos(obj):
    try:
        return sorted(n for n in dir(obj) if not n.startswith("_"))
    except Exception as e:
        return ["<dir falhou: {}>".format(e)]


def valor(x):
    """Devolve x.value se existir (Number/Integer/enum), senao x."""
    try:
        return x.value
    except Exception:
        return x


def ler_numeros(obj):
    """Tenta converter um campo de Results em lista de floats. Devolve (metodo, lista) ou (None, None)."""
    tentativas = (
        ("list(obj)", lambda: list(obj)),
        ("obj[:]", lambda: obj[:]),
        ("obj.value", lambda: obj.value),
        ("obj.get_values()", lambda: obj.get_values()),
        ("obj.values", lambda: obj.values),
    )
    for rotulo, f in tentativas:
        try:
            v = f()
            if isinstance(v, (list, tuple)) and len(v) > 0:
                return rotulo, [float(i) for i in v]
        except Exception:
            continue
    return None, None


def sondar_campo(r, campo):
    if not hasattr(r, campo):
        log("   Results.{:<22} nao exposto".format(campo))
        return None
    obj = getattr(r, campo)
    log("   Results.{} : type={}".format(campo, type(obj).__name__))
    log("      atributos: {}".format(", ".join(nomes_publicos(obj))[:600]))
    tentar("      str(obj)", lambda: str(obj), 300)
    tentar("      len(obj)", lambda: len(obj))
    tentar("      obj[0]", lambda: obj[0])
    tentar("      obj[-1]", lambda: obj[-1])
    tentar("      obj.value", lambda: obj.value, 300)
    if hasattr(obj, "echo"):
        tentar("      obj.echo()", lambda: obj.echo(), 500)
    metodo, nums = ler_numeros(obj)
    if nums is not None:
        log("      => lista de numeros via {}: n={}, primeiros={}, ultimos={}".format(
            metodo, len(nums), nums[:3], nums[-3:]))
    else:
        log("      => nao consegui converter em lista de numeros")
    return nums


def main():
    log("SoilTest - passo 2  ({})".format(datetime.datetime.now().isoformat(timespec="seconds")))
    if "g_i" in globals() and "s_i" in globals():
        s, g = globals()["s_i"], globals()["g_i"]
        log("Usando a conexao ja aberta pelo executor.")
    else:
        senha = os.environ.get("PLAXIS_PASSWORD") or getpass.getpass("Senha do servidor: ")
        s, g = new_server(HOST, PORT, password=senha)
    log("type(g)={}".format(type(g).__name__))

    # (a) Material e Tests
    log("\n== Material e Tests ==")
    for nome in ("Material", "Tests"):
        if not hasattr(g, nome):
            log("g.{} nao exposto".format(nome))
            continue
        obj = getattr(g, nome)
        log("-- g.{}: type={}".format(nome, type(obj).__name__))
        log("   atributos: {}".format(", ".join(nomes_publicos(obj))[:3500]))
        if hasattr(obj, "echo"):
            tentar("g.{}.echo()".format(nome), lambda o=obj: o.echo(), 4000)
        if hasattr(obj, "info"):
            tentar("g.{}.info()".format(nome), lambda o=obj: o.info(), 2500)

    # (b) Triaxial
    if not hasattr(g, "Triaxial"):
        log("Triaxial nao exposto; encerrando.")
        return 1
    t = g.Triaxial
    log("\n== Triaxial: comandos do objeto ==")
    tentar("t.commands()", lambda: t.commands(), 2500)
    tentar("t.info()", lambda: t.info(), 2500)

    originais = {}
    for p in PROPS_TRIAXIAL:
        try:
            originais[p] = valor(getattr(t, p))
        except Exception:
            pass
    log("Valores originais: {}".format(originais))

    log("\n== Configurando e calculando (drenado, 100 kPa, 15 %, 50 passos) ==")
    ok, _ = tentar("t.setproperties(...)", lambda: t.setproperties(
        "Behaviour", "Drained", "CellPressure", 100, "MaximumStrain", 15, "Steps", 50))
    if not ok:
        for p, v in (("CellPressure", 100), ("MaximumStrain", 15), ("Steps", 50)):
            tentar("t.setproperties({!r}, {})".format(p, v), lambda p=p, v=v: t.setproperties(p, v))
    tentar("t.echo() apos configurar", lambda: t.echo(), 1500)
    if hasattr(g, "Material"):
        tentar("g.validate(g.Material)", lambda: g.validate(g.Material), 1500)
    ok_calc, _ = tentar("g.calculate(t)", lambda: g.calculate(t), 1500)

    # (c) Results
    log("\n== Results ==")
    if not hasattr(t, "Results"):
        log("Triaxial.Results nao exposto.")
    else:
        r = t.Results
        log("type(Results)={}".format(type(r).__name__))
        log("atributos: {}".format(", ".join(nomes_publicos(r))[:3500]))
        tentar("Results.echo()", lambda: r.echo(), 2500)
        dados = {}
        for campo in CAMPOS:
            nums = sondar_campo(r, campo)
            if nums:
                dados[campo] = nums
        # Calculo de q e p' a partir de tensoes efetivas, se disponiveis
        if "SigyyE" in dados and "SigxxE" in dados:
            sy, sx = dados["SigyyE"], dados["SigxxE"]
            n = min(len(sy), len(sx))
            q = [abs(sy[i] - sx[i]) for i in range(n)]
            p = [-(sy[i] + 2 * sx[i]) / 3.0 for i in range(n)]
            log("\nq = |SigyyE - SigxxE| (n={}): inicio={}, fim={}, max={:.3f}".format(
                n, q[:2], q[-2:], max(q) if q else float("nan")))
            log("p' = -(SigyyE+2*SigxxE)/3: inicio={}, fim={}".format(p[:2], p[-2:]))
        if "Epsyy" in dados:
            e = dados["Epsyy"]
            log("Epsyy: inicio={}, fim={} (unidade a confirmar: fracao ou %)".format(e[:2], e[-2:]))

    # Restaurar
    log("\n== Restaurando valores originais do Triaxial ==")
    args = []
    for p, v in originais.items():
        if p == "Behaviour":
            args += [p, "Drained" if v == 0 else "Undrained"]
        elif p == "Direction":
            args += [p, "Compression" if v == 0 else "Extension"]
        elif p == "Consolidation":
            args += [p, "Isotropic" if v == 0 else "K0"]
        else:
            args += [p, v]
    tentar("t.setproperties(<originais>)", lambda: t.setproperties(*args))
    tentar("t.echo() final", lambda: t.echo(), 1500)
    return 0


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        log(traceback.format_exc())
        rc = 1
    try:
        with open(RELATORIO, "w", encoding="utf-8") as f:
            f.write("\n".join(_linhas))
        print("\nRelatorio gravado em: {}".format(RELATORIO))
    except Exception as e:
        print("Nao consegui gravar o relatorio: {}".format(e))
    if "g_i" not in globals():
        input("\nPressione Enter para fechar...")
        sys.exit(rc)

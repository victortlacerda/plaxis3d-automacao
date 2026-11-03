# -*- coding: utf-8 -*-
"""
soiltest_material.py - Descobre o Material carregado no SoilTest (qualquer modelo constitutivo).

O SoilModel e somente-leitura via script: o modelo e definido pelo material com que o SoilTest foi aberto.
Entao: (1) no SoilTest, troque/abra o material no modelo desejado (HS, HS small, ...) e
       (2) rode este script. Repita para cada modelo.

O que faz: lista modelo e parametros (nomes e valores), valida, e roda ensaios curtos (Triaxial drenado e
nao drenado, Oedometer) para confirmar que o modelo calcula. Restaura Triaxial e Oedometer no final.
Relatorio: soiltest_material_modelo<N>.txt (N = valor do SoilModel), ao lado do script.
"""
import os
import sys
import traceback
import datetime

AQUI = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
RELATORIO = None
_buffer = []


def log(msg=""):
    msg = str(msg)
    print(msg)
    _buffer.append(msg)
    if RELATORIO:
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


def parametros(mat):
    """Lista atributos do Material que parecem parametros (nome com inicial maiuscula ou minuscula conhecida)."""
    saida = {}
    try:
        nomes = [n for n in dir(mat) if not n.startswith("_")]
    except Exception:
        nomes = []
    ignorar = {"attr_cache", "commands", "dump", "echo", "get_cmd_line_repr", "get_equivalent", "getmetadata",
               "info", "materialcommand", "multiply", "observers", "rename", "reset_cache", "save",
               "setcolour", "setmetadata", "setproperties"}
    for n in nomes:
        if n in ignorar:
            continue
        try:
            v = getattr(mat, n)
        except Exception as e:
            saida[n] = "<erro: {}>".format(e)
            continue
        if callable(v) and not hasattr(v, "value"):
            continue
        saida[n] = valor(v)
    return saida


def conectar():
    if "g_i" in globals():
        return globals()["g_i"]
    import getpass
    from plxscripting.easy import new_server
    senha = os.environ.get("PLAXIS_PASSWORD") or getpass.getpass("Senha do servidor: ")
    return new_server("localhost", 10000, password=senha)[1]


def triaxial(g, comportamento):
    t = g.Triaxial
    log("\n-- Triaxial {} (100 kPa, 15 %, 50 passos)".format(comportamento))
    tentar("setproperties", lambda: t.setproperties(
        "Behaviour", comportamento, "Consolidation", "Isotropic", "Direction", "Compression",
        "CellPressure", 100, "MaximumStrain", 15, "Steps", 50))
    tentar("validate", lambda: g.validate(g.Material))
    ok, _ = tentar("calculate", lambda: g.calculate(t))
    if ok:
        r = t.Results
        for c in ("Epsyy", "TotalVolumetricStrain", "DeviatoricStress", "MeanEffStress", "PExcess", "SigyyE", "SigxxE"):
            log("   Results.{:<24} {}".format(c, estat(r, c)))


def oedometro(g):
    t = g.Oedometer
    log("\n-- Oedometer (1 fase: Siginc -100 kPa, 20 passos)")
    tentar("PhaseTable[0].setproperties", lambda: t.PhaseTable[0].setproperties("Duration", 1, "Siginc", -100, "Steps", 20))
    ok, _ = tentar("calculate", lambda: g.calculate(t))
    if ok:
        r = t.Results
        for c in ("Time", "Epsyy", "SigyyE", "SigxxE", "PExcess"):
            log("   Results.{:<24} {}".format(c, estat(r, c)))


def main():
    global RELATORIO
    g = conectar()
    ok, modelo = tentar("SoilModel.value", lambda: valor(g.Material.SoilModel))
    RELATORIO = os.path.join(AQUI, "soiltest_material_modelo{}.txt".format(modelo if ok else "X"))
    with open(RELATORIO, "w", encoding="utf-8") as f:
        f.write("\n".join(_buffer) + "\n")
    log("SoilTest - material  ({})".format(datetime.datetime.now().isoformat(timespec="seconds")))
    tentar("Material.echo()", lambda: g.Material.echo(), 6000)
    tentar("Material.info()", lambda: g.Material.info(), 2000)
    log("\n== Parametros (nome = valor) ==")
    for n, v in parametros(g.Material).items():
        log("  {} = {!r}".format(n, v))
    tentar("validate", lambda: g.validate(g.Material))
    tentar("Triaxial.PreconsolidationPressure (leitura)", lambda: valor(g.Triaxial.PreconsolidationPressure))
    tentar("Triaxial.setproperties('PreconsolidationPressure', 50)  [teste de escrita]",
           lambda: g.Triaxial.setproperties("PreconsolidationPressure", 50))
    tentar("Triaxial.setproperties('PreconsolidationPressure', 0)", lambda: g.Triaxial.setproperties("PreconsolidationPressure", 0))
    for comp in ("Drained", "Undrained"):
        try:
            triaxial(g, comp)
        except Exception:
            log("ERRO:\n" + traceback.format_exc())
    try:
        oedometro(g)
    except Exception:
        log("ERRO:\n" + traceback.format_exc())
    log("\n== Restaurando ==")
    tentar("Triaxial", lambda: g.Triaxial.setproperties(
        "Behaviour", "Drained", "Consolidation", "Isotropic", "Direction", "Compression",
        "CellPressure", 100, "MaximumStrain", 10, "Steps", 100))
    tentar("Oedometer.PhaseTable[0]", lambda: g.Oedometer.PhaseTable[0].setproperties("Duration", 1, "Siginc", 0, "Steps", 100))
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

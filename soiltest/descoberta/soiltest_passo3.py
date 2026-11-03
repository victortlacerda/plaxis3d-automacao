# -*- coding: utf-8 -*-
"""
soiltest_passo3.py - Descoberta de (A) outros ensaios e (B) modelos HS e HSsmall no SoilTest.

(A) Para cada ensaio (Oedometer, CRS, DSS, CDSS, CycTriaxial, General): lista tabela de fases e
    propriedades, tenta configurar um ensaio pequeno, calcula e resume os resultados.
(B) Troca o SoilModel do Material para Hardening Soil e HS small, lista os parametros,
    valida e roda um triaxial (drenado e nao drenado) em cada um.
No final, restaura o Material para Mohr-Coulomb (E=160000, nu=0.3, c=10, phi=25, psi=0).

Rode pelo Executar_script_PLAXIS.bat com o SoilTest aberto. Altera a sessao aberta, sem salvar arquivos
do SoilTest. O relatorio e gravado em tempo real: soiltest_passo3_relatorio.txt (ao lado do script).
"""
import os
import sys
import traceback
import datetime

AQUI = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
RELATORIO = os.path.join(AQUI, "soiltest_passo3_relatorio.txt")

CAMPOS = ["Time", "Epsyy", "Epsxx", "Gamxy", "SigyyE", "SigxxE", "Sigxy", "PExcess",
          "TotalVolumetricStrain", "DeviatoricStress", "MeanEffStress", "MobilizedShearStrength"]


def log(msg=""):
    msg = str(msg)
    print(msg)
    try:
        with open(RELATORIO, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass


def tentar(rotulo, fn, limite=1500):
    try:
        v = fn()
        r = repr(v)
        log("[OK ] {} -> {}".format(rotulo, r if len(r) <= limite else r[:limite] + "...<cortado>"))
        return True, v
    except Exception as e:
        log("[ERR] {} -> {}: {}".format(rotulo, type(e).__name__, str(e).replace("\n", " | ")))
        return False, None


def nomes(obj):
    try:
        return sorted(n for n in dir(obj) if not n.startswith("_"))
    except Exception as e:
        return ["<dir falhou: {}>".format(e)]


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
        return "erro ao ler: {}".format(e)
    if not v:
        return "vazio"
    return "n={} ini={:.6g} fim={:.6g} min={:.6g} max={:.6g}".format(len(v), v[0], v[-1], min(v), max(v))


def resumo_results(t, campos=CAMPOS):
    r = t.Results
    for c in campos:
        log("      Results.{:<24} {}".format(c, estat(r, c)))


def conectar():
    if "g_i" in globals():
        return globals()["g_i"]
    import getpass
    from plxscripting.easy import new_server
    senha = os.environ.get("PLAXIS_PASSWORD") or getpass.getpass("Senha do servidor: ")
    return new_server("localhost", 10000, password=senha)[1]


# ----------------------------- (A) outros ensaios -----------------------------
def sondar_tabela(t, nome, valores_linha):
    log("  -- PhaseTable de {}".format(nome))
    if not hasattr(t, "PhaseTable"):
        log("     {} nao tem PhaseTable".format(nome))
        return
    pt = t.PhaseTable
    log("     type={}  atributos={}".format(type(pt).__name__, ", ".join(nomes(pt))[:800]))
    tentar("{}.PhaseTable.echo()".format(nome), lambda: pt.echo())
    tentar("len(PhaseTable)", lambda: len(pt))
    ok, linha = tentar("PhaseTable[0]", lambda: pt[0])
    if ok:
        log("     linha[0] atributos={}".format(", ".join(nomes(linha))[:800]))
        if hasattr(linha, "echo"):
            tentar("PhaseTable[0].echo()", lambda: linha.echo())
        ok1, _ = tentar("PhaseTable[0].setproperties({})".format(valores_linha),
                        lambda: linha.setproperties(*[x for kv in valores_linha.items() for x in kv]))
        if not ok1:
            for k, v in valores_linha.items():
                tentar("PhaseTable[0].{} = {}".format(k, v), lambda k=k, v=v: setattr(linha, k, v))
        for k in valores_linha:
            tentar("   leitura PhaseTable[0].{}".format(k), lambda k=k: valor(getattr(linha, k)))
    # addphase / deletephase
    ok2, _ = tentar("{}.addphase()".format(nome), lambda: t.addphase())
    if ok2:
        tentar("PhaseTable.echo() apos addphase", lambda: t.PhaseTable.echo())
        tentar("{}.deletephase(1)".format(nome), lambda: t.deletephase(1))
        tentar("PhaseTable.echo() apos deletephase", lambda: t.PhaseTable.echo())


def ensaio(g, nome, props, valores_tabela=None):
    log("\n=== {} ===".format(nome))
    if not hasattr(g, nome):
        log("nao exposto")
        return
    t = getattr(g, nome)
    log("atributos: {}".format(", ".join(nomes(t))[:2500]))
    tentar("{}.echo()".format(nome), lambda: t.echo(), 3000)
    if valores_tabela:
        sondar_tabela(t, nome, valores_tabela)
    for k, v in props.items():
        tentar("{}.setproperties({!r}, {!r})".format(nome, k, v), lambda k=k, v=v: t.setproperties(k, v))
    tentar("{}.echo() apos configurar".format(nome), lambda: t.echo(), 3000)
    ok, _ = tentar("g.calculate({})".format(nome), lambda: g.calculate(t))
    if ok and hasattr(t, "Results"):
        resumo_results(t)


def parte_a(g):
    log("\n############ (A) OUTROS ENSAIOS (Material atual) ############")
    ensaio(g, "Oedometer", {}, {"Duration": 1, "Siginc": -100, "Steps": 20})
    ensaio(g, "CRS", {}, {"Duration": 1, "Epsinc": -0.05, "Steps": 20})
    ensaio(g, "DSS", {"AbsSigyyinit": 100, "MaximumShearStrain": 5, "Steps": 50})
    ensaio(g, "CDSS", {"AbsSigyyinit": 100, "TestControlType": "Strain", "ShearStrainAmplitude": 0.5,
                       "NumberOfCycles": 2, "NumberOfStepsPerQuarterCycle": 10, "DurationPerCycle": 1})
    ensaio(g, "CycTriaxial", {"CellPressure": 100, "TestControlType": "Strain", "AxialStrainAmplitude": 0.5,
                              "NumberOfCycles": 2, "NumberOfStepsPerQuarterCycle": 10, "DurationPerCycle": 1})
    log("\n=== General (so inspecao; nao calcula) ===")
    if hasattr(g, "General"):
        t = g.General
        tentar("General.echo()", lambda: t.echo(), 3000)
        tentar("General.commands()", lambda: t.commands(), 3000)
        tentar("General.Phases.echo()", lambda: t.Phases.echo())
        ok, ph = tentar("General.Phases[0]", lambda: t.Phases[0])
        if ok:
            log("   Phases[0] atributos: {}".format(", ".join(nomes(ph))[:1500]))
            if hasattr(ph, "echo"):
                tentar("General.Phases[0].echo()", lambda: ph.echo(), 3000)


# ----------------------------- (B) HS e HSsmall -----------------------------
MODELOS = [
    ("Hardening Soil", [3, "Hardening Soil", "HS"]),
    ("HS small", [4, "HS small", "HSsmall", "Hardening Soil with small-strain stiffness"]),
]


def trocar_modelo(g, candidatos):
    for c in candidatos:
        ok, _ = tentar("Material.setproperties('SoilModel', {!r})".format(c),
                       lambda c=c: g.Material.setproperties("SoilModel", c))
        if ok:
            return c
    return None


def triaxial_curto(g, behaviour):
    t = g.Triaxial
    tentar("Triaxial.setproperties({})".format(behaviour), lambda: t.setproperties(
        "Behaviour", behaviour, "Consolidation", "Isotropic", "Direction", "Compression",
        "CellPressure", 100, "MaximumStrain", 15, "Steps", 50))
    tentar("validate", lambda: g.validate(g.Material))
    ok, _ = tentar("calculate Triaxial ({})".format(behaviour), lambda: g.calculate(t))
    if ok:
        resumo_results(t, ["Epsyy", "TotalVolumetricStrain", "DeviatoricStress", "MeanEffStress", "PExcess"])


def parte_b(g):
    log("\n############ (B) MODELOS HS e HS small ############")
    for rotulo, candidatos in MODELOS:
        log("\n=== {} ===".format(rotulo))
        usado = trocar_modelo(g, candidatos)
        if usado is None:
            log("Nenhum candidato funcionou para {}.".format(rotulo))
            continue
        log("Candidato aceito: {!r}".format(usado))
        tentar("SoilModel.value", lambda: valor(g.Material.SoilModel))
        log("atributos do Material: {}".format(", ".join(nomes(g.Material))[:3500]))
        tentar("Material.echo()", lambda: g.Material.echo(), 5000)
        tentar("Material.info()", lambda: g.Material.info(), 2000)
        tentar("validate", lambda: g.validate(g.Material))
        triaxial_curto(g, "Drained")
        triaxial_curto(g, "Undrained")


def restaurar(g):
    log("\n############ RESTAURANDO ############")
    tentar("Material -> Mohr-Coulomb", lambda: g.Material.setproperties(
        "SoilModel", 2, "ERef", 160000, "nu", 0.3, "cRef", 10, "phi", 25, "psi", 0))
    tentar("Material.echo()", lambda: g.Material.echo(), 2000)
    tentar("Triaxial.setproperties(...)", lambda: g.Triaxial.setproperties(
        "Behaviour", "Drained", "Consolidation", "Isotropic", "Direction", "Compression",
        "CellPressure", 100, "MaximumStrain", 10, "Steps", 100))


def main():
    open(RELATORIO, "w", encoding="utf-8").close()
    log("SoilTest - passo 3  ({})".format(datetime.datetime.now().isoformat(timespec="seconds")))
    g = conectar()
    for etapa in (parte_a, parte_b):
        try:
            etapa(g)
        except Exception:
            log("ERRO na etapa {}:\n{}".format(etapa.__name__, traceback.format_exc()))
    try:
        restaurar(g)
    except Exception:
        log("ERRO ao restaurar:\n" + traceback.format_exc())
    log("\nRelatorio gravado em: {}".format(RELATORIO))
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

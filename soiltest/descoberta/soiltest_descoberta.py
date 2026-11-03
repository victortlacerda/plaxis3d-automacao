# -*- coding: utf-8 -*-
"""
soiltest_descoberta.py  -  Descoberta da API de scripting do PLAXIS SoilTest.

NAO assume nada alem do que esta no Commands Reference (comandos e objetos).
Tudo e tentado com tratamento de erro e gravado em um relatorio, para que a gente
descubra o que o servidor do SoilTest realmente expoe via plxscripting.

Uso (com o SoilTest aberto e o servidor de scripting ativo):
  "C:\\ProgramData\\Seequent\\PLAXIS Python Distribution V3\\python\\python.exe" soiltest_descoberta.py PORTA
  ... soiltest_descoberta.py PORTA --executar   (tambem roda um triaxial de teste)

A senha vem da variavel de ambiente PLAXIS_PASSWORD; se nao existir, e pedida (nao e exibida).
O relatorio e gravado ao lado do script: soiltest_descoberta_relatorio.txt
"""
import os
import sys
import getpass
import traceback
import datetime

from plxscripting.easy import new_server

HOST = "localhost"
PORT = 10000
# Mude para True para tambem rodar um triaxial de teste (altera o ensaio da sessao aberta, sem salvar).
EXECUTAR = False

# Compatibilidade com linha de comando: [PORTA] [--executar]. Ignora argumentos que nao sejam numeros
# (o executor passa o caminho do script em sys.argv).
for _a in sys.argv[1:]:
    if _a == "--executar":
        EXECUTAR = True
    elif _a.isdigit():
        PORT = int(_a)

AQUI = os.path.dirname(os.path.abspath(__file__))
RELATORIO = os.path.join(AQUI, "soiltest_descoberta_relatorio.txt")
_linhas = []


def log(msg=""):
    msg = str(msg)
    print(msg)
    _linhas.append(msg)


def tentar(rotulo, fn):
    """Executa fn(); registra resultado ou erro. Devolve (ok, valor)."""
    try:
        v = fn()
        log("[OK ] {} -> {!r}".format(rotulo, v))
        return True, v
    except Exception as e:
        log("[ERR] {} -> {}: {}".format(rotulo, type(e).__name__, e))
        return False, None


def nomes_publicos(obj):
    try:
        return sorted(n for n in dir(obj) if not n.startswith("_"))
    except Exception as e:
        return ["<dir falhou: {}>".format(e)]


def como_lista(obj, max_itens=5):
    """Tenta ler um objeto 'listavel' de resultados de varias formas."""
    for rotulo, f in (
        ("list(obj)", lambda: list(obj)),
        ("obj[:]", lambda: obj[:]),
        ("obj.value", lambda: obj.value),
        ("str(obj)", lambda: str(obj)),
    ):
        try:
            v = f()
            if isinstance(v, (list, tuple)):
                return "{} -> {} itens, primeiros: {}".format(rotulo, len(v), list(v[:max_itens]))
            return "{} -> {!r}".format(rotulo, str(v)[:300])
        except Exception:
            continue
    return "<nao consegui ler>"


def main():
    log("SoilTest - descoberta  ({})".format(datetime.datetime.now().isoformat(timespec="seconds")))
    log("Servidor: {}:{}   executar teste: {}".format(HOST, PORT, EXECUTAR))

    # 1) Conexao: reaproveita s_i/g_i quando rodado pelo executor (que ja conectou na porta);
    #    caso contrario, conecta por conta propria.
    if "g_i" in globals() and "s_i" in globals():
        s, g = globals()["s_i"], globals()["g_i"]
        log("Usando a conexao ja aberta pelo executor (s_i/g_i).")
    else:
        senha = os.environ.get("PLAXIS_PASSWORD") or getpass.getpass("Senha do servidor (nao sera exibida): ")
        try:
            s, g = new_server(HOST, PORT, password=senha)
        except Exception:
            log("Falha ao conectar. Confira se o SoilTest esta aberto, a porta e a senha:")
            log(traceback.format_exc())
            return 1
    log("Conectado. type(s)={}  type(g)={}".format(type(s).__name__, type(g).__name__))

    # 2) O que o objeto global expoe
    pub = nomes_publicos(g)
    log("\n== dir(g): {} nomes publicos ==".format(len(pub)))
    log(", ".join(pub))

    # 3) Candidatos citados no Commands Reference
    log("\n== Presenca dos nomes do manual em g ==")
    candidatos = [
        "command", "cmd", "commands", "info", "echo", "set", "setproperties", "calculate",
        "validate", "save", "close", "addphase", "insertphase", "deletephase", "index",
        "Triaxial", "CycTriaxial", "Oedometer", "CRS", "DSS", "CDSS", "PMT", "General",
        "Material", "Tests",
    ]
    for nome in candidatos:
        log("  {:<14} {}".format(nome, "SIM" if hasattr(g, nome) else "nao"))

    # 4) Comandos e info (o manual diz que 'commands' e 'info' listam tudo)
    log("\n== commands / info / echo ==")
    for nome in ("commands", "info", "echo"):
        if hasattr(g, nome):
            tentar("g.{}()".format(nome), lambda n=nome: getattr(g, n)())

    # 5) Cada ensaio: atributos, echo e leitura de propriedades do manual
    props = {
        "Triaxial": ["Behaviour", "Direction", "Consolidation", "K0", "CellPressure",
                     "MaximumStrain", "Steps", "PreconsolidationPressure"],
        "Oedometer": ["PreconsolidationPressure"],
        "CRS": ["PreconsolidationPressure"],
        "DSS": ["Behaviour", "Consolidation", "K0", "AbsSigyyEinit", "MaximumShearStrain", "Steps"],
        "CycTriaxial": ["Behaviour", "CellPressure", "NumberOfCycles", "TestControlType"],
        "CDSS": ["Behaviour", "AbsSigyyinit", "NumberOfCycles", "TestControlType"],
        "General": ["Behaviour", "Sigxxinit", "Sigyyinit", "Sigzzinit"],
    }
    log("\n== Ensaios ==")
    for teste, lista in props.items():
        if not hasattr(g, teste):
            log("-- {}: nao exposto em g".format(teste))
            continue
        obj = getattr(g, teste)
        log("-- {}: type={}".format(teste, type(obj).__name__))
        log("   atributos: {}".format(", ".join(nomes_publicos(obj))[:1500]))
        if hasattr(obj, "echo"):
            tentar("{}.echo()".format(teste), lambda o=obj: o.echo())
        for p in lista:
            ok, v = tentar("{}.{}".format(teste, p), lambda o=obj, p=p: getattr(o, p))
            if ok and hasattr(v, "value"):
                tentar("   {}.{}.value".format(teste, p), lambda v=v: v.value)

    # 6) Opcional: roda um triaxial pequeno e le resultados (altera o ensaio na sessao aberta)
    if EXECUTAR:
        log("\n== Triaxial de teste (--executar) ==")
        if not hasattr(g, "Triaxial"):
            log("Triaxial nao exposto; nada a executar.")
        else:
            t = g.Triaxial
            for rotulo, f in (
                ("setproperties Behaviour/CellPressure/MaximumStrain/Steps",
                 lambda: g.setproperties(t, "Behaviour", "Drained", "CellPressure", 100,
                                         "MaximumStrain", 15, "Steps", 50)
                 if hasattr(g, "setproperties") else t.setproperties(
                     "Behaviour", "Drained", "CellPressure", 100, "MaximumStrain", 15, "Steps", 50)),
                ("validate", lambda: g.validate(g.Material) if hasattr(g, "Material") else "sem g.Material"),
                ("calculate", lambda: g.calculate(t) if hasattr(g, "calculate") else t.calculate()),
            ):
                tentar(rotulo, f)
            if hasattr(t, "Results"):
                r = t.Results
                log("Results atributos: {}".format(", ".join(nomes_publicos(r))[:1500]))
                for campo in ("Epsyy", "SigyyE", "SigxxE", "DeviatoricStress", "MeanEffStress",
                              "PExcess", "TotalVolumetricStrain", "Eps1", "SigmaEffective1"):
                    if hasattr(r, campo):
                        log("   Results.{:<22} {}".format(campo, como_lista(getattr(r, campo))))
                    else:
                        log("   Results.{:<22} nao exposto".format(campo))
            else:
                log("Triaxial.Results nao exposto.")

    with open(RELATORIO, "w", encoding="utf-8") as f:
        f.write("\n".join(_linhas))
    log("\nRelatorio gravado em: {}".format(RELATORIO))
    return 0


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        log(traceback.format_exc())
        rc = 1
    # O executor ja pede Enter ao final; so pede aqui se rodado direto.
    if "g_i" not in globals():
        input("\nPressione Enter para fechar...")
        sys.exit(rc)

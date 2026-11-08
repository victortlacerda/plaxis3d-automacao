# -*- coding: utf-8 -*-
"""
Executa um script do projeto SEM digitar nada no terminal: pelo menu do PLAXIS 3D Input
(Expert > Python > Run script... e escolher este arquivo).

Quando o PLAXIS roda um script pelo menu, ele mesmo passa endereço, porta e senha do servidor; este lançador usa
isso para conectar (s_i, g_i), responde às perguntas do script com a lista de "respostas" do auto_config.json e
grava tudo o que for impresso em um log.

auto_config.json (na mesma pasta deste arquivo):
{
  "script": "..\\estudos\\sapata_lote.py",          caminho relativo a esta pasta ou absoluto
  "respostas": ["teste_lote.xlsx", "s"],             uma por pergunta, na ordem; "" = Enter (padrão)
  "pasta": null,                                     pasta de trabalho do script (null = a pasta do script)
  "log": "auto_log.txt"                              gravado na pasta deste arquivo
}
Também funciona pelo executor externo (aí s_i/g_i já existem e a senha é pedida uma vez).
"""
import os
import sys
import json
import getpass
import builtins
import traceback
import datetime

AQUI = os.path.dirname(os.path.abspath(globals().get("__file__", "executar_auto.py")))
CFG = json.load(open(os.path.join(AQUI, "auto_config.json"), encoding="utf-8"))
SCRIPT = CFG["script"] if os.path.isabs(CFG["script"]) else os.path.normpath(os.path.join(AQUI, CFG["script"]))
PASTA = CFG.get("pasta") or os.path.dirname(SCRIPT)
LOG = os.path.join(AQUI, CFG.get("log") or "auto_log.txt")

# --- conexão: variáveis passadas pelo PLAXIS (Run script) ou as do executor externo
if "g_i" not in globals() or globals().get("g_i") is None:
    from plxscripting.easy import new_server
    s_i, g_i = new_server()
SENHA = globals().get("AppServerPassword") or globals().get("PLAXIS_PASSWORD") or os.environ.get("PLAXIS_PASSWORD")
if not SENHA:
    SENHA = getpass.getpass("Senha do servidor PLAXIS: ")
os.environ["PLAXIS_PASSWORD"] = SENHA


class Tee(object):
    def __init__(self, a, b):
        self.a, self.b = a, b

    def write(self, t):
        for s in (self.a, self.b):
            try:
                s.write(t)
                s.flush()
            except Exception:
                pass

    def flush(self):
        for s in (self.a, self.b):
            try:
                s.flush()
            except Exception:
                pass


respostas = list(CFG.get("respostas", []))
_input_original = builtins.input


def _input(prompt=""):
    r = respostas.pop(0) if respostas else ""
    sys.stdout.write("{}{}\n".format(prompt, r))
    return r


arq_log = open(LOG, "w", encoding="utf-8")
orig_out, orig_err = sys.stdout, sys.stderr
sys.stdout = Tee(orig_out if orig_out else arq_log, arq_log)
sys.stderr = sys.stdout
builtins.input = _input
print("=== executar_auto: {} | {} ===".format(SCRIPT, datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
try:
    ns = {"g_i": g_i, "s_i": s_i, "__file__": os.path.join(PASTA, os.path.basename(SCRIPT)), "__name__": "__main__",
          "PLAXIS_PASSWORD": SENHA}
    if os.path.dirname(SCRIPT) not in sys.path:
        sys.path.insert(0, os.path.dirname(SCRIPT))
    exec(compile(open(SCRIPT, encoding="utf-8").read(), SCRIPT, "exec"), ns, ns)
    print("\n=== executar_auto: FIM OK ===")
except BaseException:  # noqa
    print("\n=== executar_auto: ERRO ===")
    print(traceback.format_exc())
finally:
    builtins.input = _input_original
    sys.stdout, sys.stderr = orig_out, orig_err
    arq_log.close()

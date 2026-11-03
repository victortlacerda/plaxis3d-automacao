"""Mock do PLAXIS Output para testar os scripts de resultados SEM o PLAXIS.

Uso (a partir de uma pasta de trabalho vazia):
    python rodar_resultados.py <script.py> <fake: sapata_resultados|subsolo_resultados> <modelo.json>

O JSON é copiado para a pasta de trabalho com o nome que o script espera
(ultimo_modelo.json ou ultimo_modelo_subsolo.json).
"""
import sys, os, shutil
AQUI = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.abspath(sys.argv[1])
FAKE, JSON_ORIG = sys.argv[2], os.path.abspath(sys.argv[3])
sys.path.insert(0, os.path.join(AQUI, "..", "fakes", FAKE))
destino = "ultimo_modelo_subsolo.json" if "subsolo" in FAKE else "ultimo_modelo.json"
shutil.copy(JSON_ORIG, os.path.join(os.getcwd(), destino))


class GI:
    Phases = ["p"]

    def view(self, p):
        return 1


os.environ["PLAXIS_PASSWORD"] = "x"
ns = {"g_i": GI(), "__file__": os.path.join(os.getcwd(), os.path.basename(SCRIPT))}
exec(compile(open(SCRIPT, encoding="utf-8").read(), SCRIPT, "exec"), ns, ns)

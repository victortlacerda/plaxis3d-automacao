# -*- coding: utf-8 -*-
"""
Manual Bentley - PLAXIS 3D Tutorial 1 - Case A: Rigid foundation (prédio como volume rígido, só peso próprio).

Não pergunta nada (só a senha do servidor): os dados estão em PARÂMETROS, abaixo.
Usa o construir() VALIDADO do plaxis_sapata_interativo.py (opções "VOLUME linear elástico não poroso" e
"SEM AÇÃO") e, em seguida, roda o plaxis_sapata_resultados.py. Mesmos comandos da rodada real de 19/10/2026,
que deu Uz = -102,6 mm no centro da sapata (manual: ~110 mm no centro do prédio).

Modelo (um quarto do prédio; os planos x = 0 e y = 0 do domínio fazem o papel de simetria):
  - domínio 75 x 75 m, profundidade 40 m; argila lacustre Mohr-Coulomb drenada; N.A. em z = -2 m;
  - prédio: volume de 18 x 18 m, de z = 0 a -2 m, material "Building" Linear Elástico NÃO POROSO
    (γ = 50 kN/m³, E = 3·10⁷ kN/m², ν = 0,15), atribuído na fase de construção;
  - fases: Initial (K0) -> Footing (o volume vira "Building"); malha coarse.

Saídas nesta pasta: Bentley_Caso_A.p3d, ultimo_modelo.json e sapata_peso_proprio.csv.
Pode ser rodado pelo executor externo ou pelo menu Expert > Run Python script.
"""
import os
import getpass

# ----------------------------------------------------------------------------
# PARÂMETROS (edite aqui)
# ----------------------------------------------------------------------------
TITULO = "PLAXIS 3D Tutorial 1 - Case A: Rigid foundation"
DOMINIO = dict(xmin=0.0, xmax=75.0, ymin=0.0, ymax=75.0, H=40.0)
SOLO = dict(nome="Lacustrine clay", gamma_unsat=17.0, gamma_sat=18.0, E=10000.0, nu=0.3, c=10.0, phi=30.0, psi=0.0)
NIVEL_AGUA = -2.0
PREDIO = dict(cx=9.0, cy=9.0, cz=0.0, L=18.0, W=18.0, d=2.0,
              nome_material="Building", gamma=50.0, E=3.0e7, nu=0.15)
MALHA = "coarse"                 # very coarse | coarse | medium | fine | very fine
REFINAR_NA_SAPATA = False
RODAR_RESULTADOS = True          # roda o plaxis_sapata_resultados.py logo depois do cálculo

# ----------------------------------------------------------------------------
PRESETS = {"very coarse": 0.1, "coarse": 0.075, "medium": 0.05, "fine": 0.035, "very fine": 0.025}
PASTA = os.path.dirname(os.path.abspath(globals().get("__file__", "bentley_caso_a.py")))
MARCA = "\nverificar_conexao()\ndados_modelo = perguntar_tudo()"


def achar(nome):
    for cand in (os.path.join(PASTA, nome), os.path.join(PASTA, "..", "..", nome),
                 os.path.join(PASTA, "..", nome)):
        if os.path.exists(cand):
            return os.path.abspath(cand)
    raise RuntimeError("Não achei {} (ele fica na pasta 'sapata').".format(nome))


ARQ_INT = achar("plaxis_sapata_interativo.py")
ARQ_RES = achar("plaxis_sapata_resultados.py")
SENHA = globals().get("PLAXIS_PASSWORD") or globals().get("AppServerPassword") or \
    os.environ.get("PLAXIS_PASSWORD") or getpass.getpass("Senha do servidor PLAXIS: ")

P = dict(
    info=dict(titulo=TITULO, empresa=""),
    dominio=DOMINIO,
    camadas=[dict(SOLO, espessura=DOMINIO["H"])],
    nivel_agua=NIVEL_AGUA,
    sapata=dict(cx=PREDIO["cx"], cy=PREDIO["cy"], cz=PREDIO["cz"], L=PREDIO["L"], W=PREDIO["W"], d=PREDIO["d"],
                B=min(PREDIO["L"], PREDIO["W"]), gamma=PREDIO["gamma"], E=PREDIO["E"], nu=PREDIO["nu"],
                nome_material=PREDIO["nome_material"], modelo="volume"),
    carga=dict(modo="nenhuma", tipo=1, direcao=1, eixo=None, valor=0.0, unidade="kN/m2"),
    malha=dict(nome=MALHA, fator=PRESETS[MALHA], refinar=REFINAR_NA_SAPATA, coarseness=0.1),
    projeto=os.path.join(PASTA, "Bentley_Caso_A.p3d"),
    calcular=True,
)

# --- definições do script interativo validado (sem a parte das perguntas)
fonte = open(ARQ_INT, encoding="utf-8").read()
i = fonte.find(MARCA)
if i < 0:
    raise RuntimeError("plaxis_sapata_interativo.py em versão inesperada (não achei o bloco principal).")
ns = {"g_i": g_i, "s_i": s_i, "__file__": os.path.join(PASTA, "plaxis_sapata_interativo.py"),
      "__name__": "bentley_caso_a", "PLAXIS_PASSWORD": SENHA}
exec(compile(fonte[:i], ARQ_INT, "exec"), ns, ns)
ns["ARQUIVO_JSON"] = os.path.join(PASTA, "ultimo_modelo.json")
ns["verificar_conexao"]()
ns["resumo"](P)
ns["construir"](P)

if RODAR_RESULTADOS:
    print("\n" + "#" * 70 + "\n# RESULTADOS\n" + "#" * 70)
    nr = {"g_i": g_i, "s_i": s_i, "__file__": os.path.join(PASTA, "plaxis_sapata_resultados.py"),
          "__name__": "bentley_caso_a_resultados", "PLAXIS_PASSWORD": SENHA}
    exec(compile(open(ARQ_RES, encoding="utf-8").read(), ARQ_RES, "exec"), nr, nr)
    print("\nReferência: na rodada real de 19/10/2026 o recalque no centro da sapata foi 102,6 mm "
          "(manual: ~110 mm no centro do prédio, que é o canto (0, 0) deste modelo de 1/4).")

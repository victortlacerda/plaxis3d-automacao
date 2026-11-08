# -*- coding: utf-8 -*-
"""
soiltest_bateria.py  -  Roda, SEM PERGUNTAS, as rodadas pendentes de validacao do SoilTest em uma unica execucao.

Usa o plaxis_soiltest_auto_dev.py (precisa estar na MESMA pasta deste arquivo) com "interativo": False.
Cada caso grava sua pasta em soiltest_saida/ (CSV, graficos, log.txt) e, no fim, este script grava
soiltest_saida/bateria_<data>.txt com o resumo de todos os casos.

COMO RODAR: PLAXIS 3D Input aberto com um projeto e o servidor de scripts ativo; rode pelo Executar_script_PLAXIS.bat
e escolha este arquivo. A senha do SoilTest vem da variavel de ambiente PLAXIS_PASSWORD; se ela nao existir,
e pedida UMA vez no inicio e reaproveitada nos casos seguintes (nunca e gravada em arquivo).

Cada caso abre uma janela nova do SoilTest (portas 10001, 10002, ...). Pode fecha-las no fim.
"""
import copy
import datetime
import getpass
import os
import traceback

AQUI = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
SCRIPT = os.path.join(AQUI, "plaxis_soiltest_auto_dev.py")

SEM = {"triaxial": {"rodar": False}, "oedometer": {"rodar": False}}
CASOS_1 = [
    # (nome, modelo, drenagem, ajustes do CONFIG, o que verificar)
    ("1_ciclicos_nao_drenados", "MC", "D", dict(SEM, **{
        "valores": {"ERef": 30000, "nu": 0.3, "cRef": 5, "phi": 30, "psi": 0},
        "cdss": {"rodar": True, "pressoes_kPa": [100], "comportamentos": ["Undrained"], "controle": "Strain",
                 "amplitude": 0.5, "ciclos": 5, "passos_por_quarto": 20},
        "triaxial_ciclico": {"rodar": True, "pressoes_kPa": [100], "comportamentos": ["Undrained"], "controle": "Strain",
                             "amplitude": 0.5, "ciclos": 5, "passos_por_quarto": 20}}),
     "Delta u deve aparecer e crescer ao longo dos ciclos"),
    ("2_controle_por_tensao", "MC", "D", dict(SEM, **{
        "valores": {"ERef": 30000, "nu": 0.3, "cRef": 5, "phi": 30, "psi": 0},
        "cdss": {"rodar": True, "pressoes_kPa": [100], "comportamentos": ["Drained", "Undrained"], "controle": "Stress",
                 "amplitude": 20, "ciclos": 5, "passos_por_quarto": 20},
        "triaxial_ciclico": {"rodar": True, "pressoes_kPa": [100], "comportamentos": ["Drained", "Undrained"],
                             "controle": "Stress", "amplitude": 50, "ciclos": 5, "passos_por_quarto": 20}}),
     "Amplitude de tensao aceita; amplitude de tau = 20 kPa (CDSS) e de q = 50 kPa (triaxial ciclico)"),
    ("3_K0_DSS_CDSS_ciclico", "LE", "D", dict(SEM, **{
        "valores": {"ERef": 30000, "nu": 0.3},
        "consolidacao": {"tipo": "K0", "K0": 0.5},
        "dss": {"rodar": True, "pressoes_kPa": [100], "comportamentos": ["Drained"]},
        "cdss": {"rodar": True, "pressoes_kPa": [100], "comportamentos": ["Drained"], "controle": "Strain", "amplitude": 0.5},
        "triaxial_ciclico": {"rodar": True, "pressoes_kPa": [100], "comportamentos": ["Drained"], "controle": "Strain",
                             "amplitude": 0.5}}),
     "Tensoes iniciais com K = 0,5 em DSS, CDSS e triaxial ciclico; G e E iguais aos do isotropico"),
    ("4a_HS_normalmente_adensado", "HS", "D", {
        "valores": {"E50ref": 40000, "Eoedref": 40000, "Eurref": 120000, "m": 0.5, "nuur": 0.2, "pref": 100,
                    "cref": 1, "phi": 35, "psi": 5},
        "consolidacao": {"tipo": "K0", "K0": 0.5}, "preadensamento": {"modo": "nenhum", "valor": 0},
        "triaxial": {"rodar": True, "pressoes_kPa": [100], "comportamentos": ["Drained"]}, "oedometer": {"rodar": False}},
     "Referencia para comparar com o 4b (mesmo material, sem pre-adensamento)"),
    ("4b_HS_OCR_2", "HS", "D", {
        "valores": {"E50ref": 40000, "Eoedref": 40000, "Eurref": 120000, "m": 0.5, "nuur": 0.2, "pref": 100,
                    "cref": 1, "phi": 35, "psi": 5},
        "consolidacao": {"tipo": "K0", "K0": 0.5}, "preadensamento": {"modo": "OCR", "valor": 2},
        "triaxial": {"rodar": True, "pressoes_kPa": [100], "comportamentos": ["Drained"]}, "oedometer": {"rodar": False}},
     "Inicio da curva q x eps_a mais rigido que no 4a; mesmo q_f"),
]


CIC_U = {"pressoes_kPa": [100], "comportamentos": ["Undrained"], "controle": "Strain", "amplitude": 0.2,
         "ciclos": 10, "passos_por_quarto": 20}
FASES = {"oedometer": {"rodar": True}, "crs": {"rodar": True, "fases": [{"Duration": 1, "Epsinc": -10, "Steps": 100}]}}
CASOS_2 = [
    # Item 1: acumulo de poropressao em ciclos com modelos que contraem (valores de teste do CONFIG)
    ("5_HSsmall_ciclico_nao_drenado", "HSsmall", "D", dict(SEM, cdss=dict(CIC_U, rodar=True), triaxial_ciclico=dict(CIC_U, rodar=True)),
     "Delta u (ou queda de sigma'v / p') acumulando de ciclo a ciclo"),
    ("6_MCC_ciclico_nao_drenado", "MCC", "D", dict(SEM, cdss=dict(CIC_U, rodar=True), triaxial_ciclico=dict(CIC_U, rodar=True)),
     "Delta u acumulando; MCC normalmente adensado deve contrair"),
    ("7_SoftSoil_ciclico_nao_drenado", "SS", "D", dict(SEM, cdss=dict(CIC_U, rodar=True), triaxial_ciclico=dict(CIC_U, rodar=True)),
     "Delta u acumulando"),
    # Item 2: efeito do pre-adensamento no edometro e no CRS (sigma'p = 100 kPa x sem pre-adensamento)
    ("8a_HS_edometro_NC", "HS", "D", dict(FASES, triaxial={"rodar": False}, preadensamento={"modo": "nenhum", "valor": 0}),
     "Referencia normalmente adensada"),
    ("8b_HS_edometro_pc100", "HS", "D", dict(FASES, triaxial={"rodar": False}, preadensamento={"modo": "pressao", "valor": 100}),
     "Menos deformacao ate ~100 kPa (recompressao com Eur) e depois curva virgem"),
    ("9a_MCC_edometro_NC", "MCC", "D", dict(FASES, triaxial={"rodar": False}, preadensamento={"modo": "nenhum", "valor": 0}),
     "Referencia normalmente adensada"),
    ("9b_MCC_edometro_pc100", "MCC", "D", dict(FASES, triaxial={"rodar": False}, preadensamento={"modo": "pressao", "valor": 100}),
     "Inclinacao kappa ate ~100 kPa e lambda depois"),
]
CASOS_3 = [
    # sigma'p padrao no edometro/CRS do MCC e do Soft Soil (sem informar pre-adensamento)
    ("10_MCC_edometro_padrao", "MCC", "D", dict(FASES, triaxial={"rodar": False}, preadensamento={"modo": "nenhum", "valor": 0}),
     "Log mostra sigma'p padrao de 100 kPa; resultado igual ao 9b (eps 13,8 % em 400 kPa)"),
    ("11_SS_edometro_padrao", "SS", "D", dict(FASES, triaxial={"rodar": False}, preadensamento={"modo": "nenhum", "valor": 0}),
     "Log mostra sigma'p padrao; inclinacao kappa* antes de 100 kPa e lambda* depois"),
]
BATERIAS = {"1": CASOS_1, "2": CASOS_2, "3": CASOS_3}
RODAR = "3"          # "1" = ciclicos MC/tensao/K0/OCR triaxial; "2" = modelos contrateis e OCR no edometro; "3" = sigma'p padrao MCC/SS
CASOS = BATERIAS[RODAR]


def mesclar(base, ajustes):
    for k, v in ajustes.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict) and k != "valores":
            mesclar(base[k], v)
        else:
            base[k] = copy.deepcopy(v)


def main():
    if not os.path.isfile(SCRIPT):
        print("ERRO: nao achei {} (coloque os dois arquivos na mesma pasta).".format(SCRIPT))
        return 1
    if not os.environ.get("PLAXIS_PASSWORD"):
        os.environ["PLAXIS_PASSWORD"] = getpass.getpass("Senha do servidor do SoilTest (pedida uma vez so): ")
    with open(SCRIPT, "rb") as f:
        codigo = compile(f.read(), SCRIPT, "exec")
    resumo = ["Bateria SoilTest {} - {}".format(RODAR, datetime.datetime.now().isoformat(timespec="seconds")), ""]
    for nome, modelo, dren, ajustes, verificar in CASOS:
        print("\n" + "#" * 70 + "\n# CASO {}  ({} / {})\n# Verificar: {}\n".format(nome, modelo, dren, verificar) + "#" * 70)
        ns = {"__name__": "soiltest_auto", "__file__": SCRIPT, "__builtins__": __builtins__}
        if "g_i" in globals():
            ns["g_i"], ns["s_i"] = globals()["g_i"], globals().get("s_i")
        try:
            exec(codigo, ns, ns)
            cfg = ns["CONFIG"]
            cfg["interativo"] = False
            cfg["modelo"], cfg["drenagem"] = modelo, dren
            mesclar(cfg, ajustes)
            ns["_linhas"].clear()
            rc = ns["main"]()
            linhas = ns["_linhas"]
            saida = next((l.split("Saida:", 1)[1].strip() for l in reversed(linhas) if "Saida:" in l), "?")
            chave = [l for l in linhas if any(t in l for t in ("Tensoes iniciais", "q_max", "tau_max", "Ultimo ciclo",
                                                                 "du max", "Esperado", "Precons", "ERR", "ATENCAO",
                                                                 "Aviso", "Versao estavel", "E50", "Fim de cada ciclo",
                                                                 "pontos; sigma_v", "sigma'p padrao"))]
            resumo += ["== {} ({} / {}) rc={}".format(nome, modelo, dren, rc), "   verificar: " + verificar,
                       "   saida: " + saida] + ["   " + l.strip() for l in chave] + [""]
        except Exception:
            tb = traceback.format_exc()
            print(tb)
            resumo += ["== {} ({} / {}) FALHOU".format(nome, modelo, dren), tb, ""]
    pasta = os.path.join(AQUI, "soiltest_saida")
    os.makedirs(pasta, exist_ok=True)
    arq = os.path.join(pasta, "bateria_{}.txt".format(datetime.datetime.now().strftime("%Y%m%d_%H%M%S")))
    with open(arq, "w", encoding="utf-8") as f:
        f.write("\n".join(resumo))
    print("\nResumo da bateria: " + arq)
    return 0


if __name__ == "__main__":
    main()

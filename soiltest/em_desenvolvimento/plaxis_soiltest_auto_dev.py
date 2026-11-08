# -*- coding: utf-8 -*-
"""
plaxis_soiltest_auto_dev.py  -  VERSAO EM DESENVOLVIMENTO (ciclicos nao drenados e controle por
tensao ainda sem validacao no PLAXIS real; use a versao estavel soiltest/plaxis_soiltest_auto.py para trabalho).

Fluxo completo: modelo + parametros -> material no PLAXIS 3D Input -> SoilTest -> ensaios -> saida.

Modelos: Mohr-Coulomb (drenado, nao drenado A/B/C, non-porous), Linear Elastic (drenado, A, C, non-porous),
Hardening Soil e HS small (drenado, A, B), Modified Cam-Clay e Soft Soil (drenado, A).

Ensaios: Triaxial, Oedometer, CRS, DSS, CDSS (cisalhamento simples ciclico) e Triaxial ciclico.
Consolidacao inicial isotropica ou K0 (Triaxial, DSS, CDSS e Triaxial ciclico) e pre-adensamento
(pressao de pre-adensamento ou OCR) nos modelos que aceitam (HS, HS small, MCC, Soft Soil).

Em uma execucao:
  1. pergunta o modelo, a drenagem, os parametros e os ensaios (Enter = valor de teste entre colchetes)
  2. cria/atualiza o material no Input e abre o SoilTest com ele (g_i.soiltest devolve a porta)
  3. roda os ensaios escolhidos e compara com solucoes teoricas quando existem
  4. grava, em soiltest_saida/auto_<modelo>_<drenagem>_<data>/ :
       - um CSV por ensaio, resumo.json e log.txt
       - graficos/ : UM ARQUIVO PNG POR GRAFICO (nada de varias figuras numa imagem so)

COMO RODAR: PLAXIS 3D Input aberto com projeto e servidor de scripting ativo; rode pelo Executar_script_PLAXIS.bat.
Senha: variavel de ambiente PLAXIS_PASSWORD ou digitada quando pedida (nunca gravada em arquivo).
Sem perguntas: "interativo": False e edite o CONFIG (modelo, drenagem, valores, "rodar" de cada ensaio).
"""
import os
import re
import sys
import csv
import json
import math
import time
import getpass
import datetime
import traceback

# Versao estavel: so o que ja foi validado no PLAXIS real. Os ensaios ciclicos (CDSS e Triaxial ciclico)
# ficam restritos a comportamento drenado e controle por deformacao. Ciclicos nao drenados e controle por
# tensao estao em soiltest/em_desenvolvimento/ (mesmo script com SOMENTE_VALIDADO = False).
SOMENTE_VALIDADO = False   # VERSAO EM DESENVOLVIMENTO: libera ciclico nao drenado e controle por tensao

# =========================== CONFIG (valores de TESTE) ===========================
CONFIG = {
    "interativo": True,                # True: pergunta tudo no console
    "modelo": "HS",                    # MC | LE | HS | HSsmall | MCC | SS
    "drenagem": "D",                   # D | UA | UB | UC | NP (as validas dependem do modelo)
    "valores": {},                     # sobrescreve valores de teste quando interativo=False. Ex.: {"phi": 33, "cref": 2}
    "porta_input": 10000,
    "espera_soiltest_s": 90,

    # Consolidacao inicial (Triaxial, DSS, CDSS, Triaxial ciclico). K0: None = automatico
    # (K0nc se informado; senao Jaky 1 - sen(phi'); MCC: a partir de M; sem phi: nu/(1-nu)).
    "consolidacao": {"tipo": "Isotropic", "K0": None},      # tipo: "Isotropic" | "K0"

    # Pre-adensamento (so HS, HS small, MCC, Soft Soil; no MC e no LE o SoilTest nao deixa editar).
    #   "nenhum"  : sem pre-adensamento
    #   "pressao" : sigma'p = valor (kPa), tensao vertical de pre-adensamento, vale para todos os ensaios
    #   "OCR"     : sigma'p = OCR x sigma'v0, com sigma'v0 lida do proprio ensaio (nao se aplica a Oedometer/CRS,
    #               que partem de tensao zero)
    "preadensamento": {"modo": "nenhum", "valor": 0},

    "triaxial": {
        "rodar": True,
        "pressoes_kPa": [50, 100, 200],            # pressoes confinantes (uma curva por pressao)
        "comportamentos": ["Drained"],             # "Drained", "Undrained" ou ambos
        "MaximumStrain": 15,                       # %
        "Steps": 100,
    },
    "oedometer": {
        "rodar": None,                             # None = padrao do modelo (desligado em MCC e Soft Soil)
        # Siginc e INCREMENTAL por fase (kPa, negativo = compressao). Aqui: carrega ate 400 kPa e descarrega ate 100.
        "fases": [{"Duration": 1, "Siginc": -25, "Steps": 10}, {"Duration": 1, "Siginc": -25, "Steps": 10},
                  {"Duration": 1, "Siginc": -50, "Steps": 10}, {"Duration": 1, "Siginc": -100, "Steps": 10},
                  {"Duration": 1, "Siginc": -200, "Steps": 10}, {"Duration": 1, "Siginc": 300, "Steps": 10}],
    },
    "crs": {
        "rodar": False,
        # Epsinc e a deformacao axial TOTAL da fase em % (negativo = compressao).
        "fases": [{"Duration": 1, "Epsinc": -5, "Steps": 50}],
    },
    "dss": {
        "rodar": False,
        "pressoes_kPa": [50, 100, 200],            # tensao vertical efetiva inicial (AbsSigyyinit)
        "comportamentos": ["Drained"],
        "MaximumShearStrain": 10,                  # %
        "Steps": 100,
    },
    "cdss": {                                      # cisalhamento simples ciclico
        "rodar": False,
        "pressoes_kPa": [100],
        "comportamentos": ["Drained"],             # "Undrained" mostra a geracao de poropressao
        "InitialStaticShear": 0,                   # kPa
        "controle": "Strain",                      # "Strain" (amplitude em %) | "Stress" (amplitude em kPa)
        "amplitude": 0.5,
        "ciclos": 3,
        "passos_por_quarto": 20,
        "duracao_por_ciclo": 1,
    },
    "triaxial_ciclico": {
        "rodar": False,
        "pressoes_kPa": [100],
        "comportamentos": ["Drained"],
        "InitialAxialStressinc": 0,                # kPa
        "controle": "Strain",                      # "Strain" (amplitude em %) | "Stress" (amplitude em kPa)
        "amplitude": 0.5,
        "ciclos": 3,
        "passos_por_quarto": 20,
        "duracao_por_ciclo": 1,
    },
    # Corte de dilatancia (so HS e HS small): limita a dilatacao quando o indice de vazios chega a eMax.
    # Funciona no triaxial DRENADO (visto: eps_v max 2,2 % -> 1,34 % com eInit 0,5 e eMax 0,52); NAO muda o nao drenado.
    # Valores de teste: use o e_init do ensaio e o e_max do material.
    "dilatancy_cutoff": {"ligar": False, "eInit": 0.5, "eMax": 0.52},
}
# ===================================================================================

MODELOS = {
    "MC":      {"nome": "Mohr-Coulomb", "numero": 2, "dren": ["D", "UA", "UB", "UC", "NP"], "precons": False, "oed": True},
    "LE":      {"nome": "Linear Elastic", "numero": 1, "dren": ["D", "UA", "UC", "NP"], "precons": False, "oed": True},
    "HS":      {"nome": "Hardening Soil", "numero": 3, "dren": ["D", "UA", "UB"], "precons": True, "oed": True},
    "HSsmall": {"nome": "HS small", "numero": 4, "dren": ["D", "UA", "UB"], "precons": True, "oed": True},
    "MCC":     {"nome": "Modified Cam-Clay", "numero": 8, "dren": ["D", "UA"], "precons": True, "oed": False},
    "SS":      {"nome": "Soft Soil", "numero": 5, "dren": ["D", "UA"], "precons": True, "oed": False},
}
# O echo mostra "Undrained A (1)"; a conferencia usa a marca (regex).
DRENAGENS = {
    "D":  {"rotulo": "Drained", "marca": r"^drained", "nomes": ["Drained", 0]},
    "UA": {"rotulo": "Undrained A (parametros efetivos)", "marca": r"^undrained\s*\(?a\)?", "nomes": ["Undrained A", 1]},
    "UB": {"rotulo": "Undrained B (resistencia nao drenada su)", "marca": r"^undrained\s*\(?b\)?", "nomes": ["Undrained B", 2]},
    "UC": {"rotulo": "Undrained C (parametros totais: su e nuU)", "marca": r"^undrained\s*\(?c\)?", "nomes": ["Undrained C", 3]},
    "NP": {"rotulo": "Non-porous (sem poropressao)", "marca": r"non.?porous", "nomes": ["Non-porous", 4]},
}
# Ensaios que tem Consolidation/K0 e os que partem de tensao zero (fases)
ENSAIOS_NOMES = {"Triaxial": "Triaxial", "Oedometer": "Edometro", "CRS": "CRS", "DSS": "DSS",
                 "CDSS": "CDSS (cisalhamento simples ciclico)", "CycTriaxial": "Triaxial ciclico"}
CHAVE_CFG = {"Triaxial": "triaxial", "Oedometer": "oedometer", "CRS": "crs", "DSS": "dss", "CDSS": "cdss",
             "CycTriaxial": "triaxial_ciclico"}
PREFIXO_ARQ = {"Triaxial": "triaxial", "Oedometer": "oedometer", "CRS": "crs", "DSS": "dss", "CDSS": "cdss",
               "CycTriaxial": "cyctriaxial"}
COM_CONSOLIDACAO = ("Triaxial", "DSS", "CDSS", "CycTriaxial")
COM_PRESSOES = ("Triaxial", "DSS", "CDSS", "CycTriaxial")
ORDEM_ENSAIOS = ("Triaxial", "Oedometer", "CRS", "DSS", "CDSS", "CycTriaxial")


def parametros(modelo, dren):
    """Lista de (chave, aliases do atributo no Input em minusculas, rotulo, valor de teste)."""
    su = ("sURef", ["suref"], "su (kPa)", 50)
    if modelo == "MC":
        if dren == "UB":
            return [("ERef", ["eref"], "E' (kPa)", 30000), ("nu", ["nu"], "nu'", 0.3), su]
        if dren == "UC":
            return [("ERef", ["eref"], "E (kPa)", 30000), ("nuU", ["nuu"], "nu_u (use ~0,495)", 0.495), su]
        return [("ERef", ["eref"], "E' (kPa)", 30000), ("nu", ["nu"], "nu'", 0.3), ("cRef", ["cref"], "c' (kPa)", 5),
                ("phi", ["phi"], "phi' (graus)", 30), ("psi", ["psi"], "psi (graus)", 0)]
    if modelo == "LE":
        if dren == "UC":
            return [("ERef", ["eref"], "E (kPa)", 30000), ("nuU", ["nuu"], "nu_u (use ~0,495)", 0.495)]
        return [("ERef", ["eref"], "E' (kPa)", 30000), ("nu", ["nu"], "nu'", 0.3)]
    if modelo in ("HS", "HSsmall"):
        p = [("E50ref", ["e50ref"], "E50ref (kPa)", 40000), ("Eoedref", ["eoedref"], "Eoedref (kPa)", 40000),
             ("Eurref", ["eurref"], "Eurref (kPa)", 120000), ("m", ["powerm"], "expoente m", 0.5),
             ("nuur", ["nuur"], "nu_ur", 0.2), ("pref", ["pref"], "pref (kPa)", 100)]
        if dren == "UB":
            p.append(su)
        else:
            p += [("cref", ["cref"], "c' ref (kPa)", 1), ("phi", ["phi"], "phi' (graus)", 35), ("psi", ["psi"], "psi (graus)", 5)]
        if modelo == "HSsmall":
            p += [("G0ref", ["g0ref"], "G0ref (kPa)", 120000), ("gamma07", ["gamma07"], "gamma0.7", 2e-4)]
        p += [("K0nc", ["k0nc"], "K0nc (vazio = automatico)", None), ("Rf", ["rf"], "Rf (vazio = 0.9)", None)]
        return p
    if modelo == "MCC":
        # O SoilTest recusa o material se PhiInter e CInter forem ambos zero.
        return [("lambda", ["lambda"], "lambda (inclinacao e x ln p)", 0.1), ("kappa", ["kappa"], "kappa", 0.02),
                ("M", ["m"], "M (inclinacao da linha de estado critico)", 1.2), ("nuur", ["nuur"], "nu_ur", 0.2),
                ("eInit", ["einit"], "e_init", 1.0), ("PhiInter", ["phiinter"], "phi da interface (graus; o SoilTest exige > 0)", 25)]
    if modelo == "SS":
        return [("lambdaModified", ["lambdamodified"], "lambda* (modificado)", 0.1),
                ("kappaModified", ["kappamodified"], "kappa* (modificado; < lambda*)", 0.02),
                ("cRef", ["cref"], "c' (kPa)", 1), ("phi", ["phi"], "phi' (graus)", 25), ("psi", ["psi"], "psi (graus)", 0),
                ("nuur", ["nuur"], "nu_ur", 0.15)]
    return []


AQUI = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
_linhas = []


def log(msg=""):
    msg = str(msg)
    print(msg)
    _linhas.append(msg)


def tentar(rotulo, fn, limite=1500):
    try:
        v = fn()
        r = repr(v)
        log("[OK ] {} -> {}".format(rotulo, r if len(r) <= limite else r[:limite] + "..."))
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
        return [n for n in dir(obj) if not n.startswith("_")]
    except Exception:
        return []


def achar_attr(obj, candidatos):
    mapa = {n.lower(): n for n in nomes(obj)}
    for c in candidatos:
        if c.lower() in mapa:
            return mapa[c.lower()]
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
    try:
        txt = str(mat.echo())
    except Exception:
        return None
    m = re.search(r"\b{}:\s*(.+?)\s*\((-?\d+)\)".format(re.escape(chave)), txt)
    return (m.group(1).strip(), int(m.group(2))) if m else None


def fmt_num(x):
    x = float(x)
    return str(int(x)) if x.is_integer() else str(x)


def nome_ensaio(comp, pressao):
    return "{}_{}kPa".format("CD" if comp == "Drained" else "CU", fmt_num(pressao).replace(".", "p"))


# ------------------------------------------------------------------ consolidacao K0 automatica
def k0_automatico(modelo, p):
    """(valor, origem) do K0 sugerido para consolidar o corpo de prova."""
    if p.get("K0nc") is not None:
        return float(p["K0nc"]), "K0nc do material"
    if modelo == "MCC" and p.get("M") is not None:
        sen = 3 * p["M"] / (6 + p["M"])          # M = 6 sen(phi_cs)/(3 - sen(phi_cs))
        return round(1 - sen, 4), "1 - sen(phi_cs), com phi_cs obtido de M"
    if p.get("phi") is not None:
        return round(1 - math.sin(math.radians(p["phi"])), 4), "Jaky: 1 - sen(phi')"
    nu = p.get("nu", p.get("nuU"))
    if nu is not None:
        return round(nu / (1 - nu), 4), "elastico: nu/(1 - nu)"
    return 0.5, "padrao"


# ------------------------------------------------------------------ entrada do usuario
def ler_numero(texto, padrao):
    while True:
        resp = input("  {} [{}]: ".format(texto, "" if padrao is None else padrao)).strip().replace(",", ".")
        if not resp:
            return padrao
        try:
            return float(resp)
        except ValueError:
            print("   Valor invalido, digite um numero (ou Enter).")


def ler_inteiro(texto, padrao):
    return int(round(ler_numero(texto, padrao)))


def ler_lista(texto, padrao):
    while True:
        resp = input("  {} [{}]: ".format(texto, ", ".join(fmt_num(x) for x in padrao))).strip()
        if not resp:
            return list(padrao)
        try:
            if ";" in resp:
                v = [float(x.replace(",", ".")) for x in resp.split(";") if x.strip()]
            else:
                v = [float(x) for x in resp.replace(",", " ").split()]
            if v:
                return v
        except ValueError:
            pass
        print("   Nao entendi. Digite numeros separados por virgula ou espaco (ex.: 50, 100, 200), ou Enter para manter.")


def sim_nao(texto, padrao):
    while True:
        resp = input("  {} (s/n) [{}]: ".format(texto, "s" if padrao else "n")).strip().lower()
        if not resp:
            return bool(padrao)
        if resp in ("s", "n"):
            return resp == "s"
        print("   Resposta invalida: digite s ou n (ou Enter para manter o padrao).")


def escolher(titulo, opcoes, padrao):
    """opcoes: lista de (chave, rotulo). Aceita o numero ou a chave; Enter = padrao."""
    print("  {}:".format(titulo))
    for i, (k, r) in enumerate(opcoes, 1):
        print("    {}) {}{}".format(i, r, "   <- padrao" if k == padrao else ""))
    while True:
        resp = input("  Escolha (numero) [{}]: ".format(padrao)).strip()
        if not resp:
            return padrao
        if resp.isdigit() and 1 <= int(resp) <= len(opcoes):
            return opcoes[int(resp) - 1][0]
        for k, r in opcoes:
            if resp.lower() == k.lower():
                return k
        print("   Opcao invalida.")


def perguntar_comportamentos(cfg_t, dren):
    if dren == "NP":
        cfg_t["comportamentos"] = ["Drained"]
        print("  Material non-porous: o SoilTest so aceita ensaio drenado.")
        return
    atual = "A" if len(cfg_t["comportamentos"]) > 1 else cfg_t["comportamentos"][0][0]
    while True:
        resp = input("  Comportamento: D = drenado, U = nao drenado, A = ambos [{}]: ".format(atual)).strip().upper()
        if not resp:
            return
        if resp in ("D", "U", "A"):
            cfg_t["comportamentos"] = {"D": ["Drained"], "U": ["Undrained"], "A": ["Drained", "Undrained"]}[resp]
            return
        print("   Resposta invalida: digite D, U ou A (ou Enter para manter [{}]).".format(atual))


def perguntar_ciclico(cfg_t, nome_pressao, dren, chave_extra, rotulo_extra):
    print("\n  -- {} --".format(nome_pressao))
    cfg_t["pressoes_kPa"] = ler_lista("Pressoes iniciais em kPa ({})".format(
        "tensao vertical efetiva" if chave_extra == "InitialStaticShear" else "pressao confinante"), cfg_t["pressoes_kPa"])
    if SOMENTE_VALIDADO:
        cfg_t["comportamentos"] = ["Drained"]
        cfg_t["controle"] = "Strain"
        print("  Versao estavel: ciclico drenado e com controle de deformacao (o resto esta em desenvolvimento).")
    else:
        perguntar_comportamentos(cfg_t, dren)
    cfg_t[chave_extra] = ler_numero(rotulo_extra, cfg_t[chave_extra])
    if not SOMENTE_VALIDADO:
        cfg_t["controle"] = escolher("Tipo de controle do ensaio",
                                     [("Strain", "controle de deformacao (amplitude em %)"),
                                      ("Stress", "controle de tensao (amplitude em kPa)")], cfg_t["controle"])
    padrao_amp = cfg_t["amplitude"]
    if cfg_t["controle"] == "Stress" and padrao_amp < 5:
        padrao_amp = 20
    if cfg_t["controle"] == "Strain" and padrao_amp >= 5:
        padrao_amp = 0.5
    cfg_t["amplitude"] = ler_numero("Amplitude ({})".format("%" if cfg_t["controle"] == "Strain" else "kPa"), padrao_amp)
    cfg_t["ciclos"] = ler_inteiro("Numero de ciclos", cfg_t["ciclos"])
    cfg_t["passos_por_quarto"] = ler_inteiro("Passos por quarto de ciclo", cfg_t["passos_por_quarto"])
    cfg_t["duracao_por_ciclo"] = ler_numero("Duracao por ciclo", cfg_t["duracao_por_ciclo"])


def perguntar(cfg):
    print("\n=== Entrada de dados (Enter mantem o valor entre colchetes) ===")
    print("    Siglas e simbolos (q, eps_a, CD/CU, OCR...): veja o glossario.md gravado na pasta de saida.")
    cfg["modelo"] = escolher("Modelo constitutivo", [(k, v["nome"]) for k, v in MODELOS.items()], cfg["modelo"])
    m = MODELOS[cfg["modelo"]]
    padrao = cfg["drenagem"] if cfg["drenagem"] in m["dren"] else m["dren"][0]
    cfg["drenagem"] = escolher("Tipo de drenagem do material", [(d, DRENAGENS[d]["rotulo"]) for d in m["dren"]], padrao)
    dren = cfg["drenagem"]
    print("\n  Parametros do material:")
    cfg["valores"] = {}
    for chave, _al, rotulo, padrao_v in parametros(cfg["modelo"], dren):
        cfg["valores"][chave] = ler_numero(rotulo, padrao_v)
    if cfg["modelo"] in ("HS", "HSsmall"):
        dil = cfg["dilatancy_cutoff"]
        dil["ligar"] = sim_nao("Ligar corte de dilatancia (dilatancy cut-off)?", dil["ligar"])
        if dil["ligar"]:
            dil["eInit"] = ler_numero("e_init (indice de vazios inicial)", dil["eInit"])
            dil["eMax"] = ler_numero("e_max (indice de vazios maximo; a dilatacao para aqui)", dil["eMax"])

    # ---- quais ensaios
    print("\n  Ensaios a rodar:")
    cfg["triaxial"]["rodar"] = sim_nao("Triaxial", cfg["triaxial"]["rodar"])
    padrao_oed = cfg["oedometer"]["rodar"] if cfg["oedometer"]["rodar"] is not None else m["oed"]
    if not m["oed"]:
        print("  Aviso: no MCC e no Soft Soil o edometro e o CRS partem de tensao zero e dao deformacao exagerada "
              "(MCC: 27 % em 100 kPa no teste). Por isso vem desligados.")
    cfg["oedometer"]["rodar"] = sim_nao("Edometro", padrao_oed)
    cfg["crs"]["rodar"] = sim_nao("CRS (compressao a velocidade de deformacao constante)", cfg["crs"]["rodar"])
    cfg["dss"]["rodar"] = sim_nao("DSS (cisalhamento simples)", cfg["dss"]["rodar"])
    cfg["cdss"]["rodar"] = sim_nao("CDSS (cisalhamento simples ciclico)", cfg["cdss"]["rodar"])
    cfg["triaxial_ciclico"]["rodar"] = sim_nao("Triaxial ciclico", cfg["triaxial_ciclico"]["rodar"])

    # ---- consolidacao e pre-adensamento
    if any(cfg[CHAVE_CFG[t]]["rodar"] for t in COM_CONSOLIDACAO):
        print("\n  Consolidacao inicial (Triaxial, DSS, CDSS e Triaxial ciclico):")
        cons = cfg["consolidacao"]
        cons["tipo"] = escolher("Tipo de consolidacao", [("Isotropic", "isotropica (sigma_x = sigma_y)"),
                                                         ("K0", "K0 (sigma_x = K0 x sigma_y)")], cons["tipo"])
        if cons["tipo"] == "K0":
            k0a, origem = k0_automatico(cfg["modelo"], {k: float(v) for k, v in cfg["valores"].items() if v is not None})
            print("  Sugestao de K0: {} ({})".format(k0a, origem))
            cons["K0"] = ler_numero("K0 do ensaio", cons["K0"] if cons["K0"] is not None else k0a)
    if m["precons"]:
        print("\n  Pre-adensamento (o SoilTest recebe a pressao de pre-adensamento vertical sigma'p):")
        pre = cfg["preadensamento"]
        pre["modo"] = escolher("Como informar", [("nenhum", "sem pre-adensamento (normalmente adensado)"),
                                                 ("pressao", "pressao de pre-adensamento sigma'p (kPa)"),
                                                 ("OCR", "OCR (sigma'p = OCR x sigma'v0 de cada ensaio)")], pre["modo"])
        if pre["modo"] == "pressao":
            pre["valor"] = ler_numero("sigma'p (kPa)", pre["valor"] or 100)
        elif pre["modo"] == "OCR":
            pre["valor"] = ler_numero("OCR", pre["valor"] or 2)
    else:
        cfg["preadensamento"]["modo"] = "nenhum"
        print("\n  Pre-adensamento: no {} o SoilTest nao permite editar a pressao de pre-adensamento (somente leitura).".format(m["nome"]))

    # ---- detalhes de cada ensaio
    if cfg["triaxial"]["rodar"]:
        tri = cfg["triaxial"]
        print("\n  -- Triaxial --")
        tri["pressoes_kPa"] = ler_lista("Pressoes confinantes sigma3 (tensao lateral efetiva) em kPa", tri["pressoes_kPa"])
        perguntar_comportamentos(tri, dren)
        tri["MaximumStrain"] = ler_numero("Deformacao axial maxima (%)", tri["MaximumStrain"])
    if cfg["crs"]["rodar"]:
        print("\n  -- CRS --")
        total = abs(cfg["crs"]["fases"][0]["Epsinc"])
        total = ler_numero("Deformacao axial total de compressao (%)", total)
        cfg["crs"]["fases"][0]["Epsinc"] = -abs(total)
    if cfg["dss"]["rodar"]:
        d = cfg["dss"]
        print("\n  -- DSS --")
        d["pressoes_kPa"] = ler_lista("Tensoes verticais efetivas iniciais sigma_v0 em kPa", d["pressoes_kPa"])
        perguntar_comportamentos(d, dren)
        d["MaximumShearStrain"] = ler_numero("Distorcao maxima (%)", d["MaximumShearStrain"])
    if cfg["cdss"]["rodar"]:
        perguntar_ciclico(cfg["cdss"], "CDSS", dren, "InitialStaticShear", "Cisalhamento estatico inicial (kPa)")
    if cfg["triaxial_ciclico"]["rodar"]:
        perguntar_ciclico(cfg["triaxial_ciclico"], "Triaxial ciclico", dren, "InitialAxialStressinc",
                          "Incremento axial inicial de tensao (kPa)")
    print("")
    return cfg


# ------------------------------------------------------------------ Input: material
def definir_com_candidatos(mat, atributo, candidatos, marca):
    for c in candidatos:
        try:
            mat.setproperties(atributo, c)
        except Exception as e:
            log("    {}={!r} recusado ({})".format(atributo, c, str(e).splitlines()[0][:80]))
            continue
        r = linha_echo(mat, atributo)
        if r and re.search(marca, r[0].lower()):
            log("[OK ] {} = {!r} -> {} ({})".format(atributo, c, r[0], r[1]))
            return True
        log("    {}={!r} aceito, mas o echo mostra {}".format(atributo, c, r))
    return False


def criar_material(g, ident, modelo, dren, valores, dil):
    mat = None
    for lista in ("Soils", "Materials"):
        try:
            for m in getattr(g, lista):
                if str(valor(m.Identification)) == ident:
                    mat = m
                    break
        except Exception:
            pass
        if mat is not None:
            break
    if mat is not None:
        log("Material '{}' ja existe: reutilizando.".format(ident))
    else:
        ok, mat = tentar("g_i.soilmat()", lambda: g.soilmat())
        if not ok:
            return None
        tentar("Identification", lambda: mat.setproperties("Identification", ident))
    info = MODELOS[modelo]
    ok = definir_com_candidatos(mat, "SoilModel", [info["numero"], info["nome"]], re.escape(info["nome"].lower().split()[0]))
    if not ok:
        log("ATENCAO: nao confirmei o SoilModel pelo echo; confira no Input.")
    dr = DRENAGENS[dren]
    if not definir_com_candidatos(mat, "DrainageType", dr["nomes"], dr["marca"]):
        log("ATENCAO: nao confirmei o DrainageType pelo echo; confira no Input.")
    if valores.get("K0nc") is not None or valores.get("Rf") is not None:
        tentar("UseDefaults = False (libera Rf/K0nc)", lambda: mat.setproperties("UseDefaults", False))
    falhas = []
    for chave, aliases, rotulo, _p in parametros(modelo, dren):
        v = valores.get(chave)
        if v is None:
            continue
        attr = achar_attr(mat, aliases)
        if attr is None:
            log("[ERR] parametro {} nao existe neste material (aliases {}).".format(chave, aliases))
            log("      Atributos: {}".format(", ".join(nomes(mat))))
            falhas.append(chave)
            continue
        ok, _ = tentar("{} ({}) = {}".format(chave, attr, v), lambda a=attr, v=v: mat.setproperties(a, v))
        if not ok:
            falhas.append(chave)
    if dil and dil.get("ligar"):
        for canon, aliases, v in (("DilatancyCutOff", ["dilatancycutoff"], True), ("eInit", ["einit"], dil["eInit"]),
                                  ("eMax", ["emax"], dil["eMax"])):
            attr = achar_attr(mat, aliases)
            if attr is None:
                log("[ERR] {} nao existe neste material.".format(canon))
                falhas.append(canon)
                continue
            ok, _ = tentar("{} ({}) = {}".format(canon, attr, v), lambda a=attr, v=v: mat.setproperties(a, v))
            if not ok:
                falhas.append(canon)
    if falhas:
        log("ATENCAO: nao aplicados: {}".format(falhas))
    return mat


def propagar_corte(g, dil):
    """O Material do SoilTest e uma copia reduzida: os atributos do corte podem nao aparecer, mas o corte
    viaja com o material (visto no triaxial drenado). Aqui so se tenta aplica-los tambem la."""
    log("Atributos do Material no SoilTest: {}".format(", ".join(nomes(g.Material))))
    estado = {}
    for canon, aliases, v in (("DilatancyCutOff", ["dilatancycutoff"], True), ("eInit", ["einit"], dil["eInit"]),
                              ("eMax", ["emax"], dil["eMax"])):
        attr = achar_attr(g.Material, aliases)
        if attr is None:
            estado[canon] = "nao exposto no Material do SoilTest"
            continue
        ok, _ = tentar("SoilTest Material.{} = {}".format(attr, v), lambda a=attr, v=v: g.Material.setproperties(a, v))
        estado[canon] = "aplicado" if ok else "recusado"
    log("Corte de dilatancia no SoilTest: {} (confira a dilatacao maxima dos ensaios drenados).".format(estado))
    return estado


# ------------------------------------------------------------------ SoilTest
def conectar_soiltest(porta, senha, espera):
    from plxscripting.easy import new_server
    limite = time.time() + espera
    ultimo = None
    while time.time() < limite:
        try:
            s, g = new_server("localhost", int(porta), password=senha)
            if hasattr(g, "Triaxial"):
                return g
            ultimo = "a porta {} nao e o SoilTest".format(porta)
        except Exception as e:
            ultimo = str(e)
        time.sleep(2)
    raise RuntimeError("Nao consegui conectar ao SoilTest na porta {}: {}".format(porta, ultimo))


def descobrir_porta(senha, espera, excluir):
    from plxscripting.easy import new_server
    limite = time.time() + espera
    while time.time() < limite:
        for p in range(10000, 10031):
            if p == excluir:
                continue
            try:
                s, g = new_server("localhost", p, password=senha)
                if hasattr(g, "Triaxial"):
                    return p
            except Exception:
                continue
        time.sleep(3)
    return None


def serie(obj):
    return [float(v) for v in obj]


def serie_opc(r, nome, n, sinal=1.0, escala=1.0):
    """Le Results.<nome>; zeros se nao existir ou se o tamanho nao bater."""
    try:
        v = serie(getattr(r, nome))
        if len(v) == n:
            return [sinal * escala * x for x in v]
    except Exception:
        pass
    return [0.0] * n


# ------------------------------------------------------------------ leitura dos resultados
def ler_triaxial(t):
    r = t.Results
    eps = serie(r.Epsyy)
    n = len(eps)
    return {"eps_a_pct": [-v * 100 for v in eps],
            "ev_pct": [-v * 100 for v in serie(r.TotalVolumetricStrain)],
            "q_kPa": serie(r.DeviatoricStress),
            "p_kPa": [-v for v in serie(r.MeanEffStress)],
            "sig_a_kPa": [-v for v in serie(r.SigyyE)],
            "sig_r_kPa": [-v for v in serie(r.SigxxE)],
            "du_kPa": serie_opc(r, "PExcess", n, sinal=-1.0)}      # du = -PExcess (sinal PLAXIS)


def ler_oed_crs(t):
    r = t.Results
    ev = serie(r.Epsyy)
    n = len(ev)
    return {"tempo": serie(r.Time), "ev_pct": [-v * 100 for v in ev],
            "sig_v_kPa": [-v for v in serie(r.SigyyE)], "sig_h_kPa": [-v for v in serie(r.SigxxE)],
            "du_kPa": serie_opc(r, "PExcess", n, sinal=-1.0)}


def ler_dss(t):
    r = t.Results
    gam = serie(r.Gamxy)
    n = len(gam)
    return {"tempo": serie_opc(r, "Time", n), "gamma_pct": [v * 100 for v in gam], "tau_kPa": serie(r.Sigxy),
            "sig_v_kPa": [-v for v in serie(r.SigyyE)], "sig_h_kPa": [-v for v in serie(r.SigxxE)],
            "ev_pct": serie_opc(r, "TotalVolumetricStrain", n, sinal=-100.0),
            "du_kPa": serie_opc(r, "PExcess", n, sinal=-1.0)}


def ler_cyc_triaxial(t):
    r = t.Results
    eps = serie(r.Epsyy)
    n = len(eps)
    sa = [-v for v in serie(r.SigyyE)]
    sr = [-v for v in serie(r.SigxxE)]
    return {"tempo": serie_opc(r, "Time", n), "eps_a_pct": [-v * 100 for v in eps],
            "ev_pct": serie_opc(r, "TotalVolumetricStrain", n, sinal=-100.0),
            "q_kPa": [a - b for a, b in zip(sa, sr)],            # q com sinal (extensao < 0)
            "p_kPa": serie_opc(r, "MeanEffStress", n, sinal=-1.0),
            "sig_a_kPa": sa, "sig_r_kPa": sr, "du_kPa": serie_opc(r, "PExcess", n, sinal=-1.0)}


LEITORES = {"Triaxial": ler_triaxial, "DSS": ler_dss, "CDSS": ler_dss, "CycTriaxial": ler_cyc_triaxial}


# ------------------------------------------------------------------ configurar e rodar ensaios
def aplicar(t, rotulo, pares):
    """Aplica (atributo, valor) em ordem: primeiro tudo junto; se recusar, um a um (mostra qual falhou)."""
    flat = [x for kv in pares for x in kv]
    try:
        t.setproperties(*flat)
        log("[OK ] {}: {}".format(rotulo, ", ".join("{}={}".format(k, v) for k, v in pares)))
        return True
    except Exception as e:
        log("    {}: conjunto recusado ({}); aplicando um a um".format(rotulo, str(e).splitlines()[0][:100]))
    ok = True
    for k, v in pares:
        try:
            t.setproperties(k, v)
        except Exception as e:
            log("[ERR] {} = {!r}: {}".format(k, v, str(e).splitlines()[0][:110]))
            ok = False
    return ok


def montar_pares(tipo, cfg_t, comp, pressao, cons_tipo):
    base = [("Behaviour", comp), ("Consolidation", cons_tipo)]
    if tipo == "Triaxial":
        return base + [("Direction", "Compression"), ("CellPressure", pressao),
                       ("MaximumStrain", cfg_t["MaximumStrain"]), ("Steps", cfg_t["Steps"])]
    if tipo == "DSS":
        return base + [("AbsSigyyinit", pressao), ("MaximumShearStrain", cfg_t["MaximumShearStrain"]),
                       ("Steps", cfg_t["Steps"])]
    ciclo = [("NumberOfCycles", int(cfg_t["ciclos"])), ("NumberOfStepsPerQuarterCycle", int(cfg_t["passos_por_quarto"])),
             ("DurationPerCycle", cfg_t["duracao_por_ciclo"])]
    forca = cfg_t["controle"] == "Strain"
    if tipo == "CDSS":
        amp = "ShearStrainAmplitude" if forca else "ShearStressAmplitude"
        return base + [("AbsSigyyinit", pressao), ("InitialStaticShear", cfg_t["InitialStaticShear"]),
                       ("TestControlType", cfg_t["controle"]), (amp, cfg_t["amplitude"])] + ciclo
    amp = "AxialStrainAmplitude" if forca else "AxialStressAmplitude"
    return base + [("CellPressure", pressao), ("InitialAxialStressinc", cfg_t["InitialAxialStressinc"]),
                   ("TestControlType", cfg_t["controle"]), (amp, cfg_t["amplitude"])] + ciclo


def sigma0(t):
    """Tensoes efetivas iniciais lidas do proprio ensaio (compressao positiva); None se nao der para ler."""
    out = {}
    for k, a in (("sxx", "Sigxxinit"), ("syy", "Sigyyinit")):
        try:
            out[k] = -float(valor(getattr(t, a)))
        except Exception:
            out[k] = None
    return out


def aplicar_preadensamento(t, tipo, pre, modelo, sv0, ext):
    """Define PreconsolidationPressure no ensaio. Devolve sigma'p aplicada (kPa) ou 0."""
    modo = pre["modo"]
    if modo == "nenhum" or not MODELOS[modelo]["precons"]:
        return 0.0
    if modo == "pressao":
        pc = float(pre["valor"])
    else:
        if tipo in ("Oedometer", "CRS"):
            log("   OCR nao se aplica ao {} (parte de tensao zero); use o modo 'pressao'. Sem pre-adensamento.".format(tipo))
            return 0.0
        if not sv0:
            log("   Nao consegui ler sigma'v0 do ensaio; OCR ignorado.")
            return 0.0
        pc = float(pre["valor"]) * sv0
        ext["OCR_pedido"] = float(pre["valor"])
    if pc <= 0:
        return 0.0
    ok, _ = tentar("PreconsolidationPressure = {:.3f} kPa".format(pc), lambda: t.setproperties("PreconsolidationPressure", pc))
    if not ok:
        return 0.0
    if sv0:
        ext["OCR_aplicado"] = pc / sv0
        if pc < sv0 * 0.999:
            log("   ATENCAO: sigma'p ({:.1f}) < sigma'v0 ({:.1f}): o corpo de prova fica normalmente adensado.".format(pc, sv0))
    return pc


def rodar_ensaio(g, tipo, nome, cfg_t, comp, pressao, ctx):
    """Triaxial, DSS, CDSS e Triaxial ciclico. Devolve (dados, ext) ou (None, None)."""
    t = getattr(g, tipo)
    cons = ctx["consolidacao"]
    if not aplicar(t, "{} {}".format(tipo, nome), montar_pares(tipo, cfg_t, comp, pressao, cons["tipo"])):
        return None, None
    ext = {"consolidacao": cons["tipo"]}
    if cons["tipo"] == "K0":
        if not aplicar(t, "K0", [("K0", ctx["k0"])]):
            log("   O K0 nao foi aceito; ensaio ignorado (rodaria isotropico sem aviso).")
            return None, None
        ext["K0"] = ctx["k0"]
    s = sigma0(t)
    ext["sigma0_kPa"] = s
    if s["sxx"] is not None and s["syy"] is not None:
        log("   Tensoes iniciais efetivas: sigma_y = {:.2f} kPa, sigma_x = {:.2f} kPa (K = {:.3f})".format(
            s["syy"], s["sxx"], s["sxx"] / s["syy"] if s["syy"] else float("nan")))
    sv0 = pressao if tipo in ("DSS", "CDSS") else (s["syy"] or pressao)
    ext["sigma_v0_kPa"] = sv0
    ext["pc_kPa"] = aplicar_preadensamento(t, tipo, ctx["preadensamento"], ctx["modelo"], sv0, ext)
    if ext["pc_kPa"]:
        ctx["pc_usados"].add(tipo)
    tentar("validate", lambda: g.validate(g.Material))
    ok, _ = tentar("calculate {} {}".format(tipo, nome), lambda: g.calculate(t))
    if not ok:
        return None, None
    try:
        return LEITORES[tipo](t), ext
    except Exception as e:
        log("Falha ao ler resultados de {}: {}".format(nome, e))
        return None, None


def configurar_fases(t, fases):
    while len(t.PhaseTable) < len(fases):
        t.addphase()
    while len(t.PhaseTable) > len(fases):
        t.deletephase(len(t.PhaseTable) - 1)
    for i, f in enumerate(fases):
        t.PhaseTable[i].setproperties(*[x for kv in f.items() for x in kv])


def rodar_fases(g, tipo, cfg_t, ctx):
    """Oedometer e CRS (tabela de fases, parte de tensao zero)."""
    t = getattr(g, tipo)
    ok, _ = tentar("{} fases".format(tipo), lambda: configurar_fases(t, cfg_t["fases"]))
    if not ok:
        return None, None
    ext = {}
    ext["pc_kPa"] = aplicar_preadensamento(t, tipo, ctx["preadensamento"], ctx["modelo"], None, ext)
    if ext["pc_kPa"]:
        ctx["pc_usados"].add(tipo)
    tentar("validate", lambda: g.validate(g.Material))
    ok, _ = tentar("calculate {}".format(tipo), lambda: g.calculate(t))
    if not ok:
        return None, None
    try:
        return ler_oed_crs(t), ext
    except Exception as e:
        log("Falha ao ler resultados do {}: {}".format(tipo, e))
        return None, None


def restaurar_preadensamento(g, tipos):
    for tipo in sorted(tipos):
        tentar("restaurar {}.PreconsolidationPressure = 0".format(tipo),
               lambda tp=tipo: getattr(g, tp).setproperties("PreconsolidationPressure", 0))


# ------------------------------------------------------------------ checagens teoricas (informativas)
def interp(x, y, xv):
    for i in range(1, len(x)):
        if (x[i - 1] - xv) * (x[i] - xv) <= 0 and x[i] != x[i - 1]:
            return y[i - 1] + (y[i] - y[i - 1]) * (xv - x[i - 1]) / (x[i] - x[i - 1])
    return None


def qf_mc(c, phi_deg, s3):
    s = math.sin(math.radians(phi_deg))
    return 2 * s / (1 - s) * (s3 + c / math.tan(math.radians(phi_deg)))


def checagem_triaxial(d, modelo, dren, p, pressao, comp, tri, ext):
    out = {"q_max_kPa": max(d["q_kPa"]), "dilatacao_max_pct": max(0.0, -min(d["ev_pct"]))}
    k0 = ext.get("consolidacao") == "K0"
    pc = ext.get("pc_kPa") or 0
    s = ext.get("sigma0_kPa") or {}
    s3 = s.get("sxx") or pressao                      # tensao confinante efetiva durante o cisalhamento
    try:
        esp = None
        if p.get("sURef") is not None:
            esp = ("2 x su", 2 * p["sURef"])
        elif comp == "Drained":
            if modelo in ("MC", "HS", "HSsmall", "SS"):
                c = p.get("cRef", p.get("cref", 0.0))
                esp = ("q_f Mohr-Coulomb", qf_mc(c, p["phi"], s3))
                out["qf_teorico_kPa"] = esp[1]
                if modelo in ("HS", "HSsmall") and not k0 and not pc:
                    phi = math.radians(p["phi"])
                    e50 = p["E50ref"] * ((c * math.cos(phi) + s3 * math.sin(phi)) /
                                         (c * math.cos(phi) + p["pref"] * math.sin(phi))) ** p["m"]
                    eps_50 = interp(d["q_kPa"], d["eps_a_pct"], 0.5 * esp[1])
                    if eps_50:
                        out["E50_simulado_kPa"] = 0.5 * esp[1] / (eps_50 / 100.0)
                        out["E50_formula_kPa"] = e50
            elif modelo == "LE":
                esp = ("q0 + E x eps_a (linear)", d["q_kPa"][0] + p["ERef"] * tri["MaximumStrain"] / 100.0)
            elif modelo == "MCC":
                esp = ("q no estado critico (3 M s3/(3-M); o ensaio pode nao chegar la)", 3 * p["M"] * s3 / (3 - p["M"]))
        elif modelo == "MCC" and not pc and not k0:
            lam, kap = p["lambda"], p["kappa"]
            esp = ("q_f nao drenado MCC normalmente adensado", p["M"] * pressao / 2 ** ((lam - kap) / lam))
        if esp:
            out["esperado"] = {"descricao": esp[0], "kPa": esp[1]}
    except Exception as e:
        log("   (checagem teorica ignorada: {})".format(e))
    return out


def checagem_fases(d, modelo, dren, p):
    """Edometro/CRS elastico (MC e LE): eps_v = sigma_v / E_oed."""
    out = {"pontos": len(d["ev_pct"]), "sigma_v_max_kPa": max(d["sig_v_kPa"]), "eps_v_max_pct": max(d["ev_pct"])}
    try:
        if modelo in ("MC", "LE") and dren in ("D", "UA", "NP") and p.get("ERef") and p.get("nu") is not None:
            E, nu = p["ERef"], p["nu"]
            eoed = E * (1 - nu) / ((1 + nu) * (1 - 2 * nu))
            i = max(range(len(d["ev_pct"])), key=lambda k: d["ev_pct"][k])
            out["E_oed_teorico_kPa"] = eoed
            out["eps_v_esperado_pct"] = 100.0 * d["sig_v_kPa"][i] / eoed
            out["eps_v_no_pico_pct"] = d["ev_pct"][i]
    except Exception as e:
        log("   (checagem teorica ignorada: {})".format(e))
    return out


def checagem_dss(d, modelo, dren, p, pressao, comp, ext):
    out = {"tau_max_kPa": max(d["tau_kPa"]), "dilatacao_max_pct": max(0.0, -min(d["ev_pct"]))}
    try:
        if modelo == "MC" and comp == "Drained" and ext.get("consolidacao") == "Isotropic" and not ext.get("pc_kPa") \
                and p.get("cRef") is not None and p.get("phi") is not None:
            phi = math.radians(p["phi"])
            out["esperado"] = {"descricao": "tau_max = c cos(phi) + sigma_v0 sen(phi) (MC, isotropico)",
                               "kPa": p["cRef"] * math.cos(phi) + pressao * math.sin(phi)}
        elif modelo == "LE" and dren in ("D", "UA", "NP") and p.get("ERef") and p.get("nu") is not None:
            G = p["ERef"] / (2 * (1 + p["nu"]))
            out["esperado"] = {"descricao": "tau = G x gamma_max, G = E/(2(1+nu)) (LE)",
                               "kPa": G * max(d["gamma_pct"]) / 100.0}
    except Exception as e:
        log("   (checagem teorica ignorada: {})".format(e))
    return out


def laco_metricas(x_frac, y, n_por_ciclo):
    """Ultimo ciclo: amplitudes, modulo secante (amplitude de y / amplitude de x) e amortecimento
    D = area do laco / (4 pi Ws), com Ws = 0.5 x ya x xa."""
    if n_por_ciclo <= 0 or len(x_frac) < n_por_ciclo + 1:
        return None
    xs, ys = x_frac[-(n_por_ciclo + 1):], y[-(n_por_ciclo + 1):]
    xa, ya = (max(xs) - min(xs)) / 2.0, (max(ys) - min(ys)) / 2.0
    if xa <= 0:
        return None
    area = abs(sum(0.5 * (ys[i] + ys[i + 1]) * (xs[i + 1] - xs[i]) for i in range(len(xs) - 1)))
    ws = 0.5 * ya * xa
    return {"amplitude_x_pct": 100 * xa, "amplitude_y_kPa": ya, "modulo_secante_kPa": ya / xa,
            "amortecimento_pct": 100.0 * area / (4 * math.pi * ws) if ws > 0 else None}


def checagem_ciclico(tipo, d, modelo, dren, p, comp, cfg_t):
    n_ciclo = 4 * int(cfg_t["passos_por_quarto"])
    # Os primeiros passos_por_quarto pontos sao uma fase inicial sem carga; depois vem os ciclos completos,
    # que comecam e terminam em zero (visto: 2 ciclos x 10 passos = 91 pontos; 3 x 20 = 261; 5 x 20 = 421).
    # Os ultimos n_ciclo passos sao, portanto, um ciclo completo.
    esperado_pontos = (4 * int(cfg_t["ciclos"]) + 1) * int(cfg_t["passos_por_quarto"]) + 1
    n = len(d["tempo"])
    out = {"pontos": n, "pontos_esperados": esperado_pontos}
    if n != esperado_pontos:
        log("   Aviso: {} pontos lidos; esperava {} ((4 x ciclos + 1) x passos + 1).".format(n, esperado_pontos))
    if tipo == "CDSS":
        m = laco_metricas([v / 100.0 for v in d["gamma_pct"]], d["tau_kPa"], n_ciclo)
        rot = "G_sec"
    else:
        m = laco_metricas([v / 100.0 for v in d["eps_a_pct"]], d["q_kPa"], n_ciclo)
        rot = "E_sec"
    if m:
        out["ultimo_ciclo"] = m
        out["rotulo_modulo"] = rot
    try:
        if modelo == "LE" and dren in ("D", "UA", "NP") and p.get("ERef") and p.get("nu") is not None and m:
            G = p["ERef"] / (2 * (1 + p["nu"]))
            if tipo == "CDSS":
                out["esperado"] = {"descricao": "G = E/(2(1+nu)) (LE)", "kPa": G}
            elif comp == "Drained":
                out["esperado"] = {"descricao": "E (LE, drenado)", "kPa": p["ERef"]}
            else:
                out["esperado"] = {"descricao": "E_u = 3G = 3E/(2(1+nu)) (LE, ~incompressivel)", "kPa": 3 * G}
    except Exception as e:
        log("   (checagem teorica ignorada: {})".format(e))
    return out


# ------------------------------------------------------------------ saida: CSV e graficos (um PNG por grafico)
def gravar_csv(caminho, dados):
    cols = list(dados)
    n = min(len(dados[c]) for c in cols)
    with open(caminho, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["passo"] + cols)
        for i in range(n):
            w.writerow([i] + [dados[c][i] for c in cols])


# (arquivo, coluna x, coluna y, rotulo x, rotulo y, titulo, opcoes)   opcoes: du=so se houver poropressao,
# invy=inverte y, logx=escala log em x
GRAFICOS = {
    "Triaxial": [
        ("triaxial_q_x_eps_a", "eps_a_pct", "q_kPa", "eps_a (%)", "q (kPa)", "Triaxial: q x eps_a", {}),
        ("triaxial_ev_x_eps_a", "eps_a_pct", "ev_pct", "eps_a (%)", "eps_v (%) [contracao +]", "Triaxial: eps_v x eps_a", {}),
        ("triaxial_du_x_eps_a", "eps_a_pct", "du_kPa", "eps_a (%)", "du (kPa) [acrescimo +]",
         "Triaxial: excesso de poropressao", {"du": True}),
        ("triaxial_trajetoria_p_q", "p_kPa", "q_kPa", "p' (kPa)", "q (kPa)", "Triaxial: trajetoria de tensoes p'-q", {}),
    ],
    "Oedometer": [
        ("oedometer_sigv_x_epsv", "ev_pct", "sig_v_kPa", "eps_v (%)", "sigma_v' (kPa)", "Edometro: tensao x deformacao",
         {"invy": True}),
        ("oedometer_epsv_x_logsigv", "sig_v_kPa", "ev_pct", "sigma_v' (kPa, escala log)", "eps_v (%)",
         "Edometro: eps_v x log sigma_v'", {"invy": True, "logx": True}),
    ],
    "CRS": [
        ("crs_sigv_x_epsv", "ev_pct", "sig_v_kPa", "eps_v (%)", "sigma_v' (kPa)", "CRS: tensao x deformacao", {}),
        ("crs_epsv_x_logsigv", "sig_v_kPa", "ev_pct", "sigma_v' (kPa, escala log)", "eps_v (%)",
         "CRS: eps_v x log sigma_v'", {"invy": True, "logx": True}),
        ("crs_du_x_tempo", "tempo", "du_kPa", "tempo", "du (kPa) [acrescimo +]", "CRS: excesso de poropressao", {"du": True}),
    ],
    "DSS": [
        ("dss_tau_x_gamma", "gamma_pct", "tau_kPa", "gamma_xy (%)", "tau_xy (kPa)", "DSS: tau x gamma", {}),
        ("dss_ev_x_gamma", "gamma_pct", "ev_pct", "gamma_xy (%)", "eps_v (%) [contracao +]", "DSS: eps_v x gamma", {}),
        ("dss_du_x_gamma", "gamma_pct", "du_kPa", "gamma_xy (%)", "du (kPa) [acrescimo +]",
         "DSS: excesso de poropressao", {"du": True}),
        ("dss_trajetoria_sigv_tau", "sig_v_kPa", "tau_kPa", "sigma_v' (kPa)", "tau_xy (kPa)",
         "DSS: trajetoria de tensoes efetivas", {}),
    ],
    "CDSS": [
        ("cdss_tau_x_gamma", "gamma_pct", "tau_kPa", "gamma_xy (%)", "tau_xy (kPa)", "CDSS: lacos tau x gamma", {}),
        ("cdss_gamma_x_tempo", "tempo", "gamma_pct", "tempo", "gamma_xy (%)", "CDSS: gamma x tempo", {}),
        ("cdss_tau_x_tempo", "tempo", "tau_kPa", "tempo", "tau_xy (kPa)", "CDSS: tau x tempo", {}),
        ("cdss_du_x_tempo", "tempo", "du_kPa", "tempo", "du (kPa) [acrescimo +]", "CDSS: excesso de poropressao", {"du": True}),
        ("cdss_trajetoria_sigv_tau", "sig_v_kPa", "tau_kPa", "sigma_v' (kPa)", "tau_xy (kPa)",
         "CDSS: trajetoria de tensoes efetivas", {}),
    ],
    "CycTriaxial": [
        ("cyctriaxial_q_x_eps_a", "eps_a_pct", "q_kPa", "eps_a (%)", "q (kPa)", "Triaxial ciclico: lacos q x eps_a", {}),
        ("cyctriaxial_eps_a_x_tempo", "tempo", "eps_a_pct", "tempo", "eps_a (%)", "Triaxial ciclico: eps_a x tempo", {}),
        ("cyctriaxial_q_x_tempo", "tempo", "q_kPa", "tempo", "q (kPa)", "Triaxial ciclico: q x tempo", {}),
        ("cyctriaxial_du_x_tempo", "tempo", "du_kPa", "tempo", "du (kPa) [acrescimo +]",
         "Triaxial ciclico: excesso de poropressao", {"du": True}),
        ("cyctriaxial_trajetoria_p_q", "p_kPa", "q_kPa", "p' (kPa)", "q (kPa)",
         "Triaxial ciclico: trajetoria de tensoes p'-q", {}),
    ],
}


# Rotulos dos eixos: simbolo + nome + sinal (o texto curto da tabela acima e trocado por este).
ROTULOS = {
    "eps_a (%)": r"$\varepsilon_a$ – deformação axial (%)",
    "q (kPa)": r"$q = \sigma'_a - \sigma'_r$ – tensão desviadora (kPa)",
    "eps_v (%) [contracao +]": r"$\varepsilon_v$ – deformação volumétrica (%) [contração +]",
    "eps_v (%)": r"$\varepsilon_v$ – deformação volumétrica (%)",
    "du (kPa) [acrescimo +]": r"$\Delta u$ – excesso de poropressão (kPa) [acréscimo +]",
    "p' (kPa)": r"$p'$ – tensão efetiva média (kPa)",
    "sigma_v' (kPa)": r"$\sigma'_v$ – tensão vertical efetiva (kPa)",
    "sigma_v' (kPa, escala log)": r"$\sigma'_v$ – tensão vertical efetiva (kPa, escala log)",
    "gamma_xy (%)": r"$\gamma_{xy}$ – distorção (%)",
    "tau_xy (kPa)": r"$\tau_{xy}$ – tensão cisalhante (kPa)",
    "tempo": "tempo (dia)",
}
# Nota de rodape de cada PNG (explica o nome das curvas)
NOTAS = {
    "Triaxial": "Curvas: CD = drenado, CU = não drenado; o número é a pressão confinante σ'3 (kPa). Compressão positiva. Siglas: glossario.md",
    "CycTriaxial": "Curvas: CD = drenado, CU = não drenado; o número é a pressão confinante σ'3 (kPa). Compressão positiva. Siglas: glossario.md",
    "DSS": "Curvas: CD = drenado, CU = não drenado; o número é a tensão vertical efetiva inicial σ'v0 (kPa). Siglas: glossario.md",
    "CDSS": "Curvas: CD = drenado, CU = não drenado; o número é a tensão vertical efetiva inicial σ'v0 (kPa). Siglas: glossario.md",
    "Oedometer": "Compressão positiva; tensão e deformação verticais, sem deformação lateral. Siglas: glossario.md",
    "CRS": "Compressão positiva; tensão e deformação verticais, sem deformação lateral. Siglas: glossario.md",
}


def graficos(pasta, titulo, todas):
    """todas: {tipo: {nome_da_curva: dados}}. Grava graficos/<arquivo>.png, um por grafico."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        log("Graficos nao gerados ({}); os CSV foram gravados.".format(e))
        return []
    sub = os.path.join(pasta, "graficos")
    os.makedirs(sub, exist_ok=True)
    gerados = []
    for tipo, series in todas.items():
        if not series:
            continue
        for arq, cx, cy, xl, yl, ti, op in GRAFICOS[tipo]:
            if op.get("du") and all(max(abs(v) for v in d[cy]) < 1e-6 for d in series.values()):
                log("   (sem excesso de poropressao: grafico {}.png omitido)".format(arq))
                continue
            fig, ax = plt.subplots(figsize=(7, 5))
            desenhou = False
            for nome, d in series.items():
                x, y = d[cx], d[cy]
                if op.get("logx"):
                    par = [(a, b) for a, b in zip(x, y) if a > 0]
                    if len(par) < 2:
                        continue
                    ax.semilogx([a for a, _ in par], [b for _, b in par], label=nome)
                else:
                    ax.plot(x, y, label=nome)
                desenhou = True
            if not desenhou:
                plt.close(fig)
                continue
            ax.set_xlabel(ROTULOS.get(xl, xl))
            ax.set_ylabel(ROTULOS.get(yl, yl))
            for a, b in (("eps_a", r"$\varepsilon_a$"), ("eps_v", r"$\varepsilon_v$"), ("sigma_v'", r"$\sigma'_v$"),
                         (" x ", " × "), ("lacos", "laços"), ("tensoes", "tensões"), ("tensao", "tensão"),
                         ("trajetoria", "trajetória"), ("poropressao", "poropressão"), ("Edometro", "Edômetro"),
                         ("deformacao", "deformação"), ("ciclico", "cíclico")):
                ti = ti.replace(a, b)
            ax.set_title("{}\n{}".format(ti, titulo), fontsize=10)
            if op.get("invy"):
                ax.invert_yaxis()
            ax.grid(True, alpha=0.3)
            if len(series) > 1 or tipo not in ("Oedometer",):
                ax.legend(fontsize=8)
            fig.tight_layout(rect=(0, 0.045, 1, 1))
            fig.text(0.012, 0.012, NOTAS.get(tipo, ""), fontsize=6.5, color="0.35", ha="left", va="bottom")
            caminho = os.path.join(sub, arq + ".png")
            fig.savefig(caminho, dpi=150)
            plt.close(fig)
            gerados.append(caminho)
    return gerados


# ------------------------------------------------------------------ glossario
GLOSSARIO = """# Glossário do plaxis_soiltest_auto.py

Este arquivo explica as siglas, os símbolos e as colunas dos CSV. Ele é gravado em cada pasta de saída.

## 1. Convenção de sinais (importante)

O PLAXIS usa **compressão negativa**. Nos CSV e nos gráficos deste script vale a convenção usual de laboratório, **compressão positiva**:

- tensões efetivas σ' > 0 em compressão;
- ε_a > 0 quando o corpo de prova encurta; ε_v > 0 quando o volume diminui (contração); ε_v < 0 é dilatação;
- Δu > 0 é acréscimo de poropressão (no PLAXIS, Δu = −PExcess).

## 2. Ensaios

| Nome no script | Ensaio | O que é |
|---|---|---|
| Triaxial | triaxial de compressão | corpo de prova cilíndrico; pressão confinante constante e carga axial crescente até a deformação máxima |
| Oedometer | edômetro | adensamento unidimensional: só deforma na vertical, sem deformação lateral; fases de carga e descarga |
| CRS | adensamento a taxa de deformação constante (Constant Rate of Strain) | como o edômetro, mas conduzido por deformação imposta |
| DSS | cisalhamento simples direto (Direct Simple Shear) | tensão vertical constante e distorção γ crescente |
| CDSS | DSS cíclico | distorção (ou tensão cisalhante) alternada, para módulo secante, amortecimento e geração de poropressão |
| CycTriaxial | triaxial cíclico | carga axial alternada em compressão e extensão |

Nos ensaios cíclicos os primeiros "passos por quarto" pontos são uma fase inicial, sem carga (deformação e tempo zero); depois vêm os ciclos completos, que começam e terminam em zero. Pontos = (4 × ciclos + 1) × passos por quarto + 1. No triaxial cíclico com controle por tensão, o primeiro meio ciclo é de extensão (q < 0).

## 3. Nome das curvas e dos arquivos (CD_50kPa, CU_100kPa)

- **CD** = Consolidated Drained: consolidação inicial e cisalhamento **drenado** (sem excesso de poropressão).
- **CU** = Consolidated Undrained: consolidação inicial e cisalhamento **não drenado** (volume constante, a poropressão varia).
- O **número** é a pressão de partida: no Triaxial e no Triaxial cíclico, a **pressão confinante σ'3** (kPa); no DSS e no CDSS, a **tensão vertical efetiva inicial σ'v0** (kPa).
- Exemplo: `triaxial_CD_50kPa.csv` = triaxial drenado com σ'3 = 50 kPa.

## 4. Grandezas dos gráficos e colunas dos CSV

Eixos: **a** = axial (direção vertical, y no PLAXIS) e **r** = radial/lateral (x no PLAXIS).

| Coluna do CSV | Símbolo | Significado |
|---|---|---|
| passo | – | número do passo de cálculo (0 = estado inicial, já consolidado) |
| tempo | t | tempo do ensaio, na unidade do SoilTest (dia nos ensaios por fases). Fica zero no Triaxial e no DSS monotônicos |
| eps_a_pct | ε_a | **deformação axial** (%) = encurtamento / altura inicial × 100. Positiva na compressão |
| ev_pct | ε_v | **deformação volumétrica** (%) = variação de volume / volume inicial × 100. Contração +, dilatação − |
| q_kPa | q | **tensão desviadora** q = σ'a − σ'r (= σ'1 − σ'3 na compressão). É a tensão que o corpo de prova suporta **além da pressão confinante**; é o dobro do raio do círculo de Mohr (τ_máx = q/2). A resistência é o pico q_f. No triaxial cíclico q tem sinal: q > 0 compressão, q < 0 extensão |
| p_kPa | p' | **tensão efetiva média** p' = (σ'a + 2σ'r)/3. O gráfico p'–q é a trajetória de tensões |
| sig_a_kPa | σ'a | tensão efetiva axial |
| sig_r_kPa | σ'r | tensão efetiva lateral. No triaxial é σ'3, a pressão confinante efetiva |
| sig_v_kPa | σ'v | tensão efetiva vertical (edômetro, CRS, DSS, CDSS) |
| sig_h_kPa | σ'h | tensão efetiva horizontal. K = σ'h/σ'v; no edômetro elástico K0 = ν/(1 − ν) |
| gamma_pct | γ_xy | **distorção** (%), deformação cisalhante de engenharia. No regime elástico τ = G·γ |
| tau_kPa | τ_xy | **tensão cisalhante** no plano horizontal (DSS e CDSS) |
| du_kPa | Δu | **excesso de poropressão** (kPa). Acréscimo +. Fica zero em ensaio drenado e em material non-porous |

## 5. Siglas dos modelos e da drenagem do material

| Sigla | Modelo |
|---|---|
| MC | Mohr-Coulomb |
| LE | Linear Elastic (elástico linear) |
| HS | Hardening Soil |
| HSsmall | Hardening Soil com rigidez a pequenas deformações |
| MCC | Modified Cam-Clay |
| SS | Soft Soil |

| Sigla | Drenagem do material (DrainageType) |
|---|---|
| D | Drained: parâmetros efetivos, sem poropressão gerada |
| UA | Undrained A: parâmetros efetivos; a poropressão é calculada (mesmo resultado do drenado no SoilTest) |
| UB | Undrained B: parâmetros efetivos de rigidez e resistência não drenada su |
| UC | Undrained C: parâmetros totais (su e ν_u) |
| NP | Non-porous: sem poropressão; só aceita ensaio drenado |

O comportamento do ensaio (CD ou CU) é escolhido à parte. Ele não depende da drenagem do material, exceto em UB, UC e NP.

## 6. Parâmetros do material

- **E'** módulo de Young efetivo; **ν'** coeficiente de Poisson efetivo; **ν_u** Poisson não drenado (≈ 0,495).
- **c'** coesão efetiva; **φ'** ângulo de atrito efetivo; **ψ** ângulo de dilatância; **su** resistência não drenada.
- **E50ref** módulo secante a 50 % de q_f na tensão de referência; **Eoedref** módulo edométrico tangente; **Eurref** módulo de descarga-recarga; **m** expoente de dependência da rigidez com a tensão; **ν_ur** Poisson de descarga-recarga; **pref** tensão de referência (100 kPa); **Rf** razão de ruptura (q_f / q_a, padrão 0,9).
- **G0ref** módulo de cisalhamento a pequenas deformações; **γ0,7** distorção em que G cai a 70 % de G0.
- **λ e κ** (MCC): inclinações da reta de compressão e de descarga em e × ln p'. **λ\\* e κ\\*** (Soft Soil): as mesmas inclinações em ε_v × ln p'. **M**: inclinação da linha de estado crítico no plano p'–q. **e_init**: índice de vazios inicial. **PhiInter**: ângulo de atrito da interface (o SoilTest recusa o MCC se PhiInter e CInter forem ambos zero).
- **Corte de dilatância** (HS e HSsmall): limita a dilatação quando o índice de vazios chega a **e_max**.

## 7. Consolidação e pré-adensamento

- **Consolidação isotrópica**: σ'x = σ'y antes do cisalhamento. **Consolidação K0**: σ'x = K0 · σ'y, com K0 = σ'h/σ'v. O K0 sugerido vem do K0nc do material, de 1 − sen φ' (Jaky), de M (MCC) ou de ν/(1 − ν).
- **σ'v0**: tensão vertical efetiva no início do cisalhamento. **σ'p**: pressão de pré-adensamento (maior tensão vertical efetiva já suportada).
- **OCR** = σ'p / σ'v0 (razão de pré-adensamento). **POP** = σ'p − σ'v0 (pressão de pré-sobrecarga). O script entrega ao SoilTest a pressão σ'p; com a opção OCR, σ'p = OCR × σ'v0 de cada ensaio.
- Só HS, HSsmall, MCC e Soft Soil aceitam editar σ'p; no MC e no LE é somente leitura.

## 8. Valores que o script calcula

- **q_f teórico (Mohr-Coulomb, drenado)** = 2 sen φ' / (1 − sen φ') · (σ'3 + c' / tg φ'). Para su: q_f = 2 su.
- **E50** simulado: q_f/2 dividido pela deformação axial em que q atinge q_f/2.
- **E_oed** = E'(1 − ν') / ((1 + ν')(1 − 2ν')): módulo edométrico elástico; ε_v = σ'v / E_oed.
- **G_sec** (CDSS) = amplitude de τ / amplitude de γ no último ciclo. **E_sec** (triaxial cíclico) = amplitude de q / amplitude de ε_a. Elástico: G = E'/(2(1 + ν')).
- **D** (amortecimento, %) = área do laço / (4π · W_s), com W_s = ½ · τ_a · γ_a (ou ½ · q_a · ε_a). Zero em material elástico.

## 9. Arquivos da pasta de saída

- um CSV por ensaio (`triaxial_CD_50kPa.csv`, `oedometer.csv`, `dss_CD_100kPa.csv`, ...);
- `graficos/`: um PNG por gráfico;
- `resumo.json`: parâmetros, consolidação, pré-adensamento e resultados das checagens;
- `log.txt`: tudo o que o script fez, com os avisos;
- `glossario.md`: este arquivo.
"""


def gravar_glossario(pasta):
    try:
        with open(os.path.join(pasta, "glossario.md"), "w", encoding="utf-8") as f:
            f.write(GLOSSARIO)
    except Exception as e:
        log("Glossario nao gravado: {}".format(e))


# ------------------------------------------------------------------ principal
def main():
    cfg = CONFIG
    if cfg["interativo"]:
        cfg = perguntar(cfg)
    modelo, dren = cfg["modelo"], cfg["drenagem"]
    if modelo not in MODELOS:
        raise ValueError("modelo deve ser um de {}".format(list(MODELOS)))
    if dren not in MODELOS[modelo]["dren"]:
        raise ValueError("drenagem {} invalida para {}; use uma de {}".format(dren, modelo, MODELOS[modelo]["dren"]))
    info = MODELOS[modelo]
    valores = {c: cfg["valores"].get(c, v) for c, _a, _r, v in parametros(modelo, dren)}
    dil = cfg["dilatancy_cutoff"] if modelo in ("HS", "HSsmall") else None
    if dren == "NP":
        for t in COM_PRESSOES:
            cfg[CHAVE_CFG[t]]["comportamentos"] = ["Drained"]
    if SOMENTE_VALIDADO:
        for t in ("CDSS", "CycTriaxial"):
            c = cfg[CHAVE_CFG[t]]
            if c.get("rodar") and (c["comportamentos"] != ["Drained"] or c["controle"] != "Strain"):
                log("Versao estavel: {} limitado a drenado e controle de deformacao (o resto esta em "
                    "soiltest/em_desenvolvimento/).".format(ENSAIOS_NOMES[t]))
                c["comportamentos"], c["controle"] = ["Drained"], "Strain"
                if c["amplitude"] >= 5:
                    c["amplitude"] = 0.5
    if cfg["oedometer"]["rodar"] is None:
        cfg["oedometer"]["rodar"] = info["oed"]
    titulo = "{} / {}".format(info["nome"], DRENAGENS[dren]["rotulo"])
    log("PLAXIS SoilTest auto - {} ({})".format(titulo, datetime.datetime.now().isoformat(timespec="seconds")))

    p = {k: float(v) for k, v in valores.items() if v is not None}
    cons = dict(cfg["consolidacao"])
    k0 = None
    if cons["tipo"] == "K0":
        k0a, origem = k0_automatico(modelo, p)
        k0 = float(cons["K0"]) if cons.get("K0") is not None else k0a
        log("Consolidacao K0 com K0 = {} ({}).".format(k0, "informado" if cons.get("K0") is not None else origem))
    pre = dict(cfg["preadensamento"])
    if pre["modo"] != "nenhum" and not info["precons"]:
        log("Pre-adensamento ignorado: no {} o SoilTest nao permite editar PreconsolidationPressure.".format(info["nome"]))
        pre["modo"] = "nenhum"
    if pre["modo"] != "nenhum":
        log("Pre-adensamento: {} = {}.".format(pre["modo"], pre["valor"]))

    if "g_i" in globals() and "s_i" in globals():
        gi = globals()["g_i"]
    else:
        from plxscripting.easy import new_server
        gi = new_server("localhost", cfg["porta_input"], password=pedir_senha("Senha do servidor Input: "))[1]
    if hasattr(gi, "Triaxial"):
        log("Conectado ao SoilTest em vez do Input. Use o servidor do PLAXIS 3D Input (porta {}).".format(cfg["porta_input"]))
        return 1

    ident = "{}_{}_teste".format(modelo, dren)
    mat = criar_material(gi, ident, modelo, dren, valores, dil)
    if mat is None:
        log("Material nao criado. Ha projeto aberto no Input?")
        return 1

    log("\n== Abrindo o SoilTest ==")
    ok, porta = tentar("g_i.soiltest(material)", lambda: gi.soiltest(mat))
    if not ok:
        log("O SoilTest recusou o material. A mensagem acima diz o que falta (ex.: PhiInter/CInter no MCC, "
            "lambda* e kappa* no Soft Soil).")
        return 1
    senha = pedir_senha("Senha do servidor do SoilTest: ")
    try:
        porta = int(valor(porta))
    except Exception:
        log("g_i.soiltest nao devolveu a porta; procurando entre 10000 e 10030...")
        porta = descobrir_porta(senha, cfg["espera_soiltest_s"], cfg["porta_input"])
        if porta is None:
            log("SoilTest nao encontrado.")
            return 1
    log("SoilTest na porta {}.".format(porta))
    g = conectar_soiltest(porta, senha, cfg["espera_soiltest_s"])
    ok, sm = tentar("SoilModel no SoilTest", lambda: valor(g.Material.SoilModel))
    if ok and int(sm) != int(info["numero"]):
        log("ATENCAO: o SoilTest abriu o modelo {} (esperado {}).".format(sm, info["numero"]))
    estado_corte = propagar_corte(g, dil) if dil and dil.get("ligar") else None

    pasta = os.path.join(AQUI, "soiltest_saida", "auto_{}_{}_{}".format(modelo, dren, datetime.datetime.now().strftime("%Y%m%d_%H%M%S")))
    os.makedirs(pasta, exist_ok=True)
    resumo = {"modelo": modelo, "drenagem": dren, "parametros": valores, "porta_soiltest": porta,
              "consolidacao": dict(cons, K0_usado=k0), "preadensamento": pre,
              "dilatancy_cutoff": dict(dil or {}, SoilTest=estado_corte)}
    ctx = {"modelo": modelo, "dren": dren, "consolidacao": cons, "k0": k0, "preadensamento": pre, "pc_usados": set()}
    todas = {}

    for tipo in ORDEM_ENSAIOS:
        cfg_t = cfg[CHAVE_CFG[tipo]]
        if not cfg_t.get("rodar"):
            continue
        log("\n================ {} ================".format(ENSAIOS_NOMES[tipo]))
        todas[tipo] = {}
        resumo[CHAVE_CFG[tipo]] = {}
        if tipo in ("Oedometer", "CRS"):
            log("-- {} --".format(ENSAIOS_NOMES[tipo]))
            d, ext = rodar_fases(g, tipo, cfg_t, ctx)
            if d is None:
                continue
            todas[tipo][tipo] = d
            gravar_csv(os.path.join(pasta, "{}.csv".format(PREFIXO_ARQ[tipo])), d)
            chk = checagem_fases(d, modelo, dren, p)
            chk.update(ext)
            resumo[CHAVE_CFG[tipo]] = chk
            log("   {} pontos; sigma_v max = {:.2f} kPa; eps_v max = {:.4f} %".format(
                chk["pontos"], chk["sigma_v_max_kPa"], chk["eps_v_max_pct"]))
            if "eps_v_esperado_pct" in chk:
                log("   Esperado (eps_v = sigma_v/E_oed, E_oed = {:.1f} kPa): {:.4f} % no pico; simulado {:.4f} %".format(
                    chk["E_oed_teorico_kPa"], chk["eps_v_esperado_pct"], chk["eps_v_no_pico_pct"]))
            continue
        for comp in cfg_t["comportamentos"]:
            for pr in cfg_t["pressoes_kPa"]:
                nome = nome_ensaio(comp, pr)
                log("\n-- {} {} --".format(ENSAIOS_NOMES[tipo], nome))
                d, ext = rodar_ensaio(g, tipo, nome, cfg_t, comp, pr, ctx)
                if d is None:
                    continue
                todas[tipo][nome] = d
                gravar_csv(os.path.join(pasta, "{}_{}.csv".format(PREFIXO_ARQ[tipo], nome)), d)
                if tipo == "Triaxial":
                    chk = checagem_triaxial(d, modelo, dren, p, pr, comp, cfg_t, ext)
                    log("   q_max simulado = {:.3f} kPa; dilatacao volumetrica maxima = {:.3f} %".format(
                        chk["q_max_kPa"], chk["dilatacao_max_pct"]))
                elif tipo == "DSS":
                    chk = checagem_dss(d, modelo, dren, p, pr, comp, ext)
                    log("   tau_max simulado = {:.3f} kPa; dilatacao volumetrica maxima = {:.3f} %".format(
                        chk["tau_max_kPa"], chk["dilatacao_max_pct"]))
                else:
                    chk = checagem_ciclico(tipo, d, modelo, dren, p, comp, cfg_t)
                    m = chk.get("ultimo_ciclo")
                    if m:
                        log("   Ultimo ciclo: {} = {:.1f} kPa; amplitude = {:.4f} % / {:.2f} kPa; amortecimento = {}".format(
                            chk["rotulo_modulo"], m["modulo_secante_kPa"], m["amplitude_x_pct"], m["amplitude_y_kPa"],
                            "{:.2f} %".format(m["amortecimento_pct"]) if m["amortecimento_pct"] is not None else "n/d"))
                    if max(abs(v) for v in d["du_kPa"]) > 1e-6:
                        log("   du max = {:.2f} kPa; du min = {:.2f} kPa".format(max(d["du_kPa"]), min(d["du_kPa"])))
                if "esperado" in chk:
                    log("   Esperado ({}): {:.3f} kPa".format(chk["esperado"]["descricao"], chk["esperado"]["kPa"]))
                if "E50_simulado_kPa" in chk:
                    log("   E50 (secante a 50% de q_f): simulado {:.0f} kPa | formula {:.0f} kPa".format(
                        chk["E50_simulado_kPa"], chk["E50_formula_kPa"]))
                chk.update(ext)
                resumo[CHAVE_CFG[tipo]][nome] = chk

    if ctx["pc_usados"]:
        restaurar_preadensamento(g, ctx["pc_usados"])

    gerados = graficos(pasta, titulo, todas)
    gravar_glossario(pasta)
    resumo["graficos"] = [os.path.relpath(c, pasta) for c in gerados]
    with open(os.path.join(pasta, "resumo.json"), "w", encoding="utf-8") as f:
        json.dump(resumo, f, indent=2, ensure_ascii=False, default=str)
    log("\n{} grafico(s) em {}".format(len(gerados), os.path.join(pasta, "graficos")))
    for c in gerados:
        log("   " + os.path.basename(c))
    log("\nSaida: {}".format(pasta))
    with open(os.path.join(pasta, "log.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(_linhas))
    return 0


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        log("ERRO:\n" + traceback.format_exc())
        rc = 1
        try:
            with open(os.path.join(AQUI, "soiltest_auto_erro.txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(_linhas))
        except Exception:
            pass
    if "g_i" not in globals():
        input("\nPressione Enter para fechar...")
        sys.exit(rc)

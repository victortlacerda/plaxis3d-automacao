# -*- coding: utf-8 -*-
"""
soiltest_campanha.py  -  Campanha de ensaios virtuais definida numa PLANILHA CSV.

Cada linha da planilha e um ensaio (ou um conjunto de curvas do mesmo ensaio) num material:
    material;ensaio;comportamento;pressoes_kPa;...
O material pode JA EXISTIR no projeto aberto (pelo nome, como esta no PLAXIS) ou ser criado antes a partir da
planilha de materiais (mesmo formato do soiltest_biblioteca.py). Para cada material o SoilTest e aberto uma vez
e todas as linhas dele rodam em sequencia.

Saida (soiltest_saida/campanha_<data>/):
    relatorio.html            resumo da campanha (uma linha por curva) + link para o relatorio de cada ensaio
    campanha_resumo.csv       mesma tabela em CSV (abre no Excel)
    <material>/<nn>_<ensaio>/ CSV, graficos, relatorio.html e resumo.json de cada linha da planilha
    log.txt, glossario.md

COLUNAS DA PLANILHA (separador ";", virgula decimal aceita; so "material" e "ensaio" sao obrigatorias)
    material            nome do material (Identification no PLAXIS; hifens sao ignorados na comparacao)
    ensaio              triaxial | edometro | crs | dss | cdss | triaxial_ciclico
    comportamento       D (drenado) | U (nao drenado) | DU (os dois)                      padrao D
    pressoes_kPa        lista separada por espaco ou "/": 50/100/200                       padrao 100
                        (triaxial e triaxial ciclico: sigma'3; DSS e CDSS: sigma'v0)
    deformacao_max_pct  triaxial: eps_a max (15); DSS: gama max (10); CRS: eps_a total (5)
    passos              triaxial e DSS: passos (100); CRS: passos (50); ciclicos: passos por quarto de ciclo (20)
    consolidacao        iso | K0                                                           padrao iso
    K0                  valor do K0 (vazio = automatico: K0nc, Jaky, M do MCC ou nu)
    preadensamento      nenhum | sigma_p | OCR (so HS, HS small, MCC e Soft Soil)          padrao nenhum
    valor_pre           sigma'p em kPa ou o OCR
    controle            deformacao | tensao (ciclicos)                                     padrao deformacao
    amplitude           ciclicos: % (deformacao) ou kPa (tensao)                           padrao 0,5
    ciclos              ciclicos: numero de ciclos                                         padrao 3
    tensao_max_kPa      edometro: tensao vertical maxima (carga dobrando a partir de 25)   padrao 400
    descarga_kPa        edometro: tensao final da descarga (0 = sem descarga)              padrao tensao_max/4
    obs                 texto livre (vai para o relatorio)

COMO RODAR: PLAXIS 3D Input aberto com um projeto (pode ser vazio se os materiais vierem da planilha de
materiais) e o servidor de scripts ativo; rode pelo Executar_script_PLAXIS.bat e escolha este arquivo.
Senha do SoilTest: variavel de ambiente PLAXIS_PASSWORD (ou digitada uma vez).
"""
import copy
import csv
import datetime
import os
import re
import traceback

AQUI = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()

# =========================== CONFIGURACAO ===========================
PLANILHA_ENSAIOS = os.path.join(AQUI, "campanha_modelo.csv")
# Planilha de materiais (formato do soiltest_biblioteca.py). Os materiais citados na campanha que NAO estao no
# projeto sao criados a partir dela. None = usar so os materiais que ja estao no projeto.
PLANILHA_MATERIAIS = os.path.join(AQUI, "..", "materiais_modelo.csv")
ATUALIZAR_EXISTENTES = False   # True = materiais que ja existem no projeto recebem os valores da planilha de materiais
FECHAR_SOILTEST = True         # fecha cada janela do SoilTest ao terminar o material
# ====================================================================

ENSAIOS = {"triaxial": "Triaxial", "edometro": "Oedometer", "edômetro": "Oedometer", "oedometer": "Oedometer",
           "crs": "CRS", "dss": "DSS", "cdss": "CDSS", "triaxial_ciclico": "CycTriaxial", "triaxial ciclico": "CycTriaxial",
           "ciclico": "CycTriaxial", "cyctriaxial": "CycTriaxial"}
FIXAS_MAT = ("nome", "modelo", "drenagem", "conferir")


def carregar_auto():
    """Prefere a copia de desenvolvimento (tem as funcoes de material do projeto); senao a estavel."""
    for nome in ("plaxis_soiltest_auto_dev.py", "plaxis_soiltest_auto.py", os.path.join("..", "plaxis_soiltest_auto.py")):
        cam = os.path.normpath(os.path.join(AQUI, nome))
        if os.path.isfile(cam):
            break
    else:
        raise FileNotFoundError("Nao achei plaxis_soiltest_auto_dev.py / plaxis_soiltest_auto.py nesta pasta nem na pasta acima.")
    ns = {"__name__": "soiltest_auto", "__file__": cam, "__builtins__": __builtins__}
    if "g_i" in globals():
        ns["g_i"], ns["s_i"] = globals()["g_i"], globals().get("s_i")
    with open(cam, "rb") as f:
        exec(compile(f.read(), cam, "exec"), ns, ns)
    return ns


# ------------------------------------------------------------------ leitura das planilhas
def _num(txt, padrao=None):
    t = str(txt or "").strip().replace(",", ".")
    if t == "":
        return padrao
    return float(t)


def _lista(txt, padrao):
    t = str(txt or "").strip()
    if not t:
        return list(padrao)
    return [float(x.replace(",", ".")) for x in re.split(r"[\s/|+]+", t) if x]


def ler_csv(caminho, minusculas=True):
    """Linhas do CSV como dicts. minusculas=False preserva o cabecalho (a planilha de materiais tem cRef e cref)."""
    with open(caminho, encoding="utf-8-sig") as f:
        linhas = [l for l in csv.reader(f, delimiter=";") if any(c.strip() for c in l)]
    linhas = [l for l in linhas if not l[0].strip().startswith("#")]
    cab = [c.strip().lower() if minusculas else c.strip() for c in linhas[0]]
    return [dict(zip(cab, [c.strip() for c in l])) for l in linhas[1:]]


def interpretar_linha(n, r):
    """Linha da planilha -> (dict com o ensaio montado, lista de erros)."""
    erros = []
    mat = r.get("material", "")
    tipo = ENSAIOS.get(r.get("ensaio", "").strip().lower())
    if not mat:
        erros.append("material vazio")
    if not tipo:
        erros.append("ensaio '{}' desconhecido (use: triaxial, edometro, crs, dss, cdss, triaxial_ciclico)".format(r.get("ensaio", "")))
    comp_txt = (r.get("comportamento") or "D").strip().upper().replace("+", "").replace(" ", "")
    comp = {"D": ["Drained"], "U": ["Undrained"], "DU": ["Drained", "Undrained"], "UD": ["Drained", "Undrained"],
            "A": ["Drained", "Undrained"]}.get(comp_txt)
    if comp is None:
        erros.append("comportamento '{}' invalido (D, U ou DU)".format(r.get("comportamento")))
        comp = ["Drained"]
    e = {"linha": n, "material": mat, "tipo": tipo, "obs": r.get("obs", ""), "comportamentos": comp}
    try:
        e["pressoes"] = _lista(r.get("pressoes_kpa"), [100])
        e["def_max"] = _num(r.get("deformacao_max_pct"))
        e["passos"] = _num(r.get("passos"))
        cons = (r.get("consolidacao") or "iso").strip().lower()
        if cons.startswith("iso"):
            e["consolidacao"] = "Isotropic"
        elif cons == "k0":
            e["consolidacao"] = "K0"
        else:
            erros.append("consolidacao '{}' invalida (iso ou K0)".format(cons))
            e["consolidacao"] = "Isotropic"
        e["K0"] = _num(r.get("k0"))
        pre = (r.get("preadensamento") or "nenhum").strip().lower().replace("'", "")
        e["pre_modo"] = {"nenhum": "nenhum", "": "nenhum", "sigma_p": "pressao", "sigmap": "pressao", "pressao": "pressao",
                         "σp": "pressao", "ocr": "OCR"}.get(pre)
        if e["pre_modo"] is None:
            erros.append("preadensamento '{}' invalido (nenhum, sigma_p ou OCR)".format(pre))
            e["pre_modo"] = "nenhum"
        e["pre_valor"] = _num(r.get("valor_pre"), 0)
        if e["pre_modo"] != "nenhum" and not e["pre_valor"]:
            erros.append("preadensamento {} sem valor_pre".format(e["pre_modo"]))
        if e["pre_modo"] == "OCR" and tipo in ("Oedometer", "CRS"):
            erros.append("OCR nao se aplica ao {} (parte de tensao zero): use preadensamento = sigma_p".format(tipo))
        ctl = (r.get("controle") or "deformacao").strip().lower()
        e["controle"] = "Stress" if ctl.startswith(("tens", "stress")) else "Strain"
        e["amplitude"] = _num(r.get("amplitude"))
        e["ciclos"] = _num(r.get("ciclos"))
        e["tensao_max"] = _num(r.get("tensao_max_kpa"), 400)
        e["descarga"] = _num(r.get("descarga_kpa"))
    except ValueError as ex:
        erros.append("numero invalido: {}".format(ex))
    return e, erros


def fases_edometro(tmax, descarga, passos=10):
    """Carga dobrando a partir de 25 kPa ate tmax e, se pedido, descarga ate 'descarga'. Siginc e incremental."""
    alvos, a = [], 25.0
    while a < tmax - 1e-9:
        alvos.append(a)
        a *= 2
    alvos.append(float(tmax))
    fases, ant = [], 0.0
    for a in alvos:
        fases.append({"Duration": 1, "Siginc": -(a - ant), "Steps": passos})
        ant = a
    if descarga is None:
        descarga = tmax / 4
    if descarga and descarga < tmax:
        fases.append({"Duration": 1, "Siginc": tmax - descarga, "Steps": passos})
    return fases


def montar_cfg(A, e):
    """CONFIG do auto com so o ensaio desta linha ligado."""
    cfg = copy.deepcopy(A["CONFIG"])
    for chave in ("triaxial", "oedometer", "crs", "dss", "cdss", "triaxial_ciclico"):
        cfg[chave]["rodar"] = False
    tipo = e["tipo"]
    c = cfg[A["CHAVE_CFG"][tipo]]
    c["rodar"] = True
    if tipo in A["COM_PRESSOES"]:
        c["pressoes_kPa"] = e["pressoes"]
        c["comportamentos"] = e["comportamentos"]
    if tipo == "Triaxial":
        c["MaximumStrain"] = e["def_max"] or 15
        c["Steps"] = int(e["passos"] or 100)
    elif tipo == "DSS":
        c["MaximumShearStrain"] = e["def_max"] or 10
        c["Steps"] = int(e["passos"] or 100)
    elif tipo == "CRS":
        c["fases"] = [{"Duration": 1, "Epsinc": -abs(e["def_max"] or 5), "Steps": int(e["passos"] or 50)}]
    elif tipo == "Oedometer":
        c["fases"] = fases_edometro(e["tensao_max"], e["descarga"])
    else:
        c["controle"] = e["controle"]
        c["amplitude"] = e["amplitude"] if e["amplitude"] is not None else (0.5 if e["controle"] == "Strain" else 20)
        c["ciclos"] = int(e["ciclos"] or 3)
        c["passos_por_quarto"] = int(e["passos"] or 20)
    return cfg


def descrever(e):
    t = e["tipo"]
    if t == "Oedometer":
        return "até {} kPa".format(_fmt(e["tensao_max"]))
    if t == "CRS":
        return "ε_a {} %".format(_fmt(e["def_max"] or 5))
    txt = "{} | {} kPa".format("+".join("CD" if c == "Drained" else "CU" for c in e["comportamentos"]),
                               "/".join(_fmt(p) for p in e["pressoes"]))
    if e["consolidacao"] == "K0":
        txt += " | K0 {}".format(_fmt(e["K0"]) if e["K0"] is not None else "auto")
    if e["pre_modo"] != "nenhum":
        txt += " | {} {}".format("σ'p" if e["pre_modo"] == "pressao" else "OCR", _fmt(e["pre_valor"]))
    if t in ("CDSS", "CycTriaxial"):
        txt += " | {} {} {} | {} ciclos".format("±", _fmt(e["amplitude"] if e["amplitude"] is not None else 0.5),
                                                 "%" if e["controle"] == "Strain" else "kPa", int(e["ciclos"] or 3))
    return txt


def _fmt(v):
    try:
        v = float(v)
    except Exception:
        return str(v)
    return ("{:.0f}" if v == int(v) else "{:g}").format(v).replace(".", ",")


# ------------------------------------------------------------------ materiais
def _norm(n):
    return str(n).replace("-", "").strip().lower()


def materiais_do_projeto(A, gi):
    out = {}
    for lista in ("Soils", "Materials"):
        try:
            mats = [m for m in getattr(gi, lista)]
        except Exception:
            continue
        for m in mats:
            try:
                out[_norm(A["valor"](m.Identification))] = m
            except Exception:
                pass
        if out:
            break
    return out


def ler_material(A, mat):
    """(nome, modelo, drenagem, valores) de um material do projeto. modelo/drenagem None se nao suportados."""
    ident = str(A["valor"](mat.Identification))
    sm = A["linha_echo"](mat, "SoilModel")
    dr = A["linha_echo"](mat, "DrainageType")
    modelo = next((k for k, v in A["MODELOS"].items() if sm and v["numero"] == sm[1]), None)
    dren = next((k for k, v in A["DRENAGENS"].items() if dr and v["nomes"][1] == dr[1]), None)
    if modelo and dren not in A["MODELOS"][modelo]["dren"]:
        dren = None
    valores = {}
    if modelo and dren:
        for chave, aliases, _r, _v in A["parametros"](modelo, dren):
            valores[chave] = None
            attr = A["achar_attr"](mat, aliases)
            if attr is None:
                continue
            try:
                valores[chave] = float(A["valor"](getattr(mat, attr)))
            except Exception:
                pass
            if chave in ("K0nc", "Rf") and valores[chave] is not None and valores[chave] <= 0:
                valores[chave] = None
    return ident, modelo, dren, valores, (sm[0] if sm else "?"), (dr[0] if dr else "?")


def criar_da_planilha(A, gi, reg):
    """Cria (ou atualiza) um material a partir de uma linha da planilha de materiais. Devolve o objeto ou None."""
    log = A["log"]
    nome, modelo, dren = reg.get("nome"), (reg.get("modelo") or "").strip(), (reg.get("drenagem") or "D").strip().upper()
    if modelo not in A["MODELOS"] or dren not in A["MODELOS"][modelo]["dren"]:
        log("   {}: modelo/drenagem invalidos na planilha de materiais ({} / {})".format(nome, modelo, dren))
        return None
    lista = A["parametros"](modelo, dren)
    chaves = {c.lower(): c for c, _a, _r, _v in lista}
    valores = {c: None for c, _a, _r, _v in lista}
    extras = {}
    for k, v in reg.items():
        if k in FIXAS_MAT or v == "":
            continue
        try:
            v = float(str(v).replace(",", "."))
        except ValueError:
            pass
        if k.lower() in chaves:
            valores[chaves[k.lower()]] = v
        else:
            extras[k] = v
    mat = A["criar_material"](gi, nome, modelo, dren, valores, None)
    if mat is None:
        return None
    for k, v in extras.items():
        attr = A["achar_attr"](mat, [k])
        if attr is None:
            log("[ERR] {}: atributo '{}' nao existe neste material".format(nome, k))
            continue
        A["tentar"]("{} = {}".format(attr, v), lambda a=attr, v=v: mat.setproperties(a, v))
    return mat


# ------------------------------------------------------------------ resultados
def linhas_resultado(A, e, modelo, dren, resumo):
    """Uma linha por curva: (curva, grandeza, simulado, teorico, diferenca, extra)."""
    chave = A["CHAVE_CFG"][e["tipo"]]
    bloco = resumo.get(chave) or {}
    out = []
    if e["tipo"] in ("Oedometer", "CRS"):
        if bloco:
            esp = bloco.get("eps_v_esperado_pct")
            out.append(("-", "ε_v máx (%)", bloco.get("eps_v_max_pct"), esp,
                        "σ'v máx {} kPa".format(A["_num"](bloco.get("sigma_v_max_kPa"), 1))))
        return out
    for curva, chk in bloco.items():
        if e["tipo"] in ("CDSS", "CycTriaxial"):
            m = chk.get("ultimo_ciclo") or {}
            amort = m.get("amortecimento_pct")
            if amort is not None and abs(amort) < 1e-6:
                amort = 0.0
            out.append((curva, "{} último ciclo (kPa)".format(chk.get("rotulo_modulo", "módulo")), m.get("modulo_secante_kPa"),
                        None, "amortecimento {} %".format(A["_num"](amort, 2)) if amort is not None else ""))
            continue
        esp = (chk.get("esperado") or {}).get("kPa")
        if "q_max_kPa" in chk:
            extra = "E50 {} kPa".format(A["_num"](chk["E50_simulado_kPa"], 0)) if chk.get("E50_simulado_kPa") else ""
            out.append((curva, "q máx (kPa)", chk.get("q_max_kPa"), esp, extra))
        else:
            out.append((curva, "τ máx (kPa)", chk.get("tau_max_kPa"), esp, ""))
    return out


# ------------------------------------------------------------------ principal
def main():
    A = carregar_auto()
    log = A["log"]
    if not os.path.isfile(PLANILHA_ENSAIOS):
        log("Planilha de ensaios nao encontrada: {}".format(PLANILHA_ENSAIOS))
        return 1
    brutas = ler_csv(PLANILHA_ENSAIOS)
    log("Campanha SoilTest: {} linha(s) em {}".format(len(brutas), PLANILHA_ENSAIOS))
    ensaios, invalidas = [], []
    for n, r in enumerate(brutas, 1):
        e, erros = interpretar_linha(n, r)
        if erros:
            invalidas.append((n, r.get("material", ""), r.get("ensaio", ""), "; ".join(erros)))
            log("   linha {}: IGNORADA ({})".format(n, "; ".join(erros)))
        else:
            ensaios.append(e)
    gi = A["obter_input"](A["CONFIG"])
    if gi is None:
        return 1

    # materiais: os do projeto + os da planilha de materiais que faltarem
    proj = materiais_do_projeto(A, gi)
    regs = {}
    if PLANILHA_MATERIAIS and os.path.isfile(PLANILHA_MATERIAIS):
        regs = {}
        for r in ler_csv(PLANILHA_MATERIAIS, minusculas=False):
            r = {(k.lower() if k.lower() in FIXAS_MAT else k): v for k, v in r.items()}
            regs[_norm(r.get("nome", ""))] = r
    elif PLANILHA_MATERIAIS:
        log("Planilha de materiais nao encontrada ({}); usando so os materiais do projeto.".format(PLANILHA_MATERIAIS))
    pedidos = []
    for e in ensaios:
        if _norm(e["material"]) not in pedidos:
            pedidos.append(_norm(e["material"]))
    origem = {}
    for nm in pedidos:
        if nm in regs and (nm not in proj or ATUALIZAR_EXISTENTES):
            log("\nMaterial {} {} a partir da planilha de materiais".format(regs[nm].get("nome"), "atualizado" if nm in proj else "criado"))
            mat = criar_da_planilha(A, gi, regs[nm])
            if mat is not None:
                proj[nm] = mat
                origem[nm] = "planilha de materiais"
        elif nm in proj:
            origem[nm] = "projeto"

    pasta = os.path.join(AQUI, "soiltest_saida", "campanha_{}".format(datetime.datetime.now().strftime("%Y%m%d_%H%M%S")))
    os.makedirs(pasta, exist_ok=True)
    A["gravar_glossario"](pasta)
    tabela, csv_linhas, figuras = [], [], []
    for nm in pedidos:
        lin_mat = [e for e in ensaios if _norm(e["material"]) == nm]
        mat = proj.get(nm)
        if mat is None:
            disp = ", ".join(sorted(str(A["valor"](m.Identification)) for m in proj.values())) or "nenhum"
            for e in lin_mat:
                invalidas.append((e["linha"], e["material"], e["tipo"], "material nao esta no projeto nem na planilha de materiais "
                                                                          "(no projeto: {})".format(disp)))
            log("\nMaterial '{}' nao encontrado (no projeto: {}).".format(lin_mat[0]["material"], disp))
            continue
        ident, modelo, dren, valores, nome_mod, nome_dr = ler_material(A, mat)
        if not (modelo and dren):
            for e in lin_mat:
                invalidas.append((e["linha"], ident, e["tipo"], "{} / {} nao suportado por este script".format(nome_mod, nome_dr)))
            log("\nMaterial '{}' ({} / {}) nao suportado.".format(ident, nome_mod, nome_dr))
            continue
        info = A["MODELOS"][modelo]
        log("\n" + "=" * 70 + "\n{} ({} / {}; origem: {}) - {} ensaio(s)\n".format(
            ident, info["nome"], A["DRENAGENS"][dren]["rotulo"], origem.get(nm, "projeto"), len(lin_mat)) + "=" * 70)
        log("   " + ", ".join("{} = {}".format(k, A["fmt_num"](v)) for k, v in valores.items() if v is not None))
        g, porta = A["abrir_soiltest"](gi, mat, A["CONFIG"]["espera_soiltest_s"], A["CONFIG"]["porta_input"], modelo)
        if g is None:
            for e in lin_mat:
                invalidas.append((e["linha"], ident, e["tipo"], "o SoilTest recusou o material (veja o log)"))
            continue
        p = {k: float(v) for k, v in valores.items() if v is not None}
        rot_mat = re.sub(r"[^\w]+", "_", ident)
        for e in lin_mat:
            tipo = e["tipo"]
            nome_ens = A["ENSAIOS_NOMES"][tipo]
            log("\n#### linha {}: {} - {} ({})".format(e["linha"], ident, nome_ens, descrever(e)))
            cfg = montar_cfg(A, e)
            if dren == "NP" and tipo in A["COM_PRESSOES"]:
                cfg[A["CHAVE_CFG"][tipo]]["comportamentos"] = ["Drained"]
            pre = {"modo": e["pre_modo"], "valor": e["pre_valor"]}
            if pre["modo"] != "nenhum" and not info["precons"]:
                log("   Pre-adensamento ignorado: no {} o SoilTest nao permite editar a pressao de pre-adensamento.".format(info["nome"]))
                pre = {"modo": "nenhum", "valor": 0}
            k0 = None
            if e["consolidacao"] == "K0" and tipo in A["COM_CONSOLIDACAO"]:
                k0a, orig = A["k0_automatico"](modelo, p)
                k0 = e["K0"] if e["K0"] is not None else k0a
                log("   Consolidacao K0 com K0 = {} ({}).".format(k0, "informado" if e["K0"] is not None else orig))
            cons = {"tipo": e["consolidacao"] if tipo in A["COM_CONSOLIDACAO"] else "Isotropic", "K0": k0}
            ctx = {"modelo": modelo, "dren": dren, "consolidacao": cons, "k0": k0, "preadensamento": pre, "pc_usados": set(),
                   "pc_fases_kPa": float(cfg.get("sigma_p_padrao_fases_kPa") or 0)}
            sub = os.path.join(pasta, rot_mat, "{:02d}_{}".format(e["linha"], A["PREFIXO_ARQ"][tipo]))
            os.makedirs(sub, exist_ok=True)
            resumo = {"modelo": modelo, "drenagem": dren, "parametros": valores, "material": ident, "linha_planilha": e["linha"],
                      "consolidacao": dict(cons, K0_usado=k0), "preadensamento": pre, "porta_soiltest": porta}
            try:
                todas = A["executar_ensaios"](g, cfg, modelo, dren, p, ctx, sub, resumo)
            except Exception as ex:
                log("   ERRO no ensaio: {}".format(str(ex).splitlines()[0][:200]))
                invalidas.append((e["linha"], ident, nome_ens, "erro ao rodar: {}".format(str(ex).splitlines()[0][:150])))
                continue
            titulo = "{} | {} | {}".format(ident, nome_ens, descrever(e))
            gerados = A["graficos"](sub, titulo, todas)
            A["relatorio_auto"](sub, titulo, resumo, gerados)
            import json
            with open(os.path.join(sub, "resumo.json"), "w", encoding="utf-8") as f:
                json.dump(resumo, f, indent=2, ensure_ascii=False, default=str)
            rel = os.path.relpath(os.path.join(sub, "relatorio.html"), pasta).replace(os.sep, "/")
            res = linhas_resultado(A, e, modelo, dren, resumo)
            if not res:
                tabela.append((e["linha"], ident, nome_ens, descrever(e), "-", '<span class="erro">sem resultado</span>', "-", "-", "-",
                               '<a href="{}">relatório</a>'.format(A["_esc"](rel))))
            for curva, grand, sim, esp, extra in res:
                dif = A["classe_diferenca"](sim, esp)[0] if esp is not None else ""
                tabela.append((e["linha"], ident, nome_ens, descrever(e), curva, "{}: {}".format(grand, A["_num"](sim, 2)),
                               A["_num"](esp, 2) if esp is not None else "-", dif or "-", A["_esc"](extra) or "-",
                               '<a href="{}">relatório</a>'.format(A["_esc"](rel))))
                csv_linhas.append([e["linha"], ident, info["nome"], dren, nome_ens, descrever(e), curva, grand,
                                   "" if sim is None else "{:.4f}".format(sim).replace(".", ","),
                                   "" if esp is None else "{:.4f}".format(esp).replace(".", ","), extra, e["obs"]])
            if gerados:
                figuras.append(A["html_imagem"](gerados[0], "linha {}: {} - {}".format(e["linha"], ident, os.path.basename(gerados[0]))))
        if FECHAR_SOILTEST:
            A["fechar_soiltest"](g)

    # saidas da campanha
    with open(os.path.join(pasta, "campanha_resumo.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["linha", "material", "modelo", "drenagem", "ensaio", "configuracao", "curva", "grandeza", "simulado",
                    "teorico", "extra", "obs"])
        w.writerows(csv_linhas)
    sec = [("Resultados", A["html_tabela"](["Linha", "Material", "Ensaio", "Configuração", "Curva", "Simulado", "Teórico",
                                            "Diferença", "Outros", "Detalhe"], tabela)
            + '<p class="nota">Uma linha por curva. Tensões em kPa, deformações em %. "Teórico" só aparece quando há '
              'solução fechada (q_f de Mohr-Coulomb, 2·su, E_oed...). CD = drenado, CU = não drenado. O relatório de cada '
              'ensaio tem os gráficos e a conferência completa.</p>')]
    if invalidas:
        sec.append(("Linhas não executadas", A["html_tabela"](["Linha", "Material", "Ensaio", "Motivo"], invalidas)))
    if figuras:
        sec.append(("Primeiro gráfico de cada ensaio", '<div class="figs">' + "".join(figuras) + "</div>"))
    sec.append(("Planilhas", '<p class="nota">Ensaios: {}<br>Materiais: {}</p>'.format(
        A["_esc"](PLANILHA_ENSAIOS), A["_esc"](PLANILHA_MATERIAIS or "não usada (só materiais do projeto)"))))
    rel = A["relatorio_html"](os.path.join(pasta, "relatorio.html"), "Campanha de ensaios SoilTest",
                              "{} linha(s) na planilha | {} executada(s) | {} não executada(s)".format(
                                  len(brutas), len(brutas) - len(set(x[0] for x in invalidas)), len(set(x[0] for x in invalidas))), sec)
    log("\nCampanha: {} linha(s), {} curva(s) com resultado, {} linha(s) nao executada(s).".format(
        len(brutas), len(csv_linhas), len(set(x[0] for x in invalidas))))
    log("Relatorio: {}\nResumo CSV: {}\nSaida: {}".format(rel, os.path.join(pasta, "campanha_resumo.csv"), pasta))
    with open(os.path.join(pasta, "log.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(A["_linhas"]))
    return 0


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(traceback.format_exc())

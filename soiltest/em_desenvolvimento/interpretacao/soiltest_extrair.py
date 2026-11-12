# -*- coding: utf-8 -*-
"""
soiltest_extrair.py  -  Puxa os triaxiais do PLAXIS SoilTest, grava os CSV e faz o relatorio de interpretacao.

Tres jeitos de usar (CONFIG["modo"] e CONFIG["rodar_ensaios"]):
  "material"  (recomendado) - PLAXIS 3D Input aberto com o projeto. O script pega o material pelo nome
              (CONFIG["material"]; vazio = mostra a lista e pergunta), abre o SoilTest com ele, roda os triaxiais
              das pressoes e comportamentos do CONFIG e interpreta.
  "aberto"    - SoilTest ja aberto (pelo Input ou sozinho) com o servidor de scripts ativo. O script conecta nele
              (CONFIG["porta_soiltest"]; None = procura de 10000 a 10030) e:
                rodar_ensaios = True  -> roda os triaxiais do CONFIG no material que estiver na janela;
                rodar_ensaios = False -> SO LE o triaxial que voce ja calculou na janela (uma curva por vez).
                  Com CONFIG["pasta_ensaios"] fixa, cada execucao acrescenta a curva nessa pasta e refaz o
                  relatorio com todas (calcule 50 kPa, rode; calcule 100 kPa, rode; ...).
Comportamento -> tipo de ensaio no relatorio: Undrained -> CIU (CAU com K0), Drained -> CID (CAD com K0).
Material Undrained C (tensoes totais) -> UU. Material Non-porous so drenado; Undrained B/C so nao drenado.

SAIDA em soiltest_saida/extracao_<material>_<data>/ (ou em pasta_ensaios):
  ensaios/triaxial_CU_100kPa.csv ... (mesmo formato do plaxis_soiltest_auto.py), graficos/*.png, parametros.csv,
  interpretacao.json, relatorio.html (material, ensaios, parametros por criterio, graficos) e log.txt.
  Opcional: CONFIG["lab_csv"] poe o ensaio de laboratorio no mesmo relatorio, como outra serie.

COMO RODAR: pelo Executar_script_PLAXIS.bat. Senha do servidor: variavel PLAXIS_PASSWORD.
Precisa, nesta pasta: soiltest_interpretacao.py; e o plaxis_soiltest_auto.py aqui ou numa das duas pastas acima.
"""
import copy
import datetime
import os
import re
import traceback

AQUI = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()

# =========================== CONFIG ===========================
CONFIG = {
    "modo": "material",                 # "material" | "aberto"
    "material": "",                     # modo material: Identification do material no Input ("" = pergunta)
    "porta_soiltest": None,             # modo aberto: porta do SoilTest (None = procura)
    "rodar_ensaios": True,              # False (so no modo aberto): le o triaxial ja calculado na janela
    "pressoes_kPa": [50, 100, 200],     # sigma'3c de cada CP (CellPressure)
    "comportamentos": ["Undrained", "Drained"],   # "Undrained" (CIU/CAU) e/ou "Drained" (CID/CAD)
    "consolidacao": "Isotropic",        # "Isotropic" | "K0" (adensamento anisotropico: CAU/CAD)
    "K0": None,                         # com "K0": valor; None = K0 automatico do modelo (1 - sen phi)
    "MaximumStrain": 20,                # % de deformacao axial final
    "Steps": 100,
    "fechar_soiltest": True,            # modo material: fecha a janela no fim
    "pasta_ensaios": "",                # "" = pasta nova por execucao; caminho = acumula ensaios e refaz o relatorio
    "lab_csv": "",                      # opcional: CSV de laboratorio (modelo_entrada_laboratorio.csv) para comparar
    "descricao": "",                    # texto livre do relatorio
    # interpretacao
    "eps_limite_pct": 15.0,
    "criterio_principal": "q máximo",
    "queda_pos_pico": 0.10,
    "r2_minimo": 0.95,
}
# ==============================================================


def _carregar(nome, extra_dirs):
    for d in [""] + extra_dirs:
        cam = os.path.normpath(os.path.join(AQUI, d, nome))
        if os.path.isfile(cam):
            ns = {"__name__": os.path.splitext(nome)[0], "__file__": cam, "__builtins__": __builtins__}
            if "g_i" in globals():
                ns["g_i"], ns["s_i"] = globals()["g_i"], globals().get("s_i")
            with open(cam, "rb") as f:
                exec(compile(f.read(), cam, "exec"), ns, ns)
            return ns
    raise FileNotFoundError("Nao achei {} (procurei nesta pasta e em {}).".format(nome, ", ".join(extra_dirs)))


def listar_materiais(gi):
    for lista in ("Soils", "Materials"):
        try:
            mats = [m for m in getattr(gi, lista)]
            if mats:
                return mats
        except Exception:
            continue
    return []


def ler_material(A, mat):
    """(nome, nome do modelo, chave do modelo, chave da drenagem, parametros) de um material do Input."""
    ident = str(A["valor"](mat.Identification))
    sm = A["linha_echo"](mat, "SoilModel")
    dr = A["linha_echo"](mat, "DrainageType")
    modelo = next((k for k, v in A["MODELOS"].items() if sm and v["numero"] == sm[1]), None)
    dren = next((k for k, v in A["DRENAGENS"].items() if dr and v["nomes"][1] == dr[1]), None)
    p = {}
    if modelo and dren:
        for chave, aliases, _r, _v in A["parametros"](modelo, dren):
            attr = A["achar_attr"](mat, aliases)
            if attr is not None:
                try:
                    p[chave] = float(A["valor"](getattr(mat, attr)))
                except Exception:
                    pass
    return ident, (sm[0] if sm else "?"), modelo, dren, p


def escolher_material(A, mats, nome, log):
    lidos = []
    for m in mats:
        try:
            lidos.append((m,) + ler_material(A, m))
        except Exception as e:
            log("Material ignorado (nao li os dados): {}".format(e))
    if nome:
        for item in lidos:
            if item[1] == nome:
                return item
        log("Material '{}' nao existe no projeto. Materiais: {}".format(nome, ", ".join(i[1] for i in lidos) or "nenhum"))
        return None
    if not lidos:
        log("O projeto nao tem materiais de solo.")
        return None
    log("Materiais do projeto:")
    for i, it in enumerate(lidos, 1):
        log("   {}) {} ({}, {})".format(i, it[1], it[2], A["DRENAGENS"][it[4]]["rotulo"] if it[4] else "drenagem ?"))
    while True:
        r = input("Numero do material: ").strip()
        if r.isdigit() and 1 <= int(r) <= len(lidos):
            return lidos[int(r) - 1]
        log("Responda com um numero de 1 a {}.".format(len(lidos)))


def comportamentos_validos(pedidos, dren, log):
    """Non-porous so drena; Undrained B e C so nao drenado (o SoilTest recusa o resto)."""
    proibido = {"NP": "Undrained", "UB": "Drained", "UC": "Drained"}.get(dren)
    ok = [c for c in pedidos if c != proibido]
    for c in pedidos:
        if c == proibido:
            log("Comportamento {} ignorado: o material {} nao aceita.".format(c, dren))
    return ok


def ler_atual(A, g, pasta_ens, log):
    """Le o triaxial ja calculado na janela do SoilTest e grava o CSV. Devolve o nome do ensaio ou None."""
    t = g.Triaxial
    try:
        d = A["ler_triaxial"](t)
    except Exception as e:
        log("Nao consegui ler os resultados do Triaxial: {}".format(e))
        return None
    if len(d["eps_a_pct"]) < 2:
        log("O Triaxial da janela ainda nao foi calculado (sem resultados). Calcule no SoilTest e rode de novo.")
        return None
    try:
        pr = float(A["valor"](t.CellPressure))
    except Exception:
        pr = d["sig_r_kPa"][0]
        log("CellPressure nao lida; usei sigma'r inicial = {:.2f} kPa".format(pr))
    try:
        b = A["valor"](t.Behaviour)
        dren = b == 0 or str(b).strip().lower().startswith("drained") or str(b).strip() == "0"
    except Exception:
        dren = max(abs(v) for v in d["du_kPa"]) < 1e-9
        log("Behaviour nao lido; pela poropressao o ensaio e {}.".format("drenado" if dren else "nao drenado"))
    nome = A["nome_ensaio"]("Drained" if dren else "Undrained", pr)
    cam = os.path.join(pasta_ens, "triaxial_{}.csv".format(nome))
    if os.path.isfile(cam):
        log("ATENCAO: ja havia triaxial_{}.csv na pasta; substituido pela curva atual.".format(nome))
    A["gravar_csv"](cam, d)
    log("Triaxial lido da janela: {} ({} pontos, q max = {:.2f} kPa)".format(nome, len(d["q_kPa"]), max(d["q_kPa"])))
    return nome


def main():
    cfg = dict(CONFIG)
    I = _carregar("soiltest_interpretacao.py", [])
    A = _carregar("plaxis_soiltest_auto.py", ["..", os.path.join("..", "..")])
    A["log"] = I["log"]                       # um log so (o do auto vai para o mesmo log.txt)
    log = I["log"]
    acfg = A["CONFIG"]
    modo = cfg["modo"]
    if modo not in ("material", "aberto"):
        log("CONFIG['modo'] deve ser 'material' ou 'aberto'.")
        return 1
    if modo == "material" and not cfg["rodar_ensaios"]:
        log("No modo material o script sempre roda os ensaios (rodar_ensaios = False so vale no modo aberto).")
        cfg["rodar_ensaios"] = True

    ident, nome_mod, modelo, dren, p = "SoilTest", "?", None, None, {}
    g = None
    if modo == "material":
        gi = A["obter_input"](acfg)
        if gi is None:
            return 1
        esc = escolher_material(A, listar_materiais(gi), cfg["material"], log)
        if esc is None:
            return 1
        mat, ident, nome_mod, modelo, dren, p = esc
        log("Material: {} ({}, {})".format(ident, nome_mod, dren))
        g, porta = A["abrir_soiltest"](gi, mat, acfg["espera_soiltest_s"], acfg["porta_input"], modelo)
        if g is None:
            return 1
    else:
        senha = A["pedir_senha"]("Senha do servidor do SoilTest: ")
        porta = cfg["porta_soiltest"] or A["descobrir_porta"](senha, acfg["espera_soiltest_s"], None)
        if porta is None:
            log("Nenhum SoilTest respondendo entre as portas 10000 e 10030. Ative o servidor de scripts na janela do "
                "SoilTest (ou use o modo 'material').")
            return 1
        g = A["conectar_soiltest"](porta, senha, acfg["espera_soiltest_s"])
        log("Conectado ao SoilTest na porta {}.".format(porta))
        try:
            num = int(A["valor"](g.Material.SoilModel))
            modelo = next((k for k, v in A["MODELOS"].items() if v["numero"] == num), None)
            nome_mod = A["MODELOS"][modelo]["nome"] if modelo else "modelo {}".format(num)
        except Exception:
            pass
        try:
            ident = str(A["valor"](g.Material.Identification)) or ident
        except Exception:
            pass

    rotulo = re.sub(r"[^A-Za-z0-9_]+", "_", ident).strip("_") or "SoilTest"
    pasta = cfg["pasta_ensaios"] or os.path.join(AQUI, "soiltest_saida", "extracao_{}_{}".format(
        rotulo, datetime.datetime.now().strftime("%Y%m%d_%H%M%S")))
    pasta_ens = os.path.join(pasta, "ensaios")
    os.makedirs(pasta_ens, exist_ok=True)

    ensaios_info = []
    try:
        echo_mat = str(g.Material.echo())
    except Exception:
        echo_mat = ""
    try:
        if cfg["rodar_ensaios"]:
            comps = comportamentos_validos(cfg["comportamentos"], dren, log)
            c = copy.deepcopy(acfg)
            for chave in ("triaxial", "oedometer", "crs", "dss", "cdss", "triaxial_ciclico"):
                c[chave]["rodar"] = False
            c["triaxial"].update({"rodar": True, "pressoes_kPa": list(cfg["pressoes_kPa"]), "comportamentos": comps,
                                  "MaximumStrain": cfg["MaximumStrain"], "Steps": cfg["Steps"]})
            cons = {"tipo": cfg["consolidacao"]}
            k0 = None
            if cons["tipo"] == "K0":
                k0 = cfg["K0"]
                if k0 is None:
                    if modelo and p:
                        k0 = A["k0_automatico"](modelo, p)[0]
                    else:
                        log("K0 automatico precisa dos parametros do material (modo material); informe CONFIG['K0'].")
                        return 1
                cons["K0"] = k0
                log("Consolidacao K0 = {:.3f}".format(k0))
            ctx = {"modelo": modelo, "dren": dren, "consolidacao": cons, "k0": k0,
                   "preadensamento": {"modo": "nenhum", "valor": 0}, "pc_usados": set(),
                   "pc_fases_kPa": float(c.get("sigma_p_padrao_fases_kPa") or 0)}
            resumo = {}
            todas = A["executar_ensaios"](g, c, modelo, dren, p, ctx, pasta_ens, resumo)
            for nome, chk in (resumo.get("triaxial") or {}).items():
                ensaios_info.append((nome, chk.get("q_max_kPa"), (chk.get("esperado") or {}).get("kPa"),
                                     (chk.get("esperado") or {}).get("descricao", "")))
            if not (todas.get("Triaxial") or {}):
                log("Nenhum triaxial rodou (veja as mensagens acima).")
        else:
            ler_atual(A, g, pasta_ens, log)
    finally:
        if modo == "material" and cfg["fechar_soiltest"]:
            A["fechar_soiltest"](g)

    # interpretacao
    I["CONFIG"].update({k: cfg[k] for k in ("eps_limite_pct", "criterio_principal", "queda_pos_pico", "r2_minimo", "descricao")})
    icfg = dict(I["CONFIG"], lab_csv=cfg["lab_csv"], pastas_simulacao=[pasta_ens], pasta_saida=pasta)
    serie = "{} PLAXIS".format(ident)
    cps = I["ler_simulacao"](pasta_ens, serie=serie, total=(dren == "UC"))
    entradas = [("Material", "{} ({}{})".format(ident, nome_mod, ", " + A["DRENAGENS"][dren]["rotulo"] if dren else "")),
                ("Origem", "material do projeto no Input" if modo == "material" else "janela do SoilTest já aberta"),
                ("Ensaios", ", ".join(sorted(cp["nome"] for cp in cps)) or "nenhum")]
    if cfg["lab_csv"]:
        if os.path.isfile(cfg["lab_csv"]):
            lab = I["ler_lab"](cfg["lab_csv"])
            log("Laboratorio: {} ({} CP(s))".format(os.path.basename(cfg["lab_csv"]), len(lab)))
            entradas.append(("Laboratório", os.path.basename(cfg["lab_csv"])))
            cps = lab + cps
        else:
            log("ATENCAO: CSV de laboratorio nao encontrado: {}".format(cfg["lab_csv"]))
    if not cps:
        log("Nada para interpretar.")
        with open(os.path.join(pasta, "log.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(I["_linhas_log"]) + "\n")
        return 1

    esc, h = A["_esc"], ""
    if p:
        rot = {k: r for k, _a, r, _v in A["parametros"](modelo, dren)} if modelo and dren else {}
        h += A["html_tabela"](["Parâmetro", "Valor"], [(rot.get(k, k), A["_num"](v, 4)) for k, v in p.items()])
    if ensaios_info:
        h += "<p><b>Ensaios rodados</b> (conferência teórica do plaxis_soiltest_auto, quando houver)</p>"
        h += A["html_tabela"](["Ensaio", "q máx simulado (kPa)", "Esperado (kPa)", "Base do esperado"],
                              [(n, A["_num"](q, 2), A["_num"](e, 2) if e is not None else "-", d) for n, q, e, d in ensaios_info])
    h += "<p><b>Configuração</b>: CellPressure = {} kPa; comportamentos: {}; consolidação {}{}; ε_a máx = {} %; {} passos.</p>".format(
        ", ".join(A["fmt_num"](x) for x in cfg["pressoes_kPa"]), ", ".join(cfg["comportamentos"]), cfg["consolidacao"],
        " (K0 = {})".format(cfg["K0"]) if cfg["consolidacao"] == "K0" and cfg["K0"] else "", cfg["MaximumStrain"], cfg["Steps"]) \
        if cfg["rodar_ensaios"] else "<p>Curvas lidas da janela do SoilTest, como foram calculadas lá.</p>"
    if echo_mat:
        h += "<p><b>Material no SoilTest</b> (echo)</p><pre style=\"font-size:11.5px;background:#f5f7fb;padding:8px\">{}</pre>".format(esc(echo_mat))
    I["gerar_saidas"](A, cps, icfg, pasta, entradas, secoes_extra=[("Material e ensaios simulados", h)],
                      titulo="Ensaios triaxiais no PLAXIS SoilTest: {}".format(ident), ferramenta="soiltest_extrair.py",
                      extra_json={"material": {"nome": ident, "modelo": nome_mod, "drenagem": dren, "parametros": p}})
    return 0


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(traceback.format_exc())

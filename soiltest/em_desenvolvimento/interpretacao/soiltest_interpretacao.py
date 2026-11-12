# -*- coding: utf-8 -*-
"""
soiltest_interpretacao.py  -  Interpretacao de ensaios triaxiais como em laudo (UU, CIU/CAU, CID/CAD).

Interpreta ensaios de LABORATORIO (CSV) e ensaios SIMULADOS (pastas de saida do plaxis_soiltest_auto.py) do mesmo
jeito, em tensao total ou efetiva conforme o tipo:
- UU: tensao total. Su por CP (q_f / 2), circulos de Mohr, phi_u (deve ser ~0).
- CIU / CAU: total e efetiva. (c, phi) e (c', phi') pelos criterios de ruptura q maximo, sigma'1/sigma'3 maxima,
  eps_a limite e fim do ensaio; trajetorias p-q, p'-q (Cambridge) e s'-t (MIT); A de Skempton na ruptura
  (A_f = du_f / (q_f - q0)); du x eps_a.
- CID / CAD: efetiva. c', phi', eps_v x eps_a, angulo de dilatancia de pico e medio.
Alertas: amolecimento pos-pico, q maximo que nao cresce com sigma3, c' negativo, R2 baixo, CP que nao chega a
eps_a limite, CIU sem du.

ENTRADA 1 - CSV de laboratorio (separador ";", virgula ou ponto decimal). Colunas do formato atual:
    ensaio ; drenagem (U/D) ; sigma3_kPa ; eps_a_pct ; q_kPa ; du_kPa (U) ; ev_pct (D)
  e colunas novas, todas opcionais:
    tipo (UU, CIU, CAU, CID, CAD) ; serie (CPs da mesma envoltoria) ; sigma1_kPa (se q_kPa vazio, q = sigma1 - sigma3)
    ; u0_kPa (contrapressao, so informativa).
  sigma3_kPa: nos ensaios adensados e a tensao efetiva lateral de adensamento sigma'3c; no UU e a pressao de camara.
  Sem "tipo": U -> CIU (ou UU se nao houver du), D -> CID; vira CAU/CAD se houver ponto em eps_a = 0 com q > 0.
  Sem "serie": a serie e o tipo.
ENTRADA 2 - pastas de saida do plaxis_soiltest_auto.py (triaxial_CD_*.csv / triaxial_CU_*.csv). Cada pasta e uma
  serie. CU -> CIU/CAU, CD -> CID/CAD (CA* quando o passo 0 ja tem q > 0, consolidacao K0).
Convencao: compressao positiva, q = sigma1 - sigma3, du = excesso de poropressao (acrescimo +), eps_v contracao +.

SAIDA em soiltest_saida/interpretacao_<data>/ : um PNG por grafico (graficos/), parametros.csv (tabela por serie e
criterio), interpretacao.json, relatorio.html e log.txt.

COMO RODAR: nao precisa do PLAXIS. Pelo Executar_script_PLAXIS.bat (edite o CONFIG) ou no terminal:
    python soiltest_interpretacao.py lab.csv [pasta_do_auto ...]
Precisa do plaxis_soiltest_auto.py nesta pasta ou numa das duas acima (soiltest/), so pelo relatorio.
Para puxar os ensaios direto do PLAXIS SoilTest, use o soiltest_extrair.py (mesma pasta), que chama este script.
Modelo do CSV de laboratorio: modelo_entrada_laboratorio.csv (mesma pasta).
"""
import csv
import datetime
import glob
import json
import math
import os
import re
import sys
import traceback

AQUI = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()

# =========================== CONFIG ===========================
CONFIG = {
    "lab_csv": os.path.join(AQUI, "dados_laboratorio", "lab.csv"),   # "" para nao ler laboratorio (modelo: modelo_entrada_laboratorio.csv)
    "pastas_simulacao": [],             # pastas de saida do plaxis_soiltest_auto.py (cada uma vira uma serie)
    "descricao": "",                    # texto livre do relatorio (amostra, obra, laudo)
    "eps_limite_pct": 15.0,             # criterio "eps_a limite" (ruptura convencional sem pico)
    "criterio_principal": "q máximo",   # criterio dos circulos de Mohr e da tabela por CP
    "queda_pos_pico": 0.10,             # alerta de amolecimento: queda relativa de q depois do pico
    "r2_minimo": 0.95,                  # alerta de envoltoria com ajuste ruim
    "pasta_saida": "",                  # vazio = soiltest_saida/interpretacao_<data>/ ao lado do script
}
# ==============================================================

CRITERIOS = ["q máximo", "σ'1/σ'3 máxima", "ε_a limite", "fim do ensaio"]
TIPOS = ("UU", "CIU", "CAU", "CID", "CAD")
_linhas_log = []


def log(msg=""):
    msg = str(msg)
    print(msg)
    _linhas_log.append(msg)


def carregar_auto():
    for nome in ("plaxis_soiltest_auto.py", os.path.join("..", "plaxis_soiltest_auto.py"),
                 os.path.join("..", "..", "plaxis_soiltest_auto.py")):
        cam = os.path.normpath(os.path.join(AQUI, nome))
        if os.path.isfile(cam):
            break
    else:
        raise FileNotFoundError("Nao achei plaxis_soiltest_auto.py nesta pasta nem na pasta acima.")
    ns = {"__name__": "soiltest_auto", "__file__": cam, "__builtins__": __builtins__}
    if "g_i" in globals():
        ns["g_i"], ns["s_i"] = globals()["g_i"], globals().get("s_i")
    with open(cam, "rb") as f:
        exec(compile(f.read(), cam, "exec"), ns, ns)
    return ns


# ------------------------------------------------------------------ leitura
def _n(x):
    x = (x or "").strip().replace(",", ".")
    return float(x) if x != "" else None


def _cp(nome, tipo, serie, fonte, s3c, eps, q, du=None, ev=None, u0=None):
    """Corpo de prova no formato interno (listas ordenadas por eps_a)."""
    ordem = sorted(range(len(eps)), key=lambda i: eps[i])
    pega = lambda v: [v[i] for i in ordem] if v is not None else None
    return {"nome": nome, "tipo": tipo, "serie": serie, "fonte": fonte, "s3c": s3c, "u0": u0,
            "eps": pega(eps), "q": pega(q), "du": pega(du), "ev": pega(ev)}


def ler_lab(caminho):
    """Le o CSV de laboratorio (formato atual ou estendido). Devolve lista de CPs."""
    brutos = {}
    with open(caminho, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            nome = (r.get("ensaio") or "").strip()
            if not nome:
                continue
            e = brutos.setdefault(nome, {"tipo": (r.get("tipo") or "").strip().upper(), "serie": (r.get("serie") or "").strip(),
                                         "dren": (r.get("drenagem") or "").strip().upper()[:1], "s3c": _n(r.get("sigma3_kPa")),
                                         "u0": _n(r.get("u0_kPa")), "eps": [], "q": [], "du": [], "ev": []})
            q = _n(r.get("q_kPa"))
            if q is None and _n(r.get("sigma1_kPa")) is not None:
                q = _n(r.get("sigma1_kPa")) - e["s3c"]
            e["eps"].append(_n(r.get("eps_a_pct"))); e["q"].append(q)
            e["du"].append(_n(r.get("du_kPa"))); e["ev"].append(_n(r.get("ev_pct")))
    cps = []
    for nome, e in brutos.items():
        tem_du = any(v is not None for v in e["du"])
        tem_ev = any(v is not None for v in e["ev"])
        tipo = e["tipo"]
        if tipo and tipo not in TIPOS:
            log("ATENCAO: {}: tipo '{}' desconhecido (use {}); ensaio ignorado.".format(nome, tipo, ", ".join(TIPOS)))
            continue
        if not tipo:
            if e["dren"] == "D" or (tem_ev and not tem_du):
                tipo = "CID"
            elif tem_du:
                tipo = "CIU"
            else:
                tipo = "UU"
                log("{}: sem coluna tipo e sem du -> interpretado como UU (tensao total).".format(nome))
            q0 = _q_inicial(e["eps"], e["q"])
            if tipo != "UU" and q0 is not None and q0 > max(1.0, 0.02 * (e["s3c"] or 0)):
                tipo = tipo.replace("CI", "CA")
                log("{}: q = {:.1f} kPa em eps_a = 0 -> adensamento anisotropico ({}).".format(nome, q0, tipo))
        if any(v is None for v in e["eps"]) or any(v is None for v in e["q"]):
            log("ATENCAO: {}: ha linhas sem eps_a ou sem q (nem sigma1); ensaio ignorado.".format(nome))
            continue
        du = e["du"] if tipo in ("CIU", "CAU") and tem_du else None
        if du is not None and any(v is None for v in du):
            log("ATENCAO: {}: du faltando em parte das linhas; so a interpretacao em tensao total.".format(nome))
            du = None
        ev = e["ev"] if tipo in ("CID", "CAD") and tem_ev and all(v is not None for v in e["ev"]) else None
        if tipo in ("CID", "CAD"):
            du = [0.0] * len(e["eps"])
        cps.append(_cp(nome, tipo, e["serie"] or tipo, "laboratório", e["s3c"], e["eps"], e["q"], du, ev, e["u0"]))
    return cps


def _q_inicial(eps, q):
    for a, b in zip(eps, q):
        if a is not None and b is not None and abs(a) < 1e-12:
            return b
    return None


def ler_simulacao(pasta, serie=None, total=False):
    """Le os triaxiais de uma pasta (saida do plaxis_soiltest_auto.py ou do soiltest_extrair.py). Uma serie por tipo
    de ensaio: "<serie> CIU", "<serie> CID" etc.
    total=True: material em tensoes totais (Undrained C); os ensaios CU viram UU (sem du)."""
    serie = serie or "SIM " + os.path.basename(os.path.normpath(pasta))
    cps = []
    for cam in sorted(glob.glob(os.path.join(pasta, "triaxial_C[DU]_*.csv"))):
        cols = {}
        with open(cam, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f, delimiter=";"):
                for k, v in r.items():
                    cols.setdefault(k, []).append(_n(v))
        if not cols.get("eps_a_pct"):
            continue
        cu = "_CU_" in os.path.basename(cam)
        s3c = cols["sig_r_kPa"][0]
        q0 = cols["q_kPa"][0]
        aniso = q0 > max(1.0, 0.02 * s3c)
        tipo = ("CAU" if aniso else "CIU") if cu else ("CAD" if aniso else "CID")
        nome = os.path.splitext(os.path.basename(cam))[0]
        du = [v or 0.0 for v in cols["du_kPa"]] if cu else [0.0] * len(cols["eps_a_pct"])
        if total and cu:
            tipo, du = "UU", None
        cps.append(_cp(nome, tipo, "{} {}".format(serie, tipo), "simulação", s3c, cols["eps_a_pct"], cols["q_kPa"], du,
                       None if cu else cols.get("ev_pct")))
    if not cps:
        log("ATENCAO: nenhum triaxial_CD_*/triaxial_CU_*.csv em {}".format(pasta))
    return cps


# ------------------------------------------------------------------ tensoes e criterios
def tensoes(cp):
    """Lista de pontos com tensoes totais (relativas a contrapressao) e efetivas."""
    pts = []
    for i, (ea, q) in enumerate(zip(cp["eps"], cp["q"])):
        du = cp["du"][i] if cp["du"] is not None else None
        s3 = cp["s3c"] if cp["tipo"] != "UU" else cp["s3c"]
        p = {"i": i, "eps": ea, "q": q, "du": du, "s3": s3, "s1": s3 + q}
        if du is not None:
            p["s3e"] = s3 - du
            p["s1e"] = p["s3e"] + q
            p["razao"] = p["s1e"] / p["s3e"] if p["s3e"] > 0 else None
        pts.append(p)
    return pts


def _interp_ponto(pts, eps_alvo):
    for a, b in zip(pts, pts[1:]):
        if a["eps"] <= eps_alvo <= b["eps"] and b["eps"] > a["eps"]:
            w = (eps_alvo - a["eps"]) / (b["eps"] - a["eps"])
            p = {"i": None, "eps": eps_alvo}
            for k in ("q", "du", "s3", "s1", "s3e", "s1e"):
                if a.get(k) is not None and b.get(k) is not None:
                    p[k] = a[k] + w * (b[k] - a[k])
            if p.get("s3e"):
                p["razao"] = p["s1e"] / p["s3e"]
            return p
    return None


def pontos_ruptura(cp, eps_lim):
    """{criterio: ponto ou None}. O ponto em eps_a = 0 nao conta."""
    pts = [p for p in tensoes(cp) if p["eps"] > 0]
    if not pts:
        return {c: None for c in CRITERIOS}
    r = {"q máximo": max(pts, key=lambda p: p["q"])}
    com_razao = [p for p in pts if p.get("razao") is not None]
    r["σ'1/σ'3 máxima"] = max(com_razao, key=lambda p: p["razao"]) if com_razao else None
    r["ε_a limite"] = _interp_ponto(tensoes(cp), eps_lim) if pts[-1]["eps"] >= eps_lim else None
    r["fim do ensaio"] = pts[-1]
    return r


def q_inicial(cp):
    return cp["q"][0] if cp["eps"] and abs(cp["eps"][0]) < 1e-12 else 0.0


# ------------------------------------------------------------------ envoltoria (implementacao unica)
def envoltoria(pontos):
    """Regressao t = m + s tan(alfa) em pontos (s, t) (total ou efetiva).

    Devolve dict: phi (graus), c (kPa), alfa (graus), m, r2, residuos (t medido - t da reta), n,
    M (q/p' no estado critico, compressao triaxial) e, quando c < 0, phi_c0 (ajuste com c = 0). None se nao der."""
    n = len(pontos)
    if n < 2:
        return None
    sx = sum(p[0] for p in pontos); sy = sum(p[1] for p in pontos)
    sxx = sum(p[0] ** 2 for p in pontos); sxy = sum(p[0] * p[1] for p in pontos)
    den = n * sxx - sx * sx
    if abs(den) < 1e-12 * max(1.0, sxx * n):
        return None
    a = (n * sxy - sx * sy) / den
    m = (sy - a * sx) / n
    if not -1 < a < 1:
        return None
    phi = math.asin(a)
    res = [p[1] - (m + a * p[0]) for p in pontos]
    ym = sy / n
    sst = sum((p[1] - ym) ** 2 for p in pontos)
    sse = sum(r * r for r in res)
    r2 = 1.0 - sse / sst if sst > 1e-12 else (1.0 if sse < 1e-9 else 0.0)
    s = math.sin(phi)
    out = {"phi": math.degrees(phi), "c": m / math.cos(phi), "alfa": math.degrees(math.atan(a)), "m": m, "r2": r2,
           "residuos": res, "n": n, "M": 6 * s / (3 - s)}
    if out["c"] < 0:
        a0 = sxy / sxx
        out["phi_c0"] = math.degrees(math.asin(a0)) if 0 <= a0 < 1 else None
    return out


def dilatancia(cp):
    """Angulo de dilatancia (triaxial): sin psi = -r / (2 - r), r = d eps_v / d eps_a (contracao +).
    Pico: maior taxa de dilatacao entre pontos consecutivos. Medio: secante do trecho dilatante (da contracao
    maxima ao eps_v minimo depois dela)."""
    if not cp.get("ev"):
        return None
    eps, ev = cp["eps"], cp["ev"]
    ang = lambda r: math.degrees(math.asin(max(-1.0, min(1.0, -r / (2 - r)))))
    taxas = [((ev[i + 1] - ev[i]) / (eps[i + 1] - eps[i]), i) for i in range(len(eps) - 1) if eps[i + 1] > eps[i]]
    if not taxas:
        return None
    rmin, imin = min(taxas)
    i_c = max(range(len(ev)), key=lambda i: ev[i])                 # contracao maxima
    if i_c >= len(ev) - 1:
        return {"dilata": False, "psi_pico": 0.0, "psi_medio": 0.0, "eps_contracao_max": eps[i_c], "ev_max": ev[i_c]}
    i_d = min(range(i_c, len(ev)), key=lambda i: ev[i])            # eps_v minimo depois dela
    r_med = (ev[i_d] - ev[i_c]) / (eps[i_d] - eps[i_c]) if eps[i_d] > eps[i_c] else 0.0
    return {"dilata": rmin < 0, "psi_pico": ang(rmin) if rmin < 0 else 0.0, "eps_psi_pico": 0.5 * (eps[imin] + eps[imin + 1]),
            "psi_medio": ang(r_med) if r_med < 0 else 0.0, "eps_contracao_max": eps[i_c], "ev_max": ev[i_c],
            "eps_fim_dilatacao": eps[i_d]}


# ------------------------------------------------------------------ interpretacao por serie
def interpretar_serie(nome, cps, cfg):
    tipo = cps[0]["tipo"]
    tipos = sorted({c["tipo"] for c in cps})
    res = {"serie": nome, "tipo": "/".join(tipos), "fonte": cps[0]["fonte"], "cps": [], "envoltorias": {"total": {}, "efetiva": {}},
           "alertas": []}
    if len(tipos) > 1:
        res["alertas"].append("Série {} mistura tipos de ensaio ({}); confira a coluna serie.".format(nome, ", ".join(tipos)))
    total = all(c["tipo"] in ("UU", "CIU", "CAU") for c in cps)
    efetiva = all(c["tipo"] != "UU" and c["du"] is not None for c in cps)
    eps_lim = cfg["eps_limite_pct"]
    for cp in sorted(cps, key=lambda c: c["s3c"]):
        rup = pontos_ruptura(cp, eps_lim)
        q0 = q_inicial(cp)
        item = {"nome": cp["nome"], "tipo": cp["tipo"], "s3c": cp["s3c"], "u0": cp["u0"], "q0": q0, "eps_max": cp["eps"][-1],
                "ruptura": {}, "dilatancia": dilatancia(cp) if cp["tipo"] in ("CID", "CAD") else None}
        for crit, p in rup.items():
            if p is None:
                item["ruptura"][crit] = None
                continue
            d = {k: p.get(k) for k in ("eps", "q", "du", "s3", "s1", "s3e", "s1e", "razao")}
            if cp["tipo"] in ("CIU", "CAU") and p.get("du") is not None and p["q"] - q0 > 1e-9:
                d["A"] = p["du"] / (p["q"] - q0)
            if cp["tipo"] == "UU":
                d["Su"] = p["q"] / 2.0
            item["ruptura"][crit] = d
        if rup["ε_a limite"] is None:
            res["alertas"].append("{}: ensaio termina em ε_a = {:g} %, antes do limite de {:g} % (critério ε_a limite sem este CP)."
                                  .format(cp["nome"], cp["eps"][-1], eps_lim))
        if cp["tipo"] in ("CIU", "CAU") and cp["du"] is None:
            res["alertas"].append("{}: {} sem Δu; só a interpretação em tensão total.".format(cp["nome"], cp["tipo"]))
        # amolecimento pos-pico
        qp, qf = rup["q máximo"], rup["fim do ensaio"]
        if qp and qf and qp["q"] > 0 and qp["eps"] < qf["eps"]:
            queda = (qp["q"] - qf["q"]) / qp["q"]
            if queda > cfg["queda_pos_pico"]:
                res["alertas"].append("{}: amolecimento pós-pico, q cai {:.0f} % (de {:.1f} kPa em ε_a = {:g} % para {:.1f} kPa no fim). "
                                      "Os critérios dão resistências diferentes; escolha o critério conforme o uso (pico ou pós-pico)."
                                      .format(cp["nome"], 100 * queda, qp["q"], qp["eps"], qf["q"]))
        res["cps"].append(item)

    # nao drenado sem pico: q ainda sobe no fim (material dilatante sem drenagem, du cada vez mais negativo)
    sem_pico = []
    for c in res["cps"]:
        cp = next(x for x in cps if x["nome"] == c["nome"])
        if c["tipo"] not in ("CIU", "CAU", "UU") or len(cp["eps"]) < 3:
            continue
        e_fim, q_fim = cp["eps"][-1], cp["q"][-1]
        alvo = 0.8 * e_fim
        q_80 = next(q for e, q in zip(cp["eps"], cp["q"]) if e >= alvo)
        if q_fim >= max(cp["q"]) - 1e-9 and q_80 > 0 and (q_fim - q_80) / q_80 > 0.05:
            d = c["ruptura"]["q máximo"] or {}
            sem_pico.append("{} (q {:.0f} → {:.0f} kPa de {:g} a {:g} %{})".format(
                c["nome"], q_80, q_fim, alvo, e_fim, ", A_f = {:.2f}".format(d["A"]) if d.get("A") is not None else ""))
    if sem_pico:
        if cps[0]["fonte"] == "simulação":
            causa = ("CAUSA: é o comportamento conhecido do Hardening Soil (e de outros modelos, como Mohr-Coulomb e HS small) "
                     "com ângulo de dilatância ψ > 0 em análise não drenada. O material tenta aumentar de volume ao "
                     "cisalhar, mas sem drenagem o volume não pode mudar; então a poropressão cai sem parar (Δu cada vez "
                     "mais negativo, A_f < 0), a tensão efetiva média cresce e q sobe sem limite. Não é erro de cálculo "
                     "do PLAXIS nem do script: é uma limitação do modelo, que superestima a resistência não drenada. "
                     "COMO EVITAR no material: ψ = 0, corte de dilatância (dilatancy cut-off, com e_max) ou Undrained B "
                     "(Su direto).")
        else:
            causa = ("CAUSAS POSSÍVEIS (confira no laudo): "
                     "(1) solo dilatante (areia densa, argila muito pré-adensada): ao cisalhar ele tende a expandir, e sem "
                     "drenagem a poropressão cai (Δu negativo, A_f < 0) e q continua subindo até o limite da cavitação ou "
                     "da contrapressão do ensaio; "
                     "(2) corpo de prova não saturado (B de Skempton baixo): parte do acréscimo de tensão é absorvida pelo "
                     "ar dos vazios, o Δu medido fica pequeno ou negativo sem que o solo seja dilatante e a resistência "
                     "parece maior do que é; confira se B ≥ 0,95 antes do cisalhamento; "
                     "(3) velocidade de cisalhamento alta demais: a poropressão não tem tempo de se equalizar no corpo de "
                     "prova, o transdutor na base mede um Δu que não representa o interior (em geral menor) e a curva sai "
                     "distorcida; confira a velocidade usada contra a calculada pelo t100 do adensamento.")
        res["alertas"].append(
            "Não drenado sem pico: q ainda cresce no fim do ensaio em {}. {} CONSEQUÊNCIA: a resistência pelo q máximo e "
            "pelo fim do ensaio depende só de onde o ensaio parou, e a envoltória total desses critérios não tem "
            "significado físico; a envoltória efetiva continua válida. Use os critérios σ'1/σ'3 máxima ou ε_a limite."
            .format("; ".join(sem_pico), causa))

    # q maximo deve crescer com sigma3 nos ensaios adensados
    if tipo != "UU":
        lst = [(c["nome"], c["s3c"], c["ruptura"]["q máximo"]["q"]) for c in res["cps"] if c["ruptura"].get("q máximo")]
        for (k1, s1, q1), (k2, s2, q2) in zip(lst, lst[1:]):
            if s2 > s1 and q2 <= q1:
                res["alertas"].append("q máximo não cresce com σ'3c: {} ({:g} kPa) tem {:.1f} kPa e {} ({:g} kPa) só {:.1f} kPa. "
                                      "Provável variabilidade entre corpos de prova; a envoltória fica distorcida."
                                      .format(k1, s1, q1, k2, s2, q2))
    else:
        sus = [c["ruptura"]["q máximo"]["Su"] for c in res["cps"] if c["ruptura"].get("q máximo")]
        if sus:
            med = sum(sus) / len(sus)
            res["Su_medio"] = med
            if med > 0 and (max(sus) - min(sus)) / med > 0.20:
                res["alertas"].append("UU: Su varia {:.0f} % entre CPs (de {:.1f} a {:.1f} kPa); confira saturação e amolgamento."
                                      .format(100 * (max(sus) - min(sus)) / med, min(sus), max(sus)))

    # envoltorias por criterio
    for crit in CRITERIOS:
        pts_t, pts_e = [], []
        for c in res["cps"]:
            d = c["ruptura"].get(crit)
            if not d:
                continue
            if total and d.get("s1") is not None:
                pts_t.append(((d["s1"] + d["s3"]) / 2.0, (d["s1"] - d["s3"]) / 2.0))
            if efetiva and d.get("s3e") is not None:
                pts_e.append(((d["s1e"] + d["s3e"]) / 2.0, (d["s1e"] - d["s3e"]) / 2.0))
        if total and pts_t:
            res["envoltorias"]["total"][crit] = envoltoria(pts_t)
        if efetiva and pts_e:
            res["envoltorias"]["efetiva"][crit] = envoltoria(pts_e)
    for chave in ("total", "efetiva"):
        ruins = []
        for crit, env in res["envoltorias"][chave].items():
            if not env:
                continue
            if env["c"] < -0.5:
                res["alertas"].append("Envoltória {} ({}): c = {:.1f} kPa negativo. Ajuste com c = 0: φ = {}."
                                      .format(chave, crit, env["c"], "{:.1f}°".format(env["phi_c0"]) if env.get("phi_c0") else "-"))
            if env["n"] > 2 and env["r2"] < cfg["r2_minimo"]:
                ruins.append("{} {:.3f}".format(crit, env["r2"]))
        if ruins:
            res["alertas"].append("Envoltória {} com ajuste ruim (R² abaixo de {:g}): {}.".format(chave, cfg["r2_minimo"], "; ".join(ruins)))
    if tipo != "UU" and len(res["cps"]) < 3:
        res["alertas"].append("Série com {} CP(s): a envoltória precisa de ao menos 2 e o laudo usa 3 ou mais.".format(len(res["cps"])))
    return res


def interpretar(cps, cfg):
    series = {}
    for c in cps:
        series.setdefault(c["serie"], []).append(c)
    return [interpretar_serie(k, v, cfg) for k, v in series.items()]


# ------------------------------------------------------------------ graficos
ROT = {
    "eps": r"$\varepsilon_a$ – deformação axial (%)",
    "q": r"$q = \sigma_1 - \sigma_3$ – tensão desviadora (kPa)",
    "du": r"$\Delta u$ – excesso de poropressão (kPa) [acréscimo +]",
    "ev": r"$\varepsilon_v$ – deformação volumétrica (%) [contração +]",
    "razao": r"$\sigma'_1/\sigma'_3$ – razão de tensões efetivas",
    "A": r"$A = \Delta u / (q - q_0)$ – parâmetro de Skempton",
    "p_ef": r"$p' = (\sigma'_1 + 2\sigma'_3)/3$ – tensão efetiva média (kPa)",
    "p_tot": r"$p = (\sigma_1 + 2\sigma_3)/3$ – tensão total média (kPa)",
    "s_ef": r"$s' = (\sigma'_1 + \sigma'_3)/2$ (kPa)",
    "t": r"$t = (\sigma_1 - \sigma_3)/2$ (kPa)",
    "sigma_ef": r"$\sigma'$ – tensão normal efetiva (kPa)",
    "sigma_tot": r"$\sigma$ – tensão normal total (kPa)",
    "tau": r"$\tau$ – tensão cisalhante (kPa)",
}
MARCAS = {"q máximo": "o", "σ'1/σ'3 máxima": "s", "ε_a limite": "^", "fim do ensaio": "D"}


def _mt(v, casas=1):
    """Numero para mathtext com virgula decimal."""
    return "{:.{}f}".format(v, casas).replace(".", "{,}")


def _arq(t):
    return re.sub(r"[^A-Za-z0-9_]+", "_", t).strip("_")


def graficos(res, cps, pasta, cfg):
    """Um PNG por grafico, por serie. Devolve {serie: [(caminho, legenda)]}."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        log("Graficos nao gerados: {}".format(e))
        return {}
    os.makedirs(os.path.join(pasta, "graficos"), exist_ok=True)
    por_nome = {(c["serie"], c["nome"]): c for c in cps}
    crit_p = cfg["criterio_principal"]
    out = {}
    for s in res:
        lst = []
        itens = s["cps"]
        cores = plt.get_cmap("viridis")
        cor = {it["nome"]: cores(0.85 * i / max(1, len(itens) - 1)) for i, it in enumerate(itens)}
        rot_cp = lambda it: "{} ({} = {:g} kPa)".format(it["nome"], "σ3" if it["tipo"] == "UU" else "σ'3c", it["s3c"])
        base = _arq(s["serie"])

        def salvar(fig, ax, arq, titulo, legenda, leg=True):
            ax.set_title("{}\nSérie {} ({})".format(titulo, s["serie"], s["tipo"]), fontsize=10)
            ax.grid(True, alpha=0.3)
            if leg:
                ax.legend(fontsize=7.5, loc="best")
            fig.tight_layout()
            cam = os.path.join(pasta, "graficos", "{}_{}.png".format(base, arq))
            fig.savefig(cam, dpi=150); plt.close(fig)
            lst.append((cam, legenda))

        def curva(chave_y, arq, titulo, legenda, f_y):
            fig, ax = plt.subplots(figsize=(7.5, 5.2))
            desenhou = False
            todos_y = []
            for it in itens:
                cp = por_nome[(s["serie"], it["nome"])]
                pts = tensoes(cp)
                ys = [f_y(cp, p) for p in pts]
                todos_y += [y for y in ys if y is not None]
                xy = [(p["eps"], y) for p, y in zip(pts, ys) if y is not None]
                if len(xy) < 2:
                    continue
                ax.plot([a for a, _ in xy], [b for _, b in xy], "-", color=cor[it["nome"]], lw=1.4, label=rot_cp(it))
                desenhou = True
                for crit, d in it["ruptura"].items():
                    if d and chave_y != "ev":
                        y = f_y(cp, d) if chave_y != "A" else d.get("A")
                        if y is not None:
                            ax.plot(d["eps"], y, MARCAS[crit], ms=6, mfc="none", color=cor[it["nome"]])
            if not desenhou:
                plt.close(fig)
                return
            if chave_y != "ev":
                for crit, mk in MARCAS.items():
                    ax.plot([], [], mk, mfc="none", color="0.3", label="ruptura: " + crit)
            ax.set_xlabel(ROT["eps"]); ax.set_ylabel(ROT[chave_y])
            ax.ticklabel_format(axis="y", useOffset=False, style="plain")
            lo, hi = min(todos_y), max(todos_y)
            if hi - lo < 1e-6 * max(1.0, abs(hi)):          # curva constante: faixa minima (sem ruido de arredondamento)
                ax.set_ylim(min(0.0, lo) - 0.1 * max(1.0, abs(hi)), max(0.0, hi) + 0.1 * max(1.0, abs(hi)))
            salvar(fig, ax, arq, titulo, legenda)

        curva("q", "q_x_eps_a", "Tensão desviadora × deformação axial", "q × ε_a com os pontos de ruptura de cada critério",
              lambda cp, p: p["q"])
        if any(it["tipo"] in ("CIU", "CAU") for it in itens):
            curva("du", "du_x_eps_a", "Excesso de poropressão × deformação axial", "Δu × ε_a", lambda cp, p: p.get("du"))
            curva("A", "A_x_eps_a", "Parâmetro A de Skempton × deformação axial",
                  "A × ε_a (A = Δu / (q − q0); só depois de 5 % do acréscimo de q até o pico)",
                  lambda cp, p: (p["du"] / (p["q"] - q_inicial(cp))) if p.get("du") is not None and p["eps"] > 0
                  and p["q"] - q_inicial(cp) > 0.05 * (max(cp["q"]) - q_inicial(cp)) else None)
        if any(it["tipo"] != "UU" for it in itens):
            curva("razao", "razao_x_eps_a", "Razão de tensões efetivas × deformação axial", "σ'1/σ'3 × ε_a",
                  lambda cp, p: p.get("razao") if p["eps"] > 0 else None)
        if any(it["tipo"] in ("CID", "CAD") for it in itens):
            curva("ev", "ev_x_eps_a", "Deformação volumétrica × deformação axial", "ε_v × ε_a (contração +)",
                  lambda cp, p: cp["ev"][p["i"]] if cp.get("ev") and p.get("i") is not None else None)

        # trajetorias
        efet = bool(s["envoltorias"]["efetiva"])
        tot = bool(s["envoltorias"]["total"])
        for modo in (["cambridge", "mit"] if efet else []) + (["total"] if tot and s["tipo"] != "UU" else []):
            fig, ax = plt.subplots(figsize=(7.5, 5.2))
            xmax = 0.0
            for it in itens:
                cp = por_nome[(s["serie"], it["nome"])]
                pts = tensoes(cp)
                if modo == "cambridge":
                    x = [(p["s1e"] + 2 * p["s3e"]) / 3 for p in pts]; y = [p["q"] for p in pts]
                elif modo == "mit":
                    x = [(p["s1e"] + p["s3e"]) / 2 for p in pts]; y = [p["q"] / 2 for p in pts]
                else:
                    x = [(p["s1"] + 2 * p["s3"]) / 3 for p in pts]; y = [p["q"] for p in pts]
                ax.plot(x, y, "-", color=cor[it["nome"]], lw=1.4, label=rot_cp(it))
                d = it["ruptura"].get(crit_p)
                if d:
                    if modo == "cambridge":
                        ax.plot((d["s1e"] + 2 * d["s3e"]) / 3, d["q"], "o", mfc="none", ms=7, color=cor[it["nome"]])
                    elif modo == "mit":
                        ax.plot((d["s1e"] + d["s3e"]) / 2, d["q"] / 2, "o", mfc="none", ms=7, color=cor[it["nome"]])
                    else:
                        ax.plot((d["s1"] + 2 * d["s3"]) / 3, d["q"], "o", mfc="none", ms=7, color=cor[it["nome"]])
                xmax = max(xmax, max(x))
            env = s["envoltorias"]["efetiva" if modo != "total" else "total"].get(crit_p)
            if env:
                xs = [0, 1.1 * xmax]
                if modo == "mit":
                    tg = math.tan(math.radians(env["alfa"]))
                    ax.plot(xs, [env["m"] + tg * v for v in xs], "--", color="#b3261e",
                            label=r"$K_f$: $t = {} + s'\,\tan {}°$".format(_mt(env["m"]), _mt(env["alfa"])))
                else:
                    sp = math.sin(math.radians(env["phi"]))
                    M = 6 * sp / (3 - sp)
                    qc = 6 * env["c"] * math.cos(math.radians(env["phi"])) / (3 - sp)
                    nome_p = "p'" if modo == "cambridge" else "p"
                    ax.plot(xs, [qc + M * v for v in xs], "--", color="#b3261e",
                            label=r"ruptura (compressão): $q = {} + {}\,{}$".format(_mt(qc), _mt(M, 3), nome_p))
            ax.set_xlim(left=0); ax.set_ylim(bottom=min(0, ax.get_ylim()[0]))
            if modo == "cambridge":
                ax.set_xlabel(ROT["p_ef"]); ax.set_ylabel(ROT["q"])
                salvar(fig, ax, "trajetoria_p_q_efetiva", "Trajetória de tensões efetivas p'–q (Cambridge)",
                       "Trajetórias p'–q; círculo = ruptura ({}); tracejado = envoltória efetiva".format(crit_p))
            elif modo == "mit":
                ax.set_xlabel(ROT["s_ef"]); ax.set_ylabel(ROT["t"])
                salvar(fig, ax, "trajetoria_s_t_efetiva", "Trajetória de tensões efetivas s'–t (MIT)",
                       "Trajetórias s'–t; círculo = ruptura ({}); tracejado = linha Kf".format(crit_p))
            else:
                ax.set_xlabel(ROT["p_tot"]); ax.set_ylabel(ROT["q"])
                salvar(fig, ax, "trajetoria_p_q_total", "Trajetória de tensões totais p–q",
                       "Trajetórias totais p–q (relativas à contrapressão); tracejado = envoltória total")

        # circulos de Mohr
        for chave in ("total", "efetiva"):
            env = s["envoltorias"][chave].get(crit_p)
            if not s["envoltorias"][chave]:
                continue
            fig, ax = plt.subplots(figsize=(7.5, 5.2))
            smax = rmax = 0.0
            for it in itens:
                d = it["ruptura"].get(crit_p)
                if not d:
                    continue
                a, b = (d["s3"], d["s1"]) if chave == "total" else (d["s3e"], d["s1e"])
                c, r = (a + b) / 2, (b - a) / 2
                th = [math.pi * k / 90 for k in range(91)]
                ax.plot([c + r * math.cos(t) for t in th], [r * math.sin(t) for t in th], "-", color=cor[it["nome"]], lw=1.4,
                        label=rot_cp(it))
                smax = max(smax, b); rmax = max(rmax, r)
            if env:
                xs = [0, 1.05 * smax]
                tg = math.tan(math.radians(env["phi"]))
                lab = (r"$\tau = {} + \sigma\,\tan {}°$" if chave == "total" else r"$\tau = {} + \sigma'\,\tan {}°$")
                ax.plot(xs, [env["c"] + tg * v for v in xs], "--", color="#b3261e", label=lab.format(_mt(env["c"]), _mt(env["phi"])))
            ax.set_aspect("equal", adjustable="box")
            ax.set_xlim(0, 1.05 * smax); ax.set_ylim(0, max(1.35 * rmax, 0.32 * smax, (env["c"] + 0.3 * rmax) if env else 0))
            ax.set_xlabel(ROT["sigma_tot" if chave == "total" else "sigma_ef"]); ax.set_ylabel(ROT["tau"])
            salvar(fig, ax, "mohr_" + chave, "Círculos de Mohr na ruptura, tensão {} ({})".format(chave, crit_p),
                   "Círculos de Mohr em tensão {} ({}) com a envoltória".format(chave, crit_p))
        out[s["serie"]] = lst
    return out


# ------------------------------------------------------------------ saidas
def _f(v, casas=1):
    return "-" if v is None else "{:.{}f}".format(v, casas).replace(".", ",")


def tabela_parametros(res):
    """Linhas (serie, tipo, fonte, tensao, criterio, n, c, phi, R2, M, phi_c0)."""
    lin = []
    for s in res:
        for chave in ("total", "efetiva"):
            for crit in CRITERIOS:
                if crit not in s["envoltorias"][chave]:
                    continue
                e = s["envoltorias"][chave][crit]
                lin.append((s["serie"], s["tipo"], s["fonte"], chave, crit, e["n"] if e else 0, e["c"] if e else None,
                            e["phi"] if e else None, e["r2"] if e else None, e["M"] if e else None, (e or {}).get("phi_c0")))
    return lin


def gravar_csv_parametros(caminho, lin):
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("serie;tipo;fonte;tensao;criterio;n_cps;c_kPa;phi_graus;R2;M;phi_c0_graus\n")
        for l in lin:
            f.write(";".join(str(x) if not isinstance(x, float) else "{:.4f}".format(x) for x in [v if v is not None else "" for v in l]) + "\n")


def relatorio(A, pasta, res, figs, cfg, entradas, secoes_extra=None, titulo=None, ferramenta="soiltest_interpretacao.py"):
    sec = []
    sec.append(("Entradas", A["html_tabela"](["Item", "Valor"], entradas + [
        ("ε_a limite", "{:g} %".format(cfg["eps_limite_pct"])), ("Critério dos círculos de Mohr", cfg["criterio_principal"]),
        ("Convenção", "compressão +; q = σ1 − σ3; Δu = excesso de poropressão (acréscimo +); ε_v contração +; "
                      "tensões totais relativas à contrapressão")])))
    lin = tabela_parametros(res)
    sec.append(("Parâmetros de resistência por critério", A["html_tabela"](
        ["Série", "Tipo", "Fonte", "Tensão", "Critério", "CPs", "c ou c' (kPa)", "φ ou φ' (°)", "R²", "M", "φ com c = 0 (°)"],
        [(l[0], l[1], l[2], l[3], l[4], l[5], _f(l[6]), _f(l[7]), _f(l[8], 4), _f(l[9], 3), _f(l[10])) for l in lin]) +
        '<p class="nota">Envoltória por regressão em (s, t): t = m + s·tan α, sen φ = tan α, c = m / cos φ. '
        "M = 6 sen φ' / (3 − sen φ') (compressão triaxial). φ com c = 0 aparece quando a regressão dá coesão negativa.</p>"))
    for s in res:
        h = ""
        if s["alertas"]:
            h += "".join('<p class="alerta">⚠ {}</p>'.format(A["_esc"](a)) for a in s["alertas"])
        else:
            h += '<p class="ok">Sem alertas.</p>'
        crit = cfg["criterio_principal"]
        cab = ["CP", "Tipo", "σ'3c ou σ3 (kPa)", "q0 (kPa)", "ε_a (%)", "q_f (kPa)", "Δu_f (kPa)", "σ'3f (kPa)", "σ'1f (kPa)",
               "σ'1/σ'3", "A_f", "Su (kPa)"]
        linhas = []
        for it in s["cps"]:
            d = it["ruptura"].get(crit) or {}
            linhas.append((it["nome"], it["tipo"], _f(it["s3c"]), _f(it["q0"]), _f(d.get("eps"), 2), _f(d.get("q")),
                           _f(d.get("du")), _f(d.get("s3e")), _f(d.get("s1e")), _f(d.get("razao"), 3), _f(d.get("A"), 3),
                           _f(d.get("Su"))))
        h += "<p><b>Ruptura de cada CP pelo critério {}</b></p>".format(A["_esc"](crit)) + A["html_tabela"](cab, linhas)
        if s.get("Su_medio") is not None:
            h += "<p>Su médio = <b>{} kPa</b></p>".format(_f(s["Su_medio"]))
        dl = [(it["nome"], _f(it["s3c"]), _f(it["dilatancia"]["psi_pico"]), _f(it["dilatancia"]["psi_medio"]),
               _f(it["dilatancia"].get("eps_contracao_max"), 2), _f(it["dilatancia"].get("eps_fim_dilatacao"), 2))
              for it in s["cps"] if it.get("dilatancia")]
        if dl:
            h += "<p><b>Dilatância</b> (sen ψ = −(dε_v/dε_a) / (2 − dε_v/dε_a); médio = secante do trecho dilatante)</p>"
            h += A["html_tabela"](["CP", "σ'3c (kPa)", "ψ pico (°)", "ψ médio (°)", "ε_a da contração máx. (%)", "ε_a do fim da dilatação (%)"], dl)
        imgs = "".join(A["html_imagem"](c, l) for c, l in figs.get(s["serie"], []))
        if imgs:
            h += '<div class="figs">{}</div>'.format(imgs)
        sec.append(("Série {} ({}, {})".format(s["serie"], s["tipo"], s["fonte"]), h))
    cam = os.path.join(pasta, "relatorio.html")
    sec = sec[:1] + list(secoes_extra or []) + sec[1:]
    A["relatorio_html"](cam, titulo or "Interpretação de ensaios triaxiais", cfg.get("descricao") or "", sec)
    with open(cam, encoding="utf-8") as f:
        txt = f.read()
    with open(cam, "w", encoding="utf-8") as f:
        f.write(txt.replace("plaxis_soiltest_auto.py em", "{} em".format(ferramenta)))
    return cam


def _limpo(o):
    if isinstance(o, float):
        return None if (math.isnan(o) or math.isinf(o)) else round(o, 6)
    if isinstance(o, dict):
        return {k: _limpo(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_limpo(v) for v in o]
    return o


def resumo_log(res):
    for s in res:
        log("")
        log("Serie {} ({}, {}, {} CP(s))".format(s["serie"], s["tipo"], s["fonte"], len(s["cps"])))
        for it in s["cps"]:
            d = it["ruptura"].get("q máximo") or {}
            extra = ""
            if d.get("A") is not None:
                extra += ", A_f = {:.3f}".format(d["A"])
            if d.get("Su") is not None:
                extra += ", Su = {:.2f} kPa".format(d["Su"])
            if it.get("dilatancia"):
                extra += ", psi pico = {:.2f}, psi medio = {:.2f} graus".format(it["dilatancia"]["psi_pico"], it["dilatancia"]["psi_medio"])
            log("   {}: sigma3c = {:g} kPa, q max = {:.2f} kPa em eps_a = {:g} %{}".format(it["nome"], it["s3c"], d.get("q", 0), d.get("eps", 0), extra))
        for chave in ("total", "efetiva"):
            if s["envoltorias"][chave] and not any(s["envoltorias"][chave].values()):
                log("   envoltoria {:8s}: sem pontos suficientes (menos de 2 CPs)".format(chave))
                continue
            for crit, e in s["envoltorias"][chave].items():
                if e:
                    log("   envoltoria {:8s} ({}): c = {:.2f} kPa, phi = {:.2f} graus, R2 = {:.4f}".format(chave, crit, e["c"], e["phi"], e["r2"]))
                else:
                    log("   envoltoria {:8s} ({}): sem pontos suficientes".format(chave, crit))
        for a in s["alertas"]:
            log("   ATENCAO: " + a)


def main(argv=None):
    cfg = dict(CONFIG)
    if argv is None:      # pelo executor do PLAXIS (g_i injetado) vale so o CONFIG
        argv = [] if "g_i" in globals() else sys.argv[1:]
    if argv:
        cfg["lab_csv"] = argv[0] if argv[0].lower().endswith(".csv") else ""
        cfg["pastas_simulacao"] = [a for a in argv if not a.lower().endswith(".csv")]
    A = carregar_auto()
    pasta = cfg["pasta_saida"] or os.path.join(AQUI, "soiltest_saida", "interpretacao_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
    os.makedirs(pasta, exist_ok=True)
    cps, entradas = [], []
    if cfg["lab_csv"]:
        if not os.path.isfile(cfg["lab_csv"]):
            log("CSV de laboratorio nao encontrado: {}".format(cfg["lab_csv"]))
            return 1
        lab = ler_lab(cfg["lab_csv"])
        log("Laboratorio: {} ({} CP(s))".format(os.path.basename(cfg["lab_csv"]), len(lab)))
        entradas.append(("Laboratório", os.path.basename(cfg["lab_csv"])))
        cps += lab
    for p in cfg["pastas_simulacao"]:
        sim = ler_simulacao(p)
        log("Simulacao: {} ({} CP(s))".format(p, len(sim)))
        entradas.append(("Simulação (plaxis_soiltest_auto)", os.path.basename(os.path.normpath(p))))
        cps += sim
    if not cps:
        log("Nenhum ensaio para interpretar.")
        return 1
    gerar_saidas(A, cps, cfg, pasta, entradas)
    return 0


def gerar_saidas(A, cps, cfg, pasta, entradas, secoes_extra=None, titulo=None, ferramenta="soiltest_interpretacao.py", extra_json=None):
    """Interpreta os CPs e grava graficos/, parametros.csv, interpretacao.json, relatorio.html e log.txt. Devolve res."""
    res = interpretar(cps, cfg)
    resumo_log(res)
    figs = graficos(res, cps, pasta, cfg)
    gravar_csv_parametros(os.path.join(pasta, "parametros.csv"), tabela_parametros(res))
    with open(os.path.join(pasta, "interpretacao.json"), "w", encoding="utf-8") as f:
        json.dump(_limpo(dict({"config": cfg, "series": res}, **(extra_json or {}))), f, indent=1, ensure_ascii=False)
    try:
        relatorio(A, pasta, res, figs, cfg, entradas, secoes_extra, titulo, ferramenta)
    except Exception:
        log("Relatorio nao gerado:\n" + traceback.format_exc())
    log("")
    log("Saida: {}".format(pasta))
    log("   {} grafico(s), parametros.csv, interpretacao.json, relatorio.html, log.txt".format(sum(len(v) for v in figs.values())))
    with open(os.path.join(pasta, "log.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(_linhas_log) + "\n")
    return res


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(traceback.format_exc())

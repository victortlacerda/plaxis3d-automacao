# -*- coding: utf-8 -*-
"""
Motor dos estudos de sapata: roda um caso completo REUSANDO, sem alterar, os scripts validados
  - plaxis_sapata_interativo.py : só as definições (até "Principal") são carregadas; construir(P) é chamado
                                  com P montado por aqui, sem perguntas;
  - plaxis_sapata_resultados.py : executado inteiro, numa pasta própria de cada caso.
Assim os comandos enviados ao PLAXIS são exatamente os já validados.

Também traz: leitura/escrita de .xlsx simples (sem openpyxl), captura do texto impresso (para ler
"Generated N elements") e o gráfico PLAXIS x métodos analíticos.
"""
import io
import os
import re
import sys
import json
import zipfile
import xml.etree.ElementTree as ET

import sapata_analitico as AN

PRESETS_MALHA = {"very coarse": 0.1, "coarse": 0.075, "medium": 0.05, "fine": 0.035, "very fine": 0.025}
MARCA_PRINCIPAL = "\nverificar_conexao()\ndados_modelo = perguntar_tudo()"


def achar_script(nome, pasta):
    aqui = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(pasta, nome), os.path.join(pasta, "..", "sapata", nome),
                 os.path.join(aqui, nome), os.path.join(aqui, "..", "sapata", nome)):
        if os.path.exists(cand):
            return os.path.abspath(cand)
    raise RuntimeError("Não achei {} (coloque-o na mesma pasta deste script: {}).".format(nome, pasta))


# ----------------------------------------------------------------------------
# Captura do que é impresso (mostra na tela e guarda)
# ----------------------------------------------------------------------------
class Tee(object):
    def __init__(self, original):
        self.original, self.buf = original, io.StringIO()

    def write(self, t):
        self.original.write(t)
        self.buf.write(t)

    def flush(self):
        self.original.flush()

    def __getattr__(self, k):
        return getattr(self.original, k)


def com_captura(fn, *a, **k):
    tee = Tee(sys.stdout)
    sys.stdout = tee
    try:
        r = fn(*a, **k)
    finally:
        sys.stdout = tee.original
    return r, tee.buf.getvalue()


# ----------------------------------------------------------------------------
# Execução no PLAXIS
# ----------------------------------------------------------------------------
class Motor(object):
    def __init__(self, g_i, s_i, pasta, senha):
        self.g_i, self.s_i, self.pasta, self.senha = g_i, s_i, pasta, senha
        self.arq_int = achar_script("plaxis_sapata_interativo.py", pasta)
        self.arq_res = achar_script("plaxis_sapata_resultados.py", pasta)
        fonte = open(self.arq_int, encoding="utf-8").read()
        i = fonte.find(MARCA_PRINCIPAL)
        if i < 0:
            raise RuntimeError("plaxis_sapata_interativo.py em versão inesperada (não achei o bloco principal).")
        self.fonte_defs = fonte[:i]
        self.fonte_res = open(self.arq_res, encoding="utf-8").read()

    def _ns_base(self, arquivo):
        return {"g_i": self.g_i, "s_i": self.s_i, "__file__": arquivo, "__name__": "estudo",
                "PLAXIS_PASSWORD": self.senha}

    def construir(self, P, pasta_caso):
        """Cria, salva e calcula o modelo do caso com o construir() validado. Devolve (texto, elementos)."""
        ns = self._ns_base(os.path.join(pasta_caso, "plaxis_sapata_interativo.py"))
        exec(compile(self.fonte_defs, self.arq_int, "exec"), ns, ns)
        ns["ARQUIVO_JSON"] = os.path.join(pasta_caso, "ultimo_modelo.json")
        ns["resumo"](P)
        _, texto = com_captura(ns["construir"], P)
        m = re.findall(r"Generated (\d+) elements", texto)
        return texto, (int(m[-1]) if m else None)

    def resultados(self, pasta_caso):
        """Roda o plaxis_sapata_resultados.py validado na pasta do caso e devolve os números."""
        ns = self._ns_base(os.path.join(pasta_caso, "plaxis_sapata_resultados.py"))
        _, texto = com_captura(exec, compile(self.fonte_res, self.arq_res, "exec"), ns, ns)
        g = ns.get
        return dict(
            qu_tang=g("qu_tang"), s_int=g("s_int"), q_10b=g("q_10b"), q_25=g("q_25"),
            q_max=g("q_max"), s_max=g("s_max"), unid=g("UNID", "kN/m²"), FS=g("FS", 3.0),
            completa=bool(g("CURVA_COMPLETA", True)), q=list(g("q") or []), s=list(g("s") or []),
            figuras=dict(curva=_se_existe(g("PNG_CURVA")), tangentes=_se_existe(g("PNG_TANGENTES")),
                         b10=_se_existe(g("PNG_10B")), mm25=_se_existe(g("PNG_25MM"))),
            csv=_se_existe(g("CSV")), texto=texto)


def _se_existe(p):
    return p if p and os.path.exists(p) else None


# ----------------------------------------------------------------------------
# Analítico ligado à entrada P
# ----------------------------------------------------------------------------
def camada_da_base(P):
    """Camada em que está a base da sapata (a de cima se a base cai numa interface)."""
    zb, topo = P["sapata"]["cz"], 0.0
    for cm in P["camadas"]:
        base = topo - cm["espessura"]
        if zb > base + 1e-9:
            return cm
        topo = base
    return P["camadas"][-1]


def analitico_de(P, FS=3.0):
    f, cm = P["sapata"], camada_da_base(P)
    D = -f["cz"]
    prof_na = -P["nivel_agua"] if P.get("nivel_agua") is not None else None
    # peso médio acima da base, ponderado pelas camadas (para a sobrecarga quando há várias)
    return AN.calcular(f["L"], f["W"], D, cm["c"], cm["phi"], cm["gamma_unsat"], cm["gamma_sat"], prof_na,
                       cm["E"], cm["nu"], FS=FS)


def grafico_comparacao(q, s, A, R, caminho, titulo="PLAXIS x métodos analíticos"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 6))
    if q and s:
        ax.plot(q, s, "-", color="#1f4e9c", lw=2.4, label="PLAXIS 3D (nó sob a sapata)")
    cores = ("#c0392b", "#e67e22", "#16a085")
    smax = max(s) if s else 50.0
    for mt, cor in zip(A["metodos"], cores):
        ax.axvline(mt["qu"], color=cor, ls="--", lw=1.6, label="qu {} = {:.0f}".format(mt["metodo"], mt["qu"]))
    if R.get("qu_tang"):
        ax.axvline(R["qu_tang"], color="#1f4e9c", ls=":", lw=1.6, label="qu PLAXIS (tangentes) = {:.0f}".format(
            R["qu_tang"]))
    qmax_eixo = max([mt["qu"] for mt in A["metodos"]] + ([max(q)] if q else []) + [R.get("qu_tang") or 0]) * 1.12
    qe = [0.0, qmax_eixo]
    se = [AN.recalque_elastico_mm(x, A["B"], A["L"], *_E_nu(A)) for x in qe]
    ax.plot(qe, se, "-", color="#7f8c8d", lw=1.4, label="Recalque elástico (rígida, Iw = {:.2f})".format(A["Iw"]))
    ax.set_xlim(0, qmax_eixo)
    ax.set_ylim(min(max(smax, 30.0) * 1.05, max(smax * 1.05, 30.0)), 0)
    ax.set_xlabel("Carga (kN/m²)")
    ax.set_ylabel("Recalque (mm)")
    ax.set_title(titulo)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8.5, loc="lower left")
    fig.tight_layout()
    fig.savefig(caminho, dpi=150)
    plt.close(fig)
    return caminho


def _E_nu(A):
    return A["_E"], A["_nu"]


def analitico_completo(P, FS=3.0):
    A = analitico_de(P, FS)
    cm = camada_da_base(P)
    A["_E"], A["_nu"] = cm["E"], cm["nu"]
    return A


# ----------------------------------------------------------------------------
# XLSX mínimo (leitura e escrita) - funciona sem openpyxl
# ----------------------------------------------------------------------------
_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _col_idx(ref):
    letras = re.match(r"([A-Z]+)", ref).group(1)
    n = 0
    for ch in letras:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def ler_xlsx(caminho, aba=None):
    """Lista de linhas (listas) da aba pedida (nome) ou da primeira aba."""
    with zipfile.ZipFile(caminho) as z:
        nomes = z.namelist()
        compart = []
        if "xl/sharedStrings.xml" in nomes:
            raiz = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in raiz.findall("m:si", _NS):
                compart.append("".join(t.text or "" for t in si.iter("{%s}t" % _NS["m"])))
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        alvo_rel = {r.get("Id"): r.get("Target") for r in rels}
        abas = [(s.get("name"), s.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"))
                for s in wb.find("m:sheets", _NS)]
        escolhida = abas[0]
        if aba:
            for a in abas:
                if a[0].strip().lower() == aba.strip().lower():
                    escolhida = a
        alvo = alvo_rel[escolhida[1]].lstrip("/")
        if not alvo.startswith("xl/"):
            alvo = "xl/" + alvo
        raiz = ET.fromstring(z.read(alvo))
    linhas = []
    for row in raiz.iter("{%s}row" % _NS["m"]):
        vals = {}
        for c in row.findall("m:c", _NS):
            t = c.get("t")
            v = c.find("m:v", _NS)
            if t == "s" and v is not None:
                val = compart[int(v.text)]
            elif t == "inlineStr":
                val = "".join(x.text or "" for x in c.iter("{%s}t" % _NS["m"]))
            elif v is None:
                val = None
            elif t in ("str", "e"):
                val = v.text
            elif t == "b":
                val = v.text == "1"
            else:
                try:
                    val = float(v.text)
                except ValueError:
                    val = v.text
            vals[_col_idx(c.get("r"))] = val
        if vals:
            linha = [None] * (max(vals) + 1)
            for k, v in vals.items():
                linha[k] = v
            linhas.append(linha)
    return linhas


def ler_tabela(caminho, aba=None):
    """Lê .xlsx ou .csv (; e vírgula decimal) e devolve lista de dicts pela linha de cabeçalho."""
    if caminho.lower().endswith(".csv"):
        with open(caminho, encoding="utf-8-sig") as f:
            linhas = [l.rstrip("\n").split(";") for l in f if l.strip()]
    else:
        linhas = ler_xlsx(caminho, aba)
    if not linhas:
        return []
    cab = [str(c).strip() if c is not None else "" for c in linhas[0]]
    saida = []
    for l in linhas[1:]:
        if not any(v not in (None, "") for v in l):
            continue
        d = {}
        for i, nome in enumerate(cab):
            if nome:
                d[nome] = l[i] if i < len(l) else None
        saida.append(d)
    return saida


def _ref(c, r):
    s = ""
    c += 1
    while c:
        c, rem = divmod(c - 1, 26)
        s = chr(65 + rem) + s
    return "{}{}".format(s, r + 1)


def salvar_xlsx(caminho, cabecalho, linhas, aba="Resumo"):
    """Planilha simples (texto e números), cabeçalho em negrito, colunas largas."""
    def esc(t):
        return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    rows = []
    for r, linha in enumerate([cabecalho] + linhas):
        cels = []
        for c, v in enumerate(linha):
            estilo = ' s="1"' if r == 0 else ""
            if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v:
                cels.append('<c r="{}"{}><v>{}</v></c>'.format(_ref(c, r), estilo, repr(float(v))))
            elif v is None or v == "":
                continue
            else:
                cels.append('<c r="{}" t="inlineStr"{}><is><t xml:space="preserve">{}</t></is></c>'.format(
                    _ref(c, r), estilo, esc(v)))
        rows.append('<row r="{}">{}</row>'.format(r + 1, "".join(cels)))
    cols = "".join('<col min="{0}" max="{0}" width="{1}" customWidth="1"/>'.format(i + 1, max(10, min(40, len(str(h)) + 4)))
                   for i, h in enumerate(cabecalho))
    sheet = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
             '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
             '</sheetView></sheetViews><cols>{}</cols><sheetData>{}</sheetData></worksheet>').format(cols, "".join(rows))
    estilos = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
               '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
               '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
               '<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>'
               '<fill><patternFill patternType="solid"><fgColor rgb="FFDCE6F2"/></patternFill></fill></fills>'
               '<borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs>'
               '<cellXfs count="2"><xf/><xf fontId="1" fillId="2" applyFont="1" applyFill="1"/></cellXfs></styleSheet>')
    with zipfile.ZipFile(caminho, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                   '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                   '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                   '</Types>')
        z.writestr("_rels/.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                   '</Relationships>')
        z.writestr("xl/workbook.xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                   'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                   '<sheets><sheet name="{}" sheetId="1" r:id="rId1"/></sheets></workbook>'.format(esc(aba)))
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
                   '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
                   '</Relationships>')
        z.writestr("xl/worksheets/sheet1.xml", sheet)
        z.writestr("xl/styles.xml", estilos)
    return caminho


def salvar_csv(caminho, cabecalho, linhas):
    def cel(v):
        if v is None:
            return ""
        if isinstance(v, float):
            return ("{:.4f}".format(v)).rstrip("0").rstrip(".").replace(".", ",")
        return str(v).replace(";", ",")
    with open(caminho, "w", encoding="utf-8-sig") as f:
        f.write(";".join(cabecalho) + "\n")
        for l in linhas:
            f.write(";".join(cel(v) for v in l) + "\n")
    return caminho


# ----------------------------------------------------------------------------
# Montagem de P (entrada do construir validado) a partir de valores simples
# ----------------------------------------------------------------------------
def montar_P(caso, pasta_caso, B, L, D, d_sap, solo, prof_na, modo, valor, passos, malha, refinar, coars,
             dist_borda_B, H, titulo=None, gamma_sap=24.0, E_sap=2.35e7, nu_sap=0.2):
    """
    B (y) e L (x) em m, D = profundidade da base (m, >= 0), solo = dict(gamma_unsat, gamma_sat, E, nu, c, phi, psi),
    prof_na (m, positiva; None = abaixo do modelo), modo 'carga' (valor em kN/m²) ou 'deslocamento' (valor em mm),
    dist_borda_B = distância da borda da sapata ao contorno lateral, em múltiplos do maior lado.
    """
    Bmax = max(B, L)
    meia_x = L / 2.0 + dist_borda_B * Bmax
    meia_y = B / 2.0 + dist_borda_B * Bmax
    if H is None:
        H = max(10.0, D + 6.0 * Bmax)
    na = -min(prof_na, H) if prof_na is not None else -H
    camada = dict(nome="Solo", espessura=H, **solo)
    if modo == "carga":
        carga = dict(modo="carga", tipo=1, direcao=1, eixo=None, valor=float(valor), unidade="kN/m2")
    elif modo == "deslocamento":
        carga = dict(modo="deslocamento", tipo=1, direcao=1, eixo=None, valor=float(valor) / 1000.0,
                     unidade="m", passos=int(passos))
    else:
        raise ValueError("modo deve ser 'carga' ou 'deslocamento' (recebido: {})".format(modo))
    if malha not in PRESETS_MALHA:
        raise ValueError("malha deve ser uma de {} (recebido: {})".format(list(PRESETS_MALHA), malha))
    return dict(
        info=dict(titulo=titulo or "PLAXIS 3D: estudo de sapata - {}".format(caso), empresa=""),
        dominio=dict(xmin=-meia_x, xmax=meia_x, ymin=-meia_y, ymax=meia_y, H=H),
        camadas=[camada], nivel_agua=na,
        sapata=dict(cx=0.0, cy=0.0, cz=-D if D else 0.0, L=L, W=B, d=d_sap, B=min(L, B), gamma=gamma_sap, E=E_sap, nu=nu_sap,
                    nome_material="Footing", modelo="placa"),
        carga=carga,
        malha=dict(nome=malha, fator=PRESETS_MALHA[malha], refinar=bool(refinar), coarseness=coars),
        projeto=os.path.join(pasta_caso, "{}.p3d".format(_seguro(caso))),
        calcular=True,
    )


def _seguro(t):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(t)).strip("_") or "caso"


def salvar_json(caminho, dados):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False, default=str)


# ----------------------------------------------------------------------------
# Planilha do lote: uma sapata por linha
# ----------------------------------------------------------------------------
COLUNAS = {   # chave normalizada -> (padrão, descrição)
    "caso": (None, "nome do caso"),
    "b": (None, "largura B (m), direção y"),
    "l": (None, "comprimento L (m), direção x; vazio = B"),
    "df": (0.0, "profundidade da base (m)"),
    "esp": (0.5, "espessura da sapata (m)"),
    "gamma_nat": (18.0, "γ não saturado (kN/m³)"),
    "gamma_sat": (20.0, "γ saturado (kN/m³)"),
    "e": (40000.0, "E' (kN/m²)"),
    "nu": (0.3, "ν'"),
    "c": (30.0, "c' (kN/m²)"),
    "phi": (20.0, "φ' (graus)"),
    "psi": (0.0, "ψ (graus)"),
    "na": (6.0, "profundidade do N.A. (m); vazio = abaixo do modelo"),
    "modo": ("carga", "carga | deslocamento"),
    "valor": (None, "carga (kN/m²) ou deslocamento (mm)"),
    "passos": (50, "passos mínimos (deslocamento)"),
    "malha": ("fine", "very coarse | coarse | medium | fine | very fine"),
    "refino": ("s", "refinar na sapata (s/n)"),
    "coarseness": (0.1, "coarseness factor da sapata"),
    "borda": (4.5, "distância da sapata ao contorno lateral, em múltiplos do maior lado"),
    "h": (None, "profundidade do modelo (m); vazio = máx(10, Df + 6 x maior lado)"),
    "fs": (3.0, "fator de segurança"),
}


def _chave(cab):
    t = str(cab).strip().lower()
    for sep in (" (", "(", " ["):
        if sep in t:
            t = t.split(sep)[0]
    return t.strip().replace(" ", "_").replace("γ", "gamma").replace("φ", "phi").replace("ψ", "psi").replace("ν", "nu")


def _num(v, padrao=None):
    if v is None or (isinstance(v, str) and not v.strip()):
        return padrao
    if isinstance(v, (int, float)):
        return float(v)
    return float(str(v).strip().replace(",", "."))


def _sim(v, padrao="s"):
    t = str(v if v not in (None, "") else padrao).strip().lower()
    return t in ("s", "sim", "y", "yes", "true", "1", "1.0", "verdadeiro")


def ler_casos(caminho):
    brutas = ler_tabela(caminho, aba="Sapatas")
    casos, erros = [], []
    for i, b in enumerate(brutas, start=2):
        r = {_chave(k): v for k, v in b.items()}
        try:
            caso = str(r.get("caso") or "caso_{}".format(i - 1)).strip()
            if caso.endswith(".0"):
                caso = caso[:-2]
            B = _num(r.get("b"))
            if not B or B <= 0:
                raise ValueError("B ausente ou inválido")
            L = _num(r.get("l"), B)
            modo = str(r.get("modo") or "carga").strip().lower()
            modo = "deslocamento" if modo.startswith("desl") else "carga"
            valor = _num(r.get("valor"))
            if not valor or valor <= 0:
                raise ValueError("valor da carga/deslocamento ausente")
            phi = _num(r.get("phi"), 20.0)
            caso_d = dict(
                caso=caso, B=B, L=L, Df=_num(r.get("df"), 0.0), esp=_num(r.get("esp"), 0.5),
                solo=dict(gamma_unsat=_num(r.get("gamma_nat"), 18.0), gamma_sat=_num(r.get("gamma_sat"), 20.0),
                          E=_num(r.get("e"), 40000.0), nu=_num(r.get("nu"), 0.3), c=_num(r.get("c"), 30.0),
                          phi=phi, psi=min(_num(r.get("psi"), 0.0), phi)),
                na=_num(r.get("na"), None) if r.get("na") not in (None, "") else None,
                modo=modo, valor=valor, passos=int(_num(r.get("passos"), 50)),
                malha=str(r.get("malha") or "fine").strip().lower(), refino=_sim(r.get("refino")),
                coarseness=_num(r.get("coarseness"), 0.1), borda=_num(r.get("borda"), 4.5),
                H=_num(r.get("h"), None), FS=_num(r.get("fs"), 3.0))
            if caso_d["malha"] not in PRESETS_MALHA:
                raise ValueError("malha '{}' inválida".format(caso_d["malha"]))
            if caso_d["solo"]["c"] < 0.2:
                print("    (aviso) caso {}: c' < 0,2 kN/m² pode dificultar a convergência".format(caso))
            casos.append(caso_d)
        except Exception as e:  # noqa
            erros.append("linha {}: {}".format(i, e))
    return casos, erros

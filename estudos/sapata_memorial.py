# -*- coding: utf-8 -*-
"""
Memorial de cálculo em Word (.docx) e HTML (abre no navegador; Ctrl+P salva em PDF).

Sem dependências externas: o .docx é montado direto em XML (Office Open XML) com zipfile, para funcionar no
Python que vem com o PLAXIS. O conteúdo é descrito como uma lista de blocos:
    ("h1", "Título"), ("h2", "Seção"), ("p", "Texto"), ("nota", "Texto menor"),
    ("tabela", ["Col 1", "Col 2"], [[...], [...]]), ("img", "caminho.png", "Legenda", largura_cm),
    ("quebra",)
e gerado com salvar_docx(blocos, caminho) e salvar_html(blocos, caminho, titulo).

memorial_sapata(dados) monta os blocos de um caso de sapata (parâmetros, modelo, curva, critérios,
comparação com métodos analíticos, conclusão e campo de assinatura).
"""
import os
import html
import struct
import zipfile
import datetime

EMU_POR_CM = 360000


def _xml(t):
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def _png_tamanho(caminho):
    with open(caminho, "rb") as f:
        cab = f.read(24)
    if cab[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("não é PNG: " + caminho)
    return struct.unpack(">II", cab[16:24])


def fmt_num(x, casas=1):
    if x is None:
        return "n/d"
    if isinstance(x, str):
        return x
    return "{:,.{}f}".format(x, casas).replace(",", "X").replace(".", ",").replace("X", ".")


# ----------------------------------------------------------------------------
# DOCX
# ----------------------------------------------------------------------------
_ESTILOS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri"/>
<w:sz w:val="22"/><w:lang w:val="pt-BR"/></w:rPr></w:rPrDefault>
<w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="264" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:qFormat/>
<w:pPr><w:spacing w:after="240"/></w:pPr><w:rPr><w:b/><w:color w:val="0D2B4E"/><w:sz w:val="40"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
<w:pPr><w:keepNext/><w:spacing w:before="360" w:after="120"/><w:outlineLvl w:val="0"/></w:pPr>
<w:rPr><w:b/><w:color w:val="0D2B4E"/><w:sz w:val="30"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
<w:pPr><w:keepNext/><w:spacing w:before="240" w:after="80"/><w:outlineLvl w:val="1"/></w:pPr>
<w:rPr><w:b/><w:color w:val="16467A"/><w:sz w:val="25"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Caption"><w:name w:val="caption"/><w:basedOn w:val="Normal"/><w:qFormat/>
<w:pPr><w:jc w:val="center"/><w:spacing w:after="200"/></w:pPr><w:rPr><w:i/><w:color w:val="555555"/><w:sz w:val="19"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Nota"><w:name w:val="Nota"/><w:basedOn w:val="Normal"/>
<w:rPr><w:color w:val="555555"/><w:sz w:val="19"/></w:rPr></w:style>
<w:style w:type="table" w:styleId="TabelaGrade"><w:name w:val="Tabela Grade"/><w:tblPr><w:tblBorders>
<w:top w:val="single" w:sz="4" w:color="A6B4C8"/><w:left w:val="single" w:sz="4" w:color="A6B4C8"/>
<w:bottom w:val="single" w:sz="4" w:color="A6B4C8"/><w:right w:val="single" w:sz="4" w:color="A6B4C8"/>
<w:insideH w:val="single" w:sz="4" w:color="A6B4C8"/><w:insideV w:val="single" w:sz="4" w:color="A6B4C8"/>
</w:tblBorders><w:tblCellMar><w:left w:w="90" w:type="dxa"/><w:right w:w="90" w:type="dxa"/></w:tblCellMar></w:tblPr></w:style>
</w:styles>"""

_TIPOS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Default Extension="png" ContentType="image/png"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
</Types>"""

_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
</Relationships>"""


def _par(texto, estilo=None, negrito=False, alinhar=None):
    ppr = ""
    if estilo or alinhar:
        ppr = "<w:pPr>{}{}</w:pPr>".format('<w:pStyle w:val="{}"/>'.format(estilo) if estilo else "",
                                          '<w:jc w:val="{}"/>'.format(alinhar) if alinhar else "")
    runs = []
    for i, linha in enumerate(str(texto).split("\n")):
        if i:
            runs.append("<w:r><w:br/></w:r>")
        runs.append('<w:r>{}<w:t xml:space="preserve">{}</w:t></w:r>'.format(
            "<w:rPr><w:b/></w:rPr>" if negrito else "", _xml(linha)))
    return "<w:p>{}{}</w:p>".format(ppr, "".join(runs))


def _tabela(cab, linhas, larg_total_twips=9300):
    n = max(1, len(cab))
    w = int(larg_total_twips / n)
    grade = "".join('<w:gridCol w:w="{}"/>'.format(w) for _ in range(n))

    def cel(t, cabecalho):
        sombra = '<w:shd w:val="clear" w:color="auto" w:fill="DCE6F2"/>' if cabecalho else ""
        return ('<w:tc><w:tcPr><w:tcW w:w="{}" w:type="dxa"/>{}</w:tcPr>{}</w:tc>'.format(
            w, sombra, _par(t, negrito=cabecalho)))
    xml = ['<w:tbl><w:tblPr><w:tblStyle w:val="TabelaGrade"/><w:tblW w:w="{}" w:type="dxa"/></w:tblPr>'
           '<w:tblGrid>{}</w:tblGrid>'.format(larg_total_twips, grade)]
    xml.append('<w:tr><w:trPr><w:tblHeader/></w:trPr>' + "".join(cel(c, True) for c in cab) + "</w:tr>")
    for l in linhas:
        xml.append("<w:tr>" + "".join(cel(c, False) for c in l) + "</w:tr>")
    xml.append("</w:tbl>")
    return "".join(xml) + _par("")


def _imagem(rid, idx, largura_cm, px):
    cx = int(largura_cm * EMU_POR_CM)
    cy = int(cx * px[1] / float(px[0]))
    return ('<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:drawing>'
            '<wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/>'
            '<wp:docPr id="{i}" name="Figura {i}"/>'
            '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
            '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            '<pic:nvPicPr><pic:cNvPr id="{i}" name="img{i}.png"/><pic:cNvPicPr/></pic:nvPicPr>'
            '<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            '<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic>'
            '</wp:inline></w:drawing></w:r></w:p>').format(cx=cx, cy=cy, i=idx, rid=rid)


def salvar_docx(blocos, caminho, titulo="Memorial de cálculo"):
    corpo, rels, midias = [], [], []
    for b in blocos:
        tipo = b[0]
        if tipo == "titulo":
            corpo.append(_par(b[1], "Title"))
        elif tipo == "h1":
            corpo.append(_par(b[1], "Heading1"))
        elif tipo == "h2":
            corpo.append(_par(b[1], "Heading2"))
        elif tipo == "p":
            corpo.append(_par(b[1]))
        elif tipo == "nota":
            corpo.append(_par(b[1], "Nota"))
        elif tipo == "tabela":
            corpo.append(_tabela(b[1], b[2]))
        elif tipo == "img":
            if not b[1] or not os.path.exists(b[1]):
                corpo.append(_par("[figura não encontrada: {}]".format(b[1]), "Nota"))
                continue
            idx = len(midias) + 1
            rid = "rIdImg{}".format(idx)
            midias.append((rid, "media/img{}.png".format(idx), b[1]))
            corpo.append(_imagem(rid, idx, b[3] if len(b) > 3 else 15.0, _png_tamanho(b[1])))
            if len(b) > 2 and b[2]:
                corpo.append(_par(b[2], "Caption"))
        elif tipo == "quebra":
            corpo.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
           'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
           'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
           'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
           'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><w:body>'
           + "".join(corpo) +
           '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
           '<w:pgMar w:top="1418" w:right="1134" w:bottom="1418" w:left="1418" w:header="709" w:footer="709" w:gutter="0"/>'
           '</w:sectPr></w:body></w:document>')
    drels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
             '<Relationship Id="rIdEst" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>']
    for rid, alvo, _ in midias:
        drels.append('<Relationship Id="{}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
                     'Target="{}"/>'.format(rid, alvo))
    drels.append("</Relationships>")
    agora = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    core = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            '<dc:title>{}</dc:title><dcterms:created xsi:type="dcterms:W3CDTF">{}</dcterms:created>'
            '</cp:coreProperties>').format(_xml(titulo), agora)
    with zipfile.ZipFile(caminho, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _TIPOS)
        z.writestr("_rels/.rels", _RELS)
        z.writestr("docProps/core.xml", core)
        z.writestr("word/document.xml", doc)
        z.writestr("word/styles.xml", _ESTILOS)
        z.writestr("word/_rels/document.xml.rels", "".join(drels))
        for _, alvo, origem in midias:
            z.write(origem, "word/" + alvo)
    return caminho


# ----------------------------------------------------------------------------
# HTML
# ----------------------------------------------------------------------------
_CSS = """
:root{--azul:#0d2b4e;--azul2:#16467a;--linha:#c9d4e3;--fundo:#f4f7fb;--texto:#1d2733;--sub:#5b6878}
*{box-sizing:border-box} body{margin:0;background:var(--fundo);color:var(--texto);font:15px/1.55 'Segoe UI',Calibri,Arial,sans-serif}
main{max-width:900px;margin:24px auto;background:#fff;padding:40px 56px;border-radius:10px;box-shadow:0 6px 24px rgba(13,43,78,.08)}
h1.titulo{color:var(--azul);font-size:28px;margin:0 0 6px} h1{color:var(--azul);font-size:21px;margin:30px 0 8px;border-bottom:2px solid var(--linha);padding-bottom:4px}
h2{color:var(--azul2);font-size:17px;margin:20px 0 6px} p{margin:6px 0 10px} .nota{color:var(--sub);font-size:13px}
table{border-collapse:collapse;width:100%;margin:8px 0 16px;font-size:14px} th,td{border:1px solid var(--linha);padding:5px 8px;text-align:left;vertical-align:top}
th{background:#dce6f2} figure{margin:12px 0 18px;text-align:center} figure img{max-width:100%;border:1px solid var(--linha);border-radius:6px}
figcaption{color:var(--sub);font-style:italic;font-size:13px;margin-top:4px}
@media print{body{background:#fff} main{box-shadow:none;margin:0;padding:0;max-width:none} h1{break-after:avoid} figure,table{break-inside:avoid}}
@media (max-width:640px){main{padding:20px 16px;margin:0;border-radius:0}}
"""


def salvar_html(blocos, caminho, titulo="Memorial de cálculo"):
    pasta = os.path.dirname(os.path.abspath(caminho))
    partes = []
    for b in blocos:
        tipo = b[0]
        if tipo == "titulo":
            partes.append('<h1 class="titulo">{}</h1>'.format(html.escape(b[1])))
        elif tipo in ("h1", "h2"):
            partes.append("<{0}>{1}</{0}>".format(tipo, html.escape(b[1])))
        elif tipo in ("p", "nota"):
            partes.append('<p{}>{}</p>'.format(' class="nota"' if tipo == "nota" else "",
                                               html.escape(str(b[1])).replace("\n", "<br>")))
        elif tipo == "tabela":
            cab = "".join("<th>{}</th>".format(html.escape(str(c))) for c in b[1])
            lin = "".join("<tr>{}</tr>".format("".join("<td>{}</td>".format(html.escape(str(c))) for c in l))
                          for l in b[2])
            partes.append("<table><thead><tr>{}</tr></thead><tbody>{}</tbody></table>".format(cab, lin))
        elif tipo == "img":
            if not b[1] or not os.path.exists(b[1]):
                continue
            rel = os.path.relpath(b[1], pasta).replace("\\", "/")
            partes.append('<figure><img src="{}" alt="{}"><figcaption>{}</figcaption></figure>'.format(
                html.escape(rel), html.escape(b[2] if len(b) > 2 else ""), html.escape(b[2] if len(b) > 2 else "")))
        elif tipo == "quebra":
            partes.append('<div style="break-after:page"></div>')
    doc = ('<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
           '<meta name="viewport" content="width=device-width,initial-scale=1"><title>{}</title><style>{}</style>'
           '</head><body><main>{}</main></body></html>').format(html.escape(titulo), _CSS, "\n".join(partes))
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(doc)
    return caminho


# ----------------------------------------------------------------------------
# Conteúdo do memorial de uma sapata
# ----------------------------------------------------------------------------
def memorial_sapata(d):
    """
    d: dict com
      titulo, caso, data, responsavel (opcional)
      entrada: P do script interativo (dominio, camadas, nivel_agua, sapata, carga, malha)
      elementos (int ou None), resultados: dict(qu_tang, s_int, q_10b, q_25, q_max, s_max, unid, FS, modo)
      analitico: saída de sapata_analitico.calcular(...)
      figuras: dict(curva, tangentes, b10, mm25, comparacao) com caminhos PNG
    """
    P, R, A = d["entrada"], d["resultados"], d.get("analitico")
    f, cam, dom, m, c = P["sapata"], P["camadas"], P["dominio"], P["malha"], P["carga"]
    FS = R.get("FS", 3.0)
    un = R.get("unid", "kN/m²")
    D = max(0.0, -f["cz"])
    B = []
    B.append(("titulo", d.get("titulo") or "Memorial de cálculo - capacidade de carga de sapata"))
    B.append(("p", "Caso: {}\nData: {}\nFerramenta: PLAXIS 3D 2024.2 (modelo gerado por script Python) e "
                   "métodos analíticos clássicos.".format(d.get("caso", "-"),
                                                         d.get("data") or datetime.date.today().strftime("%d/%m/%Y"))))

    B.append(("h1", "1. Objetivo"))
    B.append(("p", "Estimar a capacidade de carga e a tensão admissível de uma sapata isolada {} x {} m, com base "
                   "a {} m de profundidade, a partir da curva carga x recalque obtida no PLAXIS 3D, e conferir o "
                   "resultado com os métodos de Terzaghi, Meyerhof e Vesić e com o recalque elástico.".format(
                       fmt_num(f["L"], 2), fmt_num(f["W"], 2), fmt_num(D, 2))))

    B.append(("h1", "2. Parâmetros"))
    B.append(("h2", "2.1 Solo (Mohr-Coulomb, drenado)"))
    linhas, topo = [], 0.0
    for cm in cam:
        linhas.append([cm["nome"], "{} a {}".format(fmt_num(topo, 1), fmt_num(topo - cm["espessura"], 1)),
                       fmt_num(cm["gamma_unsat"], 1), fmt_num(cm["gamma_sat"], 1), fmt_num(cm["E"], 0),
                       fmt_num(cm["nu"], 2), fmt_num(cm["c"], 1), fmt_num(cm["phi"], 1), fmt_num(cm["psi"], 1)])
        topo -= cm["espessura"]
    B.append(("tabela", ["Camada", "z (m)", "γ (kN/m³)", "γsat (kN/m³)", "E' (kN/m²)", "ν'", "c' (kN/m²)",
                         "φ' (°)", "ψ (°)"], linhas))
    B.append(("p", "Nível d'água: z = {} m.".format(fmt_num(P["nivel_agua"], 2))))
    B.append(("h2", "2.2 Sapata"))
    B.append(("tabela", ["Item", "Valor"], [
        ["Dimensões (L x B)", "{} x {} m".format(fmt_num(f["L"], 2), fmt_num(f["W"], 2))],
        ["Profundidade da base D", "{} m".format(fmt_num(D, 2))],
        ["Modelagem", "placa elástica (plate)" if f.get("modelo", "placa") == "placa"
         else "volume linear elástico não poroso"],
        ["Espessura d / γ / E / ν", "{} m / {} kN/m³ / {} kN/m² / {}".format(
            fmt_num(f["d"], 2), fmt_num(f["gamma"], 1), fmt_num(f["E"], 0), fmt_num(f["nu"], 2))],
    ]))

    B.append(("h1", "3. Modelo numérico"))
    B.append(("tabela", ["Item", "Valor"], [
        ["Domínio", "x de {} a {} m; y de {} a {} m; profundidade {} m".format(
            fmt_num(dom["xmin"], 1), fmt_num(dom["xmax"], 1), fmt_num(dom["ymin"], 1), fmt_num(dom["ymax"], 1),
            fmt_num(dom["H"], 1))],
        ["Malha", "{} (fator {}){}{}".format(m["nome"], fmt_num(m["fator"], 3),
                                             "; refino na sapata, coarseness {}".format(fmt_num(m["coarseness"], 2))
                                             if m.get("refinar") else "",
                                             "; {} elementos".format(d["elementos"]) if d.get("elementos") else "")],
        ["Fases", "Initial (K0) -> Footing (ativa a sapata) -> {}".format(
            "Load (carga distribuída crescente até a ruptura)" if c["modo"] == "carga"
            else "Displacement (recalque prescrito de {} mm)".format(fmt_num(c["valor"] * 1000.0, 1)))],
        ["Curva", "ΣMstage x deslocamento vertical do nó no centro da sapata"],
    ]))

    B.append(("h1", "4. Resultados do PLAXIS"))
    B.append(("img", d["figuras"].get("curva"), "Figura 1 - Curva carga x recalque (PLAXIS 3D)", 14.5))
    crit = []
    if R.get("qu_tang") is not None:
        crit.append(["Interseção das tangentes", fmt_num(R["qu_tang"], 0), fmt_num(R["qu_tang"] / FS, 0),
                     "recalque na interseção {} mm".format(fmt_num(R.get("s_int"), 1))])
    else:
        crit.append(["Interseção das tangentes", "n/d", "n/d", "curva sem patamar ou poucos pontos"])
    crit.append(["Recalque = 10% de B", fmt_num(R.get("q_10b"), 0),
                 fmt_num(R["q_10b"] / FS, 0) if R.get("q_10b") is not None else "n/d",
                 "s = {} mm".format(fmt_num(0.1 * f["B"] * 1000.0, 0))])
    crit.append(["Recalque de 25 mm (Terzaghi e Peck)", "-", fmt_num(R.get("q_25"), 0),
                 "já é admissível por recalque (sem FS)"])
    B.append(("tabela", ["Critério", "qu ({})".format(un), "qa ({})".format(un), "Observação"], crit))
    B.append(("p", "Carga máxima atingida: {} {} com {} mm de recalque. FS = {}.".format(
        fmt_num(R.get("q_max"), 1), un, fmt_num(R.get("s_max"), 1), fmt_num(FS, 1))))
    for chave, leg in (("tangentes", "Figura 2 - Interseção das tangentes"),
                       ("b10", "Figura 3 - Critério de 10% de B"), ("mm25", "Figura 4 - Recalque de 25 mm")):
        if d["figuras"].get(chave):
            B.append(("img", d["figuras"][chave], leg, 12.5))

    if A:
        B.append(("h1", "5. Comparação com métodos analíticos"))
        linhas = []
        for mt in A["metodos"]:
            razao = (R["qu_tang"] / mt["qu"]) if R.get("qu_tang") and mt["qu"] else None
            linhas.append([mt["metodo"], fmt_num(mt["Nc"], 2), fmt_num(mt["Nq"], 2), fmt_num(mt["Ng"], 2),
                           fmt_num(mt["qu"], 0), fmt_num(mt["qa"], 0),
                           fmt_num(razao, 2) if razao else "n/d"])
        B.append(("tabela", ["Método", "Nc", "Nq", "Nγ", "qu ({})".format(un), "qa ({})".format(un),
                             "PLAXIS / método"], linhas))
        B.append(("p", "Recalque elástico (sapata rígida, Iw = {}): a tensão de {} {} causa 25 mm; em qa de "
                       "Vesić o recalque elástico é {} mm.".format(
                           fmt_num(A["Iw"], 2), fmt_num(A["q_25mm"], 0), un,
                           fmt_num(A["metodos"][2]["recalque_qa_mm"], 1))))
        B.append(("nota", "Hipóteses: " + A["hipoteses"] + ". Sobrecarga efetiva na base q = {} kN/m²; "
                          "γ efetivo no termo de Nγ = {} kN/m³.".format(fmt_num(A["metodos"][0]["q"], 1),
                                                                         fmt_num(A["metodos"][0]["gamma_ef"], 2))))
        if d["figuras"].get("comparacao"):
            B.append(("img", d["figuras"]["comparacao"], "Figura 5 - Curva do PLAXIS e métodos analíticos", 14.5))

    B.append(("h1", "6. Conclusão"))
    cands = []
    if R.get("qu_tang") is not None:
        cands.append(("qu (tangentes)/FS", R["qu_tang"] / FS))
    if R.get("q_10b") is not None:
        cands.append(("qu (10% de B)/FS", R["q_10b"] / FS))
    if R.get("q_25") is not None:
        cands.append(("tensão para 25 mm", R["q_25"]))
    if cands:
        nome, val = min(cands, key=lambda t: t[1])
        B.append(("p", "Pelos critérios aplicados à curva do PLAXIS, a tensão admissível é governada por {}: "
                       "qa = {} {}. Valor sujeito à revisão do responsável técnico.".format(nome, fmt_num(val, 0), un)))
        B.append(("tabela", ["Critério", "qa ({})".format(un)], [[n, fmt_num(v, 0)] for n, v in cands]))
    else:
        B.append(("p", "A curva não permitiu aplicar os critérios (veja os avisos do cálculo)."))
    B.append(("nota", "Referências: Terzaghi (1943) Theoretical Soil Mechanics; Meyerhof (1963) Canadian "
                      "Geotechnical Journal 1(1); Vesić (1975) Foundation Engineering Handbook; Hansen (1970) "
                      "Danish Geotechnical Institute Bulletin 28; Terzaghi e Peck (1948) Soil Mechanics in "
                      "Engineering Practice; Bowles (1996) Foundation Analysis and Design; Coduto (2001) "
                      "Foundation Design."))
    B.append(("p", "\n\n______________________________________\n{}\nResponsável técnico - CREA ____________".format(
        d.get("responsavel") or "Nome do responsável")))
    return B


if __name__ == "__main__":
    # Teste rápido sem PLAXIS: gera um memorial de exemplo na pasta atual
    blocos = [("titulo", "Teste do gerador"), ("h1", "Seção"), ("p", "Texto com acentuação: ç ã é ψ φ γ."),
              ("tabela", ["A", "B"], [["1", "2"], ["3", "4"]])]
    print(salvar_docx(blocos, "teste_memorial.docx"), salvar_html(blocos, "teste_memorial.html"))

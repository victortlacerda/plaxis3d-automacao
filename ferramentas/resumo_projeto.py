# -*- coding: utf-8 -*-
"""
Resumo do projeto aberto no PLAXIS 3D Input (só leitura; não altera nada).
Imprime o echo() de tudo que encontrar: borehole, camadas, materiais, sapata/placa, cargas,
deslocamentos prescritos, polígonos e fases. Útil para reproduzir um modelo com os mesmos inputs.

Grava na pasta do script:
  - resumo_projeto.txt  : o texto completo (igual às versões anteriores);
  - resumo_projeto.html : painel (dashboard) com projeto, materiais, estruturas e cargas, fases com o status do
                          cálculo e todos os dados brutos pesquisáveis. Abre sozinho no navegador.
"""
import os
import re
import html as H
import datetime

PASTA = os.path.dirname(os.path.abspath(globals().get("__file__", ".")))
SAIDA = os.path.join(PASTA, "resumo_projeto.txt")
SAIDA_HTML = os.path.join(PASTA, "resumo_projeto.html")
linhas = []
blocos = []          # (título, texto do echo) para o painel


def sai(txt=""):
    print(txt)
    linhas.append(str(txt))


def bloco(titulo, obj):
    sai("\n" + "=" * 70)
    sai(titulo)
    sai("=" * 70)
    try:
        txt = obj.echo()
        sai(txt)
        blocos.append((titulo, str(txt)))
    except Exception as e:  # noqa
        sai("(sem echo: {})".format(str(e).strip().splitlines()[-1] if str(e).strip() else repr(e)))


def lista(nome_colecao):
    """Devolve os itens de g_i.<colecao>, ou [] se não existir."""
    try:
        col = getattr(g_i, nome_colecao)
        return list(col)
    except Exception:
        return []


# ----------------------------------------------------------------------------
# Leitura (igual às versões anteriores, com mais coleções)
# ----------------------------------------------------------------------------
for rotulo, get in (("Projeto", lambda: g_i), ("Contorno do solo (SoilContour)", lambda: g_i.SoilContour)):
    try:
        bloco(rotulo, get())
    except Exception as e:  # noqa
        sai("\n{}: indisponível ({})".format(rotulo, e))

colecoes = [
    ("Boreholes", "Borehole"),
    ("Soillayers", "Camada de solo"),
    ("SoilMaterials", "Material de solo"),
    ("Materials", "Material"),
    ("PlateMaterials", "Material de placa"),
    ("Polygons", "Polígono"),
    ("Plates", "Placa"),
    ("Beams", "Viga/coluna (beam)"),
    ("EmbeddedBeams", "Estaca (embedded beam)"),
    ("SurfaceLoads", "Carga de superfície"),
    ("LineLoads", "Carga de linha"),
    ("PointLoads", "Carga pontual"),
    ("SurfaceDisplacements", "Deslocamento prescrito de superfície"),
    ("PrescribedDisplacements", "Deslocamento prescrito"),
    ("Phases", "Fase"),
]
vistos = set()
for nome, rotulo in colecoes:
    itens = lista(nome)
    for i, obj in enumerate(itens):
        chave = (nome, i)
        if chave in vistos:
            continue
        vistos.add(chave)
        bloco("{} [{}] #{}".format(rotulo, nome, i + 1), obj)

for nome in ("Borehole_1", "Soillayer_1", "Soil", "Footing", "Polygon_1", "Polygon_1_1", "Plate_1",
             "SurfaceLoad_1", "PointLoad_1", "SurfaceDisplacement_1", "InitialPhase"):
    try:
        obj = getattr(g_i, nome)
    except Exception:
        continue
    bloco("Objeto " + nome, obj)

try:
    with open(SAIDA, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas))
    print("\n>>> Resumo salvo em", SAIDA)
except Exception as e:  # noqa
    print("\n(não consegui salvar o arquivo: {})".format(e))


# ----------------------------------------------------------------------------
# Painel HTML
# ----------------------------------------------------------------------------
RE_CAB = re.compile(r'^(\w+) named "([^"]+)"(?: on (\S+))?')


def interpretar(txt):
    """echo() -> dict(tipo, nome, props={caminho: valor}, simples={chave: valor})."""
    ls = [l.rstrip() for l in str(txt).splitlines() if l.strip()]
    if not ls:
        return None
    m = RE_CAB.match(ls[0].strip())
    tipo, nome = (m.group(1), m.group(2)) if m else ("?", ls[0].strip())
    props, simples, pilha = {}, {}, []
    for l in ls[1:]:
        nivel = (len(l) - len(l.lstrip(" "))) // 2
        t = l.strip()
        while pilha and pilha[-1][0] >= nivel:
            pilha.pop()
        mc = RE_CAB.match(t)
        if mc:
            pilha.append((nivel, mc.group(1)))
            continue
        if ":" not in t:
            continue
        k, v = t.split(":", 1)
        k, v = k.strip(), v.strip()
        if not v:
            pilha.append((nivel, k))
            continue
        caminho = ".".join([p[1] for p in pilha] + [k])
        props[caminho] = v
        simples.setdefault(k, v)
    return dict(tipo=tipo, nome=nome, props=props, simples=simples)


def limpa(v):
    if v is None:
        return "-"
    v = v.strip()
    if v.startswith('"') and v.endswith('"'):
        v = v[1:-1]
    v = re.sub(r"\s*\(\d+\)$", "", v)          # "Drained (0)" -> "Drained"
    m = re.match(r"^(-?\d+\.\d{4,})(.*)$", v)   # 0.33333333333331 -> 0.3333
    if m:
        v = "{:.4g}{}".format(float(m.group(1)), m.group(2))
    return v


def pega(obj, *chaves):
    for k in chaves:
        if k in obj["simples"]:
            return limpa(obj["simples"][k])
    return "-"


def tabela(cab, linhas_, classe=""):
    if not linhas_:
        return '<p class="vazio">Nada encontrado.</p>'
    return '<div class="tab"><table class="{}"><thead><tr>{}</tr></thead><tbody>{}</tbody></table></div>'.format(
        classe, "".join("<th>{}</th>".format(H.escape(c)) for c in cab),
        "".join("<tr>{}</tr>".format("".join("<td>{}</td>".format(c) for c in l)) for l in linhas_))


def gerar_painel():
    objs, por_nome = [], {}
    for titulo, txt in blocos:
        o = interpretar(txt)
        if not o:
            continue
        o["titulo"], o["texto"] = titulo, txt
        if o["nome"] in por_nome:          # mesmo objeto lido por coleção e por nome: fica o mais completo
            if len(o["props"]) > len(por_nome[o["nome"]]["props"]):
                objs[objs.index(por_nome[o["nome"]])] = o
                por_nome[o["nome"]] = o
            continue
        por_nome[o["nome"]] = o
        objs.append(o)
    proj = next((o for o in objs if o["tipo"] == "Project"), None)
    solos = [o for o in objs if o["tipo"] == "SoilMat"]
    placas_m = [o for o in objs if o["tipo"] == "PlateMat"]
    outros_m = [o for o in objs if o["tipo"].endswith("Mat") and o not in solos + placas_m]
    fases = [o for o in objs if o["tipo"] in ("InitialPhase", "Phase")]
    estrut = [o for o in objs if o["tipo"] in ("StagedFeature", "SourceFeature", "SourceEntity", "CutObject")
              and o["nome"] not in ("Soillayer_1",)]

    def status_fase(o):
        r = pega(o, "CalculationResult")
        log = pega(o, "LogInfo")
        if r.upper().startswith("OK") or log.upper() == "OK":
            return '<span class="ok">OK</span>'
        if r in ("-", "None") and log in ("-", ""):
            return '<span class="neutro">não calculada</span>'
        return '<span class="falha">{}</span>'.format(H.escape(log if log not in ("-", "") else r))

    tit = pega(proj, "Title") if proj else "-"
    emp = pega(proj, "Company") if proj else "-"
    n_ok = sum(1 for f in fases if "ok" in status_fase(f))
    cards = [("Materiais de solo", len(solos)), ("Materiais estruturais", len(placas_m) + len(outros_m)),
             ("Estruturas e cargas", len(estrut)), ("Fases calculadas", "{}/{}".format(n_ok, len(fases)))]

    sec_proj = tabela(["Item", "Valor"], [[H.escape(k), H.escape(pega(proj, k))] for k in
                                          ("Title", "Company", "UnitForce", "UnitLength", "UnitTime", "Mode",
                                           "WaterWeight", "Gravity")]) if proj else '<p class="vazio">-</p>'
    sec_solo = tabela(["Material", "Modelo", "Drenagem", "γunsat", "γsat", "E'ref", "E'inc", "ν'", "c'ref", "φ'",
                       "ψ", "K0", "Rinter"],
                      [[H.escape(pega(o, "Identification")), pega(o, "SoilModel"), pega(o, "DrainageType"),
                        pega(o, "gammaUnsat"), pega(o, "gammaSat"), pega(o, "ERef", "Eref", "E50Ref", "E50ref"),
                        pega(o, "EInc", "Einc"), pega(o, "nu", "nuUR"), pega(o, "cRef", "cref"), pega(o, "phi"),
                        pega(o, "psi"), pega(o, "K0Primary"), pega(o, "Rinter")] for o in solos])
    sec_placa = tabela(["Material", "Tipo", "γ", "d", "E1", "ν12", "Isotrópico"],
                       [[H.escape(pega(o, "Identification")), pega(o, "MaterialType"), pega(o, "Gamma", "gamma"),
                         pega(o, "d"), pega(o, "E1"), pega(o, "StructNu12"), pega(o, "Isotropic")]
                        for o in placas_m])
    sec_outros = tabela(["Material", "Tipo", "Principais propriedades"],
                        [[H.escape(pega(o, "Identification")), H.escape(o["tipo"]),
                          H.escape("; ".join("{} = {}".format(k, limpa(v)) for k, v in list(o["simples"].items())[:10]))]
                         for o in outros_m]) if outros_m else ""
    sec_est = tabela(["Objeto", "Tipo", "Dados"],
                     [[H.escape(o["nome"]), H.escape(o["tipo"]),
                       H.escape("; ".join("{} = {}".format(k, limpa(v)) for k, v in list(o["simples"].items())[:8])
                                or "-")] for o in estrut])
    linha_tempo = "".join('<div class="etapa"><div class="bola {}"></div><b>{}</b><small>{}</small></div>'.format(
        "verde" if "ok" in status_fase(f) else ("cinza" if "neutro" in status_fase(f) else "vermelho"),
        H.escape(pega(f, "Identification")), H.escape(pega(f, "DeformCalcType"))) for f in fases)
    sec_fases = tabela(["#", "Fase", "Anterior", "Cálculo", "Status", "ΣMstage", "ΣMweight", "Força Z",
                        "Passos", "Zera desloc."],
                       [[pega(f, "Number"), H.escape(pega(f, "Identification")),
                         H.escape(re.sub(r'^\w+ named "([^"]+)"$', r"\1", pega(f, "PreviousPhase"))),
                         pega(f, "DeformCalcType"), status_fase(f),
                         limpa(f["props"].get("Reached.SumMstage")) if "Reached.SumMstage" in f["props"] else pega(f, "SumMstage"),
                         pega(f, "SumMweight"), limpa(f["props"].get("Reached.ForceZ", "-")),
                         "{}-{}".format(pega(f, "FirstStep"), pega(f, "LastStep")),
                         limpa(f["props"].get("Deform.ResetDisplacementsToZero", "-"))] for f in fases])
    brutos = "".join('<details data-busca="{}"><summary>{} <span class="tipo">{}</span></summary><pre>{}</pre></details>'.format(
        H.escape((o["titulo"] + " " + o["texto"]).lower()), H.escape(o["nome"]), H.escape(o["tipo"]),
        H.escape(o["texto"])) for o in objs)
    doc = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Resumo do projeto PLAXIS</title><style>
:root{{--bg:#f3f6fa;--card:#fff;--txt:#1d2733;--sub:#5b6878;--linha:#d6dee9;--azul:#0d2b4e;--th:#e3ebf5;
--ok:#1e8e4f;--falha:#c0392b}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0f1720;--card:#16212d;--txt:#dfe7f0;--sub:#94a3b5;--linha:#2a3a4c;
--azul:#7fb8ff;--th:#1d2b3a;--ok:#4cd187;--falha:#ff7b6b}}}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--txt);font:14px/1.5 'Segoe UI',Arial,sans-serif}}
header{{background:linear-gradient(135deg,#0d2b4e,#1d5b96);color:#fff;padding:26px 32px}}
header h1{{margin:0;font-size:24px}} header .sub{{color:#cfe0f3;margin-top:4px}}
main{{max-width:1200px;margin:0 auto;padding:20px 32px 40px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:-36px 0 18px}}
.card{{background:var(--card);border:1px solid var(--linha);border-radius:12px;padding:14px 16px;box-shadow:0 6px 18px rgba(0,0,0,.08)}}
.card b{{display:block;font-size:26px;color:var(--azul)}} .card span{{color:var(--sub)}}
section{{background:var(--card);border:1px solid var(--linha);border-radius:12px;padding:16px 18px;margin-bottom:16px}}
h2{{margin:0 0 10px;font-size:17px;color:var(--azul)}} .tab{{overflow-x:auto}}
table{{border-collapse:collapse;width:100%;font-size:13px}} th,td{{border-bottom:1px solid var(--linha);padding:6px 8px;text-align:left;vertical-align:top}}
th{{background:var(--th);white-space:nowrap}} .ok{{color:var(--ok);font-weight:600}} .falha{{color:var(--falha);font-weight:600}}
.neutro,.vazio{{color:var(--sub)}} .tempo{{display:flex;gap:0;overflow-x:auto;padding:6px 0 14px}}
.etapa{{flex:1;min-width:120px;text-align:center;position:relative}} .etapa:not(:last-child)::after{{content:"";position:absolute;top:9px;left:55%;width:90%;height:2px;background:var(--linha)}}
.bola{{width:18px;height:18px;border-radius:50%;margin:0 auto 6px;position:relative;z-index:1}}
.verde{{background:var(--ok)}} .vermelho{{background:var(--falha)}} .cinza{{background:var(--sub)}}
.etapa b{{display:block;font-size:13px}} .etapa small{{color:var(--sub)}}
input{{width:100%;padding:8px 10px;border:1px solid var(--linha);border-radius:8px;background:var(--bg);color:var(--txt);margin-bottom:10px}}
details{{border-bottom:1px solid var(--linha);padding:6px 0}} summary{{cursor:pointer;font-weight:600}}
.tipo{{color:var(--sub);font-weight:400;font-size:12px}} pre{{white-space:pre-wrap;font-size:12px;background:var(--bg);padding:10px;border-radius:8px;max-height:420px;overflow:auto}}
footer{{color:var(--sub);font-size:12px;text-align:center;padding-bottom:24px}}
@media (max-width:640px){{header,main{{padding-left:16px;padding-right:16px}}}}
</style></head><body>
<header><h1>{tit}</h1><div class="sub">{emp} · resumo lido do PLAXIS 3D Input em {data}</div></header>
<main><div class="cards">{cards}</div>
<section><h2>Projeto</h2>{sproj}</section>
<section><h2>Fases</h2><div class="tempo">{tempo}</div>{sfases}</section>
<section><h2>Materiais de solo</h2>{ssolo}</section>
<section><h2>Materiais estruturais</h2>{splaca}{soutros}</section>
<section><h2>Geometria, estruturas e cargas</h2>{sest}
<p class="vazio">No modo Staged construction o PLAXIS mostra pouco de cada objeto geométrico; rode este script no modo Structures para ver as coordenadas.</p></section>
<section><h2>Dados completos ({n} objetos)</h2><input id="busca" placeholder="Pesquisar (ex.: sigz, phi, Phase_2)...">{brutos}</section>
</main><footer>Gerado por resumo_projeto.py · também salvo em resumo_projeto.txt</footer>
<script>
document.getElementById('busca').addEventListener('input',function(){{var t=this.value.toLowerCase();
document.querySelectorAll('details').forEach(function(d){{var ok=!t||d.dataset.busca.indexOf(t)>=0;d.style.display=ok?'':'none';if(t&&ok)d.open=true;}});}});
</script></body></html>""".format(
        tit=H.escape(tit if tit != "-" else "Projeto PLAXIS 3D"), emp=H.escape(emp if emp != "-" else "sem Company"),
        data=datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        cards="".join('<div class="card"><b>{}</b><span>{}</span></div>'.format(v, H.escape(k)) for k, v in cards),
        sproj=sec_proj, tempo=linha_tempo, sfases=sec_fases, ssolo=sec_solo, splaca=sec_placa, soutros=sec_outros,
        sest=sec_est, n=len(objs), brutos=brutos)
    with open(SAIDA_HTML, "w", encoding="utf-8") as f:
        f.write(doc)
    return SAIDA_HTML


try:
    painel = gerar_painel()
    print(">>> Painel salvo em", painel)
    try:
        import webbrowser
        webbrowser.open("file:///" + painel.replace("\\", "/"))
    except Exception:
        pass
except Exception as e:  # noqa
    print("\n(não consegui gerar o painel HTML: {})".format(e))

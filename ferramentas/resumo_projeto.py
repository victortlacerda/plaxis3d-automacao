# -*- coding: utf-8 -*-
"""
Resumo do projeto aberto no PLAXIS 3D Input (só leitura; não altera nada).
Imprime o echo() de tudo que encontrar: borehole, camadas, materiais, sapata/placa, cargas,
deslocamentos prescritos, polígonos e fases. Útil para reproduzir um modelo com os mesmos inputs.

Também grava o texto em "resumo_projeto.txt" na pasta do script.
"""
import os

PASTA = os.path.dirname(os.path.abspath(globals().get("__file__", ".")))
SAIDA = os.path.join(PASTA, "resumo_projeto.txt")
linhas = []


def sai(txt=""):
    print(txt)
    linhas.append(str(txt))


def bloco(titulo, obj):
    sai("\n" + "=" * 70)
    sai(titulo)
    sai("=" * 70)
    try:
        sai(obj.echo())
    except Exception as e:  # noqa
        sai("(sem echo: {})".format(str(e).strip().splitlines()[-1] if str(e).strip() else repr(e)))


def lista(nome_colecao):
    """Devolve os itens de g_i.<colecao>, ou [] se não existir."""
    try:
        col = getattr(g_i, nome_colecao)
        return list(col)
    except Exception:
        return []


# --- projeto e contorno
for rotulo, get in (("Projeto", lambda: g_i), ("Contorno do solo (SoilContour)", lambda: g_i.SoilContour)):
    try:
        bloco(rotulo, get())
    except Exception as e:  # noqa
        sai("\n{}: indisponível ({})".format(rotulo, e))

# --- coleções (cada uma só aparece se existir no projeto)
colecoes = [
    ("Boreholes", "Borehole"),
    ("Soillayers", "Camada de solo"),
    ("SoilMaterials", "Material de solo"),
    ("Materials", "Material"),
    ("PlateMaterials", "Material de placa"),
    ("Polygons", "Polígono"),
    ("Plates", "Placa"),
    ("SurfaceLoads", "Carga de superfície"),
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

# --- nomes diretos mais comuns (caso as coleções acima não existam)
for nome in ("Borehole_1", "Soillayer_1", "Soil", "Footing", "Polygon_1", "Polygon_1_1", "Plate_1",
             "SurfaceLoad_1", "PointLoad_1", "SurfaceDisplacement_1", "InitialPhase"):
    if any(nome in l for l in linhas[:0]):
        continue
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

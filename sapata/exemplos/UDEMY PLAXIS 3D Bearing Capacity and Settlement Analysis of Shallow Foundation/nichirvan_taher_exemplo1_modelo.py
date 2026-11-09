# -*- coding: utf-8 -*-
"""
Exemplo 1 - Capacidade de carga (qu) de sapata rasa 1,0 x 1,0 x 0,5 m  (PLAXIS 3D)

Roda pelo executor externo: ele já entrega as variáveis s_i e g_i.
Etapas (iguais às do PDF):
  1. Propriedades do projeto e contorno -5..5 (10 x 10 m)
  2. Borehole em (-5,-5), camada 0 a -10 m, nível d'água em -6 m
  3. Material do solo (Mohr-Coulomb, drenado) e da sapata (placa elástica)
  4. Sapata (superfície 1x1 -> placa) + carga de superfície -1000 kN/m2
  5. Malha (fina, com refinamento na sapata) + ponto de curva em (0,0,0)
  6. Fases: Initial (K0) -> Footing -> Load, e cálculo

Depois rode nichirvan_taher_exemplo1_resultados.py para extrair a curva carga x recalque.
"""
import os
import sys
import getpass

from plxscripting.easy import new_server

# ----------------------------------------------------------------------------
# PARÂMETROS (edite aqui)
# ----------------------------------------------------------------------------
HOST = "localhost"

# Contorno do modelo
XMIN, XMAX, YMIN, YMAX = -5.0, 5.0, -5.0, 5.0
PROFUNDIDADE = 10.0          # camada de 0 a -10 m
NIVEL_AGUA = -6.0            # Head do borehole

# Solo (Phi-C)
SOLO = dict(gamma_unsat=18.0, gamma_sat=20.0, E=40000.0, nu=0.3,
            c=30.0, phi=20.0, psi=0.0)

# Sapata (placa elástica)
SAPATA_LADO = 1.0
SAPATA = dict(gamma=24.0, d=0.5, E=2.35e7, nu=0.2)

CARGA = 1000.0               # kN/m2 (aplicada para baixo => sigz = -1000)

# Malha: presets do GUI (valores lidos no histórico de comandos do PLAXIS 3D 2024.2).
# O fator é relativo ao tamanho do modelo; neste domínio (10 x 10 x 10 m, sapata com
# coarseness 0.1) cada preset gera aproximadamente:
#   very coarse 0.1 -> 1.901 elementos | coarse 0.075 -> 3.485 | medium 0.05 -> 9.455
#   fine 0.035 -> 23.855 (igual ao vídeo) | very fine 0.025 -> 61.048
PRESETS_MALHA = {"very coarse": 0.1, "coarse": 0.075, "medium": 0.05,
                 "fine": 0.035, "very fine": 0.025}
MALHA = "fine"               # um dos nomes acima, ou um número (ex.: 0.04)

if isinstance(MALHA, str):
    if MALHA.lower() not in PRESETS_MALHA:
        raise ValueError("MALHA = '{}' inválido. Use um destes: {} ou um número.".format(
            MALHA, ", ".join(sorted(PRESETS_MALHA))))
    TAMANHO_RELATIVO_MALHA = PRESETS_MALHA[MALHA.lower()]
else:
    TAMANHO_RELATIVO_MALHA = float(MALHA)
COARSENESS_SAPATA = 0.1      # no vídeo: de 0.5 para 0.1

SALVAR_EM = os.path.join(
    os.path.dirname(os.path.abspath(globals().get("__file__", "."))),
    "Exemplo1_Sapata.p3d")
CRIAR_PROJETO_NOVO = True    # False => usa o projeto já aberto no PLAXIS


# ----------------------------------------------------------------------------
# Utilitários
# ----------------------------------------------------------------------------
def etapa(msg):
    print("\n>>> " + msg)


def primeiro(res):
    """Alguns comandos devolvem tupla; pega o primeiro objeto."""
    if isinstance(res, (tuple, list)):
        return res[0]
    return res


def tentar(descricao, *funcs):
    """Executa a primeira alternativa que funcionar; avisa se precisou de fallback."""
    erros = []
    for i, f in enumerate(funcs):
        try:
            r = f()
            if i > 0:
                print("    (aviso) '{}' funcionou pela alternativa {}".format(descricao, i + 1))
            return r
        except Exception as e:  # noqa
            erros.append("alt {}: {}".format(i + 1, e))
    raise RuntimeError("Falhou: {}\n    ".format(descricao) + "\n    ".join(erros))


def obter_senha():
    pw = globals().get("PLAXIS_PASSWORD") or os.environ.get("PLAXIS_PASSWORD")
    if not pw:
        pw = getpass.getpass("Senha do servidor PLAXIS: ")
    return pw


# ----------------------------------------------------------------------------
# 1. Projeto e contorno
# ----------------------------------------------------------------------------
if CRIAR_PROJETO_NOVO:
    etapa("Novo projeto")
    s_i.new()

etapa("Propriedades do projeto (m, kN, dia; gamma_w = 10) e contorno 10 x 10 m")
g_i.setproperties("Title", "PLAXIS 3D: Bearing Capacity and Settlement Analysis of Shallow Foundation",
                  "UnitForce", "kN", "UnitLength", "m", "UnitTime", "day",
                  "WaterWeight", 10.0)
g_i.SoilContour.initializerectangular(XMIN, YMIN, XMAX, YMAX)

# ----------------------------------------------------------------------------
# 2. Borehole, camada e nível d'água
# ----------------------------------------------------------------------------
etapa("Borehole em ({}, {}), camada 0 a -{} m, Head = {}".format(XMIN, YMIN, PROFUNDIDADE, NIVEL_AGUA))
borehole = g_i.borehole(XMIN, YMIN)
borehole.Head = NIVEL_AGUA
g_i.soillayer(PROFUNDIDADE)          # camada de espessura 10 m (topo 0, base -10)

# ----------------------------------------------------------------------------
# 3. Materiais
# ----------------------------------------------------------------------------
def definir_props(obj, descricao, lista):
    """
    Seta uma propriedade por vez. Cada item é (nomes_alternativos, valor...).
    Tenta cada nome/valor até um funcionar; no fim, lista TUDO que falhou de uma vez.
    """
    falhas = []
    for nomes, valores in lista:
        if isinstance(nomes, str):
            nomes = (nomes,)
        if not isinstance(valores, tuple):
            valores = (valores,)
        ok = False
        ultimo_erro = None
        for nome in nomes:
            for v in valores:
                try:
                    obj.setproperties(nome, v)
                    ok = True
                    break
                except Exception as e:  # noqa
                    ultimo_erro = e
            if ok:
                break
        if not ok:
            falhas.append("{} (erro: {})".format("/".join(nomes), str(ultimo_erro).strip().splitlines()[-1]))
    if falhas:
        # Diagnóstico: mostra as propriedades que o objeto realmente tem
        try:
            print("\n    --- propriedades reais de '{}' (echo) ---".format(descricao))
            print(obj.echo())
            print("    --- fim do echo ---")
        except Exception as e:  # noqa
            print("    (echo indisponível: {})".format(e))
        raise RuntimeError("Propriedades de '{}' que NÃO foram aceitas:\n    - ".format(descricao)
                           + "\n    - ".join(falhas))


etapa("Material do solo: Mohr-Coulomb, drenado")
mat_solo = g_i.soilmat()
definir_props(mat_solo, "solo", [
    (("Identification", "MaterialName"), "Soil"),
    ("SoilModel", (2, "Mohr-Coulomb")),            # 2 = Mohr-Coulomb
    ("DrainageType", ("Drained", 0)),
    (("gammaUnsat", "gamma_unsat"), SOLO["gamma_unsat"]),
    (("gammaSat", "gamma_sat"), SOLO["gamma_sat"]),
    (("Eref", "E"), SOLO["E"]),
    ("nu", SOLO["nu"]),
    (("cref", "c"), SOLO["c"]),
    (("phi", "phi_ref"), SOLO["phi"]),
    ("psi", SOLO["psi"]),
])
# Demais abas (water, interfaces, initial K0 = automatic) ficam no padrão, como no vídeo.

etapa("Atribuindo o solo à camada")
g_i.Soillayers[0].Soil.Material = mat_solo

etapa("Material da sapata: placa elástica isotrópica")
mat_sapata = g_i.platemat()
definir_props(mat_sapata, "sapata (identificação/tipo)", [
    (("Identification", "MaterialName"), "Footing"),
    (("MaterialType", "PlateType"), ("Elastic", 0)),
])
definir_props(mat_sapata, "sapata", [
    (("Isotropic", "isotropic"), True),
    (("gamma", "Gamma"), SAPATA["gamma"]),
    (("d", "D", "Thickness"), SAPATA["d"]),
    (("E1", "E", "Eref"), SAPATA["E"]),
    (("StructNu12", "nu12", "nu", "Nu12"), SAPATA["nu"]),
])

# ----------------------------------------------------------------------------
# 4. Estruturas: superfície 1x1 em z=0 -> placa + carga de superfície
# ----------------------------------------------------------------------------
etapa("Modo Structures: superfície {0} x {0} m centrada na origem".format(SAPATA_LADO))
g_i.gotostructures()
h = SAPATA_LADO / 2.0
superficie = primeiro(g_i.surface((-h, h, 0), (h, h, 0), (h, -h, 0), (-h, -h, 0)))

etapa("Convertendo a superfície em placa e atribuindo material")
alvos = [superficie]
try:
    alvos.append(g_i.Polygon_1)
except Exception:
    pass


def _criar(cmds):
    """Tenta cada nome de comando em cada alvo; se tudo falhar, mostra TODOS os erros."""
    if isinstance(cmds, str):
        cmds = (cmds,)
    erros = []
    for cmd in cmds:
        for a in alvos:
            try:
                return primeiro(getattr(g_i, cmd)(a))
            except Exception as e:  # noqa
                msg = str(e).strip().splitlines()
                erros.append("g_i.{}({}) -> {}".format(cmd, a, msg[-1] if msg else repr(e)))
    raise RuntimeError("Nenhuma tentativa funcionou:\n    " + "\n    ".join(erros))


placa = _criar("plate")
placa.Material = mat_sapata

etapa("Carga de superfície uniforme sigz = -{} kN/m2".format(CARGA))
carga = _criar(("surfaceload", "surfload", "surfaceLoad"))
tentar("sigz",
       lambda: setattr(carga, "sigz", -CARGA),
       lambda: carga.setproperties("sigz", -CARGA))

# ----------------------------------------------------------------------------
# 5. Malha + ponto de curva (pré-cálculo) no centro da sapata
# ----------------------------------------------------------------------------
etapa("Modo Mesh: refinamento da sapata (coarseness {}) e geração da malha".format(COARSENESS_SAPATA))
g_i.gotomesh()


def _ler_lista(obj, nome="CoarsenessFactor"):
    """Polygon_1.CoarsenessFactor é uma 'Number list': tenta converter para lista de floats."""
    try:
        cf = getattr(obj, nome)
    except Exception:
        return None
    for conv in (lambda: [float(v) for v in cf],
                 lambda: [float(v) for v in cf.value],
                 lambda: [float(cf)]):
        try:
            return conv()
        except Exception:
            continue
    return None


def setar_coarseness(poly, valor):
    """Tenta várias formas de gravar a lista e CONFERE lendo de volta."""
    antes = _ler_lista(poly)
    print("    CoarsenessFactor antes : {}".format(antes))
    n = len(antes) if antes else 1

    def _por_indice():
        for i in range(n):
            poly.CoarsenessFactor[i] = valor

    tentativas = [
        ("setproperties escalar", lambda: g_i.setproperties(poly, "CoarsenessFactor", valor)),
        ("atribuição escalar", lambda: setattr(poly, "CoarsenessFactor", valor)),
        ("atribuição em lista", lambda: setattr(poly, "CoarsenessFactor", [valor] * n)),
        ("setproperties em lista", lambda: g_i.setproperties(poly, "CoarsenessFactor", [valor] * n)),
        ("por índice", _por_indice),
    ]
    for nome, f in tentativas:
        try:
            f()
        except Exception as e:  # noqa
            msg = str(e).strip().splitlines()
            print("    - {}: erro ({})".format(nome, msg[-1] if msg else repr(e)))
            continue
        depois = _ler_lista(poly)
        if depois and all(abs(v - valor) < 1e-9 for v in depois):
            print("    CoarsenessFactor depois: {}  (OK via '{}')".format(depois, nome))
            return True
        print("    - {}: sem efeito (lido de volta: {})".format(nome, depois))
    return False


# No PLAXIS 3D 2024.2 o coarseness da superfície fica no polígono do modo Mesh (Polygon_1_1), e não em
# Polygon_1 (que devolve uma lista somente leitura). aplicar_coarseness() é a mesma rotina validada no
# Exemplo 2 e no script interativo: grava em Polygon_1_N e confere lendo de volta do servidor.
def _num_ou_lista(txt):
    """Extrai os números que aparecem depois de 'CoarsenessFactor' num texto de echo()."""
    import re
    achados = []
    for mt in re.finditer(r"CoarsenessFactor[^0-9\-+\n]*([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)", txt):
        achados.append(float(mt.group(1)))
    return achados or None


def ler_coarseness_servidor(nome):
    """Lê o coarseness de um objeto buscado de novo em g_i (echo() vem do servidor)."""
    try:
        obj = getattr(g_i, nome)
    except Exception:
        return None
    try:
        v = _num_ou_lista(str(obj.echo()))
        if v:
            return v
    except Exception:
        pass
    return _ler_lista(obj)


def _confere(nome, valor):
    lido = ler_coarseness_servidor(nome)
    return bool(lido) and all(abs(v - valor) < 1e-9 for v in lido), lido


def aplicar_coarseness(valor):
    """
    O coarseness de uma superfície fica nos polígonos do modo Mesh (Polygon_1_1, ...), e não em
    Polygon_1. No log do Exemplo 1 o comando que funcionou foi 'set Polygon_1_1.CoarsenessFactor 0.1'.
    Tenta (1) direto nos Polygon_1_N existentes e (2) por índice em Polygon_1.CoarsenessFactor[i].
    Devolve True se algum caminho foi confirmado lendo de volta do servidor.
    """
    nomes = []
    for j in range(1, 13):
        nome = "Polygon_1_{}".format(j)
        try:
            getattr(g_i, nome).echo()
            nomes.append(nome)
        except Exception:
            pass
    print("    Polígonos do modo Mesh encontrados: {}".format(nomes or "nenhum"))

    for nome in nomes:
        print("    {}: coarseness atual = {}".format(nome, ler_coarseness_servidor(nome)))
        for rotulo, f in (
            ("atribuição direta", lambda n=nome: setattr(getattr(g_i, n), "CoarsenessFactor", valor)),
            ("setproperties", lambda n=nome: g_i.setproperties(getattr(g_i, n), "CoarsenessFactor", valor)),
        ):
            try:
                f()
            except Exception as e:  # noqa
                msg = str(e).strip().splitlines()
                print("    - {} em {}: erro ({})".format(rotulo, nome, msg[0] if msg else repr(e)))
                continue
            ok, lido = _confere(nome, valor)
            if ok:
                print("    {}: coarseness = {}  (OK via '{}', conferido no servidor)".format(nome, lido, rotulo))
                break
            print("    - {} em {}: não confirmado (lido de volta: {})".format(rotulo, nome, lido))
    if nomes and all(_confere(n, valor)[0] for n in nomes):
        return True

    # Caminho 2: lista em Polygon_1 (era assim no primeiro teste do Exemplo 1)
    try:
        poly = g_i.Polygon_1
        antes = _ler_lista(poly)
        print("    Polygon_1.CoarsenessFactor antes: {}".format(antes))
        for i in range(len(antes) if antes else 1):
            poly.CoarsenessFactor[i] = valor
        ok, lido = _confere("Polygon_1", valor)
        print("    Polygon_1.CoarsenessFactor depois: {} ({})".format(lido, "OK" if ok else "não confirmado"))
        if ok and (not nomes or all(_confere(n, valor)[0] for n in nomes)):
            return True
    except Exception as e:  # noqa
        msg = str(e).strip().splitlines()
        print("    - por índice em Polygon_1: erro ({})".format(msg[0] if msg else repr(e)))

    # Caminho 3: a MESMA sequência de tentativas do nichirvan_taher_exemplo1_modelo.py (a que funcionou no Exemplo 1),
    # na mesma ordem, caso o índice só funcione depois das tentativas anteriores.
    try:
        poly = g_i.Polygon_1
        n = len(_ler_lista(poly) or [1])

        def _por_indice():
            for i in range(n):
                poly.CoarsenessFactor[i] = valor

        for rotulo, f in (
            ("setproperties escalar", lambda: g_i.setproperties(poly, "CoarsenessFactor", valor)),
            ("atribuição escalar", lambda: setattr(poly, "CoarsenessFactor", valor)),
            ("atribuição em lista", lambda: setattr(poly, "CoarsenessFactor", [valor] * n)),
            ("setproperties em lista", lambda: g_i.setproperties(poly, "CoarsenessFactor", [valor] * n)),
            ("por índice", _por_indice),
        ):
            try:
                f()
            except Exception as e:  # noqa
                msg = str(e).strip().splitlines()
                print("    - (sequência do Ex.1) {}: erro ({})".format(rotulo, msg[0] if msg else repr(e)))
        for nome in (nomes or ["Polygon_1"]):
            ok, lido = _confere(nome, valor)
            print("    {}: coarseness após a sequência do Ex.1 = {} ({})".format(
                nome, lido, "OK" if ok else "não confirmado"))
            if ok:
                return True
    except Exception as e:  # noqa
        msg = str(e).strip().splitlines()
        print("    - sequência do Ex.1: erro ({})".format(msg[0] if msg else repr(e)))
    return False




ok_coarse = False
try:
    ok_coarse = aplicar_coarseness(COARSENESS_SAPATA)
except Exception as e:  # noqa
    print("    - coarseness: {}".format(str(e).strip().splitlines()[0]))
if not ok_coarse:
    try:
        poly = g_i.Polygon_1
    except Exception:
        poly = superficie
    ok_coarse = setar_coarseness(poly, COARSENESS_SAPATA)      # forma antiga, como último recurso
if not ok_coarse:
    print("    (AVISO) não consegui alterar o coarseness da sapata por script.")
    print("    Ajuste manualmente no modo Mesh (Polygon_1_1 -> Coarseness factor = {}) e gere a malha de novo."
          .format(COARSENESS_SAPATA))

res_malha = g_i.mesh(TAMANHO_RELATIVO_MALHA)
if res_malha not in (None, "", True):
    print("    mesh ->", res_malha)
print("    Malha gerada (relative element size = {}). Com 'fine' + coarseness 0,1 o esperado é ~23.855 elementos."
      .format(TAMANHO_RELATIVO_MALHA))

etapa("Selecionando nó em (0, 0, 0) para a curva carga x recalque")
senha = obter_senha()
porta_out = g_i.selectmeshpoints()
s_o, g_o = new_server(HOST, porta_out, password=senha)
g_o.addcurvepoint("node", 0.0, 0.0, 0.0)
g_o.update()                              # atualiza e fecha o Output da malha

# ----------------------------------------------------------------------------
# 6. Fases
# ----------------------------------------------------------------------------
etapa("Modo Staged construction")
g_i.gotostages()

tentar("Initial phase = K0 procedure",
       lambda: setattr(g_i.InitialPhase, "DeformCalcType", "K0 procedure"),
       lambda: g_i.InitialPhase.setproperties("DeformCalcType", "K0 procedure"))

fase_sapata = g_i.phase(g_i.InitialPhase)
fase_sapata.Identification = "Footing"
fase_sapata.Deform.ResetDisplacementsToZero = True
tentar("ativar placa na fase Footing",
       lambda: g_i.activate(g_i.Plate_1, fase_sapata),
       lambda: g_i.activate(g_i.Plates[0], fase_sapata),
       lambda: g_i.activate(placa, fase_sapata))

fase_carga = g_i.phase(fase_sapata)
fase_carga.Identification = "Load"
fase_carga.Deform.ResetDisplacementsToZero = True   # recalque só após aplicar a carga
tentar("ativar carga na fase Load",
       lambda: g_i.activate(g_i.SurfaceLoad_1, fase_carga),
       lambda: g_i.activate(g_i.SurfaceLoads[0], fase_carga),
       lambda: g_i.activate(carga, fase_carga))

# ----------------------------------------------------------------------------
# Salvar e calcular
# ----------------------------------------------------------------------------
etapa("Salvando em " + SALVAR_EM)
g_i.save(SALVAR_EM)

etapa("Calculando (a fase Load tende a parar por colapso perto de 800 kN/m2: é o esperado)")
try:
    g_i.calculate()
except Exception as e:
    print("    calculate() levantou: {}".format(e))

for fase in g_i.Phases:
    try:
        print("    {:<12} -> {}".format(fase.Identification.value, fase.LogInfo.value))
    except Exception:
        pass

try:
    g_i.save(SALVAR_EM)
except Exception:
    pass

print("\nModelo pronto e calculado. Agora rode nichirvan_taher_exemplo1_resultados.py.")

# -*- coding: utf-8 -*-
"""
Exemplo 2 - Capacidade de carga admissível (qa) por RECALQUE, com deslocamento prescrito (PLAXIS 3D)

Mesmo solo do Exemplo 1, sapata 3,0 x 3,0 x 0,8 m, SEM carga de superfície: em vez dela, um
deslocamento prescrito de superfície de 2,5 cm para baixo na sapata (como no PDF, item 6).
A força necessária para impor esse recalque, dividida pela área da sapata, dá a tensão
(no PDF: 3173 kN / 9 m2 = 352,5 kN/m2).

Roda pelo executor externo (ele já entrega s_i e g_i). Não pergunta nada: edite os PARÂMETROS abaixo.

Fases: Initial (K0) -> Footing (ativa a placa) -> Settlement (ativa o deslocamento prescrito).
Depois rode exemplo2_resultados.py.

Validado no PLAXIS real (Exemplo 1): tudo, exceto o deslocamento prescrito (comando, nomes das
propriedades), que está "não testado": se algo for recusado o script mostra o echo() do objeto.
"""
import os
import json
import getpass

from plxscripting.easy import new_server

# ----------------------------------------------------------------------------
# PARÂMETROS (edite aqui)
# ----------------------------------------------------------------------------
HOST = "localhost"

XMIN, XMAX, YMIN, YMAX = -5.0, 5.0, -5.0, 5.0     # contorno (igual ao Exemplo 1)
PROFUNDIDADE = 10.0
NIVEL_AGUA = -6.0

SOLO = dict(gamma_unsat=18.0, gamma_sat=20.0, E=40000.0, nu=0.3, c=30.0, phi=20.0, psi=0.0)

SAPATA_L, SAPATA_W = 3.0, 3.0                      # comprimento (x) e largura (y)
SAPATA = dict(gamma=24.0, d=0.8, E=2.35e7, nu=0.2)  # espessura 0,8 m
CX, CY, CZ = 0.0, 0.0, 0.0                         # centro e cota da sapata

DESLOC_PRESCRITO = 0.025                           # m, para baixo (uz = -0,025)

PRESETS_MALHA = {"very coarse": 0.1, "coarse": 0.075, "medium": 0.05, "fine": 0.035, "very fine": 0.025}
MALHA = "fine"                                     # nome do preset ou número
COARSENESS_SAPATA = 0.1

PASTA = os.path.dirname(os.path.abspath(globals().get("__file__", ".")))
SALVAR_EM = os.path.join(PASTA, "Exemplo2_Sapata.p3d")
ARQUIVO_JSON = os.path.join(PASTA, "exemplo2_modelo.json")

if isinstance(MALHA, str):
    TAMANHO_RELATIVO_MALHA = PRESETS_MALHA[MALHA.lower()]
else:
    TAMANHO_RELATIVO_MALHA = float(MALHA)


def fmt(x):
    return "{:g}".format(x)


def _ler(prompt, default_txt):
    sufixo = " [{}]".format(default_txt) if default_txt not in (None, "") else ""
    try:
        return input("  {}{}: ".format(prompt, sufixo)).strip()
    except EOFError:
        raise RuntimeError("Sem terminal interativo para ler as respostas.")


def perguntar_float(prompt, default=None, lo=None, hi=None, lo_incl=True, hi_incl=True, unidade=""):
    rotulo = prompt + (" ({})".format(unidade) if unidade else "")
    while True:
        txt = _ler(rotulo, fmt(default) if default is not None else None)
        if txt == "" and default is not None:
            v = float(default)
        else:
            try:
                v = float(txt.replace(",", "."))
            except ValueError:
                print("    ! Digite um número (use ponto ou vírgula).")
                continue
        if lo is not None and (v < lo if lo_incl else v <= lo):
            print("    ! O valor deve ser {} {}.".format(">=" if lo_incl else ">", fmt(lo)))
            continue
        if hi is not None and (v > hi if hi_incl else v >= hi):
            print("    ! O valor deve ser {} {}.".format("<=" if hi_incl else "<", fmt(hi)))
            continue
        return v


def perguntar_int(prompt, default, lo, hi):
    while True:
        txt = _ler(prompt, str(default))
        try:
            v = default if txt == "" else int(txt)
        except ValueError:
            print("    ! Digite um número inteiro.")
            continue
        if v < lo or v > hi:
            print("    ! Digite um valor entre {} e {}.".format(lo, hi))
            continue
        return v


def perguntar_texto(prompt, default):
    txt = _ler(prompt, default)
    return txt or default


def perguntar_sim_nao(prompt, default=True):
    padrao = "s" if default else "n"
    while True:
        txt = _ler(prompt + " (s/n)", padrao).lower()
        if txt == "":
            return default
        if txt in ("s", "sim", "y", "yes"):
            return True
        if txt in ("n", "nao", "não", "no"):
            return False
        print("    ! Responda s ou n.")


def perguntar_opcao(titulo, opcoes, default=1):
    print("\n  " + titulo)
    for i, o in enumerate(opcoes, 1):
        print("    {}) {}".format(i, o))
    return perguntar_int("Opção", default, 1, len(opcoes))


def aviso(msg):
    print("    (aviso) " + msg)


def etapa(msg):
    print("\n>>> " + msg)


def titulo(msg):
    print("\n" + "-" * 70)
    print(msg)
    print("-" * 70)




def primeiro(res):
    if isinstance(res, (tuple, list)):
        return res[0]
    return res


def tentar(descricao, *funcs):
    erros = []
    for i, f in enumerate(funcs):
        try:
            r = f()
            if i > 0:
                print("    (aviso) '{}' funcionou pela alternativa {}".format(descricao, i + 1))
            return r
        except Exception as e:  # noqa
            msg = str(e).strip().splitlines()
            erros.append("alt {}: {}".format(i + 1, msg[-1] if msg else repr(e)))
    raise RuntimeError("Falhou: {}\n    ".format(descricao) + "\n    ".join(erros))


def definir_props(obj, descricao, lista):
    """Seta uma propriedade por vez (nomes/valores alternativos) e lista tudo que falhar."""
    falhas = []
    for nomes, valores in lista:
        if isinstance(nomes, str):
            nomes = (nomes,)
        if not isinstance(valores, tuple):
            valores = (valores,)
        ok, ultimo = False, None
        for nome in nomes:
            for v in valores:
                try:
                    obj.setproperties(nome, v)
                    ok = True
                    break
                except Exception as e:  # noqa
                    ultimo = e
            if ok:
                break
        if not ok:
            falhas.append("{} (erro: {})".format("/".join(nomes), str(ultimo).strip().splitlines()[-1]))
    if falhas:
        try:
            print("\n    --- propriedades reais de '{}' (echo) ---".format(descricao))
            print(obj.echo())
            print("    --- fim do echo ---")
        except Exception:
            pass
        raise RuntimeError("Propriedades de '{}' que NÃO foram aceitas:\n    - ".format(descricao)
                           + "\n    - ".join(falhas))


def setar_attr(obj, nome, valor):
    tentar(nome, lambda: setattr(obj, nome, valor), lambda: obj.setproperties(nome, valor))


def obter_senha():
    pw = globals().get("PLAXIS_PASSWORD") or os.environ.get("PLAXIS_PASSWORD")
    if not pw:
        pw = getpass.getpass("Senha do servidor PLAXIS: ")
    return pw


def _ler_lista(obj, nome="CoarsenessFactor"):
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

    # Caminho 3: a MESMA sequência de tentativas do exemplo1_modelo.py (a que funcionou no Exemplo 1),
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


def ativar(descricao, nomes, fase):
    """Ativa um objeto numa fase pelo NOME (activate Plate_1 Phase_1 funcionou no PLAXIS real)."""
    tentativas = [(lambda n=n: g_i.activate(getattr(g_i, n), fase)) for n in nomes]
    tentar(descricao, *tentativas)



# ----------------------------------------------------------------------------
# Construção do modelo
# ----------------------------------------------------------------------------
senha = obter_senha()

etapa("Novo projeto")
s_i.new()
g_i.setproperties("Title", "PLAXIS 3D: Exemplo 2 - sapata com deslocamento prescrito",
                  "UnitForce", "kN", "UnitLength", "m", "UnitTime", "day", "WaterWeight", 10.0)
g_i.SoilContour.initializerectangular(XMIN, YMIN, XMAX, YMAX)

etapa("Borehole em ({}, {}), camada 0 a -{} m, N.A. z = {}".format(XMIN, YMIN, PROFUNDIDADE, NIVEL_AGUA))
borehole = g_i.borehole(XMIN, YMIN)
borehole.Head = NIVEL_AGUA
g_i.soillayer(PROFUNDIDADE)

etapa("Material do solo (Mohr-Coulomb, drenado)")
mat_solo = g_i.soilmat()
definir_props(mat_solo, "solo", [
    (("Identification", "MaterialName"), "Soil"),
    ("SoilModel", (2, "Mohr-Coulomb")),
    ("DrainageType", ("Drained", 0)),
    (("gammaUnsat", "gamma_unsat"), SOLO["gamma_unsat"]),
    (("gammaSat", "gamma_sat"), SOLO["gamma_sat"]),
    (("Eref", "E"), SOLO["E"]),
    ("nu", SOLO["nu"]),
    (("cref", "c"), SOLO["c"]),
    (("phi", "phi_ref"), SOLO["phi"]),
    ("psi", SOLO["psi"]),
])
g_i.Soillayers[0].Soil.Material = mat_solo

etapa("Material da sapata (placa elástica isotrópica)")
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

etapa("Modo Structures: superfície {} x {} m em z = {}".format(fmt(SAPATA_L), fmt(SAPATA_W), fmt(CZ)))
g_i.gotostructures()
hx, hy = SAPATA_L / 2.0, SAPATA_W / 2.0
poly = primeiro(g_i.surface((CX - hx, CY + hy, CZ), (CX + hx, CY + hy, CZ),
                            (CX + hx, CY - hy, CZ), (CX - hx, CY - hy, CZ)))
alvos = [poly]
try:
    alvos.append(g_i.Polygon_1)
except Exception:
    pass


def criar(cmds):
    """Tenta cada comando em cada alvo; se tudo falhar mostra todos os erros."""
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


etapa("Convertendo a superfície em placa")
placa = criar("plate")
placa.Material = mat_sapata

etapa("Deslocamento prescrito de superfície: uz = -{} m (não testado)".format(fmt(DESLOC_PRESCRITO)))
desl = criar(("surfdispl", "surfacedisplacement", "surfdisplacement", "surfdisp", "prescribeddisplacement"))
try:
    print("    objeto criado:", desl)
except Exception:
    pass
# Eixos x e y livres (a sapata só é empurrada para baixo); z prescrito.
for nomes, valores in ((("Displacement_x", "DisplacementX"), ("Free", 0)),
                       (("Displacement_y", "DisplacementY"), ("Free", 0))):
    try:
        definir_props(desl, "deslocamento prescrito (livre)", [(nomes, valores)])
    except Exception as e:  # noqa
        print("    (aviso) não consegui deixar {} livre: {}".format(nomes[0], str(e).splitlines()[0]))
definir_props(desl, "deslocamento prescrito (z)", [
    (("Displacement_z", "DisplacementZ"), ("Prescribed", 1)),
    (("uz", "uz_start", "Uz_start"), -DESLOC_PRESCRITO),     # no PLAXIS 3D 2024.2 o nome é 'uz' (Distribution já é Uniform)
])
try:
    print(desl.echo())
except Exception:
    pass

# ----------------------------------------------------------------------------
# Malha
# ----------------------------------------------------------------------------
etapa("Modo Mesh: preset (fator {})".format(fmt(TAMANHO_RELATIVO_MALHA)))
g_i.gotomesh()
ok = False
try:
    ok = aplicar_coarseness(COARSENESS_SAPATA)
except Exception as e:  # noqa
    print("    - coarseness: {}".format(str(e).strip().splitlines()[0]))
if not ok:
    print("\n    (ATENÇÃO) Não consegui aplicar o coarseness {} por script.".format(fmt(COARSENESS_SAPATA)))
    print("    No modo Mesh: selecione Polygon_1_1 e coloque Coarseness factor = {}.".format(fmt(COARSENESS_SAPATA)))
    if _ler("Depois de ajustar, tecle Enter para gerar a malha (x cancela)", "").lower() == "x":
        raise RuntimeError("Cancelado: coarseness não aplicado.")
res_malha = g_i.mesh(TAMANHO_RELATIVO_MALHA)
if res_malha not in (None, "", True):
    print("    mesh ->", res_malha)

etapa("Nó para a curva deslocamento em ({}, {}, {})".format(fmt(CX), fmt(CY), fmt(CZ)))
porta_out = g_i.selectmeshpoints()
s_o, g_o = new_server(HOST, porta_out, password=senha)
g_o.addcurvepoint("node", CX, CY, CZ)
g_o.update()

# ----------------------------------------------------------------------------
# Fases
# ----------------------------------------------------------------------------
etapa("Modo Staged construction: Initial (K0) -> Footing -> Settlement")
g_i.gotostages()
tentar("Initial phase = K0 procedure",
       lambda: setattr(g_i.InitialPhase, "DeformCalcType", "K0 procedure"),
       lambda: g_i.InitialPhase.setproperties("DeformCalcType", "K0 procedure"))
fase_sapata = g_i.phase(g_i.InitialPhase)
fase_sapata.Identification = "Footing"
fase_sapata.Deform.ResetDisplacementsToZero = True
ativar("ativar placa na fase Footing", ["Plate_1"], fase_sapata)

fase_rec = g_i.phase(fase_sapata)
fase_rec.Identification = "Settlement"
fase_rec.Deform.ResetDisplacementsToZero = True
_nomes_desl = ["SurfaceDisplacement_1", "PrescribedDisplacement_1", "SurfDispl_1", "SurfaceDisplacement1"]
tentar("ativar deslocamento prescrito na fase Settlement",
       *([(lambda n=n: g_i.activate(getattr(g_i, n), fase_rec)) for n in _nomes_desl]
         + [lambda: g_i.activate(desl, fase_rec),
            lambda: g_i.activate(getattr(g_i, str(desl).strip()), fase_rec)]))

with open(ARQUIVO_JSON, "w", encoding="utf-8") as fh:
    json.dump(dict(area=SAPATA_L * SAPATA_W, B=min(SAPATA_L, SAPATA_W), desloc_m=DESLOC_PRESCRITO,
                   cx=CX, cy=CY, cz=CZ), fh, indent=2)

etapa("Salvando em " + SALVAR_EM)
g_i.save(SALVAR_EM)

etapa("Calculando (as fases devem terminar sem falha: o deslocamento é imposto)")
try:
    g_i.calculate()
except Exception as e:  # noqa
    print("    calculate() levantou: {}".format(e))
for fase in g_i.Phases:
    try:
        print("    {:<14} -> LogInfo {}".format(fase.Identification.value, fase.LogInfo.value))
    except Exception:
        pass
try:
    g_i.save(SALVAR_EM)
except Exception:
    pass
print("\nPronto. Rode exemplo2_resultados.py com este projeto aberto.")

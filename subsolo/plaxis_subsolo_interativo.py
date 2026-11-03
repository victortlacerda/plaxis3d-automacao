# -*- coding: utf-8 -*-
"""
PLAXIS 3D - Subsolo com radier estrutural (Caso B do Tutorial 1 do manual da Bentley).

Script SEPARADO do plaxis_sapata_interativo.py (que continua intacto). Roda pelo executor externo, que
já entrega s_i e g_i. O script PERGUNTA os dados no terminal; Enter aceita o valor entre colchetes
(os padrões são os do Caso B do manual). Grava "ultimo_modelo_subsolo.json" para o
plaxis_subsolo_resultados.py.

Modelo (um quarto do prédio; os planos x = xmin e y = ymin do domínio fazem o papel de simetria):
  - solo argiloso de 1 camada, Mohr-Coulomb, rigidez crescente com a profundidade (E'ref + E'inc);
  - volume de escavação (subsolo) criado por extrusão da superfície; o solo desse volume é desativado
    na fase "Excavation";
  - piso (plate) no fundo do subsolo, paredes (plates) nas bordas +x e +y, coluna e vigas (beams);
  - cargas: surface load no piso, line load nas paredes, point load no topo da coluna;
  - fases: Initial (K0) -> Excavation (escava + paredes) -> Construction (piso + vigas + coluna)
    -> Loading (todas as cargas).

TUDO nas partes estruturais é "(não testado)": este script foi escrito a partir do manual, sem o
histórico de comandos do PLAXIS para beams, line loads, decomposição e desativação de volume.
Por isso cada item é tentado com alternativas; se algum falhar o script NÃO aborta: registra a falha,
imprime o echo do objeto (para descobrir os nomes reais das propriedades), segue com o que der e, no
fim, lista o que ficou faltando. O projeto só é calculado se nada falhou.
"""
import os
import json
import getpass

from plxscripting.easy import new_server

HOST = "localhost"
PORTA_PADRAO = 10000
TITULO_PADRAO = "PLAXIS 3D: Subsolo com radier (modelo interativo)"
PASTA = os.path.dirname(os.path.abspath(globals().get("__file__", ".")))
ARQUIVO_JSON = os.path.join(PASTA, "ultimo_modelo_subsolo.json")

# Presets do GUI (lidos no histórico de comandos do PLAXIS 3D 2024.2)
PRESETS_MALHA = (("very coarse", 0.1), ("coarse", 0.075), ("medium", 0.05),
                 ("fine", 0.035), ("very fine", 0.025))


# ----------------------------------------------------------------------------
# Utilitários de entrada
# ----------------------------------------------------------------------------
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




def verificar_conexao():
    """Leitura inofensiva só para detectar cedo se o servidor do PLAXIS Input parou de responder
    (evita preencher todas as perguntas e só então falhar em s_i.new())."""
    gi = globals().get("g_i")
    if gi is None:
        return
    try:
        gi.echo()
    except Exception as e:  # noqa
        txt = "{} {}".format(type(e).__name__, e)
        if "Connection" in txt or "10061" in txt or "Max retries" in txt:
            raise RuntimeError(
                "O PLAXIS Input não está respondendo (conexão recusada). Confira se o PLAXIS 3D Input continua "
                "aberto e se o servidor de scripts está ativo (Expert > Configure remote scripting server, "
                "'Start server', porta {}), e rode o executor de novo.".format(PORTA_PADRAO))



# ----------------------------------------------------------------------------
# Perguntas
# ----------------------------------------------------------------------------
def perguntar_tudo():
    P = {}
    print("=" * 70)
    print(" PLAXIS 3D - SUBSOLO COM RADIER (Caso B do manual da Bentley)")
    print(" Enter aceita o valor entre colchetes (padrão = Caso B do manual).")
    print(" Unidades: m, kN, dia. Eixo z positivo para cima (terreno em z = 0).")
    print("=" * 70)

    P["info"] = dict(titulo=TITULO_PADRAO, empresa="")
    if perguntar_sim_nao("Definir Title e Company do projeto (n = manter o padrão)?", False):
        P["info"]["titulo"] = perguntar_texto("Title", TITULO_PADRAO)
        P["info"]["empresa"] = perguntar_texto("Company", "")

    # --- 1. Domínio
    titulo("1) DOMÍNIO DO MODELO")
    xmin = perguntar_float("x mínimo", 0.0, unidade="m")
    xmax = perguntar_float("x máximo", 75.0 if 75.0 > xmin else xmin + 75.0, lo=xmin, lo_incl=False, unidade="m")
    ymin = perguntar_float("y mínimo", 0.0, unidade="m")
    ymax = perguntar_float("y máximo", 75.0 if 75.0 > ymin else ymin + 75.0, lo=ymin, lo_incl=False, unidade="m")
    H = perguntar_float("Profundidade total do modelo (positiva; o fundo fica em z = -H)", 40.0,
                        lo=0.0, lo_incl=False, unidade="m")
    P["dominio"] = dict(xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax, H=H)

    # --- 2. Solo (1 camada, rigidez crescente com a profundidade)
    titulo("2) SOLO (1 camada, Mohr-Coulomb, drenado)")
    nome = perguntar_texto("Nome do material", "Lacustrine clay")
    gu = perguntar_float("Peso específico não saturado", 17.0, lo=0.0, lo_incl=False, unidade="kN/m3")
    gs = perguntar_float("Peso específico saturado", max(18.0, gu), lo=0.0, lo_incl=False, unidade="kN/m3")
    E = perguntar_float("Módulo de Young E'ref (em z = zref)", 5000.0, lo=0.0, lo_incl=False, unidade="kN/m2")
    Einc = perguntar_float("Incremento de rigidez com a profundidade E'inc (0 = rigidez constante)", 500.0,
                           lo=0.0, unidade="kN/m2 por m")
    zref = 0.0
    if Einc > 0:
        zref = perguntar_float("Cota de referência zref (E'ref vale nessa cota)", 0.0, hi=0.0, unidade="m")
    nu = perguntar_float("Coeficiente de Poisson ν'", 0.3, lo=0.0, hi=0.5, lo_incl=False, hi_incl=False)
    c = perguntar_float("Coesão c'", 10.0, lo=0.0, unidade="kN/m2")
    if c < 0.2:
        aviso("c' < 0,2 kN/m2 pode dificultar a convergência no PLAXIS.")
    phi = perguntar_float("Ângulo de atrito φ'", 30.0, lo=0.0, hi=89.0, unidade="graus")
    psi = perguntar_float("Ângulo de dilatância ψ", 0.0, lo=0.0, hi=phi, unidade="graus")
    na = perguntar_float("Cota z do nível freático (0 = superfície; -H = fundo do modelo)", -2.0,
                         lo=-H, hi=0.0, unidade="m")
    P["solo"] = dict(nome=nome, gamma_unsat=gu, gamma_sat=gs, E=E, Einc=Einc, zref=zref, nu=nu, c=c,
                     phi=phi, psi=psi)
    P["nivel_agua"] = na

    # --- 3. Subsolo (volume escavado)
    titulo("3) SUBSOLO (volume escavado)")
    d = P["dominio"]
    while True:
        bx0 = perguntar_float("x do canto inferior do subsolo", xmin, lo=d["xmin"], hi=d["xmax"], unidade="m")
        by0 = perguntar_float("y do canto inferior do subsolo", ymin, lo=d["ymin"], hi=d["ymax"], unidade="m")
        Lb = perguntar_float("Comprimento do subsolo no modelo (direção x)", 18.0, lo=0.0, lo_incl=False, unidade="m")
        Wb = perguntar_float("Largura do subsolo no modelo (direção y)", 18.0, lo=0.0, lo_incl=False, unidade="m")
        Hb = perguntar_float("Profundidade da escavação", 2.0, lo=0.0, hi=H, lo_incl=False, hi_incl=False,
                             unidade="m")
        erros = []
        if bx0 + Lb > d["xmax"] or by0 + Wb > d["ymax"]:
            erros.append("o subsolo sai do domínio")
        if erros:
            print("    ! " + "; ".join(erros) + ". Digite de novo.\n")
            continue
        break
    if bx0 > d["xmin"] or by0 > d["ymin"]:
        aviso("o subsolo não encosta nos planos x = xmin / y = ymin: não há simetria; as paredes dos quatro "
              "lados seriam necessárias (este script só cria paredes em +x e +y).")
    P["subsolo"] = dict(x0=bx0, y0=by0, L=Lb, W=Wb, Hb=Hb)

    # --- 4. Piso e paredes (plates)
    titulo("4) PISO E PAREDES (plates elásticas isotrópicas)")
    print("  Piso:")
    piso = dict(nome=perguntar_texto("Nome do material do piso", "Basement floor"),
                gamma=perguntar_float("Peso específico", 15.0, lo=0.0, lo_incl=False, unidade="kN/m3"),
                E=perguntar_float("Módulo de Young E", 3.0e7, lo=0.0, lo_incl=False, unidade="kN/m2"),
                nu=perguntar_float("Coeficiente de Poisson ν", 0.15, lo=0.0, hi=0.5, lo_incl=False, hi_incl=False),
                d=perguntar_float("Espessura d", 0.5, lo=0.0, lo_incl=False, unidade="m"))
    P["piso"] = piso
    P["paredes"] = None
    if perguntar_sim_nao("Incluir paredes (plates nas bordas +x e +y do subsolo)?", True):
        print("  Paredes:")
        while True:
            nm = perguntar_texto("Nome do material das paredes", "Basement wall")
            if nm == piso["nome"]:
                print("    ! Esse nome já é do piso. Escolha outro.")
                continue
            break
        P["paredes"] = dict(nome=nm,
                            gamma=perguntar_float("Peso específico", 15.5, lo=0.0, lo_incl=False, unidade="kN/m3"),
                            E=perguntar_float("Módulo de Young E", 3.0e7, lo=0.0, lo_incl=False, unidade="kN/m2"),
                            nu=perguntar_float("Coeficiente de Poisson ν", 0.15, lo=0.0, hi=0.5, lo_incl=False,
                                               hi_incl=False),
                            d=perguntar_float("Espessura d", 0.3, lo=0.0, lo_incl=False, unidade="m"))

    # --- 5. Coluna e vigas (beams)
    titulo("5) COLUNA E VIGAS (beams elásticos, seção definida pelo usuário)")
    P["coluna"] = None
    P["vigas"] = None
    if perguntar_sim_nao("Incluir coluna e vigas?", True):
        xc = perguntar_float("x da coluna", bx0 + 6.0 if bx0 + 6.0 < bx0 + Lb else bx0 + Lb / 2.0,
                             lo=bx0, hi=bx0 + Lb, unidade="m")
        yc = perguntar_float("y da coluna", by0 + 6.0 if by0 + 6.0 < by0 + Wb else by0 + Wb / 2.0,
                             lo=by0, hi=by0 + Wb, unidade="m")
        print("  Coluna (vertical, do terreno z = 0 até o piso):")
        P["coluna"] = dict(x=xc, y=yc,
                           nome=perguntar_texto("Nome do material da coluna", "Basement column"),
                           gamma=perguntar_float("Peso específico", 24.0, lo=0.0, lo_incl=False, unidade="kN/m3"),
                           A=perguntar_float("Área da seção A", 0.49, lo=0.0, lo_incl=False, unidade="m2"),
                           I2=perguntar_float("Momento de inércia I2", 0.020, lo=0.0, lo_incl=False, unidade="m4"),
                           I3=perguntar_float("Momento de inércia I3", 0.020, lo=0.0, lo_incl=False, unidade="m4"),
                           E=perguntar_float("Módulo de Young E", 3.0e7, lo=0.0, lo_incl=False, unidade="kN/m2"))
        print("  Vigas horizontais (no nível do piso, ao longo de x = {} e de y = {}):".format(fmt(xc), fmt(yc)))
        while True:
            nm = perguntar_texto("Nome do material das vigas", "Basement beam")
            if nm == P["coluna"]["nome"]:
                print("    ! Esse nome já é da coluna. Escolha outro.")
                continue
            break
        P["vigas"] = dict(nome=nm,
                          gamma=perguntar_float("Peso específico", 6.0, lo=0.0, lo_incl=False, unidade="kN/m3"),
                          A=perguntar_float("Área da seção A", 0.7, lo=0.0, lo_incl=False, unidade="m2"),
                          I2=perguntar_float("Momento de inércia I2", 0.029, lo=0.0, lo_incl=False, unidade="m4"),
                          I3=perguntar_float("Momento de inércia I3", 0.058, lo=0.0, lo_incl=False, unidade="m4"),
                          E=perguntar_float("Módulo de Young E", 3.0e7, lo=0.0, lo_incl=False, unidade="kN/m2"))

    # --- 6. Cargas (0 = não criar)
    titulo("6) CARGAS (valor 0 = não aplicar; módulo, sempre para baixo, aplicadas na fase Loading)")
    cargas = dict(
        superficie=perguntar_float("Carga distribuída no piso (surface load)", 5.3, lo=0.0, unidade="kN/m2"),
        linha=0.0, pontual=0.0)
    if P["paredes"]:
        cargas["linha"] = perguntar_float("Carga linear no topo das paredes (line load)", 385.0, lo=0.0,
                                          unidade="kN/m")
    if P["coluna"]:
        cargas["pontual"] = perguntar_float("Carga pontual no topo da coluna (point load)", 11650.0, lo=0.0,
                                            unidade="kN")
    P["cargas"] = cargas

    # --- 7. Malha
    titulo("7) MALHA")
    nomes_m = ["{} (fator {})".format(n_, fmt(f)) for n_, f in PRESETS_MALHA]
    idx = perguntar_opcao("Element distribution (o manual usa Coarse):", nomes_m, 2)
    P["malha"] = dict(nome=PRESETS_MALHA[idx - 1][0], fator=PRESETS_MALHA[idx - 1][1])

    # --- 8. Projeto
    titulo("8) PROJETO E CÁLCULO")
    arq = perguntar_texto("Nome do arquivo do projeto", "Subsolo_radier.p3d")
    if not arq.lower().endswith(".p3d"):
        arq += ".p3d"
    P["projeto"] = os.path.join(PASTA, arq)
    P["calcular"] = perguntar_sim_nao("Calcular agora?", True)
    return P


def resumo(P):
    d, s, b, m, cg = P["dominio"], P["solo"], P["subsolo"], P["malha"], P["cargas"]
    print("\n" + "=" * 70)
    print(" RESUMO")
    print("=" * 70)
    print(" Domínio : x [{}, {}]  y [{}, {}]  profundidade {} m".format(
        fmt(d["xmin"]), fmt(d["xmax"]), fmt(d["ymin"]), fmt(d["ymax"]), fmt(d["H"])))
    print(" Solo    : {}  γ {}/{}  E'ref {} (+{} por m, zref {})  ν' {}  c' {}  φ' {}  ψ {}".format(
        s["nome"], fmt(s["gamma_unsat"]), fmt(s["gamma_sat"]), fmt(s["E"]), fmt(s["Einc"]), fmt(s["zref"]),
        fmt(s["nu"]), fmt(s["c"]), fmt(s["phi"]), fmt(s["psi"])))
    print(" N.A.    : z = {} m".format(fmt(P["nivel_agua"])))
    print(" Subsolo : x [{}, {}]  y [{}, {}]  escavação {} m".format(
        fmt(b["x0"]), fmt(b["x0"] + b["L"]), fmt(b["y0"]), fmt(b["y0"] + b["W"]), fmt(b["Hb"])))
    pi = P["piso"]
    print(" Piso    : \"{}\"  d {} m  γ {}  E {}  ν {}".format(pi["nome"], fmt(pi["d"]), fmt(pi["gamma"]),
                                                              fmt(pi["E"]), fmt(pi["nu"])))
    if P["paredes"]:
        pa = P["paredes"]
        print(" Paredes : \"{}\"  d {} m  γ {}  E {}  ν {}".format(pa["nome"], fmt(pa["d"]), fmt(pa["gamma"]),
                                                                  fmt(pa["E"]), fmt(pa["nu"])))
    if P["coluna"]:
        co, vg = P["coluna"], P["vigas"]
        print(" Coluna  : ({}, {})  \"{}\"  A {}  I2 {}  I3 {}  γ {}".format(
            fmt(co["x"]), fmt(co["y"]), co["nome"], fmt(co["A"]), fmt(co["I2"]), fmt(co["I3"]), fmt(co["gamma"])))
        print(" Vigas   : \"{}\"  A {}  I2 {}  I3 {}  γ {}  (ao longo de x = {} e y = {})".format(
            vg["nome"], fmt(vg["A"]), fmt(vg["I2"]), fmt(vg["I3"]), fmt(vg["gamma"]), fmt(co["x"]), fmt(co["y"])))
    print(" Cargas  : piso {} kN/m2 | paredes {} kN/m | coluna {} kN".format(
        fmt(cg["superficie"]), fmt(cg["linha"]), fmt(cg["pontual"])))
    print(" Fases   : Initial (K0) -> Excavation -> Construction -> Loading")
    print(" Malha   : {} (fator {})".format(m["nome"], fmt(m["fator"])))
    info = P["info"]
    if info["titulo"] != TITULO_PADRAO or info["empresa"]:
        print(" Projeto : Title \"{}\"  Company \"{}\"".format(info["titulo"], info["empresa"]))
    print(" Arquivo : {}  | calcular: {}".format(P["projeto"], "sim" if P["calcular"] else "não"))
    print("=" * 70)



# ----------------------------------------------------------------------------
# Auxiliares específicos deste modelo
# ----------------------------------------------------------------------------
def nome_obj(obj):
    """Nome de um objeto do PLAXIS (ex.: 'Plate_2'), ou None se não for possível ler."""
    for f in (lambda: obj.Name.value, lambda: str(obj.Name), lambda: obj.Name):
        try:
            v = f()
            if isinstance(v, str) and v and "<" not in v and " " not in v.strip():
                return v.strip()
        except Exception:
            pass
    return None


def ativar_obj(descricao, obj, fase):
    """Ativa um objeto na fase: primeiro pelo nome (forma validada no PLAXIS real), depois direto."""
    nome = nome_obj(obj)
    alts = []
    if nome:
        alts.append(lambda: g_i.activate(getattr(g_i, nome), fase))
    alts.append(lambda: g_i.activate(obj, fase))
    tentar(descricao, *alts)


def props_opcionais(obj, descricao, lista):
    """Como definir_props, mas só avisa quando falha (propriedades não essenciais)."""
    try:
        definir_props(obj, descricao, lista)
        return True
    except Exception as e:  # noqa
        aviso("{}: {}".format(descricao, str(e).strip().splitlines()[0]))
        return False


# ----------------------------------------------------------------------------
# Construção do modelo
# ----------------------------------------------------------------------------
def construir(P):
    d, so, b, cg, m = P["dominio"], P["solo"], P["subsolo"], P["cargas"], P["malha"]
    pi, pa, co, vg = P["piso"], P["paredes"], P["coluna"], P["vigas"]
    x0, y0, Lb, Wb, Hb = b["x0"], b["y0"], b["L"], b["W"], b["Hb"]
    x1, y1 = x0 + Lb, y0 + Wb
    falhas = []

    def seguro(descricao, fn):
        """Executa fn; se falhar registra a falha e devolve None (o modelo segue sendo construído)."""
        try:
            return fn()
        except Exception as e:  # noqa
            txt = str(e).strip()
            print("    (FALHOU) {}:\n    {}".format(descricao, txt.replace("\n", "\n    ")))
            falhas.append(descricao)
            return None

    sem_executor = globals().get("g_i") is None
    porta_in = PORTA_PADRAO
    if sem_executor:
        print("\n  Conexão com o PLAXIS Input (executor externo não detectado):")
        porta_in = perguntar_int("Porta do servidor Input", PORTA_PADRAO, 1, 65535)
    senha = obter_senha()
    if sem_executor:
        etapa("Conectando ao PLAXIS Input em {}:{}".format(HOST, porta_in))
        s_novo, g_novo = new_server(HOST, porta_in, password=senha)
        globals()["s_i"], globals()["g_i"] = s_novo, g_novo
    verificar_conexao()

    # ---------------- projeto, borehole, solo (trechos iguais aos validados na sapata)
    info = P["info"]
    etapa("Novo projeto")
    s_i.new()
    g_i.setproperties("Title", info.get("titulo") or TITULO_PADRAO,
                      "UnitForce", "kN", "UnitLength", "m", "UnitTime", "day", "WaterWeight", 10.0)
    if info.get("empresa"):
        try:
            g_i.setproperties("Company", info["empresa"])
        except Exception as e:  # noqa
            aviso("não consegui definir Company: {}".format(str(e).strip().splitlines()[-1]))
    g_i.SoilContour.initializerectangular(d["xmin"], d["ymin"], d["xmax"], d["ymax"])

    etapa("Borehole em ({}, {}), N.A. z = {}".format(fmt(d["xmin"]), fmt(d["ymin"]), fmt(P["nivel_agua"])))
    borehole = g_i.borehole(d["xmin"], d["ymin"])
    borehole.Head = P["nivel_agua"]
    g_i.soillayer(d["H"])

    etapa("Material do solo (Mohr-Coulomb, drenado)")
    mat_solo = g_i.soilmat()
    definir_props(mat_solo, "solo " + so["nome"], [
        (("Identification", "MaterialName"), so["nome"]),
        ("SoilModel", (2, "Mohr-Coulomb")),
        ("DrainageType", ("Drained", 0)),
        (("gammaUnsat", "gamma_unsat"), so["gamma_unsat"]),
        (("gammaSat", "gamma_sat"), so["gamma_sat"]),
        (("Eref", "E"), so["E"]),
        ("nu", so["nu"]),
        (("cref", "c"), so["c"]),
        (("phi", "phi_ref"), so["phi"]),
        ("psi", so["psi"]),
    ])
    if so["Einc"] > 0:
        etapa("Rigidez crescente com a profundidade: E'inc = {} por m, zref = {} (não testado)".format(
            fmt(so["Einc"]), fmt(so["zref"])))
        seguro("E'inc / zref do solo", lambda: definir_props(mat_solo, "solo (rigidez com a profundidade)", [
            (("Einc", "E_inc", "EInc", "Eincrement"), so["Einc"]),
            (("zref", "Zref", "z_ref"), so["zref"]),
        ]))
    g_i.Soillayers[0].Soil.Material = mat_solo

    # ---------------- materiais estruturais
    def criar_platemat(rotulo, dados):
        etapa("Material de plate: {} (d = {} m)".format(dados["nome"], fmt(dados["d"])))
        mat = g_i.platemat()
        definir_props(mat, rotulo + " (identificação/tipo)", [
            (("Identification", "MaterialName"), dados["nome"]),
            (("MaterialType", "PlateType"), ("Elastic", 0)),
        ])
        definir_props(mat, rotulo, [
            (("Isotropic", "isotropic"), True),
            (("gamma", "Gamma"), dados["gamma"]),
            (("d", "D", "Thickness"), dados["d"]),
            (("E1", "E", "Eref"), dados["E"]),
            (("StructNu12", "nu12", "nu", "Nu12"), dados["nu"]),
        ])
        return mat

    def criar_beammat(rotulo, dados):
        etapa("Material de beam: {} (não testado)".format(dados["nome"]))
        mat = g_i.beammat()
        definir_props(mat, rotulo + " (identificação/tipo)", [
            (("Identification", "MaterialName"), dados["nome"]),
            (("MaterialType", "BeamType"), ("Elastic", 0)),
        ])
        # Seção definida pelo usuário: se o nome/valor não for aceito, A e I seguem sendo tentados.
        props_opcionais(mat, rotulo + " (tipo de seção)", [
            (("CrossSectionType", "SectionType", "CrossSection"), ("User-defined", "UserDefined", "Userdefined"))])
        definir_props(mat, rotulo, [
            (("gamma", "Gamma"), dados["gamma"]),
            (("A", "Area"), dados["A"]),
            (("I2", "Iy", "I22", "Imajor"), dados["I2"]),
            (("I3", "Iz", "I33", "Iminor"), dados["I3"]),
            (("E", "E1", "Eref"), dados["E"]),
        ])
        return mat

    mat_piso = seguro("material do piso", lambda: criar_platemat("piso", pi))
    mat_parede = seguro("material das paredes", lambda: criar_platemat("paredes", pa)) if pa else None
    mat_coluna = seguro("material da coluna", lambda: criar_beammat("coluna", co)) if co else None
    mat_viga = seguro("material das vigas", lambda: criar_beammat("vigas", vg)) if vg else None

    # ---------------- geometria estrutural
    etapa("Modo Structures: volume do subsolo (extrusão de {} m)".format(fmt(Hb)))
    g_i.gotostructures()
    poly_topo = primeiro(g_i.surface((x0, y1, 0.0), (x1, y1, 0.0), (x1, y0, 0.0), (x0, y0, 0.0)))
    res_ext = tentar("extrude (volume do subsolo)",
                     lambda: g_i.extrude(poly_topo, 0, 0, -Hb),
                     lambda: g_i.extrude(g_i.Polygon_1, 0, 0, -Hb),
                     lambda: g_i.extrude([poly_topo], 0, 0, -Hb))
    vol_objs = list(res_ext) if isinstance(res_ext, (list, tuple)) else [res_ext]
    print("    objetos criados pela extrusão: {}".format([nome_obj(v) or str(v) for v in vol_objs]))
    seguro("apagar a superfície auxiliar do topo", lambda: g_i.delete(poly_topo))

    obj = dict(piso=None, paredes=[], coluna=None, vigas=[], c_sup=None, c_linha=[], c_pt=None)

    # --- piso (plate) + surface load
    etapa("Piso: plate em z = {} (não testado)".format(fmt(-Hb)))
    poly_piso = seguro("superfície do piso", lambda: primeiro(g_i.surface(
        (x0, y1, -Hb), (x1, y1, -Hb), (x1, y0, -Hb), (x0, y0, -Hb))))
    if poly_piso is not None:
        def _piso():
            pl = tentar("plate do piso", lambda: primeiro(g_i.plate(poly_piso)))
            if mat_piso is not None:
                pl.Material = mat_piso
            return pl
        obj["piso"] = seguro("plate do piso", _piso)
        if cg["superficie"] > 0:
            def _csup():
                cs = tentar("surface load do piso", lambda: primeiro(g_i.surfload(poly_piso)))
                setar_attr(cs, "sigz", -cg["superficie"])
                return cs
            obj["c_sup"] = seguro("surface load do piso", _csup)

    # --- paredes (plates nas bordas +x e +y)
    if pa:
        etapa("Paredes: plates em x = {} e y = {} (não testado)".format(fmt(x1), fmt(y1)))
        for rot, pts in (("parede em x = {}".format(fmt(x1)),
                          ((x1, y0, 0.0), (x1, y1, 0.0), (x1, y1, -Hb), (x1, y0, -Hb))),
                         ("parede em y = {}".format(fmt(y1)),
                          ((x0, y1, 0.0), (x1, y1, 0.0), (x1, y1, -Hb), (x0, y1, -Hb)))):
            def _parede(pts=pts):
                sup = primeiro(g_i.surface(*pts))
                pl = tentar("plate", lambda: primeiro(g_i.plate(sup)))
                if mat_parede is not None:
                    pl.Material = mat_parede
                return pl
            pl = seguro(rot, _parede)
            if pl is not None:
                obj["paredes"].append(pl)

    # --- linhas e beams
    def criar_linha(cmd, p1, p2):
        return tentar("{} {} -> {}".format(cmd, p1, p2),
                      lambda: primeiro(getattr(g_i, cmd)(p1, p2)),
                      lambda: primeiro(getattr(g_i, cmd)(primeiro(g_i.line(p1, p2)))))

    if co:
        etapa("Coluna e vigas (beams) (não testado)")
        xc, yc = co["x"], co["y"]

        def _beam(p1, p2, mat):
            bm = criar_linha("beam", p1, p2)
            if mat is not None:
                bm.Material = mat
            return bm
        obj["coluna"] = seguro("coluna (beam vertical)", lambda: _beam((xc, yc, 0.0), (xc, yc, -Hb), mat_coluna))
        for rot, p1, p2 in (("viga ao longo de x (y = {})".format(fmt(yc)), (x0, yc, -Hb), (x1, yc, -Hb)),
                            ("viga ao longo de y (x = {})".format(fmt(xc)), (xc, y0, -Hb), (xc, y1, -Hb))):
            bm = seguro(rot, lambda p1=p1, p2=p2: _beam(p1, p2, mat_viga))
            if bm is not None:
                obj["vigas"].append(bm)

    # --- cargas de linha (topo das paredes) e pontual (topo da coluna)
    if pa and cg["linha"] > 0:
        etapa("Cargas de linha de {} kN/m no topo das paredes (não testado)".format(fmt(cg["linha"])))
        for rot, p1, p2 in (("line load em x = {}".format(fmt(x1)), (x1, y0, 0.0), (x1, y1, 0.0)),
                            ("line load em y = {}".format(fmt(y1)), (x1, y1, 0.0), (x0, y1, 0.0))):
            def _linha(p1=p1, p2=p2):
                ll = criar_linha("lineload", p1, p2)
                definir_props(ll, "line load", [(("qz_start", "qz", "Fz", "Fz_start"), -cg["linha"])])
                try:
                    ll.setproperties("qz_end", -cg["linha"])
                except Exception:
                    pass          # com distribuição uniforme só o valor inicial é usado
                return ll
            ll = seguro(rot, _linha)
            if ll is not None:
                obj["c_linha"].append(ll)
    if co and cg["pontual"] > 0:
        etapa("Carga pontual de {} kN no topo da coluna (não testado)".format(fmt(cg["pontual"])))

        def _pt():
            xc, yc = co["x"], co["y"]
            pt = tentar("ponto no topo da coluna",
                        lambda: primeiro(g_i.point(xc, yc, 0.0)), lambda: (xc, yc, 0.0))
            cp = tentar("criar carga pontual",
                        lambda: primeiro(g_i.pointload(pt)),
                        lambda: primeiro(g_i.pointload((xc, yc, 0.0))),
                        lambda: primeiro(g_i.pointload(xc, yc, 0.0)))
            setar_attr(cp, "Fz", -cg["pontual"])
            return cp
        obj["c_pt"] = seguro("point load da coluna", _pt)

    # ---------------- malha
    etapa("Modo Mesh: preset '{}' (fator {})".format(m["nome"], fmt(m["fator"])))
    g_i.gotomesh()
    res_malha = seguro("gerar a malha", lambda: g_i.mesh(m["fator"]))
    if res_malha not in (None, "", True):
        print("    mesh ->", res_malha)

    # ---------------- pontos para as curvas (lidos pelo script de resultados)
    pontos = []
    if co:
        pontos.append(dict(rotulo="topo da coluna", x=co["x"], y=co["y"], z=0.0))
        pontos.append(dict(rotulo="base da coluna (piso)", x=co["x"], y=co["y"], z=-Hb))
    pontos.append(dict(rotulo="centro do piso", x=(x0 + x1) / 2.0, y=(y0 + y1) / 2.0, z=-Hb))
    pontos.append(dict(rotulo="canto do piso (simetria)", x=x0, y=y0, z=-Hb))

    def _nos():
        etapa("Nós para as curvas: {}".format("; ".join(p_["rotulo"] for p_ in pontos)))
        porta_out = g_i.selectmeshpoints()
        s_o, g_o = new_server(HOST, porta_out, password=senha)
        for p_ in pontos:
            g_o.addcurvepoint("node", p_["x"], p_["y"], p_["z"])
        g_o.update()
    seguro("nós para as curvas", _nos)

    # ---------------- fases
    etapa("Modo Staged construction: Initial (K0) -> Excavation -> Construction -> Loading")
    g_i.gotostages()
    tentar("Initial phase = K0 procedure",
           lambda: setattr(g_i.InitialPhase, "DeformCalcType", "K0 procedure"),
           lambda: g_i.InitialPhase.setproperties("DeformCalcType", "K0 procedure"))

    def ativar_seguro(descricao, o, fase):
        if o is not None:
            seguro(descricao, lambda: ativar_obj(descricao, o, fase))

    fase_esc = g_i.phase(g_i.InitialPhase)
    fase_esc.Identification = "Excavation"

    def _desativar_solo():
        feitos = 0
        for v in vol_objs:
            nome = nome_obj(v)
            alts = []
            if nome:
                alts.append(lambda nome=nome: g_i.deactivate(getattr(g_i, nome), fase_esc))
            alts.append(lambda v=v: g_i.deactivate(v, fase_esc))
            try:
                tentar("desativar solo do subsolo", *alts)
                feitos += 1
            except Exception as e:  # noqa
                print("    - {} ({})".format(nome or v, str(e).strip().splitlines()[-1]))
        if feitos == 0:
            raise RuntimeError("nenhum dos objetos {} aceitou 'deactivate'".format(
                [nome_obj(v) or str(v) for v in vol_objs]))
    etapa("Fase Excavation: desativa o solo do subsolo e ativa as paredes (não testado)")
    seguro("desativar o solo do subsolo na fase Excavation", _desativar_solo)
    for i, pl in enumerate(obj["paredes"], 1):
        ativar_seguro("ativar parede {} na fase Excavation".format(i), pl, fase_esc)

    fase_con = g_i.phase(fase_esc)
    fase_con.Identification = "Construction"
    etapa("Fase Construction: ativa o piso, a coluna e as vigas")
    ativar_seguro("ativar o piso na fase Construction", obj["piso"], fase_con)
    ativar_seguro("ativar a coluna na fase Construction", obj["coluna"], fase_con)
    for i, bm in enumerate(obj["vigas"], 1):
        ativar_seguro("ativar viga {} na fase Construction".format(i), bm, fase_con)

    fase_car = g_i.phase(fase_con)
    fase_car.Identification = "Loading"
    etapa("Fase Loading: ativa as cargas")
    ativar_seguro("ativar a surface load na fase Loading", obj["c_sup"], fase_car)
    for i, ll in enumerate(obj["c_linha"], 1):
        ativar_seguro("ativar line load {} na fase Loading".format(i), ll, fase_car)
    ativar_seguro("ativar a point load na fase Loading", obj["c_pt"], fase_car)

    # ---------------- parâmetros para o script de resultados
    dados = dict(
        versao=1, projeto=P["projeto"],
        subsolo=dict(x0=x0, y0=y0, L=Lb, W=Wb, Hb=Hb),
        pontos=pontos,
        fases=["Excavation", "Construction", "Loading"],
        piso=dict(nome=nome_obj(obj["piso"]) if obj["piso"] is not None else None),
        coluna=dict(x=co["x"], y=co["y"]) if co else None,
        cargas=cg,
    )
    with open(ARQUIVO_JSON, "w", encoding="utf-8") as fh:
        json.dump(dados, fh, indent=2, ensure_ascii=False)
    print("    Parâmetros gravados em {}".format(ARQUIVO_JSON))

    etapa("Salvando em " + P["projeto"])
    seguro("salvar o projeto", lambda: g_i.save(P["projeto"]))

    if falhas:
        print("\n" + "=" * 70)
        print(" ATENÇÃO: o modelo foi construído, mas {} item(ns) falharam:".format(len(falhas)))
        for f_ in falhas:
            print("   - " + f_)
        print(" O projeto foi salvo SEM calcular. Envie este log (com os 'echo' acima) para ajustar os")
        print(" comandos, ou complete os itens no PLAXIS Input e calcule por lá.")
        print("=" * 70)
        return

    if P["calcular"]:
        etapa("Calculando (Excavation -> Construction -> Loading)")
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
            g_i.save(P["projeto"])
        except Exception:
            pass
        print("\nModelo calculado. Rode plaxis_subsolo_resultados.py com este projeto aberto.")
    else:
        print("\nModelo criado e salvo (sem calcular).")


# ----------------------------------------------------------------------------
# Principal
# ----------------------------------------------------------------------------


verificar_conexao()
dados_modelo = perguntar_tudo()
resumo(dados_modelo)
print("\n  ATENÇÃO: isto cria um NOVO projeto no PLAXIS (o projeto aberto agora será descartado).")
if perguntar_sim_nao("Continuar?", True):
    construir(dados_modelo)
else:
    print("\nCancelado. Nada foi alterado no PLAXIS.")
